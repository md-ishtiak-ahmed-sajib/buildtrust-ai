"""Fenced attempts: a live lease prevents concurrent publication, retries are bounded."""

import uuid
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .money import utcnow
from .operations_models import JobAttempt
from .security import DomainError
from .diagnostics import log


def future(seconds):
    return (
        (datetime.now(UTC) + timedelta(seconds=seconds))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def claim(session, kind, identity):
    latest = session.scalar(
        select(JobAttempt)
        .where(JobAttempt.kind == kind, JobAttempt.entity_id == identity)
        .order_by(JobAttempt.attempt.desc())
    )
    if latest and latest.status == "RUNNING" and latest.lease_until > utcnow():
        return None
    if latest and latest.attempt >= 5:
        raise DomainError(
            409,
            "RETRY_LIMIT",
            "Five attempts reached; reconcile this work item before a new request.",
        )
    if latest and latest.status == "RUNNING":
        latest.status, latest.finished_at = "INTERRUPTED", utcnow()
    attempt = JobAttempt(
        kind=kind,
        entity_id=identity,
        attempt=latest.attempt + 1 if latest else 1,
        lease_token=uuid.uuid4().hex,
        status="RUNNING",
        started_at=utcnow(),
        heartbeat_at=utcnow(),
        lease_until=future(120),
    )
    session.add(attempt)
    session.flush()
    return attempt.id


def ensure_retry(session, kind, identity):
    latest = session.scalar(
        select(JobAttempt)
        .where(JobAttempt.kind == kind, JobAttempt.entity_id == identity)
        .order_by(JobAttempt.attempt.desc())
    )
    if latest and latest.attempt >= 5:
        raise DomainError(
            409,
            "RETRY_LIMIT",
            "Five attempts reached; reconcile the work item before submitting a new request.",
        )
    if latest and latest.status == "RUNNING" and latest.lease_until > utcnow():
        raise DomainError(409, "JOB_RUNNING", "A worker already owns this task.")


def heartbeat(session, identity):
    record = session.get(JobAttempt, identity)
    if not record or record.status != "RUNNING" or record.lease_until <= utcnow():
        raise DomainError(
            409, "JOB_LEASE_LOST", "Worker lease expired; results were not published."
        )
    record.heartbeat_at, record.lease_until = utcnow(), future(120)


def owns(session, identity):
    record = session.get(JobAttempt, identity)
    return bool(record and record.status == "RUNNING" and record.lease_until > utcnow())


def finish(session, identity, status):
    record = session.get(JobAttempt, identity)
    if record and record.status == "RUNNING":
        if record.lease_until <= utcnow():
            status = "INTERRUPTED"
        record.status, record.finished_at = status, utcnow()
        record.next_attempt_at = (
            future(min(300, 2**record.attempt))
            if status in ("FAILED", "INTERRUPTED", "WAITING")
            else None
        )
        duration = (
            datetime.fromisoformat(record.finished_at.replace("Z", "+00:00"))
            - datetime.fromisoformat(record.started_at.replace("Z", "+00:00"))
        ).total_seconds()
        log.info(
            json.dumps(
                {
                    "event": "job_finished",
                    "kind": record.kind,
                    "entity_id": record.entity_id,
                    "attempt": record.attempt,
                    "status": status,
                    "duration_ms": round(duration * 1000),
                }
            )
        )
