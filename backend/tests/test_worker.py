"""Durable recovery and paid-task safety without a live provider."""
import asyncio
import json

from sqlalchemy import select, func

from app import jobs, worker, models as m, advanced_models as a, pricing
from app.database import transaction
from app.money import canonical
from app.operations_models import JobAttempt
from conftest import valid_invoice
from test_advanced_upgrade import demo


def test_expired_workflow_lease_resumes_without_duplicate_proposal(env):
    app, client, headers = env
    invoice = valid_invoice(client, headers["operator"])
    with transaction(app.state.engine, True) as session:
        actor = session.scalar(select(m.User).where(m.User.role == "OPERATOR"))
        run = m.Workflow(invoice_id=invoice["id"], actor_id=actor.id, status="RUNNING")
        session.add(run)
        session.flush()
        identity = run.id
        attempt_id = jobs.claim(session, "workflow", identity)
        session.get(JobAttempt, attempt_id).lease_until = "2000-01-01T00:00:00Z"
    assert worker.due(app.state.engine) == []  # Recovery schedules backoff first.
    with transaction(app.state.engine, True) as session:
        old = session.get(JobAttempt, attempt_id)
        assert old.status == "INTERRUPTED"
        old.next_attempt_at = "2000-01-01T00:00:00Z"
    candidates = asyncio.run(worker.run_once(app.state.engine, app.state.settings))
    assert candidates == [("workflow", identity)]
    assert asyncio.run(worker.run_once(app.state.engine, app.state.settings)) == []
    with transaction(app.state.engine) as session:
        assert session.get(m.Workflow, identity).status == "AWAITING_APPROVAL"
        assert session.scalar(select(func.count()).select_from(m.Proposal).where(m.Proposal.invoice_id == invoice["id"])) == 1
        attempts = list(session.scalars(select(JobAttempt).where(JobAttempt.entity_id == identity, JobAttempt.kind == "workflow").order_by(JobAttempt.attempt)))
        assert [r.status for r in attempts] == ["INTERRUPTED", "AWAITING_APPROVAL"]


def price_task(env, state):
    app, _, _ = env
    data = demo(env)
    with transaction(app.state.engine, True) as session:
        actor = session.scalar(select(m.User).where(m.User.role == "OPERATOR"))
        record = a.PriceSearch(project_id=data["project_id"], material_id=data["material_id"], actor_id=actor.id,
                               fingerprint="durable-fixture", request_json=canonical({"mode": "LIVE", "country": "US", "city": "New York", "query": "steel", "quantity": "20", "unit": "tonne"}),
                               states_json=canonical({"serpapi": {"status": "DISABLED"}, "dataforseo": state}), status="INTERRUPTED")
        session.add(record)
        session.flush()
        return record.id


def test_known_remote_task_is_retrieved_without_repeating_paid_submission(env, monkeypatch, paid_fixture):
    identity = price_task(env, {"status": "WAITING", "remote_id": "fixture-remote-42"})
    app, _, _ = env
    app.state.settings.dataforseo_login = "fixture"
    app.state.settings.dataforseo_password = "fixture"
    calls = []
    async def retrieve(self, remote, request, settings):
        calls.append(remote)
        return []
    async def forbidden_submit(*args, **kwargs):
        raise AssertionError("Paid task must never be resubmitted")
    monkeypatch.setattr(pricing.DataForSEOProvider, "retrieve", retrieve)
    monkeypatch.setattr(pricing.DataForSEOProvider, "submit", forbidden_submit)
    assert asyncio.run(worker.run_once(app.state.engine, app.state.settings)) == [("price_search", identity)]
    assert calls == ["fixture-remote-42"]
    with transaction(app.state.engine) as session:
        record = session.get(a.PriceSearch, identity)
        assert record.status == "EMPTY"
        assert json.loads(record.states_json)["dataforseo"]["remote_id"] == "fixture-remote-42"


def test_uncertain_paid_submission_stays_held_for_reconciliation(env):
    identity = price_task(env, {"status": "SUBMITTING"})
    app, _, _ = env
    assert asyncio.run(worker.run_once(app.state.engine, app.state.settings)) == []
    with transaction(app.state.engine) as session:
        record = session.get(a.PriceSearch, identity)
        assert json.loads(record.states_json)["dataforseo"]["status"] == "UNKNOWN_SUBMISSION"
        assert session.scalar(select(func.count()).select_from(JobAttempt)) == 0


def test_old_worker_cannot_overwrite_current_owner_result(env, monkeypatch, paid_fixture):
    identity = price_task(env, {"status": "WAITING", "remote_id": "fixture-fenced"})
    app, _, _ = env
    app.state.settings.dataforseo_login = "fixture"
    app.state.settings.dataforseo_password = "fixture"
    async def transfer_owner(self, remote, request, settings):
        with transaction(app.state.engine, True) as session:
            attempt = session.scalar(select(JobAttempt).where(JobAttempt.kind == "price_search", JobAttempt.entity_id == identity))
            attempt.lease_until = "2000-01-01T00:00:00Z"
            record = session.get(a.PriceSearch, identity)
            record.status = "COMPLETE"
            record.states_json = canonical({"new_owner": {"status": "COMPLETE"}})
        return []
    monkeypatch.setattr(pricing.DataForSEOProvider, "retrieve", transfer_owner)
    asyncio.run(worker.run_once(app.state.engine, app.state.settings))
    with transaction(app.state.engine) as session:
        record = session.get(a.PriceSearch, identity)
        assert record.status == "COMPLETE"
        assert json.loads(record.states_json) == {"new_owner": {"status": "COMPLETE"}}
