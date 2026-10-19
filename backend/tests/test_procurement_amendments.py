from sqlalchemy import select
from app import models as m, commercial_models as cm, procurement
from app.database import transaction
from test_accounting_controls import control
from test_documents_workflow import upload
from conftest import valid_invoice


def sources(env):
    app, client, h = env
    project = valid_invoice(client, h["operator"])["project_id"]
    item = {
        "item_code": "AMEND-CEMENT",
        "description": "Amendment cement specified 50 kg bag",
        "quantity": "100",
        "unit": "bag",
        "unit_rate": "700",
        "amount": "70000",
    }

    def confirm(payload, name, role):
        response = upload(client, h["operator"], payload, name, project)
        assert response.status_code == 201, response.text
        result = client.post(
            f"/api/v1/documents/{response.json()['id']}/confirm", headers=h[role]
        )
        assert result.status_code == 200, result.text

    confirm({"document_type": "BOQ", "items": [item]}, "amend-boq.json", "admin")
    confirm(
        {
            "document_type": "PO",
            "po_number": "AMEND-PO",
            "supplier_code": "DEMO-CEMENT",
            "currency": "BDT",
            "items": [item],
        },
        "amend-po.json",
        "manager",
    )
    confirm(
        {
            "document_type": "GRN",
            "po_number": "AMEND-PO",
            "receipt_number": "AMEND-GRN",
            "items": [{**item, "quantity": "80", "amount": "56000"}],
        },
        "amend-grn.json",
        "manager",
    )
    with transaction(app.state.engine) as session:
        boq = session.scalar(
            select(m.BOQItem).where(m.BOQItem.item_code == "AMEND-CEMENT")
        )
        po = session.scalar(
            select(m.PurchaseOrder).where(m.PurchaseOrder.number == "AMEND-PO")
        )
        line = session.scalar(select(m.POLine).where(m.POLine.po_id == po.id))
        return project, boq.id, boq.version, po.id, po.version, line.id


def test_amendment_keeps_original_lines_and_requires_separate_value_authority(env):
    app, client, h = env
    project, boq, bv, po, pv, line = sources(env)
    payload = {
        "kind": "PROCUREMENT_AMENDMENT",
        "po_line_id": line,
        "expected_po_version": pv,
        "boq_item_id": boq,
        "retire_quantity": "20",
        "replacement_quantity": "20",
        "replacement_rate": "750",
        "successor_po_number": "AMEND-PO-R1",
        "reason": "Prospective replacement quantity only",
        "evidence": "Fictional independently checked amendment evidence",
    }
    response = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={"project_id": project, "name": "Needs authority", "payload": payload},
    )
    assert response.status_code == 422 and "separate authorization" in response.text
    authority = control(
        env,
        project,
        {
            "kind": "PROCUREMENT_AUTHORIZATION",
            "boq_item_id": boq,
            "expected_boq_version": bv,
            "extra_value": "1000",
            "reason": "Separately approve prospective 1000 BDT procurement uplift",
        },
    )
    assert authority["calculated"]["authorized_value"] == "71000.00"
    approved = control(env, project, payload)
    with transaction(app.state.engine) as session:
        original = session.get(m.POLine, line)
        assert original.quantity == "100" and original.rate == "700"
        assert procurement.quantity(session, original) == 80
        assert session.get(m.PurchaseOrder, po).version == pv + 1
        successor = session.scalar(
            select(m.PurchaseOrder).where(m.PurchaseOrder.number == "AMEND-PO-R1")
        )
        replacement = session.scalar(
            select(m.POLine).where(m.POLine.po_id == successor.id)
        )
        assert replacement.quantity == "20" and replacement.rate == "750"
        assert procurement.authorization(session, session.get(m.BOQItem, boq)) == (
            100,
            7100000,
        )
        assert procurement.commitments(
            session, session.get(m.Project, project), session.get(m.BOQItem, boq)
        ) == (100, 7100000)
        assert (
            session.scalar(
                select(cm.ProcurementAmendment).where(
                    cm.ProcurementAmendment.control_id == approved["id"]
                )
            ).retired_quantity
            == "20"
        )
    # Accepted delivery still uses the original 700 rate; no records or cash were rewritten.
    response = client.post(
        "/api/v1/controls",
        headers=h["operator"],
        json={
            "project_id": project,
            "name": "Cannot retire received goods",
            "payload": {
                **payload,
                "expected_po_version": pv + 1,
                "retire_quantity": "1",
                "replacement_quantity": "0",
                "successor_po_number": "",
            },
        },
    )
    assert response.status_code == 422 and "protected historical rates" in response.text
    assert (
        client.get(
            f"/api/v1/accounting/summary?project_id={project}", headers=h["auditor"]
        ).json()["recorded_cash"]
        == "1000000.00"
    )


def test_stale_procurement_approval_and_self_check_are_denied(env):
    _, client, h = env
    project, boq, bv, *_ = sources(env)
    data = {
        "kind": "PROCUREMENT_AUTHORIZATION",
        "boq_item_id": boq,
        "expected_boq_version": bv,
        "additional_quantity": "5",
        "reason": "Additional supported future scope",
    }
    waiting = control(env, project, data, finish=False)
    row = client.post(
        f"/api/v1/controls/{waiting['id']}/submit",
        headers=h["operator"],
        json={"expected_version": waiting["version"]},
    ).json()
    denied = client.post(
        f"/api/v1/controls/{row['id']}/check",
        headers=h["operator"],
        json={"expected_version": row["version"]},
    )
    assert denied.status_code == 403
    checked = client.post(
        f"/api/v1/controls/{row['id']}/check",
        headers=h["manager"],
        json={"expected_version": row["version"]},
    ).json()
    control(env, project, {**data, "additional_quantity": "10"})
    denied = client.post(
        f"/api/v1/controls/{row['id']}/approve",
        headers=h["admin"],
        json={"expected_version": checked["version"]},
    )
    assert denied.status_code == 409
