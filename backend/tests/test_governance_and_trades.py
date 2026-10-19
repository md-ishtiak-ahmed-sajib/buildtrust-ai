import json
from pathlib import Path

import pymupdf
import pytest
from app import models as m
from app.advanced_math import calculate_takeoff
from app.advanced_schemas import TakeoffInput
from app.database import transaction
from conftest import prepared, valid_invoice
from sqlalchemy import select
from test_accounting_controls import control


@pytest.mark.parametrize(
    "kind,dimensions,quantity",
    [
        (
            "EARTHWORK",
            {
                "top_length": "4",
                "top_width": "3",
                "bottom_length": "4",
                "bottom_width": "3",
                "depth": "2",
            },
            "24.000000",
        ),
        (
            "BACKFILL",
            {"excavated_volume": "20", "excluded_volume": "5", "volume_factor": "1"},
            "15.000000",
        ),
        (
            "DISPOSAL",
            {"excavated_volume": "20", "excluded_volume": "5", "volume_factor": "1.2"},
            "18.000000",
        ),
        (
            "MASONRY",
            {"length": "10", "height": "3", "thickness": "0.2", "opening_area": "6"},
            "4.800000",
        ),
        (
            "FINISHES",
            {"length": "10", "height": "3", "opening_area": "6", "faces": "2"},
            "48.000000",
        ),
        ("DOORS_WINDOWS", {"length": "1.2", "height": "1.5", "count": "4"}, "7.200000"),
        ("ROOFING", {"length": "10", "width": "8", "slope_factor": "1.1"}, "88.000000"),
        ("PAVEMENT", {"length": "10", "width": "8", "height": "0.15"}, "12.000000"),
        ("TRIANGULAR_PRISM", {"length": "4", "width": "3", "height": "2"}, "12.000000"),
        (
            "FRUSTUM",
            {
                "top_length": "2",
                "top_width": "2",
                "bottom_length": "4",
                "bottom_width": "4",
                "height": "1.5",
            },
            "14.000000",
        ),
    ],
)
def test_trade_independent_examples(kind, dimensions, quantity):
    data = TakeoffInput(
        project_id=1,
        profile_id=1,
        name="Sourced geometry",
        calculation=kind,
        dimensions=dimensions,
    )
    assert calculate_takeoff(data)["quantity"] == quantity


def test_supplied_rebar_schedule():
    data = TakeoffInput(
        project_id=1,
        profile_id=1,
        name="Supplied schedule",
        calculation="REBAR_SCHEDULE",
        nominal_mass_source="Supplied fictional nominal mass table",
        reinforcement_schedule=[
            {"length": "12", "count": "10", "unit_mass_kg_m": "1.58"},
            {"length": "6", "count": "4", "unit_mass_kg_m": "1"},
        ],
    )
    assert calculate_takeoff(data)["quantity"] == "213.600000"


def test_supplier_change_invalidates_pending_approval(env):
    app, client, h = env
    proposal = prepared(env)
    with transaction(app.state.engine) as session:
        supplier = session.get(
            m.Supplier, session.get(m.Proposal, proposal["id"]).supplier_id
        )
        identity, version, code, name = (
            supplier.id,
            supplier.version,
            supplier.code,
            supplier.name,
        )
    record = control(
        env,
        proposal["project_id"],
        {
            "kind": "SUPPLIER_CHANGE",
            "supplier_id": identity,
            "expected_supplier_version": version,
            "code": code,
            "name": name,
            "beneficiary_token": "NEW-FICTIONAL-BENEFICIARY",
            "verification_reference": "Independent offline verification record SIM-001",
            "verification_attested": True,
        },
    )
    assert record["status"] == "APPROVED"
    with transaction(app.state.engine) as session:
        row = session.get(m.Proposal, proposal["id"])
        assert row.status == "BLOCKED"
        reservation = session.scalar(
            select(m.Reservation).where(m.Reservation.proposal_id == row.id)
        )
        assert reservation.state == "RELEASED"
    assert client.get("/api/v1/audit/verify", headers=h["auditor"]).json()["valid"]


def test_rule_profile_has_independent_edition_review_and_restricted_templates(env):
    app, client, h = env
    project_id = valid_invoice(client, h["operator"])["project_id"]
    control(
        env,
        project_id,
        {
            "kind": "RULE_PROFILE",
            "code": "PROJECT_2026_01",
            "name": "Explicit project geometry rule",
            "edition": "Project specification revision 1",
            "source_url": "https://example.com/project-rules",
            "rule_reference": "Project instruction 4: all openings explicitly supplied",
            "reviewer_evidence": "Fictional reviewer SIM-001; external professional acceptance pending",
            "templates": ["MASONRY"],
        },
    )
    profiles = client.get("/api/v1/measurement/profiles", headers=h["operator"]).json()
    profile = next(r for r in profiles if r["code"].startswith("PROJECT_2026_01"))
    assert profile["verification_status"] == "REVIEWED_PROJECT_RULES"
    data = {
        "project_id": project_id,
        "profile_id": profile["id"],
        "name": "Reviewed masonry",
        "calculation": "MASONRY",
        "dimensions": {
            "length": "10",
            "height": "3",
            "thickness": "0.2",
            "opening_area": "6",
        },
    }
    response = client.post(
        "/api/v1/takeoff/calculate", headers=h["operator"], json=data
    )
    assert response.status_code == 200, response.text
    assert response.json()["quantity"] == "4.800000"
    assert (
        response.json()["profile_snapshot"]["rules"]["professional_acceptance"]
        == "REQUIRES_EXTERNAL_ACCEPTANCE"
    )
    data["calculation"] = "COUNT"
    data["dimensions"] = {"count": "2"}
    assert (
        client.post(
            "/api/v1/takeoff/calculate", headers=h["operator"], json=data
        ).status_code
        == 422
    )


def scanned_pdf():
    native = pymupdf.open()
    page = native.new_page()
    page.insert_text((55, 90), "Invoice Number: INV-SCANNED-001", fontsize=22)
    page.insert_text((55, 130), "Currency: BDT", fontsize=22)
    image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    scanned = pymupdf.open()
    page = scanned.new_page()
    page.insert_image(page.rect, stream=image)
    assert not page.get_text().strip()
    data = scanned.tobytes()
    native.close()
    scanned.close()
    return data


def test_missing_ocr_models_preserves_manual_review(env, tmp_path):
    app, client, h = env
    app.state.settings.ocr_enabled = True
    app.state.settings.ocr_tessdata_dir = tmp_path / "missing-models"
    project_id = valid_invoice(client, h["operator"])["project_id"]
    response = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": project_id},
        files={"file": ("scanned.pdf", scanned_pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["extraction_status"] == "NEEDS_REVIEW"


def test_real_scanned_ocr_through_upload_and_persisted_evidence(env):
    models = Path(__file__).resolve().parents[2] / "data" / "ocr-models"
    if (
        not (models / "eng.traineddata").exists()
        or not (models / "ben.traineddata").exists()
    ):
        pytest.skip("Optional pinned OCR models are not installed; no runtime download")
    app, client, h = env
    app.state.settings.ocr_enabled = True
    app.state.settings.ocr_tessdata_dir = models
    project_id = valid_invoice(client, h["operator"])["project_id"]
    response = client.post(
        "/api/v1/documents/upload",
        headers=h["operator"],
        data={"project_id": project_id},
        files={"file": ("scanned.pdf", scanned_pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["extraction_status"] == "NEEDS_REVIEW"
    with transaction(app.state.engine) as session:
        document = session.get(m.Document, response.json()["id"])
        assert "INV-SCANNED-001" in document.text
        event = session.scalar(
            select(m.AuditEvent).where(
                m.AuditEvent.entity_id == str(document.id),
                m.AuditEvent.event_type == "DOCUMENT_EXTRACTED",
            )
        )
        details = json.loads(event.details_json)
        assert details["ocr"]["status"] == "COMPLETED"
        assert details["page_evidence"][0]["confidence"] is None


def test_reviewed_opening_rules_use_recorded_threshold_without_double_deduction(env):
    _, client, h = env
    project_id = valid_invoice(client, h["operator"])["project_id"]
    control(env, project_id, {"kind": "RULE_PROFILE", "code": "FICTIONAL_OPENINGS_2026", "name": "Fictional project opening rule", "edition": "Fictional revision 1",
        "source_url": "https://example.com/fictional-project-rules", "rule_reference": "Fictional clause 4.1: deduct individual openings strictly above 0.5 m2; not an NRM compliance claim",
        "reviewer_evidence": "Independent fictional review; professional standard acceptance remains pending", "templates": ["MASONRY"],
        "opening_rules": [{"calculation": "MASONRY", "threshold_m2": "0.5", "comparison": "GT"}]})
    profiles = client.get(f"/api/v1/measurement/profiles?project_id={project_id}", headers=h["operator"]).json()
    profile = next(row for row in profiles if row["code"].startswith("FICTIONAL_OPENINGS_2026"))
    payload = {"project_id": project_id, "profile_id": profile["id"], "name": "Sourced masonry opening schedule", "calculation": "MASONRY",
        "dimensions": {"length": "10", "height": "3", "thickness": "0.2", "opening_area": "0"}, "drawing_reference": "D-OPEN-01",
        "openings": [{"width": "0.5", "height": "0.5", "count": "1", "reference": "Small opening retained"}, {"width": "1", "height": "1", "count": "1", "reference": "Large opening deducted"}]}
    response = client.post("/api/v1/takeoff/calculate", headers=h["operator"], json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["quantity"] == "5.800000"
    assert [row["deducted"] for row in response.json()["profile_applied_rules"]] == [False, True]
    saved = client.post("/api/v1/takeoff/sheets", headers=h["operator"], json=payload)
    assert saved.status_code == 201, saved.text
    assert saved.json()["result"]["profile_snapshot"]["source_url"] == profile["source_url"]
    duplicate = client.post("/api/v1/takeoff/calculate", headers=h["operator"], json={**payload, "deduction": "0.2", "deduction_reason": "Already supplied"})
    assert duplicate.status_code == 422 and "not both" in duplicate.text
    other = client.get("/api/v1/projects", headers=h["operator"]).json()[1]["id"]
    other_profiles = client.get(f"/api/v1/measurement/profiles?project_id={other}", headers=h["operator"]).json()
    assert profile["id"] not in [row["id"] for row in other_profiles]


def test_compaction_uses_supplied_factor_only():
    data = TakeoffInput(project_id=1, profile_id=1, name="Explicit compaction input", calculation="COMPACTION",
        dimensions={"loose_volume": "20", "compaction_factor": "0.9"}, assumptions="Fictional supplied conversion; field density acceptance is separate")
    assert calculate_takeoff(data)["quantity"] == "18.000000"
