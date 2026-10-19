"""Bounded local scheduler over durable workflow/search intents and fenced attempts."""

import asyncio
import json

from sqlalchemy import select, exists, or_, func

from . import advanced_models as a, jobs, models as m
from .database import transaction
from .diagnostics import log
from .money import canonical, utcnow
from .operations_models import JobAttempt


def recover(session):
    """Another process's live lease is respected; expired owners cannot publish."""
    for attempt in session.scalars(
        select(JobAttempt)
        .where(JobAttempt.status == "RUNNING", JobAttempt.lease_until <= utcnow())
        .limit(100)
    ):
        jobs.finish(session, attempt.id, "INTERRUPTED")
        cls = (
            m.Workflow
            if attempt.kind == "workflow"
            else a.PriceSearch
            if attempt.kind == "price_search"
            else None
        )
        record = session.get(cls, attempt.entity_id) if cls else None
        if record and record.status == "RUNNING":
            record.status = "INTERRUPTED"
            if cls is m.Workflow:
                record.error = "Worker lease expired; bounded recovery is scheduled."
    for record in session.scalars(
        select(a.PriceSearch)
        .where(
            a.PriceSearch.status.in_(
                ("QUEUED", "RUNNING", "INTERRUPTED", "FAILED", "WAITING")
            ),
            a.PriceSearch.states_json.contains("SUBMITTING"),
        )
        .limit(100)
    ):
        latest = session.scalar(
            select(JobAttempt)
            .where(JobAttempt.kind == "price_search", JobAttempt.entity_id == record.id)
            .order_by(JobAttempt.attempt.desc())
        )
        if latest and latest.status == "RUNNING" and latest.lease_until > utcnow():
            continue
        states = json.loads(record.states_json)
        changed = False
        for state in states.values():
            if state["status"] == "SUBMITTING":
                state["status"] = (
                    "WAITING" if state.get("remote_id") else "UNKNOWN_SUBMISSION"
                )
                changed = True
        if changed:
            record.states_json = canonical(states)
            record.status = "INTERRUPTED"


def due(engine):
    with transaction(engine, True) as session:
        recover(session)
        candidates = []
        for cls, kind, statuses in (
            (m.Workflow, "workflow", ("QUEUED", "RUNNING", "FAILED", "INTERRUPTED")),
            (
                a.PriceSearch,
                "price_search",
                ("QUEUED", "RUNNING", "FAILED", "INTERRUPTED", "WAITING"),
            ),
        ):
            # Exclude terminal retry limits before applying the batch bound so
            # old exhausted jobs cannot starve newer requests.
            exhausted = exists(
                select(JobAttempt.id).where(
                    JobAttempt.kind == kind,
                    JobAttempt.entity_id == cls.id,
                    JobAttempt.attempt >= 5,
                )
            )
            latest_id = (
                select(func.max(JobAttempt.id))
                .where(JobAttempt.kind == kind, JobAttempt.entity_id == cls.id)
                .correlate(cls)
                .scalar_subquery()
            )
            held = exists(
                select(JobAttempt.id).where(
                    JobAttempt.id == latest_id,
                    or_(
                        (JobAttempt.status == "RUNNING")
                        & (JobAttempt.lease_until > utcnow()),
                        JobAttempt.next_attempt_at > utcnow(),
                    ),
                )
            ).correlate(cls)
            query = select(cls).where(cls.status.in_(statuses), ~exhausted, ~held)
            if cls is a.PriceSearch:
                query = query.where(
                    ~a.PriceSearch.states_json.contains("UNKNOWN_SUBMISSION")
                )
            for record in session.scalars(query.order_by(cls.id).limit(100)):
                attempt = session.scalar(
                    select(JobAttempt)
                    .where(JobAttempt.kind == kind, JobAttempt.entity_id == record.id)
                    .order_by(JobAttempt.attempt.desc())
                )
                if attempt and (
                    attempt.attempt >= 5
                    or (attempt.status == "RUNNING" and attempt.lease_until > utcnow())
                    or (attempt.next_attempt_at and attempt.next_attempt_at > utcnow())
                ):
                    continue
                if kind == "price_search":
                    states = json.loads(record.states_json)
                    if any(
                        state["status"] in ("UNKNOWN_SUBMISSION", "SUBMITTING")
                        and not state.get("remote_id")
                        for state in states.values()
                    ):
                        continue
                candidates.append((kind, record.id))
                break  # At most one workflow and one search per scheduler batch.
        return candidates


async def run_once(engine, settings):
    from .workflow import run_workflow
    from .pricing import run_search

    candidates = await asyncio.to_thread(due, engine)
    outcomes = await asyncio.gather(
        *(
            asyncio.to_thread(run_workflow, engine, settings, identity)
            if kind == "workflow"
            else run_search(engine, settings, identity)
            for kind, identity in candidates
        ),
        return_exceptions=True,
    )
    for (kind, identity), outcome in zip(candidates, outcomes):
        if isinstance(outcome, BaseException):
            # Exception messages can contain provider URLs or credentials; metadata only.
            log.warning(
                json.dumps(
                    {
                        "event": "job_dispatch_failed",
                        "kind": kind,
                        "entity_id": identity,
                        "error_type": type(outcome).__name__,
                    }
                )
            )
    return candidates


async def serve(engine, settings, stopped):
    while not stopped.is_set():
        try:
            await run_once(engine, settings)
        except Exception as error:
            log.warning(
                json.dumps(
                    {"event": "scheduler_error", "error_type": type(error).__name__}
                )
            )
        try:
            await asyncio.wait_for(stopped.wait(), timeout=settings.job_poll_seconds)
        except TimeoutError:
            pass
