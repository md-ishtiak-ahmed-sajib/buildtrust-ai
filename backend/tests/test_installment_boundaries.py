"""The same edge cases over invoice and measured-certificate payables."""

import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, func
from app import models as m, control_models as c
from app.database import transaction
from app.finance import business_date
from test_accounting_controls import control, setup_accounting
from test_commercial import certified_work, prepare_certificate_payment


def source(env, kind):
    if kind == "certificate":
        project, _, payable, code = certified_work(env)
        return project, payable, code
    _, client, h = env
    invoice, policy, code, acceptance, _ = setup_accounting(env)
    project = invoice["project_id"]
    control(
        env,
        project,
        {
            "kind": "INVOICE_RECONCILIATION",
            "policy_id": policy["id"],
            "invoice_id": invoice["id"],
            "acceptance_ids": [acceptance],
            "recognition_date": str(business_date()),
        },
    )
    return (
        project,
        client.get(
            f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
        ).json()["payables"][0],
        code,
    )


@pytest.mark.parametrize("kind", ["invoice", "certificate"])
@pytest.mark.parametrize(
    "change", ["expiry", "approver_role", "creator_membership", "credit"]
)
def test_installment_rechecks_current_authority_balance_and_expiry(env, kind, change):
    app, client, h = env
    project, payable, code = source(env, kind)
    proposal = prepare_certificate_payment(env, payable, "30000")
    if change == "credit":
        control(
            env,
            project,
            {
                "kind": "CREDIT_NOTE",
                "payable_id": payable["id"],
                "expected_payable_version": payable["version"],
                "cost_code_id": code,
                "amount": "10000",
                "recognition_date": str(business_date()),
                "reference": "PENDING-CREDIT",
            },
        )
    elif change == "approver_role":
        with transaction(app.state.engine) as session:
            manager = session.scalar(
                select(m.User).where(m.User.role == "FINANCE_MANAGER")
            )
            identity, version = manager.id, manager.version
        changed = client.patch(
            f"/api/v1/administration/users/{identity}",
            headers=h["admin"],
            json={"expected_version": version, "role": "AUDITOR", "active": True},
        )
        assert changed.status_code == 200, changed.text
    else:
        with transaction(app.state.engine, True) as session:
            row = session.get(m.Proposal, proposal["id"])
            if change == "expiry":
                row.expires_at = "2000-01-01T00:00:00.000000Z"
            if change == "creator_membership":
                session.delete(session.get(m.Membership, (row.requested_by, project)))
    denied = client.post(
        f"/api/v1/payments/{proposal['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "edge-" + change},
    )
    assert denied.status_code in (403, 409), denied.text
    with transaction(app.state.engine) as session:
        assert session.get(m.Project, project).balance_minor == 100000000
        assert session.scalar(select(func.count()).select_from(m.Payment)) == 0
        assert session.get(c.Payable, payable["id"]).paid_minor == 0
        assert (
            session.scalar(
                select(m.Reservation.state).where(
                    m.Reservation.proposal_id == proposal["id"]
                )
            )
            == "RELEASED"
        )


@pytest.mark.parametrize("kind", ["invoice", "certificate"])
def test_concurrent_credits_approve_only_one_source_version(env, kind):
    app, client, h = env
    project, payable, code = source(env, kind)
    waiting = []
    for index in range(2):
        row = control(
            env,
            project,
            {
                "kind": "CREDIT_NOTE",
                "payable_id": payable["id"],
                "expected_payable_version": payable["version"],
                "cost_code_id": code,
                "amount": "40000",
                "recognition_date": str(business_date()),
                "reference": f"RACE-{index}",
            },
            finish=False,
        )
        for action, role in [("submit", "operator"), ("check", "manager")]:
            response = client.post(
                f"/api/v1/controls/{row['id']}/{action}",
                headers=h[role],
                json={"expected_version": row["version"]},
            )
            assert response.status_code == 200, response.text
            row = response.json()
        waiting.append(row)

    def approve(row):
        return client.post(
            f"/api/v1/controls/{row['id']}/approve",
            headers=h["admin"],
            json={"expected_version": row["version"]},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(approve, waiting))
    assert sorted(r.status_code for r in responses) == [200, 409]
    with transaction(app.state.engine) as session:
        assert session.get(c.Payable, payable["id"]).credit_minor == 4000000
        assert session.get(m.Project, project).balance_minor == 100000000
