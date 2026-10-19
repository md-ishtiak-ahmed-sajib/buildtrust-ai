import pytest
from sqlalchemy import select, func
from app.models import AuditEvent, Invoice, InvoiceLine, Proposal, BOQItem, POLine
from app.database import transaction
from app.seed import demo_payloads
from app.money import canonical, minor
from conftest import valid_invoice, prepared


def upload(client, headers, data, name="invoice.json", project_id=1):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={"project_id": project_id},
        files={"file": (name, canonical(data).encode(), "application/json")},
    )


def test_duplicate_identity_and_hash(env):
    app, client, h = env
    data = demo_payloads()["scenario-b-valid"]
    response = upload(client, h["operator"], data)
    assert response.status_code == 201
    assert response.json()["extraction_status"] == "DUPLICATE"
    data["notes"] = "A different file with the same business identity"
    second = upload(client, h["operator"], data)
    assert second.json()["extraction_status"] == "DUPLICATE"
    with transaction(app.state.engine) as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(Invoice)
                .where(Invoice.number == "INV-CEMENT-070")
            )
            == 1
        )


def test_content_not_filename_controls_extraction(env):
    _, client, h = env
    data = demo_payloads()["scenario-b-valid"]
    data["invoice_number"] = "ACTUAL-CONTENT-123"
    response = upload(client, h["operator"], data, "scenario-a-inflated.json")
    assert response.status_code == 201
    detail = client.get(
        f"/api/v1/documents/{response.json()['id']}/extraction", headers=h["operator"]
    ).json()
    assert detail["data"]["invoice_number"] == "ACTUAL-CONTENT-123"
    assert (
        detail["revisions"][0]["fields"][0]["source_document_id"]
        == response.json()["id"]
    )
    assert all(f["confidence"] is None for f in detail["revisions"][0]["fields"])


def test_csv_real_content(env):
    _, client, h = env
    data = demo_payloads()["scenario-b-valid"]
    import csv, io

    stream = io.StringIO()
    row = {k: v for k, v in data.items() if k != "items"}
    row.update(data["items"][0])
    row["invoice_number"] = "CSV-REAL-CONTENT"
    writer = csv.DictWriter(stream, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    response = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": 1},
        files={"file": ("source.csv", stream.getvalue().encode(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    assert any(
        i["invoice_number"] == "CSV-REAL-CONTENT"
        for i in client.get("/api/v1/invoices", headers=h["operator"]).json()
    )


def test_procurement_confirmation_permissions(env):
    _, client, h = env
    data = {
        "document_type": "BOQ",
        "items": [
            {
                "item_code": "NEW-ITEM",
                "description": "Certified structural component",
                "quantity": "10",
                "unit": "each",
                "unit_rate": "1000",
            }
        ],
    }
    result = upload(client, h["operator"], data)
    identity = result.json()["id"]
    assert result.json()["extraction_status"] == "EXTRACTED"
    assert (
        client.post(
            f"/api/v1/documents/{identity}/confirm", headers=h["operator"]
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/documents/{identity}/confirm", headers=h["manager"]
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/documents/{identity}/confirm", headers=h["admin"]
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/documents/{identity}/extraction",
            headers=h["admin"],
            json={"version": 1, "data": data},
        ).status_code
        == 409
    )


def test_correction_revisions_and_stale_version(env):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])
    doc_id = invoice["document_id"]
    payload = client.get(
        f"/api/v1/documents/{doc_id}/extraction", headers=h["operator"]
    ).json()
    data = payload["data"]
    data["notes"] = "Reviewed original supplier evidence"
    response = client.patch(
        f"/api/v1/documents/{doc_id}/extraction",
        headers=h["operator"],
        json={"version": 1, "data": data},
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert (
        client.patch(
            f"/api/v1/documents/{doc_id}/extraction",
            headers=h["operator"],
            json={"version": 1, "data": data},
        ).status_code
        == 409
    )
    updated = client.get(
        f"/api/v1/documents/{doc_id}/extraction", headers=h["auditor"]
    ).json()
    assert len(updated["revisions"]) == 2
    assert all(f["human_reviewed"] for f in updated["revisions"][-1]["fields"])


@pytest.mark.parametrize(
    "name,content,status",
    [
        ("evil.exe", b"code", 415),
        ("fake.pdf", b"not a pdf", 415),
        ("empty.json", b"", 413),
        ("bad.json", b"{bad json", 422),
    ],
)
def test_upload_validation(env, name, content, status):
    _, client, h = env
    response = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": 1},
        files={"file": (name, content)},
    )
    assert response.status_code == status, response.text
    assert "traceback" not in response.text.lower()


def test_prompt_injection_cannot_grant_approval(env):
    _, client, h = env
    invoice = next(
        i
        for i in client.get("/api/v1/invoices", headers=h["operator"]).json()
        if i["invoice_number"] == "INV-INJECTION"
    )
    result = client.post(
        f"/api/v1/invoices/{invoice['id']}/analyze", headers=h["operator"]
    ).json()
    assert "SUSPICIOUS_INSTRUCTIONS" in {f["code"] for f in result["findings"]}
    proposal = client.post(
        "/api/v1/payments/proposals",
        json={"invoice_id": invoice["id"]},
        headers=h["operator"],
    ).json()
    assert proposal["status"] == "BLOCKED"


def test_agent_workflow_calls_tools_and_waits_for_human(env):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])
    response = client.post(
        "/api/v1/agent/analyze",
        json={"invoice_id": invoice["id"]},
        headers=h["operator"],
    )
    assert response.status_code == 202
    identity = response.json()["workflow_id"]
    run = client.get(
        f"/api/v1/agent/workflows/{identity}", headers=h["operator"]
    ).json()
    assert run["status"] == "AWAITING_APPROVAL", run
    assert len(run["steps"]) == 9
    assert all(s["status"] == "COMPLETED" for s in run["steps"])
    with transaction(app.state.engine) as s:
        assert (
            s.get(Proposal, run["result"]["proposal_id"]).status == "PENDING_APPROVAL"
        )
    again = client.post(
        "/api/v1/agent/analyze",
        json={"invoice_id": invoice["id"]},
        headers=h["operator"],
    ).json()
    assert (
        client.get(
            f"/api/v1/agent/workflows/{again['workflow_id']}", headers=h["operator"]
        ).json()["result"]["proposal_id"]
        == run["result"]["proposal_id"]
    )


@pytest.mark.parametrize(
    "question",
    [
        "Why was this invoice blocked?",
        "How much does the claim exceed verified delivery?",
        "Can we safely pay this invoice today?",
        "What happens if receivables are delayed by 15 days?",
        "Which invoices are awaiting approval?",
    ],
)
def test_grounded_copilot_queries_without_llm(env, question):
    _, client, h = env
    response = client.post(
        "/api/v1/agent/ask",
        headers=h["operator"],
        json={"project_id": 1, "invoice_id": 1, "question": question},
    )
    assert response.status_code == 200, response.text
    assert response.json()["explanation_source"] == "deterministic"
    assert response.json()["answer"]


def test_audit_chain_and_tampered_record_detection(env):
    app, client, h = env
    assert client.get("/api/v1/audit/verify", headers=h["auditor"]).json()["valid"]
    with transaction(app.state.engine, True) as s:
        event = s.scalar(select(AuditEvent).order_by(AuditEvent.id))
        identity = event.id
        event.details_json = '{"tampered":true}'
    result = client.get("/api/v1/audit/verify", headers=h["auditor"]).json()
    assert not result["valid"]
    assert result["failed_event_id"] == identity


def test_reset_preserves_chain_and_requires_admin_demo_mode(env):
    app, client, h = env
    before = client.get("/api/v1/audit/verify", headers=h["auditor"]).json()[
        "checked_events"
    ]
    assert client.post("/api/v1/demo/reset", headers=h["operator"]).status_code == 403
    response = client.post("/api/v1/demo/reset", headers=h["admin"])
    assert response.status_code == 200
    check = client.get("/api/v1/audit/verify", headers=h["auditor"]).json()
    assert check["valid"] and check["checked_events"] > before
    assert len(client.get("/api/v1/projects", headers=h["operator"]).json()) == 2
    app.state.settings.demo_mode = False
    assert client.post("/api/v1/demo/reset", headers=h["admin"]).status_code == 404


def test_competing_invoice_cannot_reuse_reserved_receipts(env):
    prepared(env)
    _, client, h = env
    data = demo_payloads()["scenario-b-valid"]
    data["invoice_number"] = "SECOND-CLAIM"
    assert upload(client, h["operator"], data).status_code == 201
    inv = next(
        i
        for i in client.get("/api/v1/invoices", headers=h["operator"]).json()
        if i["invoice_number"] == "SECOND-CLAIM"
    )
    report = client.post(
        f"/api/v1/invoices/{inv['id']}/analyze", headers=h["operator"]
    ).json()
    assert "RECEIPT_REUSE" in {f["code"] for f in report["findings"]}


def test_approval_threshold_and_admin_ceiling(env):
    app, client, h = env
    with transaction(app.state.engine, True) as s:
        inv = s.get(Invoice, 2)
        line = s.scalar(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id))
        line.rate = "1100"
        line.amount_minor = minor("110000")
        s.scalar(select(POLine).where(POLine.po_id == inv.po_id)).rate = "1100"
        s.scalar(
            select(BOQItem).where(
                BOQItem.project_id == inv.project_id, BOQItem.item_code == "CEMENT-50KG"
            )
        ).rate = "1100"
        inv.subtotal_minor = inv.total_minor = minor("110000")
    p = client.post(
        "/api/v1/payments/proposals", headers=h["operator"], json={"invoice_id": 2}
    ).json()
    assert p["status"] == "PENDING_APPROVAL"
    denied = client.post(f"/api/v1/payments/{p['id']}/approve", headers=h["manager"])
    assert (
        denied.status_code == 403
        and denied.json()["error"]["code"] == "PAYMENT_LIMIT_EXCEEDED"
    )
    assert (
        client.post(
            f"/api/v1/payments/{p['id']}/approve", headers=h["admin"]
        ).status_code
        == 200
    )
