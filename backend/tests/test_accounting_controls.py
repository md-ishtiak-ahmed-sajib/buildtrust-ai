"""Independently specified accounting examples over actual protected APIs."""

from app import control_models as c
from app import models as m
from app.database import transaction
from app.finance import business_date
from conftest import approved, valid_invoice
from sqlalchemy import select


def control(env, project_id, payload, name="Reviewed accounting example", finish=True):
    _, client, h = env
    response = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project_id,
            "name": name,
            "payload": {
                "evidence": "Fictional independently specified acceptance example",
                **payload,
            },
        },
    )
    assert response.status_code == 201, response.text
    row = response.json()
    if finish:
        for action, role in (
            ("submit", "operator"),
            ("check", "manager"),
            ("approve", "admin"),
        ):
            response = client.post(
                f"/api/v1/controls/{row['id']}/{action}",
                headers=h[role],
                json={"expected_version": row["version"]},
            )
            assert response.status_code == 200, response.text
            row = response.json()
    return row


def setup_accounting(env):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])
    project_id = invoice["project_id"]
    policy = control(
        env,
        project_id,
        {"kind": "ACCOUNTING_POLICY", "effective_date": str(business_date())},
    )
    response = client.post(
        "/api/v1/accounting/cost-codes",
        headers=h["operator"],
        json={
            "project_id": project_id,
            "code": "MAT.CEMENT",
            "name": "Cement material costs",
        },
    )
    assert response.status_code == 201, response.text
    code = response.json()["id"]
    with transaction(app.state.engine) as session:
        line = session.scalar(
            select(m.ReceiptLine).where(m.ReceiptLine.item_code == "CEMENT-50KG")
        )
        line_id = line.id
    acceptance = control(
        env,
        project_id,
        {
            "kind": "ACCEPTANCE",
            "policy_id": policy["id"],
            "receipt_line_id": line_id,
            "cost_code_id": code,
            "recognition_date": str(business_date()),
        },
    )
    with transaction(app.state.engine) as session:
        recognition = session.scalar(
            select(c.Recognition).where(c.Recognition.record_id == acceptance["id"])
        )
        acceptance_id = recognition.id
    return invoice, policy, code, acceptance_id, line_id


def test_split_invoices_allocate_one_acceptance_without_double_cost(env):
    from copy import deepcopy
    from decimal import Decimal
    from app.seed import demo_payloads
    from test_documents_workflow import upload
    app, client, h = env
    invoice, policy, code, acceptance_id, receipt_line_id = setup_accounting(env)
    project_id = invoice["project_id"]
    for number, quantity, amount, expected_accrual in (("SPLIT-40", "40", "28000", "42000.00"), ("SPLIT-60", "60", "42000", "0.00")):
        payload = deepcopy(demo_payloads()["scenario-b-valid"])
        payload.update(invoice_number=number, subtotal=amount, grand_total=amount)
        payload["items"][0].update(quantity=quantity, amount=amount)
        response = upload(client, h["operator"], payload, f"{number}.json", project_id)
        assert response.status_code == 201, response.text
        inv = next(row for row in client.get(f"/api/v1/invoices?project_id={project_id}", headers=h["operator"]).json() if row["invoice_number"] == number)
        control(env, project_id, {"kind": "INVOICE_RECONCILIATION", "policy_id": policy["id"], "invoice_id": inv["id"],
                "acceptance_ids": [acceptance_id], "recognition_date": str(business_date())})
        summary = client.get(f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]).json()
        assert summary["incurred_cost"] == "70000.00"
        assert summary["accrued_liability"] == expected_accrual
    assert summary["accounts_payable"] == "70000.00" and summary["recorded_cash"] == "1000000.00"
    with transaction(app.state.engine) as session:
        allocations = list(session.scalars(select(c.RecognitionAllocation).where(c.RecognitionAllocation.recognition_id == acceptance_id)))
        assert sum(Decimal(row.quantity) for row in allocations) == 100
        assert sum(row.amount_minor for row in allocations) == 7000000
        claims = list(session.scalars(select(c.InvoiceEntitlement).where(c.InvoiceEntitlement.receipt_line_id == receipt_line_id)))
        assert sum(Decimal(row.canonical_quantity) for row in claims) == 100
    rejected = client.post("/api/v1/controls", headers=h["operator"], json={"project_id": project_id, "name": "No third use", "payload": {
        "kind": "INVOICE_RECONCILIATION", "policy_id": policy["id"], "invoice_id": invoice["id"], "acceptance_ids": [acceptance_id],
        "recognition_date": str(business_date()), "evidence": "Fully allocated acceptance cannot support a third invoice"}})
    assert rejected.status_code == 422 and "fully reconciled" in rejected.text


def test_acceptance_invoice_payment_cost_recognized_once(env):
    _, client, h = env
    invoice, policy, code, acceptance_id, line_id = setup_accounting(env)
    project_id = invoice["project_id"]
    first = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert first["incurred_cost"] == "70000.00"
    assert first["accrued_liability"] == "70000.00"
    assert first["recorded_cash"] == "1000000.00"
    control(
        env,
        project_id,
        {
            "kind": "INVOICE_RECONCILIATION",
            "policy_id": policy["id"],
            "invoice_id": invoice["id"],
            "acceptance_ids": [acceptance_id],
            "recognition_date": str(business_date()),
        },
    )
    second = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert second["incurred_cost"] == "70000.00"
    assert second["accrued_liability"] == "0.00"
    assert second["accounts_payable"] == "70000.00"
    proposal = approved(env)
    response = client.post(
        f"/api/v1/payments/{proposal['id']}/execute",
        headers={**h["manager"], "Idempotency-Key": "accounting-payment"},
    )
    assert response.status_code == 200, response.text
    final = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert final["incurred_cost"] == "70000.00"
    assert final["accounts_payable"] == "0.00"
    assert final["recorded_cash"] == "930000.00"
    journals = client.get(
        f"/api/v1/accounting/journals?project_id={project_id}", headers=h["auditor"]
    ).json()
    from decimal import Decimal

    assert len(journals) == 3
    for journal in journals:
        assert sum(Decimal(r["debit"]) for r in journal["entries"]) == sum(
            Decimal(r["credit"]) for r in journal["entries"]
        )


def test_certificate_revenue_is_separate_from_cash_collection(env):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])
    project_id = invoice["project_id"]
    policy = control(
        env,
        project_id,
        {"kind": "ACCOUNTING_POLICY", "effective_date": str(business_date())},
    )
    cert = control(
        env,
        project_id,
        {
            "kind": "CUSTOMER_CERTIFICATE",
            "policy_id": policy["id"],
            "customer": "Fictional client",
            "certificate_number": "CLIENT-001",
            "revenue": "200000",
            "recognition_date": str(business_date()),
        },
    )
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert summary["recognized_revenue"] == "200000.00"
    assert summary["accounts_receivable"] == "200000.00"
    assert summary["recorded_cash"] == "1000000.00"
    balances = client.get(
        f"/api/v1/accounting/balances?project_id={project_id}", headers=h["auditor"]
    ).json()
    ar = balances["receivables"][0]
    control(
        env,
        project_id,
        {
            "kind": "CUSTOMER_RECEIPT",
            "receivable_id": ar["id"],
            "expected_receivable_version": ar["version"],
            "amount": "50000",
            "received_date": str(business_date()),
            "reference": "SIMULATED-CUSTOMER-RECEIPT",
        },
    )
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert summary["recognized_revenue"] == "200000.00"
    assert summary["accounts_receivable"] == "150000.00"
    assert summary["recorded_cash"] == "1050000.00"
    duplicate = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project_id,
            "name": "Duplicate customer receipt",
            "payload": {
                "kind": "CUSTOMER_RECEIPT",
                "evidence": "Repeated fictional receipt reference",
                "receivable_id": ar["id"],
                "expected_receivable_version": ar["version"] + 1,
                "amount": "50000",
                "received_date": str(business_date()),
                "reference": "SIMULATED-CUSTOMER-RECEIPT",
            },
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_ACCOUNTING_REFERENCE"


def test_control_separation_snapshot_and_project_access(env):
    _, client, h = env
    project_id = valid_invoice(client, h["operator"])["project_id"]
    row = control(
        env,
        project_id,
        {"kind": "ACCOUNTING_POLICY", "effective_date": str(business_date())},
        finish=False,
    )
    response = client.post(
        f"/api/v1/controls/{row['id']}/submit",
        headers=h["operator"],
        json={"expected_version": row["version"]},
    )
    row = response.json()
    denied = client.post(
        f"/api/v1/controls/{row['id']}/check",
        headers=h["operator"],
        json={"expected_version": row["version"]},
    )
    assert denied.status_code == 403
    stale = client.patch(
        f"/api/v1/controls/{row['id']}",
        headers=h["operator"],
        json={
            "project_id": project_id,
            "expected_version": 1,
            "name": "Overwrite locked submission",
            "payload": row["payload"],
        },
    )
    assert stale.status_code == 409
    denied = client.post(
        "/api/v1/controls",
        headers=h["auditor"],
        json={
            "project_id": project_id,
            "name": "Unauthorized",
            "payload": row["payload"],
        },
    )
    assert denied.status_code == 403


def test_sequential_installments_and_supplier_credit(env):
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
        },
    )
    for index, (amount, cash) in enumerate(
        (("30000", "970000.00"), ("40000", "930000.00"))
    ):
        payable = client.get(
            f"/api/v1/accounting/balances?project_id={project_id}",
            headers=h["operator"],
        ).json()["payables"][0]
        response = client.post(
            f"/api/v1/payables/{payable['id']}/installments",
            headers=h["operator"],
            json={"expected_version": payable["version"], "amount": amount},
        )
        assert response.status_code == 201, response.text
        proposal = response.json()
        assert proposal["status"] == "PENDING_APPROVAL", proposal
        response = client.post(
            f"/api/v1/payments/{proposal['id']}/approve", headers=h["manager"]
        )
        assert response.status_code == 200, response.text
        headers = {**h["manager"], "Idempotency-Key": f"installment-{index}"}
        response = client.post(
            f"/api/v1/payments/{proposal['id']}/execute", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["balance_after"] == cash
        retry = client.post(
            f"/api/v1/payments/{proposal['id']}/execute", headers=headers
        )
        assert retry.json() == response.json()
    with transaction(app.state.engine) as session:
        allocations = list(
            session.scalars(
                select(m.ReceiptAllocation)
                .join(m.Proposal)
                .where(m.Proposal.invoice_id == invoice["id"])
            )
        )
        assert len(allocations) == 0
        claims = list(
            session.scalars(
                select(c.InvoiceEntitlement).where(
                    c.InvoiceEntitlement.invoice_id == invoice["id"]
                )
            )
        )
        assert len(claims) == 1 and claims[0].state == "CONSUMED"
    payable = client.get(
        f"/api/v1/accounting/balances?project_id={project_id}", headers=h["operator"]
    ).json()["payables"][0]
    assert payable["paid"] == "70000.00" and payable["remaining"] == "0.00"
    control(
        env,
        project_id,
        {
            "kind": "CREDIT_NOTE",
            "payable_id": payable["id"],
            "expected_payable_version": payable["version"],
            "amount": "10000",
            "cost_code_id": code,
            "recognition_date": str(business_date()),
            "reference": "CREDIT-001",
        },
    )
    result = client.get(
        f"/api/v1/accounting/balances?project_id={project_id}", headers=h["operator"]
    ).json()["payables"][0]
    assert result["supplier_credit"] == "10000.00"
    summary = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert summary["recorded_cash"] == "930000.00"
    assert client.get("/api/v1/audit/verify", headers=h["auditor"]).json()["valid"]


def test_retention_requires_separate_approval_and_payment(env):
    app, client, h = env
    invoice, policy, code, acceptance_id, _ = setup_accounting(env)
    project_id = invoice["project_id"]
    with transaction(app.state.engine, True) as session:
        row = session.get(m.Invoice, invoice["id"])
        row.retention_minor = 350000
        row.total_minor = 6650000
        row.version += 1
        po = session.get(m.PurchaseOrder, row.po_id)
        po.retention_percent = "5"
        po.version += 1
    control(
        env,
        project_id,
        {
            "kind": "INVOICE_RECONCILIATION",
            "policy_id": policy["id"],
            "invoice_id": invoice["id"],
            "acceptance_ids": [acceptance_id],
            "recognition_date": str(business_date()),
        },
    )
    for index, amount in enumerate(("66500", "3500")):
        p = client.get(
            f"/api/v1/accounting/balances?project_id={project_id}",
            headers=h["operator"],
        ).json()["payables"][0]
        if index:
            assert p["remaining"] == "0.00" and p["retention"] == "3500.00"
            control(
                env,
                project_id,
                {
                    "kind": "RETENTION_RELEASE",
                    "payable_id": p["id"],
                    "expected_payable_version": p["version"],
                    "amount": "3500",
                    "recognition_date": str(business_date()),
                },
            )
            p = client.get(
                f"/api/v1/accounting/balances?project_id={project_id}",
                headers=h["operator"],
            ).json()["payables"][0]
        response = client.post(
            f"/api/v1/payables/{p['id']}/installments",
            headers=h["operator"],
            json={"amount": amount, "expected_version": p["version"]},
        )
        assert response.status_code == 201, response.text
        proposal = response.json()
        assert proposal["status"] == "PENDING_APPROVAL", proposal
        response = client.post(
            f"/api/v1/payments/{proposal['id']}/approve", headers=h["manager"]
        )
        assert response.status_code == 200, response.text
        response = client.post(
            f"/api/v1/payments/{proposal['id']}/execute",
            headers={**h["manager"], "Idempotency-Key": f"retention-{index}"},
        )
        assert response.status_code == 200, response.text
    position = client.get(
        f"/api/v1/accounting/summary?project_id={project_id}", headers=h["auditor"]
    ).json()
    assert (
        position["incurred_cost"] == "70000.00"
        and position["recorded_cash"] == "930000.00"
    )
    assert position["account_balances"]["RETENTION_PAYABLE"] == "0.00"
    payable = client.get(
        f"/api/v1/accounting/balances?project_id={project_id}", headers=h["operator"]
    ).json()["payables"][0]
    excessive = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project_id,
            "name": "Credit cannot count released retention twice",
            "payload": {
                "kind": "CREDIT_NOTE",
                "evidence": "Fictional excessive credit rejection",
                "payable_id": payable["id"],
                "expected_payable_version": payable["version"],
                "amount": "70001",
                "cost_code_id": code,
                "recognition_date": str(business_date()),
                "reference": "EXCESSIVE-CREDIT",
            },
        },
    )
    assert excessive.status_code == 422, excessive.text
