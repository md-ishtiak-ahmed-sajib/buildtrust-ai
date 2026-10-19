import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from app import control_models as c
from app import documents, jobs
from app import models as m
from app.authority import conversion
from app.database import transaction
from app.finance import business_date
from app.security import DomainError
from conftest import valid_invoice
from sqlalchemy import func, select
from test_accounting_controls import control, setup_accounting


def test_parser_does_not_hold_sqlite_writer(env, monkeypatch):
    app, client, h = env
    original = documents.parse_file
    checked = []

    def parse(*args, **kwargs):
        with transaction(app.state.engine, True) as session:
            session.execute(select(1))
            checked.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(documents, "parse_file", parse)
    project_id = valid_invoice(client, h["operator"])["project_id"]
    response = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": project_id},
        files={
            "file": (
                "review.json",
                json.dumps({"document_type": "INVOICE", "items": []}).encode(),
                "application/json",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert checked == [True]


def test_request_envelope_and_secret_free_diagnostics(env, caplog):
    _, client, h = env
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.test", "password": "secret-never-log-this"},
    )
    assert response.status_code == 401
    assert len(response.headers["X-Request-ID"]) == 32
    assert "secret-never-log-this" not in caplog.text
    response = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        content=b"x" * (11 * 1024 * 1024),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_lease_fencing_and_bounded_attempts(env):
    app, _, _ = env
    with transaction(app.state.engine, True) as session:
        first = jobs.claim(session, "fixture", 99)
        assert jobs.claim(session, "fixture", 99) is None
        jobs.heartbeat(session, first)
        jobs.finish(session, first, "FAILED")
        for expected in range(2, 6):
            identity = jobs.claim(session, "fixture", 99)
            assert identity and identity != first
            jobs.finish(session, identity, "FAILED")
        with pytest.raises(DomainError) as error:
            jobs.claim(session, "fixture", 99)
        assert error.value.code == "RETRY_LIMIT"


def test_last_admin_protected_and_team_credentials_survive(env):
    _, client, h = env
    response = client.get("/api/v1/administration/users", headers=h["admin"])
    assert response.status_code == 200
    admin = next(row for row in response.json() if row["role"] == "ADMIN")
    denied = client.patch(
        f"/api/v1/administration/users/{admin['id']}",
        headers=h["admin"],
        json={"expected_version": admin["version"], "role": "AUDITOR", "active": True},
    )
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "LAST_ADMIN"
    project_id = valid_invoice(client, h["operator"])["project_id"]
    denied = client.post(
        f"/api/v1/administration/members?project_id={project_id}",
        headers=h["admin"],
        json={"user_id": admin["id"], "member": False},
    )
    assert denied.status_code == 409
    assert client.get("/api/v1/auth/me", headers=h["admin"]).json()["role"] == "ADMIN"
    created = client.post("/api/v1/administration/users", headers=h["admin"], json={
        "email": "second-admin@example.test", "name": "Second local Admin", "role": "ADMIN", "password": "Isolated-Test-Password-2026"})
    assert created.status_code == 201, created.text
    # A second global Admin without project membership cannot replace the only project Admin.
    denied = client.patch(f"/api/v1/administration/users/{admin['id']}", headers=h["admin"],
                          json={"expected_version": admin["version"], "role": "AUDITOR", "active": True})
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "LAST_PROJECT_ADMIN"


def test_archived_runs_are_discoverable_and_read_only(env):
    _, client, h = env
    old_id = valid_invoice(client, h["operator"])["project_id"]
    assert client.post("/api/v1/demo/reset", headers=h["admin"]).status_code == 200
    response = client.get("/api/v1/projects/archived", headers=h["auditor"])
    assert response.status_code == 200, response.text
    assert any(row["id"] == old_id for row in response.json())
    response = client.get(
        f"/api/v1/registers/documents?project_id={old_id}", headers=h["auditor"]
    )
    assert response.status_code == 200 and response.json()["total"] > 0
    denied = client.post(
        "/api/v1/accounting/cost-codes",
        headers=h["operator"],
        json={
            "project_id": old_id,
            "code": "NO.WRITE",
            "name": "Archived modification",
        },
    )
    assert denied.status_code == 409


def test_non_bdt_authority_requires_recorded_fx(env):
    app, client, h = env
    project_id = valid_invoice(client, h["operator"])["project_id"]
    with transaction(app.state.engine) as session:
        with pytest.raises(DomainError) as error:
            conversion(session, project_id, "USD", 10000)
        assert error.value.code == "AUTHORITY_FX_REQUIRED"
    response = client.post(
        "/api/v1/prices/exchange-rates",
        headers=h["manager"],
        json={
            "project_id": project_id,
            "base": "USD",
            "quote": "BDT",
            "factor": "120",
            "observed_date": str(business_date()),
            "source": "Fictional manually sourced test FX observation",
        },
    )
    assert response.status_code == 201, response.text
    with transaction(app.state.engine) as session:
        converted = conversion(session, project_id, "USD", 10000)
        assert converted["amount_minor"] == 1200000
        assert converted["rate_id"]


def test_partial_cash_reservation_keeps_unpaid_schedule_and_concurrent_execution(env):
    app, client, h = env
    invoice, policy, code, acceptance_id, _ = setup_accounting(env)
    project_id = invoice["project_id"]
    control(
        env,
        project_id,
        {
            "kind": "INVOICE_RECONCILIATION",
            "policy_id": policy["id"],
            "invoice_id": invoice["id"],
            "acceptance_ids": [acceptance_id],
            "recognition_date": str(business_date()),
            "due_date": str(business_date() + timedelta(days=20)),
        },
    )
    payable = client.get(
        f"/api/v1/accounting/balances?project_id={project_id}", headers=h["operator"]
    ).json()["payables"][0]
    response = client.post(
        f"/api/v1/payables/{payable['id']}/installments",
        headers=h["operator"],
        json={"amount": "30000", "expected_version": payable["version"]},
    )
    assert response.status_code == 201, response.text
    proposal = response.json()
    forecast = client.get(
        f"/api/v1/finance/extended-forecast?project_id={project_id}&horizon=30",
        headers=h["auditor"],
    ).json()
    assert forecast["reserved"] == "30000.00"
    assert any(
        row["amount"] == "40000.00"
        for day in forecast["scenarios"][0]["days"]
        for row in day["obligations"]
    )
    assert (
        client.post(
            f"/api/v1/payments/{proposal['id']}/approve", headers=h["manager"]
        ).status_code
        == 200
    )

    def execute(index):
        return client.post(
            f"/api/v1/payments/{proposal['id']}/execute",
            headers={
                **h["manager"],
                "Idempotency-Key": f"competing-installment-{index}",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, range(2)))
    assert sorted(result.status_code for result in results) == [200, 409]
    with transaction(app.state.engine) as session:
        assert session.get(m.Project, project_id).balance_minor == 97000000
        assert (
            session.scalar(
                select(func.count(c.InvoiceEntitlement.id)).where(
                    c.InvoiceEntitlement.invoice_id == invoice["id"]
                )
            )
            == 1
        )
