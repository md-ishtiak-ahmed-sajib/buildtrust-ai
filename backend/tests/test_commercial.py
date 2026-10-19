"""Independent commercial examples through authenticated persisted interfaces."""

from datetime import timedelta
from decimal import Decimal
import json

from sqlalchemy import select, func

from app import models as m, control_models as c, commercial_models as cm
from app.database import transaction
from app.finance import business_date
from conftest import valid_invoice
from test_accounting_controls import control, setup_accounting
from test_documents_workflow import upload


def commercial_setup(env, direction="SUPPLIER", retention="0", custom=False):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])
    project = invoice["project_id"]
    policy = control(env, project, {"kind": "ACCOUNTING_POLICY", "effective_date": str(business_date())})
    response = client.post("/api/v1/accounting/cost-codes", headers=h["operator"],
                           json={"project_id": project, "code": "WORK.FOUNDATION", "name": "Foundation works"})
    assert response.status_code == 201, response.text
    cost_code = response.json()["id"]
    with transaction(app.state.engine) as session:
        supplier = session.scalar(select(m.Supplier).where(m.Supplier.code == "DEMO-CEMENT"))
        supplier_id, supplier_name = supplier.id, supplier.name
        boq = session.scalar(select(m.BOQItem).where(m.BOQItem.item_code == "CEMENT-50KG"))
        line = {"code": boq.item_code, "description": boq.description, "unit": boq.unit,
                "quantity": "100", "rate": "700", "cost_code_id": cost_code, "boq_item_id": boq.id}
    if custom:
        payload = {"document_type": "BOQ", "items": [{"item_code": "NEW-CEMENT", "description": line["description"],
                   "unit": "bag", "quantity": "200", "unit_rate": "800", "amount": "160000"}]}
        doc = upload(client, h["operator"], payload, "new-boq.json", project).json()
        confirmed = client.post(f"/api/v1/documents/{doc['id']}/confirm", headers=h["admin"])
        assert confirmed.status_code == 200, confirmed.text
        with transaction(app.state.engine) as session:
            boq = session.scalar(select(m.BOQItem).where(m.BOQItem.item_code == "NEW-CEMENT"))
            line.update(code=boq.item_code, boq_item_id=boq.id, quantity="100", rate="800")
    payload = {"kind": "COMMERCIAL_CONTRACT", "number": "CON-001", "direction": direction,
               "policy_id": policy["id"], "effective_date": str(business_date()), "payment_terms_days": 30,
               "retention_percent": retention, "lines": [line]}
    payload.update(supplier_id=supplier_id) if direction == "SUPPLIER" else payload.update(customer="Fictional client")
    contract = control(env, project, payload, "Fictional contract")
    return project, contract, line, supplier_id, supplier_name, cost_code


def test_rfq_bid_award_publishes_trusted_po_without_changing_boq(env):
    app, client, h = env
    project, contract, line, supplier_id, supplier_name, code = commercial_setup(env, custom=True)
    response = client.post("/api/v1/materials", headers=h["operator"], json={"project_id": project,
                           "name": line["description"], "unit": "bag", "specification": {"grade": "Portland", "package": "50 kg"}})
    assert response.status_code == 201, response.text
    material = response.json()
    rfq = control(env, project, {"kind": "RFQ", "number": "RFQ-001", "contract_id": contract["id"],
                  "item_code": line["code"], "material_id": material["id"], "quantity": "100",
                  "closing_date": str(business_date()), "delivery_date": str(business_date() + timedelta(days=5)), "destination": "Dhaka site"})
    quote = client.post("/api/v1/quotations", headers=h["operator"], json={"material_id": material["id"],
                        "supplier": supplier_name, "title": line["description"], "price": "700", "unit": "bag", "quoted_quantity": "100",
                        "specification": material["specification"], "can_deliver": True, "delivery_days": 2,
                        "freight_basis": "INCLUDED", "tax_basis": "INCLUDED", "tax": "0", "handling": "0", "other_cost": "0",
                        "valid_until": str(business_date() + timedelta(days=7))})
    assert quote.status_code == 201, quote.text
    verified = client.post(f"/api/v1/quotations/{quote.json()['id']}/verify", headers=h["manager"], json={"expected_version": quote.json()["version"]})
    assert verified.status_code == 200, verified.text
    from app.advanced_models import PriceObservation
    with transaction(app.state.engine) as session:
        observation_id = session.scalar(select(PriceObservation.id).where(PriceObservation.quotation_id == quote.json()["id"]))
        before = session.get(m.BOQItem, line["boq_item_id"]).quantity
    bid = control(env, project, {"kind": "COMMERCIAL_BID", "rfq_id": rfq["id"], "supplier_id": supplier_id,
                  "observation_id": observation_id, "technical_evidence": "Independently checked full specification and delivery"})
    recommendation = control(env, project, {"kind": "PURCHASE_RECOMMENDATION", "rfq_id": rfq["id"],
                             "bid_ids": [bid["id"]], "selected_bid_id": bid["id"], "selection_reason": "Only verified eligible quotation; single-source warning reviewed"})
    assert recommendation["calculated"]["single_source"] is True
    award = control(env, project, {"kind": "PURCHASE_AWARD", "recommendation_id": recommendation["id"], "po_number": "AWARD-001"})
    with transaction(app.state.engine) as session:
        publication = session.scalar(select(cm.CommercialPublication).where(cm.CommercialPublication.control_id == award["id"]))
        po = session.get(m.PurchaseOrder, publication.source_id)
        assert po.approved and po.number == "AWARD-001"
        assert session.get(m.BOQItem, line["boq_item_id"]).quantity == before
        pol = session.scalar(select(m.POLine).where(m.POLine.po_id == po.id))
        assert pol.quantity == "100" and pol.rate == "700.000000"
        assert session.scalar(select(c.CostCodeLink.cost_code_id).where(c.CostCodeLink.source_id == pol.id)) == code
    duplicate = client.post("/api/v1/controls", headers=h["operator"], json={"project_id": project, "name": "Duplicate award",
                            "payload": {"kind": "PURCHASE_AWARD", "recommendation_id": recommendation["id"], "po_number": "AWARD-002", "evidence": "Same recommendation cannot be awarded twice"}})
    assert duplicate.status_code == 422, duplicate.text


def test_supplier_certificate_installments_claim_acceptance_once(env):
    app, client, h = env
    invoice, policy, code, recognition_id, receipt_id = setup_accounting(env)
    project = invoice["project_id"]
    with transaction(app.state.engine) as session:
        recognition = session.get(c.Recognition, recognition_id)
        acceptance_id = recognition.record_id
        supplier_id = session.get(m.Invoice, invoice["id"]).supplier_id
    contract = control(env, project, {"kind": "COMMERCIAL_CONTRACT", "number": "CERT-CON-001", "direction": "SUPPLIER",
                       "supplier_id": supplier_id, "policy_id": policy["id"], "effective_date": str(business_date()), "payment_terms_days": 30,
                       "lines": [{"code": "CEMENT-50KG", "description": "Portland Cement 50 kg bag", "quantity": "100", "unit": "bag", "rate": "700", "cost_code_id": code}]})
    cert = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "IPC-001",
                   "recognition_date": str(business_date()), "due_date": str(business_date() + timedelta(days=5)),
                   "lines": [{"item_code": "CEMENT-50KG", "cumulative_quantity": "100"}], "acceptance_ids": [acceptance_id]})
    assert cert["calculated"]["amount"] == "70000.00"
    blocked = client.post(f"/api/v1/invoices/{invoice['id']}/analyze", headers=h["operator"])
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["payment_eligible"] is False
    balances = client.get(f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]).json()
    payable = balances["payables"][0]
    for index, (amount, expected_cash) in enumerate((("30000", "970000.00"), ("40000", "930000.00"))):
        prepared = client.post(f"/api/v1/payables/{payable['id']}/installments", headers=h["operator"],
                               json={"expected_version": payable["version"], "amount": amount})
        assert prepared.status_code == 201, prepared.text
        proposal = prepared.json()
        assert proposal["invoice_id"] is None and proposal["certificate_id"] == cert["id"]
        approved = client.post(f"/api/v1/payments/{proposal['id']}/approve", headers=h["manager"])
        assert approved.status_code == 200, approved.text
        result = client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h["manager"], "Idempotency-Key": f"cert-installment-{index}"})
        assert result.status_code == 200, result.text
        assert result.json()["balance_after"] == expected_cash
        retry = client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h["manager"], "Idempotency-Key": f"cert-installment-{index}"})
        assert retry.json() == result.json()
        payable = client.get(f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]).json()["payables"][0]
    summary = client.get(f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]).json()
    assert summary["incurred_cost"] == "70000.00" and summary["accounts_payable"] == "0.00"
    with transaction(app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(cm.CertificateAllocation)) == 1
        assert session.scalar(select(func.count()).select_from(m.ReceiptAllocation)) == 0


def test_customer_cumulative_certificate_variation_preserves_prior_rates(env):
    _, client, h = env
    project, contract, line, _, _, _ = commercial_setup(env, direction="CUSTOMER", retention="5")
    first = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "CLIENT-IPC-01",
                    "recognition_date": str(business_date()), "lines": [{"item_code": line["code"], "cumulative_quantity": "50"}]})
    assert first["calculated"]["amount"] == "33250.00"
    variation = control(env, project, {"kind": "CONTRACT_VARIATION", "contract_id": contract["id"], "number": "VO-01", "item_code": line["code"],
                         "additional_quantity": "20", "proposed_rate": "750", "claimed_value": "16000", "reason": "Additional authorized future quantity", "time_impact_days": 3})
    assert variation["calculated"]["approved_value"] == "15000.00"
    second = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "CLIENT-IPC-02",
                     "recognition_date": str(business_date()), "lines": [{"item_code": line["code"], "cumulative_quantity": "120"}]})
    assert second["calculated"]["cumulative_work"] == "85000.00"
    assert second["calculated"]["previous_work"] == "35000.00"
    assert second["calculated"]["amount"] == "47500.00"
    summary = client.get(f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]).json()
    assert summary["recognized_revenue"] == "85000.00"
    assert summary["recorded_cash"] == "1000000.00"


def test_rate_variation_only_reprices_future_uncommitted_quantity(env):
    _, client, h = env
    project, contract, line, _, _, _ = commercial_setup(env, direction="CUSTOMER")
    first = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "RATE-IPC-01",
                    "recognition_date": str(business_date()), "lines": [{"item_code": line["code"], "cumulative_quantity": "50"}]})
    # This contract is linked to an already committed 100-bag procurement BOQ,
    # so reprice a fresh customer contract without that procurement linkage.
    payload = dict(contract["payload"])
    payload["number"] = "CUSTOMER-FUTURE-01"
    payload["lines"] = [{**line, "boq_item_id": None}]
    future = control(env, project, payload)
    first = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": future["id"], "number": "FUTURE-IPC-01",
                    "recognition_date": str(business_date()), "lines": [{"item_code": line["code"], "cumulative_quantity": "50"}]})
    variation = control(env, project, {"kind": "CONTRACT_VARIATION", "contract_id": future["id"], "number": "RATE-VO-01", "item_code": line["code"],
                         "additional_quantity": "0", "reprice_quantity": "50", "proposed_rate": "750", "claimed_value": "2500", "reason": "Prospective price adjustment only"})
    assert variation["calculated"]["approved_value"] == "2500.00"
    second = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": future["id"], "number": "FUTURE-IPC-02",
                     "recognition_date": str(business_date()), "lines": [{"item_code": line["code"], "cumulative_quantity": "100"}]})
    assert first["calculated"]["amount"] == "35000.00"
    assert second["calculated"]["amount"] == "37500.00"
    assert second["calculated"]["cumulative_work"] == "72500.00"
    denied = client.post("/api/v1/controls", headers=h["operator"], json={"project_id": project, "name": "Cannot rewrite certified work", "payload": {
        "kind": "CONTRACT_VARIATION", "contract_id": future["id"], "number": "BAD-RATE-VO", "item_code": line["code"], "additional_quantity": "0", "reprice_quantity": "1",
        "proposed_rate": "900", "claimed_value": "200", "reason": "Already certified work must retain its historical rate", "evidence": "Independent boundary example"}})
    assert denied.status_code == 422 and "Repricing" in denied.text


def test_work_acceptance_requires_checked_measurement_and_no_duplicate_source(env):
    _, client, h = env
    project, contract, line, _, _, _ = commercial_setup(env)
    # Quantity sheets use compatible units; count cannot stand in for a mass/package measurement.
    sheet = client.post("/api/v1/takeoff/sheets", headers=h["operator"], json={"project_id": project, "profile_id": 1, "name": "Measured count",
                        "calculation": "COUNT", "dimensions": {"count": "100"}, "drawing_reference": "DRG-001"})
    assert sheet.status_code == 201, sheet.text
    data = {"project_id": project, "name": "Unsupported bag conversion", "payload": {"kind": "WORK_ACCEPTANCE", "contract_id": contract["id"],
            "item_code": line["code"], "quantity": "100", "recognition_date": str(business_date()), "measurement_id": sheet.json()["id"], "evidence": "Checked work must match supplied units"}}
    response = client.post("/api/v1/controls", headers=h["operator"], json=data)
    assert response.status_code == 422 and "checked" in response.text


def certified_work(env, retention="0"):
    app, client, h = env
    project, original, _, supplier, _, code = commercial_setup(env)
    contract = control(env, project, {"kind": "COMMERCIAL_CONTRACT", "number": "WORK-CON-01", "direction": "SUPPLIER",
                       "supplier_id": supplier, "policy_id": original["payload"]["policy_id"], "effective_date": str(business_date()),
                       "payment_terms_days": 30, "retention_percent": retention,
                       "lines": [{"code": "CONCRETE", "description": "Measured foundation concrete", "unit": "m3", "quantity": "10", "rate": "7000", "cost_code_id": code}]})
    sheet = client.post("/api/v1/takeoff/sheets", headers=h["operator"], json={"project_id": project, "profile_id": 1, "name": "Foundation as built",
                        "calculation": "RECTANGULAR_VOLUME", "dimensions": {"length": "5", "width": "2", "height": "1"}, "drawing_reference": "AS-BUILT-001", "revision": "2"})
    assert sheet.status_code == 201, sheet.text
    checked = client.post(f"/api/v1/takeoff/sheets/{sheet.json()['id']}/check", headers=h["manager"], json={"expected_version": sheet.json()["version"], "reason": "Independent site measurement"})
    assert checked.status_code == 200, checked.text
    acceptance = control(env, project, {"kind": "WORK_ACCEPTANCE", "contract_id": contract["id"], "item_code": "CONCRETE",
                         "quantity": "10", "measurement_id": sheet.json()["id"], "recognition_date": str(business_date())})
    duplicate = client.post("/api/v1/controls", headers=h["operator"], json={"project_id": project, "name": "Duplicate measured work", "payload": acceptance["payload"]})
    assert duplicate.status_code == 422, duplicate.text
    cert = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "WORK-IPC-001",
                   "recognition_date": str(business_date()), "due_date": str(business_date() + timedelta(days=3)),
                   "lines": [{"item_code": "CONCRETE", "cumulative_quantity": "10"}], "acceptance_ids": [acceptance["id"]]})
    payable = client.get(f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]).json()["payables"][0]
    return project, cert, payable, code


def prepare_certificate_payment(env, payable, amount=None):
    _, client, h = env
    response = client.post(f"/api/v1/payables/{payable['id']}/installments", headers=h["operator"],
                           json={"expected_version": payable["version"], "amount": amount or payable["remaining"]})
    assert response.status_code == 201, response.text
    proposal = response.json()
    denial = client.post(f"/api/v1/payments/{proposal['id']}/approve", headers=h["operator"])
    assert denial.status_code == 403
    response = client.post(f"/api/v1/payments/{proposal['id']}/approve", headers=h["manager"])
    assert response.status_code == 200, response.text
    return proposal


def test_certified_work_rollback_retry_and_concurrent_settlement(env):
    from concurrent.futures import ThreadPoolExecutor
    app, client, h = env
    project, cert, payable, code = certified_work(env)
    proposal = prepare_certificate_payment(env, payable)
    app.state.execution_failure_hook = lambda: (_ for _ in ()).throw(RuntimeError("Injected sandbox failure"))
    first = client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h["manager"], "Idempotency-Key": "cert-failed"})
    assert first.status_code == 503, first.text
    retry = client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h["manager"], "Idempotency-Key": "cert-failed"})
    assert retry.status_code == 503 and retry.json() == first.json()
    with transaction(app.state.engine) as session:
        assert session.get(m.Project, project).balance_minor == 100000000
        assert session.get(c.Payable, payable["id"]).paid_minor == 0
        assert session.scalar(select(func.count()).select_from(m.Payment)) == 0
        assert session.scalar(select(m.Reservation.state).where(m.Reservation.proposal_id == proposal["id"])) == "RELEASED"
    app.state.execution_failure_hook = None
    proposal = prepare_certificate_payment(env, payable)
    def execute():
        return client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h["manager"], "Idempotency-Key": "cert-concurrent"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    with transaction(app.state.engine) as session:
        assert session.get(m.Project, project).balance_minor == 93000000
        assert session.scalar(select(func.count()).select_from(m.Payment)) == 1
        assert session.scalar(select(func.count()).select_from(cm.CertificateAllocation)) == 1
    control(env, project, {"kind": "CREDIT_NOTE", "payable_id": payable["id"], "expected_payable_version": payable["version"] + 1,
             "amount": "10000", "cost_code_id": code, "recognition_date": str(business_date()), "reference": "CERT-CREDIT-01"})
    summary = client.get(f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]).json()
    assert summary["recorded_cash"] == "930000.00" and summary["incurred_cost"] == "60000.00"


def test_certified_retention_release_is_separate_payment_and_no_null_schedule_collision(env):
    _, client, h = env
    project, cert, payable, _ = certified_work(env, retention="5")
    assert payable["remaining"] == "66500.00" and payable["retention"] == "3500.00"
    first = prepare_certificate_payment(env, payable)
    result = client.post(f"/api/v1/payments/{first['id']}/execute", headers={**h["manager"], "Idempotency-Key": "cert-net"})
    assert result.status_code == 200, result.text
    control(env, project, {"kind": "RETENTION_RELEASE", "payable_id": payable["id"], "expected_payable_version": payable["version"] + 1,
             "amount": "3500", "recognition_date": str(business_date())})
    payable = client.get(f"/api/v1/accounting/balances?project_id={project}", headers=h["auditor"]).json()["payables"][0]
    assert payable["remaining"] == "3500.00" and payable["retention"] == "0.00"
    second = prepare_certificate_payment(env, payable)
    result = client.post(f"/api/v1/payments/{second['id']}/execute", headers={**h["manager"], "Idempotency-Key": "cert-retention"})
    assert result.status_code == 200 and result.json()["balance_after"] == "930000.00", result.text


def test_commercial_copilot_uses_approved_sources_without_authority(env):
    _, client, h = env
    project, contract, *_ = commercial_setup(env)
    result = client.post("/api/v1/advanced/ask", headers=h["operator"], json={"project_id": project, "question": "Explain our contracts and certificates"})
    assert result.status_code == 200, result.text
    assert result.json()["tools"] == ["commercial_evidence_register"]
    assert any(row["control_id"] == contract["id"] for row in result.json()["sources"])


def test_materials_on_site_incorporation_does_not_recognize_cost_twice(env):
    app, client, h = env
    invoice, policy, code, recognition_id, _ = setup_accounting(env)
    project = invoice["project_id"]
    with transaction(app.state.engine) as session:
        acceptance_id = session.get(c.Recognition, recognition_id).record_id
        supplier_id = session.get(m.Invoice, invoice["id"]).supplier_id
    contract = control(env, project, {"kind": "COMMERCIAL_CONTRACT", "number": "MOS-CON-01", "direction": "SUPPLIER",
        "supplier_id": supplier_id, "policy_id": policy["id"], "effective_date": str(business_date()), "payment_terms_days": 30,
        "materials_on_site_allowed": True,
        "lines": [{"code": "CONCRETE", "description": "Concrete including supplied cement", "quantity": "20", "unit": "m3", "rate": "5000", "cost_code_id": code}]})
    first = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "MOS-IPC-01",
        "recognition_date": str(business_date()), "lines": [{"item_code": "CONCRETE", "cumulative_quantity": "0"}],
        "materials_on_site": "70000", "materials_evidence": "Confirmed supplier cement accepted and eligible under the contract", "acceptance_ids": [acceptance_id], "materials_acceptance_ids": [acceptance_id]})
    assert first["calculated"]["amount"] == "70000.00"
    sheet = client.post("/api/v1/takeoff/sheets", headers=h["operator"], json={"project_id": project, "profile_id": 1, "name": "Concrete incorporation",
        "calculation": "RECTANGULAR_VOLUME", "dimensions": {"length": "5", "width": "4", "height": "1"}, "drawing_reference": "AS-BUILT-MOS-01"})
    assert sheet.status_code == 201, sheet.text
    checked = client.post(f"/api/v1/takeoff/sheets/{sheet.json()['id']}/check", headers=h["manager"], json={"expected_version": sheet.json()["version"]})
    assert checked.status_code == 200, checked.text
    work = control(env, project, {"kind": "WORK_ACCEPTANCE", "contract_id": contract["id"], "item_code": "CONCRETE", "quantity": "20",
        "recognition_date": str(business_date()), "measurement_id": sheet.json()["id"], "incorporated_acceptance_ids": [acceptance_id],
        "incorporation_evidence": "As-built measurement and delivery trace confirm incorporation of the previously recognized cement"})
    assert work["calculated"]["gross_cost"] == "100000.00"
    assert work["calculated"]["amount"] == "30000.00"
    second = control(env, project, {"kind": "INTERIM_CERTIFICATE", "contract_id": contract["id"], "number": "MOS-IPC-02",
        "recognition_date": str(business_date()), "lines": [{"item_code": "CONCRETE", "cumulative_quantity": "20"}],
        "materials_on_site": "0", "acceptance_ids": [work["id"]]})
    assert second["calculated"]["amount"] == "30000.00"
    summary = client.get(f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]).json()
    assert summary["incurred_cost"] == "100000.00" and summary["accounts_payable"] == "100000.00"
    assert summary["accrued_liability"] == "0.00" and summary["recorded_cash"] == "1000000.00"
