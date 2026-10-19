from sqlalchemy import select
from app import models as m, control_models as c
from app.database import transaction
from conftest import approved
from test_accounting_controls import setup_accounting, control
from app.finance import business_date


def test_cost_codes_reconcile_acceptance_invoice_payment_and_preserve_history(env):
    app, client, h = env
    invoice, policy, code, recognition, _ = setup_accounting(env)
    project = invoice["project_id"]
    control(env, project, {"kind": "INVOICE_RECONCILIATION", "policy_id": policy["id"], "invoice_id": invoice["id"],
                          "acceptance_ids": [recognition], "recognition_date": str(business_date())})
    proposal = approved(env)
    result = client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h["manager"], "Idempotency-Key": "cost-code-payment"})
    assert result.status_code == 200, result.text
    response = client.get(f"/api/v1/accounting/cost-code-position?project_id={project}", headers=h["auditor"])
    assert response.status_code == 200, response.text
    row = next(row for row in response.json()["rows"] if row["id"] == code)
    assert row["cost"] == row["commitment"] == row["paid"] == "70000.00"
    assert row["accrual"] == row["payable"] == row["remaining_commitment"] == "0.00"
    assert row["budget"] is None
    sources = client.get(f"/api/v1/accounting/sources?project_id={project}", headers=h["auditor"]).json()["cost_sources"]
    source = next(row for row in sources if row["type"] == "PO_LINE" and row["cost_code_id"] == code)
    other = client.post("/api/v1/accounting/cost-codes", headers=h["operator"], json={"project_id": project, "code": "MAT.RECODE", "name": "Future mapping only"}).json()
    with transaction(app.state.engine) as session:
        before = [(row.id, row.cost_code_id, row.debit_minor, row.credit_minor) for row in session.scalars(select(c.JournalLine))]
    control(env, project, {"kind": "COST_CODE_ASSIGNMENT", "source_type": "PO_LINE", "source_id": source["id"],
            "expected_source_version": source["version"], "expected_link_version": source["link_version"], "cost_code_id": other["id"]})
    with transaction(app.state.engine) as session:
        after = [(row.id, row.cost_code_id, row.debit_minor, row.credit_minor) for row in session.scalars(select(c.JournalLine))]
        assert before == after
    report = client.get(f"/api/v1/accounting/cost-code-position?project_id={project}", headers=h["auditor"]).json()
    assert any("recoded after acceptance" in message for message in report["exceptions"])


def test_profit_is_not_treated_as_budget_cost_overrun(env):
    from test_advanced_upgrade import demo, estimate
    _, client, h = env
    data = demo(env)
    current = estimate(client, h, data["estimate_id"])
    current["fields"]["profit_percent"] = "10"
    response = client.patch(f"/api/v1/estimates/{current['id']}", headers=h["operator"], json={"expected_version": current["version"], "name": current["name"], "fields": current["fields"]})
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["cost_total"] == "1400000.00" and current["tender_total"] == "1540000.00"
    for action, role in (("submit", "operator"), ("check", "manager"), ("approve", "admin")):
        response = client.post(f"/api/v1/estimates/{current['id']}/{action}", headers=h[role], json={"expected_version": current["version"]})
        assert response.status_code == 200, response.text
        current = response.json()
    report = client.get(f"/api/v1/finance/cost-control?project_id={data['project_id']}", headers=h["auditor"]).json()
    assert report["forecast_vs_budget"] == "0.00" and report["budget_overrun"] is False
    assert report["tender_vs_budget"] == "140000.00"
