from datetime import timedelta
from app.finance import business_date
from test_accounting_controls import control
from test_advanced_upgrade import demo, estimate


def test_component_contract_keeps_labour_and_reconciles_tax_retention_schedules(env):
    _, client, h = env
    data = demo(env)
    project = data["project_id"]
    row = estimate(client, h, data["estimate_id"])
    fields = row["fields"]
    line = fields["lines"][0]
    line["components"].append(
        {
            "id": "labour",
            "description": "Steel placement labour",
            "category": "LABOUR",
            "consumption": "1",
            "unit": "tonne",
            "unit_price": "5000",
        }
    )
    response = client.patch(
        f"/api/v1/estimates/{row['id']}",
        headers=h["operator"],
        json={
            "expected_version": row["version"],
            "name": row["name"],
            "fields": fields,
        },
    )
    assert response.status_code == 200, response.text
    row = response.json()
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
    code = client.post(
        "/api/v1/accounting/cost-codes",
        headers=h["operator"],
        json={
            "project_id": project,
            "code": "MAT.COMP",
            "name": "Composite material costs",
        },
    ).json()
    control(
        env,
        project,
        {
            "kind": "SUPPLIER_CHANGE",
            "code": "COMP",
            "name": "Composite Supplier",
            "beneficiary_token": "SANDBOX-COMP",
            "verification_reference": "Independent fictional callback",
            "verification_attested": True,
        },
    )
    supplier = client.get(
        f"/api/v1/suppliers?project_id={project}", headers=h["operator"]
    ).json()[0]
    contract = control(
        env,
        project,
        {
            "kind": "COMMERCIAL_CONTRACT",
            "number": "COMP-01",
            "direction": "SUPPLIER",
            "supplier_id": supplier["id"],
            "policy_id": policy["id"],
            "effective_date": str(business_date()),
            "payment_terms_days": 30,
            "tax_percent": "10",
            "retention_percent": "5",
            "lines": [
                {
                    "code": "MAT",
                    "description": line["components"][0]["description"],
                    "quantity": "20",
                    "unit": "tonne",
                    "rate": "74000",
                    "cost_code_id": code["id"],
                }
            ],
        },
    )
    payload = {
        "kind": "CONTRACT_ESTIMATE_LINK",
        "contract_id": contract["id"],
        "item_code": "MAT",
        "estimate_id": row["id"],
        "estimate_line_id": line["id"],
        "component_id": line["components"][0]["id"],
        "complete_cost_scope_confirmed": True,
        "allocation_quantity": "20",
        "schedule": [
            {"quantity": "10", "due_date": str(business_date() + timedelta(days=10))},
            {"quantity": "10", "due_date": str(business_date() + timedelta(days=20))},
        ],
    }
    mapping = control(env, project, payload)
    route = f"/api/v1/finance/extended-forecast?project_id={project}&estimate_id={row['id']}&use_contract_links=true"
    result = client.get(route, headers=h["auditor"])
    assert result.status_code == 200, result.text
    result = result.json()
    # Cost: material1,480,000 + untouched labour100,000. Cash: net1,554,000 + labour100,000,
    # with retention74,000 explicitly unscheduled. Recoverable tax148,000 is not cost.
    assert result["overlay_cost"] == "1580000.00"
    assert result["overlay_cash"] == "1728000.00"
    assert result["scenarios"][0]["days"][20]["closing"] == "346000.00"
    assert sum(float(v["amount"]) for v in result["unscheduled_obligations"]) == 74000
    preview = client.get(
        f"/api/v1/estimates/{row['id']}/forecast", headers=h["operator"]
    ).json()
    assert preview["scenarios"] == result["scenarios"]
    assert preview["overlay_cost"] == result["overlay_cost"]
    # A second allocation on the same contract source cannot overlap another component.
    other = {
        **payload,
        "component_id": "labour",
        "source_offset": "0",
        "target_offset": "0",
    }
    denied = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Unsupported overlap",
            "payload": {**other, "evidence": "Independent overlapping source boundary"},
        },
    )
    assert denied.status_code == 422
    assert estimate(client, h, row["id"])["cost_total"] == "1500000.00"
    second = control(
        env,
        project,
        {
            **contract["payload"],
            "number": "COMP-02",
            "lines": [{**contract["payload"]["lines"][0], "rate": "80000"}],
        },
    )
    overlap = {
        **payload,
        "contract_id": second["id"],
        "allocation_quantity": "1",
        "target_offset": "0",
        "source_offset": "0",
        "schedule": [],
    }
    denied = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Exact matching but overlapping contract",
            "payload": {
                **overlap,
                "evidence": "Same component scope cannot be charged twice",
            },
        },
    )
    assert denied.status_code == 422 and "overlap" in denied.text, denied.text
    # Replace the first mapping by ten tonnes, then allocate the other ten
    # to a different contract. Both source prices and all unrelated costs survive.
    control(
        env,
        project,
        {
            **payload,
            "allocation_quantity": "10",
            "source_offset": "0",
            "target_offset": "0",
            "schedule": [],
            "due_date": str(business_date() + timedelta(days=20)),
        },
    )
    control(
        env,
        project,
        {
            **overlap,
            "allocation_quantity": "10",
            "target_offset": "10",
            "due_date": str(business_date() + timedelta(days=20)),
        },
    )
    split = client.get(route, headers=h["auditor"])
    assert split.status_code == 200, split.text
    assert split.json()["overlay_cost"] == "1640000.00"
    assert split.json()["overlay_cash"] == "1794000.00"


def test_schedule_change_updates_cash_movement_and_can_be_unscheduled(env):
    app, client, h = env
    project = client.get("/api/v1/projects", headers=h["operator"]).json()[0]["id"]
    source = control(
        env,
        project,
        {
            "kind": "OBLIGATION",
            "direction": "OUTFLOW",
            "category": "PAYROLL",
            "amount": "10000",
            "due_date": str(business_date() + timedelta(days=10)),
        },
    )
    from sqlalchemy import select
    from app.database import transaction
    from app import control_models as c, models as m

    with transaction(app.state.engine) as session:
        row = session.scalar(
            select(c.Obligation).where(
                c.Obligation.source_type == "CONTROL",
                c.Obligation.source_id == source["id"],
            )
        )
        identity, version, movement = row.id, row.version, row.cash_movement_id
    changed = control(
        env,
        project,
        {
            "kind": "OBLIGATION_SCHEDULE_CHANGE",
            "obligation_id": identity,
            "expected_obligation_version": version,
            "due_date": str(business_date() + timedelta(days=20)),
            "reason": "Reviewed payroll schedule correction",
        },
    )
    with transaction(app.state.engine) as session:
        row = session.get(c.Obligation, identity)
        cash = session.get(m.CashMovement, movement)
        assert (
            row.due_date == cash.due_date == str(business_date() + timedelta(days=20))
        )
        version = row.version
    control(
        env,
        project,
        {
            "kind": "OBLIGATION_SCHEDULE_CHANGE",
            "obligation_id": identity,
            "expected_obligation_version": version,
            "due_date": None,
            "reason": "Payment timing is now unresolved",
        },
    )
    with transaction(app.state.engine) as session:
        assert session.get(c.Obligation, identity).due_date is None
        assert session.get(m.CashMovement, movement).settled
        assert session.get(m.Project, project).balance_minor == 100000000
