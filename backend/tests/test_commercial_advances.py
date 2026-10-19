"""Contract-bound advances and explicit tax/retention reconcile without cash fabrication."""

import pytest
from sqlalchemy import select
from app import control_models as c
from app.database import transaction
from app.finance import business_date
from test_accounting_controls import control
from test_commercial import commercial_setup


@pytest.mark.parametrize("direction", ["SUPPLIER", "CUSTOMER"])
def test_assigned_advance_tax_and_retention_are_separate(env, direction):
    app, client, h = env
    project, original, line, *_ = commercial_setup(env, direction=direction)
    policy = control(
        env,
        project,
        {
            "kind": "ACCOUNTING_POLICY",
            "effective_date": str(business_date()),
            "tax_treatment": "RECOVERABLE",
            "tax_percent": "10",
        },
    )
    contract_payload = {
        **original["payload"],
        "number": "TAX-ADVANCE-CONTRACT",
        "policy_id": policy["id"],
        "tax_percent": "10",
        "retention_percent": "5",
        "advance_recovery_percent": "20",
    }
    contract = control(env, project, contract_payload)
    debit, credit = (
        ("ADVANCE", "OPENING_EQUITY")
        if direction == "SUPPLIER"
        else ("OPENING_EQUITY", "CUSTOMER_ADVANCE")
    )
    opening = control(
        env,
        project,
        {
            "kind": "OPENING_BALANCE",
            "recognition_date": str(business_date()),
            "entries": [
                {"account": debit, "debit": "20000"},
                {"account": credit, "credit": "20000"},
            ],
        },
    )
    with transaction(app.state.engine) as session:
        journal = session.scalar(
            select(c.Journal).where(c.Journal.record_id == opening["id"])
        )
        source_id = journal.id
    assignment = control(
        env,
        project,
        {
            "kind": "ADVANCE_ASSIGNMENT",
            "contract_id": contract["id"],
            "advance_source_id": source_id,
            "amount": "14000",
            "counterparty_attested": True,
        },
    )
    payload = {
        "kind": "INTERIM_CERTIFICATE",
        "contract_id": contract["id"],
        "number": "ADV-IPC-01",
        "recognition_date": str(business_date()),
        "lines": [{"item_code": line["code"], "cumulative_quantity": "100"}],
        "advance_recovery": "14000",
        "advance_assignment_id": assignment["id"],
    }
    if direction == "SUPPLIER":
        sources = client.get(
            f"/api/v1/accounting/sources?project_id={project}", headers=h["operator"]
        ).json()
        receipt = next(
            r for r in sources["receipt_lines"] if r["item_code"] == line["code"]
        )
        acceptance = control(
            env,
            project,
            {
                "kind": "ACCEPTANCE",
                "policy_id": policy["id"],
                "receipt_line_id": receipt["id"],
                "cost_code_id": line["cost_code_id"],
                "recognition_date": str(business_date()),
            },
        )
        payload["acceptance_ids"] = [acceptance["id"]]
    certificate = control(env, project, payload)
    assert certificate["calculated"]["amount"] == "59500.00"
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]
    ).json()
    assert summary["recorded_cash"] == "1000000.00"
    balances = summary["account_balances"]
    assert balances["ADVANCE" if direction == "SUPPLIER" else "CUSTOMER_ADVANCE"] == (
        "6000.00" if direction == "SUPPLIER" else "-6000.00"
    )
    if direction == "SUPPLIER":
        assert summary["incurred_cost"] == "70000.00"
        assert balances["RECOVERABLE_TAX"] == "7000.00"
    else:
        assert summary["recognized_revenue"] == "70000.00"
        assert balances["OUTPUT_TAX"] == "-7000.00"
    # The remaining 6000 may be assigned elsewhere, but not a second full allocation.
    denied = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Overallocated advance",
            "payload": {
                "kind": "ADVANCE_ASSIGNMENT",
                "contract_id": original["id"],
                "advance_source_id": source_id,
                "amount": "7000",
                "counterparty_attested": True,
                "evidence": "Explicit source boundary",
            },
        },
    )
    assert denied.status_code == 422 and "balance" in denied.text
    wrong = {**payload, "contract_id": original["id"], "number": "WRONG-ADVANCE"}
    denied = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Wrong contract advance",
            "payload": {**wrong, "evidence": "Must bind the contract counterparty"},
        },
    )
    assert denied.status_code == 422
    # Reverse sourced certification allocations without refunding cash or
    # reversing accepted base cost. Restored advance stays linked to its contract.
    balance_kind = "payables" if direction == "SUPPLIER" else "receivables"
    balance = client.get(
        f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
    ).json()[balance_kind][0]
    control(
        env,
        project,
        {
            "kind": "CERTIFICATE_CORRECTION",
            "certificate_id": certificate["id"],
            "expected_balance_version": balance["version"],
            "base_amount": "10000",
            "tax_amount": "1000",
            "retention_amount": "500",
            "advance_amount": "2000",
            "recognition_date": str(business_date()),
            "reference": "TAX-ADV-REV",
            "reason": "Source-linked reversal of explicit contractual terms",
        },
    )
    corrected = client.get(
        f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]
    ).json()
    assert corrected["recorded_cash"] == "1000000.00"
    assert corrected["account_balances"][
        "ADVANCE" if direction == "SUPPLIER" else "CUSTOMER_ADVANCE"
    ] == ("8000.00" if direction == "SUPPLIER" else "-8000.00")
    balance = client.get(
        f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
    ).json()[balance_kind][0]
    assert balance["remaining"] == "51000.00" and balance["retention"] == "3000.00"
    assert corrected[
        "incurred_cost" if direction == "SUPPLIER" else "recognized_revenue"
    ] == ("70000.00" if direction == "SUPPLIER" else "60000.00")


def test_recovery_cannot_use_unassigned_journal(env):
    _, client, h = env
    project, original, line, *_ = commercial_setup(env, direction="CUSTOMER")
    payload = {
        **original["payload"],
        "number": "RECOVERY-CON",
        "advance_recovery_percent": "20",
    }
    contract = control(env, project, payload)
    response = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Unassigned advance",
            "payload": {
                "kind": "INTERIM_CERTIFICATE",
                "contract_id": contract["id"],
                "number": "UNASSIGNED",
                "recognition_date": str(business_date()),
                "advance_recovery": "10",
                "lines": [{"item_code": line["code"], "cumulative_quantity": "1"}],
                "evidence": "No counterparty assignment",
            },
        },
    )
    assert response.status_code == 422 and "contract assignment" in response.text
