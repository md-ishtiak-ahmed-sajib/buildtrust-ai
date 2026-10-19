from app.finance import business_date
from conftest import valid_invoice
from test_accounting_controls import control
from test_advanced_upgrade import demo


def test_cost_performance_independent_golden_example(env):
    _, client, h = env
    project_id = valid_invoice(client, h["operator"])["project_id"]
    today = str(business_date())
    control(
        env,
        project_id,
        {
            "kind": "OPENING_BALANCE",
            "recognition_date": today,
            "entries": [
                {"account": "PROJECT_COST", "debit": "450000"},
                {"account": "ACCRUED_LIABILITY", "credit": "450000"},
            ],
        },
    )
    baseline = control(
        env,
        project_id,
        {
            "kind": "PERFORMANCE_BASELINE",
            "bac": "1000000",
            "planned_values": [{"date": today, "value": "500000"}],
        },
    )
    control(
        env,
        project_id,
        {
            "kind": "PROGRESS",
            "baseline_id": baseline["id"],
            "as_of": today,
            "earned_value": "400000",
            "physical_progress_evidence": "Fictional checked quantity survey and baseline valuation SIM-001",
        },
    )
    result = client.get(
        f"/api/v1/finance/performance?project_id={project_id}", headers=h["auditor"]
    )
    assert result.status_code == 200, result.text
    evm = result.json()["evm"]
    assert evm["BAC"] == "1000000.00" and evm["PV"] == "500000.00"
    assert evm["EV"] == "400000.00" and evm["AC"] == "450000.00"
    assert evm["CV"] == "-50000.00" and evm["SV"] == "-100000.00"
    assert evm["EAC"]["remaining_at_budget"] == "1050000.00"
    assert evm["ETC"]["remaining_at_budget"] == "600000.00"
    assert evm["VAC"]["remaining_at_budget"] == "-50000.00"
    assert evm["TCPI"] == "1.090909"


def test_revenue_margin_and_reporting_fx_gap(env):
    _, client, h = env
    project_id = valid_invoice(client, h["operator"])["project_id"]
    today = str(business_date())
    policy = control(
        env, project_id, {"kind": "ACCOUNTING_POLICY", "effective_date": today}
    )
    control(
        env,
        project_id,
        {
            "kind": "OPENING_BALANCE",
            "recognition_date": today,
            "entries": [
                {"account": "PROJECT_COST", "debit": "150000"},
                {"account": "ACCRUED_LIABILITY", "credit": "150000"},
            ],
        },
    )
    control(
        env,
        project_id,
        {
            "kind": "CUSTOMER_CERTIFICATE",
            "policy_id": policy["id"],
            "customer": "Fictional client",
            "certificate_number": "CERT-200",
            "revenue": "200000",
            "recognition_date": today,
        },
    )
    report = client.get(
        f"/api/v1/finance/performance?project_id={project_id}&reporting_currency=USD",
        headers=h["auditor"],
    ).json()
    assert report["project_margin_percent"] == "25.000000"
    assert report["recorded_cash"] == "1000000.00"
    assert not report["reporting_currency"]["available"]
    assert report["reporting_currency"]["factor"] is None


def test_extended_forecast_and_uncommitted_material_scenario(env):
    _, client, h = env
    data = demo(env)
    base = client.get(
        f"/api/v1/finance/extended-forecast?project_id={data['project_id']}&horizon=90&estimate_id={data['estimate_id']}",
        headers=h["operator"],
    )
    assert base.status_code == 200, base.text
    assert len(base.json()["scenarios"][0]["days"]) == 90
    assert base.json()["scenarios"][0]["days"][20]["closing"] == "600000.00"
    change = client.get(
        f"/api/v1/finance/extended-forecast?project_id={data['project_id']}&horizon=90&estimate_id={data['estimate_id']}&scenario=MATERIAL_ESCALATION&material_percent=5.714285714285714285714286",
        headers=h["operator"],
    )
    assert change.status_code == 200, change.text
    assert change.json()["scenarios"][0]["days"][20]["closing"] == "520000.00"
    assert change.json()["recorded_balance"] == "2000000.00"


def test_reviewed_project_duration_and_forecast_margin_snapshot(env):
    from datetime import timedelta
    from test_advanced_upgrade import estimate
    _, client, h = env
    data = demo(env)
    project_id = data["project_id"]
    today = business_date()
    missing = client.get(f"/api/v1/finance/extended-forecast?project_id={project_id}&use_project_schedule=true", headers=h["auditor"])
    assert missing.status_code == 422
    schedule = control(env, project_id, {"kind": "PROJECT_SCHEDULE", "start_date": str(today), "completion_date": str(today + timedelta(days=89))})
    response = client.get(f"/api/v1/finance/extended-forecast?project_id={project_id}&use_project_schedule=true", headers=h["auditor"])
    assert response.status_code == 200, response.text
    assert response.json()["horizon_days"] == 90 and response.json()["schedule_source_id"] == schedule["id"]
    current = estimate(client, h, data["estimate_id"])
    current["fields"]["lines"][0]["components"][0]["unit_price"] = "7500"
    response = client.patch(f"/api/v1/estimates/{current['id']}", headers=h["operator"], json={"expected_version": current["version"], "name": "Forecast cost 150000", "fields": current["fields"]})
    assert response.status_code == 200, response.text
    current = response.json()
    for action, role in (("submit", "operator"), ("check", "manager"), ("approve", "admin")):
        response = client.post(f"/api/v1/estimates/{current['id']}/{action}", headers=h[role], json={"expected_version": current["version"]})
        assert response.status_code == 200, response.text
        current = response.json()
    policy = control(env, project_id, {"kind": "ACCOUNTING_POLICY", "effective_date": str(today)})
    response = client.post("/api/v1/accounting/cost-codes", headers=h["operator"], json={"project_id": project_id, "code": "FULL.SCOPE", "name": "Complete fictional scope"})
    assert response.status_code == 201, response.text
    contract = control(env, project_id, {"kind": "COMMERCIAL_CONTRACT", "number": "FORECAST-CLIENT-01", "direction": "CUSTOMER", "customer": "Fictional forecast client", "policy_id": policy["id"], "effective_date": str(today), "payment_terms_days": 30,
        "lines": [{"code": "WORK", "description": "Complete fictional work scope", "quantity": "100", "unit": "m3", "rate": "2000", "cost_code_id": response.json()["id"]}]})
    forecast = control(env, project_id, {"kind": "FINANCIAL_FORECAST", "customer_contract_ids": [contract["id"]], "cost_method": "APPROVED_ESTIMATE", "estimate_id": current["id"], "as_of": str(today), "complete_scope_confirmed": True})
    assert forecast["calculated"]["forecast_cost"] == "150000.00"
    assert forecast["calculated"]["forecast_revenue"] == "200000.00"
    assert forecast["calculated"]["forecast_margin_percent"] == "25.000000"
    response = client.get(f"/api/v1/finance/performance?project_id={project_id}", headers=h["auditor"])
    assert response.status_code == 200, response.text
    assert response.json()["forecast_snapshot"]["control_id"] == forecast["id"]
    assert response.json()["recognized_revenue"] is None
    assert response.json()["recorded_cash"] == "2000000.00"
    assert response.json()["forecast_snapshot"]["source_status"] == "UNCHANGED"
    control(env, project_id, {"kind": "CONTRACT_VARIATION", "contract_id": contract["id"], "number": "FORECAST-VO-01",
        "item_code": "WORK", "additional_quantity": "10", "proposed_rate": "2000", "claimed_value": "20000",
        "reason": "Additional independently approved revenue scope"})
    updated = client.get(f"/api/v1/finance/performance?project_id={project_id}", headers=h["auditor"]).json()
    assert updated["forecast_snapshot"]["source_status"] == "SOURCE_CHANGED"
    assert updated["forecast_snapshot"]["forecast_revenue"] == "200000.00"
    assert updated["recorded_cash"] == "2000000.00"
