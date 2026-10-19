from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func
from app.database import transaction
from app.models import (
    InvoiceLine,
    Project,
    Payment,
    LedgerEntry,
    Proposal,
    AuditEvent,
    User,
    Membership,
)
from app.money import minor
from conftest import valid_invoice, prepared, approved


def test_full_authorized_payment_and_idempotency(env):
    p = approved(env)
    app, client, h = env
    auth = {**h["manager"], "Idempotency-Key": "one-payment"}
    first = client.post(f"/api/v1/payments/{p['id']}/execute", headers=auth)
    assert first.status_code == 200, first.text
    assert first.json()["balance_after"] == "930000.00"
    assert first.json()["simulation"] is True
    assert first.json()["mock_transaction_id"].startswith("MOCK-")
    second = client.post(f"/api/v1/payments/{p['id']}/execute", headers=auth)
    assert second.json() == first.json()
    receipt = client.get(f"/api/v1/payments/{p['id']}/receipt", headers=h["auditor"])
    assert receipt.json() == first.json()
    with transaction(app.state.engine) as s:
        assert s.scalar(select(func.count()).select_from(Payment)) == 1
        assert s.scalar(select(func.count()).select_from(LedgerEntry)) == 2
        assert s.get(Project, p["project_id"]).balance_minor == minor("930000")


def test_concurrent_same_key_settles_once(env):
    p = approved(env)
    app, client, h = env

    def call(_):
        return client.post(
            f"/api/v1/payments/{p['id']}/execute",
            headers={**h["manager"], "Idempotency-Key": "overlap"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    with transaction(app.state.engine) as s:
        assert s.scalar(select(func.count()).select_from(Payment)) == 1


@pytest.mark.parametrize("role", ["operator", "auditor"])
def test_role_denied_approval_and_execution(env, role):
    p = prepared(env)
    app, client, h = env
    assert (
        client.post(f"/api/v1/payments/{p['id']}/approve", headers=h[role]).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/payments/{p['id']}/execute",
            headers={**h[role], "Idempotency-Key": "denied"},
        ).status_code
        == 403
    )
    with transaction(app.state.engine) as s:
        assert s.get(Proposal, p["id"]).status == "PENDING_APPROVAL"
        assert s.scalar(select(func.count()).select_from(Payment)) == 0
        assert (
            s.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "UNAUTHORIZED_ACTION")
            )
            >= 2
        )


def test_separation_of_duties(env):
    _, client, h = env
    inv = valid_invoice(client, h["manager"])
    p = client.post(
        "/api/v1/payments/proposals",
        headers=h["manager"],
        json={"invoice_id": inv["id"]},
    ).json()
    result = client.post(f"/api/v1/payments/{p['id']}/approve", headers=h["manager"])
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "SEPARATION_OF_DUTIES"


@pytest.mark.parametrize("field", ["amount", "beneficiary", "currency", "source"])
def test_changed_snapshot_rejected(env, field):
    p = approved(env)
    app, client, h = env
    with transaction(app.state.engine, True) as s:
        proposal = s.get(Proposal, p["id"])
        if field == "amount":
            proposal.amount_minor += 1
        if field == "beneficiary":
            proposal.beneficiary_fingerprint = "changed"
        if field == "currency":
            proposal.currency = "USD"
        if field == "source":
            s.scalar(
                select(InvoiceLine).where(InvoiceLine.invoice_id == p["invoice_id"])
            ).quantity = "101"
    result = client.post(
        f"/api/v1/payments/{p['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "changed"},
    )
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "APPROVAL_SNAPSHOT_CHANGED"
    with transaction(app.state.engine) as s:
        assert s.get(Project, p["project_id"]).balance_minor == minor("1000000")


def test_expiry_rejected(env):
    p = approved(env)
    app, client, h = env
    with transaction(app.state.engine, True) as s:
        s.get(Proposal, p["id"]).expires_at = "2000-01-01T00:00:00.000000Z"
    result = client.post(
        f"/api/v1/payments/{p['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "expired"},
    )
    assert result.status_code == 409
    with transaction(app.state.engine) as s:
        assert s.get(Project, p["project_id"]).balance_minor == minor("1000000")


def test_failed_execution_rolls_back_and_releases(env):
    p = approved(env)
    app, client, h = env

    def failure():
        raise RuntimeError("injected failure after balance mutation")

    app.state.execution_failure_hook = failure
    result = client.post(
        f"/api/v1/payments/{p['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "failed"},
    )
    assert result.status_code == 503, result.text
    retry = client.post(
        f"/api/v1/payments/{p['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "failed"},
    )
    assert retry.status_code == 503 and retry.json() == result.json()
    assert retry.headers["x-request-id"] != result.headers["x-request-id"]
    with transaction(app.state.engine) as s:
        assert s.get(Project, p["project_id"]).balance_minor == minor("1000000")
        assert s.scalar(select(func.count()).select_from(Payment)) == 0
        assert s.scalar(select(func.count()).select_from(LedgerEntry)) == 0
        assert s.get(Proposal, p["id"]).status == "FAILED"


def test_current_cash_rechecked_after_approval(env):
    p = approved(env)
    app, client, h = env
    with transaction(app.state.engine, True) as s:
        s.get(Project, p["project_id"]).balance_minor = minor("150000")
    result = client.post(
        f"/api/v1/payments/{p['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "short"},
    )
    assert result.status_code == 409
    assert "PAYMENT_BLOCKED" == result.json()["error"]["code"]


def test_execution_requires_key_and_approval(env):
    p = prepared(env)
    _, client, h = env
    assert (
        client.post(
            f"/api/v1/payments/{p['id']}/execute", headers=h["manager"]
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/payments/{p['id']}/execute",
            headers={**h["manager"], "Idempotency-Key": "no-approval"},
        ).status_code
        == 409
    )


def test_entity_access_and_inactive_account(env):
    app, client, h = env
    inv = valid_invoice(client, h["operator"])
    with transaction(app.state.engine, True) as s:
        operator = s.scalar(select(User).where(User.role == "OPERATOR"))
        s.delete(s.get(Membership, (operator.id, inv["project_id"])))
    assert (
        client.get(f"/api/v1/invoices/{inv['id']}", headers=h["operator"]).status_code
        == 404
    )
    with transaction(app.state.engine, True) as s:
        s.scalar(select(User).where(User.role == "OPERATOR")).active = False
    assert client.get("/api/v1/auth/me", headers=h["operator"]).status_code == 401
