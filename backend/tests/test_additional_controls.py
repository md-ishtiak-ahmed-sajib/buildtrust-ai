from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import io
from sqlalchemy import select, func
from app.database import transaction
from app.models import (
    Invoice,
    InvoiceLine,
    Project,
    Payment,
    BOQItem,
    POLine,
    Reservation,
)
from app.money import minor
from conftest import prepared, approved, valid_invoice


def test_real_pdf_extraction_and_raster_preview(env):
    _, client, h = env
    path = Path(__file__).resolve().parents[2] / "demo/fixtures/scenario-a-inflated.pdf"
    result = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": 1},
        files={"file": ("arbitrary-name.pdf", path.read_bytes(), "application/pdf")},
    )
    assert result.status_code == 201, result.text
    assert result.json()["extraction_status"] == "NEEDS_REVIEW"
    identity = result.json()["id"]
    extracted = client.get(
        f"/api/v1/documents/{identity}/extraction", headers=h["operator"]
    ).json()
    assert extracted["data"]["invoice_number"] == "INV-STEEL-095"
    assert extracted["data"]["items"][0]["quantity"] == "95"
    image = client.get(f"/api/v1/documents/{identity}/preview", headers=h["auditor"])
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    assert client.get(f"/api/v1/documents/{identity}/preview").status_code == 401


def test_scanned_pdf_manual_entry_is_honest(env):
    _, client, h = env
    from reportlab.pdfgen import canvas

    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.showPage()
    pdf.save()
    r = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": 1},
        files={"file": ("scan.pdf", stream.getvalue(), "application/pdf")},
    )
    assert r.status_code == 201 and r.json()["extraction_status"] == "NEEDS_REVIEW"
    from app.seed import demo_payloads

    data = demo_payloads()["scenario-b-valid"]
    data["invoice_number"] = "MANUALLY-REVIEWED"
    corrected = client.patch(
        f"/api/v1/documents/{r.json()['id']}/extraction",
        headers=h["operator"],
        json={"version": 1, "data": data},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["reviewed_by"] is not None


def test_concurrent_different_keys_cannot_double_pay(env):
    p = approved(env)
    app, client, h = env

    def execute(index):
        return client.post(
            f"/api/v1/payments/{p['id']}/execute",
            headers={**h["manager"], "Idempotency-Key": f"different-{index}"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(execute, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    with transaction(app.state.engine) as s:
        assert s.scalar(select(func.count()).select_from(Payment)) == 1


def test_idempotency_key_conflicts_across_proposals(env):
    p = approved(env)
    _, client, h = env
    key = {**h["manager"], "Idempotency-Key": "global-idempotency-key"}
    assert (
        client.post(f"/api/v1/payments/{p['id']}/execute", headers=key).status_code
        == 200
    )
    # A blocked proposal is still a different request and must not receive another proposal's receipt.
    steel = next(
        i
        for i in client.get("/api/v1/invoices", headers=h["operator"]).json()
        if i["invoice_number"] == "INV-STEEL-095"
    )
    p2 = client.post(
        "/api/v1/payments/proposals",
        headers=h["operator"],
        json={"invoice_id": steel["id"]},
    ).json()
    result = client.post(
        f"/api/v1/payments/{p2['id']}/execute",
        headers={**h["admin"], "Idempotency-Key": "global-idempotency-key"},
    )
    # Amount authorization may deny the oversized steel claim before revealing any receipt.
    assert result.status_code in (403, 409)
    assert "mock_transaction_id" not in result.json()


def test_rejection_releases_cash_reservation(env):
    p = prepared(env)
    _, client, h = env
    assert (
        client.post(
            f"/api/v1/payments/{p['id']}/reject", headers=h["manager"]
        ).status_code
        == 200
    )
    forecast = client.get("/api/v1/cashflow/forecast", headers=h["operator"]).json()
    assert forecast["reserved"] == "0.00" and forecast["available_cash"] == "1000000.00"


def test_admin_ceiling_is_enforced(env):
    app, client, h = env
    with transaction(app.state.engine, True) as s:
        inv = s.get(Invoice, 2)
        inv.subtotal_minor = inv.total_minor = minor("1100000")
        line = s.scalar(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id))
        line.rate = "11000"
        line.amount_minor = minor("1100000")
        s.scalar(select(POLine).where(POLine.po_id == inv.po_id)).rate = "11000"
        s.scalar(
            select(BOQItem).where(
                BOQItem.project_id == inv.project_id, BOQItem.item_code == "CEMENT-50KG"
            )
        ).rate = "11000"
        s.get(Project, 1).balance_minor = minor("2000000")
    p = client.post(
        "/api/v1/payments/proposals", headers=h["operator"], json={"invoice_id": 2}
    ).json()
    assert p["status"] == "BLOCKED"
    result = client.post(f"/api/v1/payments/{p['id']}/approve", headers=h["admin"])
    assert (
        result.status_code == 403
        and result.json()["error"]["code"] == "PAYMENT_LIMIT_EXCEEDED"
    )


def test_new_upload_cannot_supply_authoritative_role(env):
    _, client, h = env
    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": "operator@buildtrust.demo",
            "password": "Test-Demo-Password!2026",
            "role": "ADMIN",
        },
    )
    assert r.status_code == 200 and r.json()["user"]["role"] == "OPERATOR"


def test_optional_llm_failure_falls_back(env, monkeypatch):
    app, client, h = env
    app.state.settings.llm_provider = "ollama"
    app.state.settings.ollama_model = "test"
    import httpx

    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("app.workflow.httpx.post", fail)
    r = client.post(
        "/api/v1/agent/ask",
        headers=h["operator"],
        json={
            "project_id": 1,
            "invoice_id": 1,
            "question": "Why was this invoice blocked?",
        },
    )
    assert r.status_code == 200 and r.json()["explanation_source"] == "deterministic"


def test_revoked_approver_cannot_authorize_execution(env):
    from app.models import User

    p = approved(env)
    app, client, h = env
    with transaction(app.state.engine, True) as session:
        session.scalar(
            select(User).where(User.role == "FINANCE_MANAGER")
        ).role = "OPERATOR"
    response = client.post(
        f"/api/v1/payments/{p['id']}/execute",
        headers={**h["admin"], "Idempotency-Key": "revoked-checker"},
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "APPROVAL_INVALID"
    )


def test_archived_run_is_read_only(env):
    _, client, h = env
    invoice = valid_invoice(client, h["operator"])
    assert client.post("/api/v1/demo/reset", headers=h["admin"]).status_code == 200
    assert (
        client.get(
            f"/api/v1/invoices/{invoice['id']}", headers=h["auditor"]
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/payments/proposals",
            headers=h["operator"],
            json={"invoice_id": invoice["id"]},
        ).status_code
        == 409
    )


def test_invalid_extraction_confirmation_is_structured(env):
    _, client, h = env
    r = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": 1},
        files={
            "file": (
                "incomplete.json",
                b'{"document_type":"BOQ","items":[]}',
                "application/json",
            )
        },
    )
    assert r.status_code == 201 and r.json()["extraction_status"] == "NEEDS_REVIEW"
    response = client.post(
        f"/api/v1/documents/{r.json()['id']}/confirm", headers=h["admin"]
    )
    assert (
        response.status_code == 422
        and response.json()["error"]["code"] == "DOCUMENT_REVIEW_REQUIRED"
    )


def test_overlapping_preparation_reuses_one_proposal(env):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])

    def prepare(_):
        return client.post(
            "/api/v1/payments/proposals",
            headers=h["operator"],
            json={"invoice_id": invoice["id"]},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(prepare, range(2)))
    assert all(r.status_code == 201 for r in responses)
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with transaction(app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(Reservation)) == 1


def test_overlapping_invoices_compete_for_delivery_once(env):
    _, client, h = env
    from app.seed import demo_payloads
    from app.money import canonical

    original = valid_invoice(client, h["operator"])
    data = demo_payloads()["scenario-b-valid"]
    data["invoice_number"] = "COMPETING-CLAIM"
    assert (
        client.post(
            "/api/v1/documents/upload",
            headers=h["operator"],
            data={"project_id": 1},
            files={
                "file": ("competing.json", canonical(data).encode(), "application/json")
            },
        ).status_code
        == 201
    )
    second = next(
        i
        for i in client.get("/api/v1/invoices", headers=h["operator"]).json()
        if i["invoice_number"] == "COMPETING-CLAIM"
    )

    def prepare(identity):
        return client.post(
            "/api/v1/payments/proposals",
            headers=h["operator"],
            json={"invoice_id": identity},
        ).json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(prepare, [original["id"], second["id"]]))
    assert sorted(r["status"] for r in responses) == ["BLOCKED", "PENDING_APPROVAL"]


def test_financial_tool_independently_checks_project_access(env):
    import pytest
    from app.models import User, Membership
    from app.payments import create_proposal
    from app.security import DomainError

    app, _, _ = env
    with transaction(app.state.engine, True) as session:
        actor = session.scalar(select(User).where(User.role == "OPERATOR"))
        session.delete(session.get(Membership, (actor.id, 1)))
        session.flush()
        with pytest.raises(DomainError) as failure:
            create_proposal(session, session.get(Invoice, 2), app.state.settings, actor)
        assert failure.value.status == 404
        assert session.scalar(select(func.count()).select_from(Reservation)) == 0
