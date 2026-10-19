import json
import pytest
from sqlalchemy import select
from app import control_models as c, models as m
from app.database import transaction
from app.finance import business_date
from test_accounting_controls import control
from test_commercial import (
    certified_work,
    prepare_certificate_payment,
    commercial_setup,
)


@pytest.mark.parametrize("settled", [False, True])
def test_supplier_financial_then_separate_cost_correction_keeps_cash_and_sources(
    env, settled
):
    app, client, h = env
    project, certificate, payable, code = certified_work(env)
    before = certificate["calculated"]
    if settled:
        proposal = prepare_certificate_payment(env, payable)
        response = client.post(
            f"/api/v1/payments/{proposal['id']}/execute",
            headers={**h["manager"], "Idempotency-Key": "correction-settled"},
        )
        assert response.status_code == 200, response.text
        payable = client.get(
            f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
        ).json()["payables"][0]
    corrected = control(
        env,
        project,
        {
            "kind": "CERTIFICATE_CORRECTION",
            "certificate_id": certificate["id"],
            "expected_balance_version": payable["version"],
            "base_amount": "10000",
            "reference": "SUP-COR-01",
            "recognition_date": str(business_date()),
            "reason": "Supported certification value correction only",
        },
    )
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]
    ).json()
    assert (
        summary["incurred_cost"] == "70000.00"
        and summary["accrued_liability"] == "10000.00"
    )
    assert summary["recorded_cash"] == ("930000.00" if settled else "1000000.00")
    current = client.get(
        f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
    ).json()["payables"][0]
    assert current["remaining"] == ("0.00" if settled else "60000.00")
    assert current["supplier_credit"] == ("10000.00" if settled else "0.00")
    acceptance = certificate["payload"]["acceptance_ids"][0]
    control(
        env,
        project,
        {
            "kind": "ACCEPTED_COST_CORRECTION",
            "financial_correction_id": corrected["id"],
            "acceptance_id": acceptance,
            "amount": "10000",
            "recognition_date": str(business_date()),
            "reason": "Separate measured-value correction supported by site evidence",
        },
    )
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]
    ).json()
    assert (
        summary["incurred_cost"] == "60000.00"
        and summary["accrued_liability"] == "0.00"
    )
    with transaction(app.state.engine) as session:
        original = session.get(c.ControlRecord, certificate["id"])
        accepted = session.get(c.ControlRecord, acceptance)
        assert json.loads(original.calculated_json) == before
        assert json.loads(accepted.payload_json)["quantity"] == "10"
        assert json.loads(accepted.calculated_json)["amount_minor"] == 7000000
    denied = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Cannot reverse twice",
            "payload": {
                "kind": "ACCEPTED_COST_CORRECTION",
                "financial_correction_id": corrected["id"],
                "acceptance_id": acceptance,
                "amount": "1",
                "recognition_date": str(business_date()),
                "reason": "Already fully used correction",
                "evidence": "Independent boundary evidence",
            },
        },
    )
    assert denied.status_code == 422 and "exceeds" in denied.text


@pytest.mark.parametrize("collected", [False, True])
def test_customer_correction_never_makes_negative_receivable_or_refunds_cash(
    env, collected
):
    _, client, h = env
    project, contract, line, *_ = commercial_setup(env, direction="CUSTOMER")
    certificate = control(
        env,
        project,
        {
            "kind": "INTERIM_CERTIFICATE",
            "contract_id": contract["id"],
            "number": "CLIENT-COR-IPC",
            "recognition_date": str(business_date()),
            "lines": [{"item_code": line["code"], "cumulative_quantity": "100"}],
        },
    )
    receivable = client.get(
        f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
    ).json()["receivables"][0]
    if collected:
        control(
            env,
            project,
            {
                "kind": "CUSTOMER_RECEIPT",
                "receivable_id": receivable["id"],
                "expected_receivable_version": receivable["version"],
                "amount": "70000",
                "received_date": str(business_date()),
                "reference": "CLIENT-PAY-01",
            },
        )
        receivable = client.get(
            f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
        ).json()["receivables"][0]
    control(
        env,
        project,
        {
            "kind": "CERTIFICATE_CORRECTION",
            "certificate_id": certificate["id"],
            "expected_balance_version": receivable["version"],
            "base_amount": "10000",
            "reference": "CLIENT-COR-01",
            "recognition_date": str(business_date()),
            "reason": "Supported customer certification reversal",
        },
    )
    current = client.get(
        f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]
    ).json()["receivables"][0]
    assert current["remaining"] == ("0.00" if collected else "60000.00")
    assert current["customer_credit"] == ("10000.00" if collected else "0.00")
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]
    ).json()
    assert summary["recognized_revenue"] == "60000.00"
    assert summary["recorded_cash"] == ("1070000.00" if collected else "1000000.00")
