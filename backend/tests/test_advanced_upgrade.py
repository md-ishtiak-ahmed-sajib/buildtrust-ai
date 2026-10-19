"""Offline provider protocol fixtures and actual API/persistence regression checks."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
import sqlite3
import pytest
from sqlalchemy import select
from app import advanced_models as a, models as m, audit, pricing
from app.database import transaction
from app.advanced_math import unit_factor, calculate_takeoff
from app.advanced_schemas import TakeoffInput
from app.price_providers import SerpApiProvider, DataForSEOProvider, safe_url
from app.money import digest, decimal


def demo(env):
    _, client, h = env
    response = client.post("/api/v1/advanced/demo-project", headers=h["admin"])
    assert response.status_code == 201, response.text
    return response.json()


def estimate(client, h, identity):
    return client.get(f"/api/v1/estimates/{identity}", headers=h["operator"]).json()


def search(env, data, mode="DEMO"):
    _, client, h = env
    result = client.post(
        f"/api/v1/materials/{data['material_id']}/prices/refresh",
        json={"mode": mode, "quantity": "20"},
        headers=h["operator"],
    )
    assert result.status_code == 202, result.text
    return result.json()


def selection(env, data):
    _, client, h = env
    task = search(env, data)
    offers = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?search_id={task['id']}",
        headers=h["operator"],
    ).json()
    current = estimate(client, h, data["estimate_id"])
    response = client.post(
        f"/api/v1/materials/{data['material_id']}/prices/select",
        json={
            "estimate_id": current["id"],
            "expected_version": current["version"],
            "line_id": "steel-line",
            "component_id": "steel-material",
            "observation_id": offers["recommended_observation_id"],
            "search_id": task["id"],
        },
        headers=h["operator"],
    )
    assert response.status_code == 200, response.text
    return response.json(), task, offers


def quote(data, **changes):
    return {
        "material_id": data["material_id"],
        "supplier": "Test fictional supplier",
        "title": "16 mm B500B steel",
        "price": "75",
        "currency": "BDT",
        "unit": "kg",
        "quoted_quantity": "20000",
        "minimum_quantity": "1000",
        "specification": {"grade": "B500B", "diameter_mm": "16", "standard": "BS 4449"},
        "can_deliver": True,
        "delivery_days": 3,
        "freight_basis": "INCLUDED",
        "tax_basis": "INCLUDED",
        "tax": "0",
        "handling": "0",
        "other_cost": "0",
        "quotation_date": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=7)).isoformat(),
        **changes,
    }


def verified_quote(env, data, **changes):
    _, client, h = env
    response = client.post(
        "/api/v1/quotations", json=quote(data, **changes), headers=h["operator"]
    )
    assert response.status_code == 201, response.text
    record = response.json()
    verified = client.post(
        f"/api/v1/quotations/{record['id']}/verify",
        json={"expected_version": record["version"]},
        headers=h["manager"],
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


def test_provider_protocol_fixtures():
    request = {"country": "US", "city": "New York"}
    # Synthetic protocol fixtures based on official response fields, not live offers.
    serp = {
        "shopping_results": [
            {
                "title": "B500B 16 mm steel per kg",
                "source": "Fixture Merchant",
                "extracted_price": "2.25",
                "price": "$2.25",
                "product_link": "https://www.google.com/shopping/product/123",
                "product_id": "123",
            }
        ]
    }
    result = SerpApiProvider.parse(serp, request)[0]
    assert result["source_url"] == serp["shopping_results"][0]["product_link"]
    assert result["currency"] == "USD" and result["unit"] == "kg"
    assert result["specification"]["grade"] == "B500B"
    assert result["freight_basis"] == "UNKNOWN"
    dfs = {
        "tasks": [
            {
                "status_code": 20000,
                "result": [
                    {
                        "items": [
                            {
                                "title": "Steel B500B",
                                "seller": "Fixture Merchant B",
                                "price": {"current": "80.125", "currency": "BDT"},
                                "url": "https://example.org/steel",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    parsed = DataForSEOProvider.parse(dfs, request)[0]
    assert (
        parsed["price"] == "80.125"
        and parsed["source_url"] == "https://example.org/steel"
    )
    assert parsed["unit"] is None


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/x",
        "https://127.0.0.1/x",
        "https://localhost/x",
        "https://user:pass@example.com/x",
        "javascript:alert(1)",
        "https://169.254.169.254/metadata",
    ],
)
def test_source_url_rejects_unsafe(url):
    with pytest.raises(ValueError):
        safe_url(url)


def test_dimension_conversions():
    assert unit_factor("kg", "tonne") == Decimal(".001")
    assert unit_factor("bag", "kg", "50") == 50
    assert unit_factor("thousand", "each") == 1000
    assert unit_factor("ft3", "m3") == Decimal(".028316846592")
    with pytest.raises(ValueError):
        unit_factor("bag", "kg")
    with pytest.raises(ValueError):
        unit_factor("m3", "tonne", density="1600")
    assert unit_factor(
        "m3",
        "tonne",
        density="1600",
        assumption="Dry loose bulk density from project test",
    ) == Decimal("1.6")


@pytest.mark.parametrize(
    "kind,dimensions,quantity,unit",
    [
        (
            "RECTANGULAR_VOLUME",
            {"length": "0.4", "width": "0.4", "height": "3", "count": "20"},
            "9.600000",
            "m3",
        ),
        (
            "REBAR",
            {"diameter_mm": "16", "length": "12", "count": "10"},
            "189.629630",
            "kg",
        ),
        (
            "FORMWORK_COLUMN",
            {"length": "0.4", "width": "0.4", "height": "3", "count": "20"},
            "96.000000",
            "m2",
        ),
        (
            "FORMWORK_BEAM",
            {"length": "5", "width": "0.3", "height": "0.6"},
            "7.500000",
            "m2",
        ),
        ("AREA", {"length": "5", "width": "4"}, "20.000000", "m2"),
    ],
)
def test_core_takeoff_math(kind, dimensions, quantity, unit):
    data = TakeoffInput(
        project_id=1,
        profile_id=1,
        name="Test geometry",
        calculation=kind,
        dimensions=dimensions,
    )
    result = calculate_takeoff(data)
    assert (result["quantity"], result["unit"]) == (quantity, unit)
    assert result["warnings"]


def test_no_provider_is_not_demo(env):
    _, client, h = env
    data = demo(env)
    task = search(env, data, "LIVE")
    status = client.get(
        f"/api/v1/prices/searches/{task['id']}", headers=h["operator"]
    ).json()
    assert status["status"] == "NO_PROVIDERS"
    prices = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?search_id={task['id']}",
        headers=h["operator"],
    ).json()
    assert prices["offers"] == [] and prices["recommended_observation_id"] is None
    assert "No currently verifiable" in prices["notice"]


def test_flagship_price_estimate_forecast_snapshot(env):
    app, client, h = env
    data = demo(env)
    before = client.get(
        f"/api/v1/estimates/{data['estimate_id']}/forecast", headers=h["operator"]
    ).json()
    assert before["scenarios"][0]["lowest_balance"] == "600000.00"
    updated, task, offers = selection(env, data)
    assert updated["total"] == "1480000.00"
    incompatible = [r for r in offers["offers"] if r["compatibility"] == "Incompatible"]
    assert len(incompatible) == 1 and not incompatible[0]["eligible"]
    after = client.get(
        f"/api/v1/estimates/{updated['id']}/forecast", headers=h["operator"]
    ).json()
    assert after["scenarios"][0]["lowest_balance"] == "520000.00"
    assert after["recorded_cash"] == "2000000.00"
    control = client.get(
        f"/api/v1/finance/cost-control?project_id={data['project_id']}",
        headers=h["operator"],
    ).json()
    assert control["budget_overrun"] and control["forecast_vs_budget"] == "30000.00"
    cached = search(env, data)
    assert cached["cached"] and cached["id"] == task["id"]
    with transaction(app.state.engine) as session:
        chosen = session.scalar(
            select(a.PriceSelection).where(
                a.PriceSelection.estimate_id == updated["id"]
            )
        )
        snapshot = json.loads(chosen.snapshot_json)
        assert chosen.snapshot_hash == digest(snapshot)
        assert (
            snapshot["source_type"] == "DEMO"
            and snapshot["landed_unit_cost"] == "74000.000000"
        )
        assert audit.verify(session)["valid"]
    assert estimate(client, h, updated["id"])["total"] == "1480000.00"


def test_estimate_independent_approval_and_revision(env):
    _, client, h = env
    data = demo(env)
    current, _, _ = selection(env, data)
    path = f"/api/v1/estimates/{current['id']}"
    submitted = client.post(
        path + "/submit",
        json={"expected_version": current["version"]},
        headers=h["operator"],
    )
    assert submitted.status_code == 200, submitted.text
    submitted = submitted.json()
    denied = client.post(
        path + "/approve",
        json={"expected_version": submitted["version"]},
        headers=h["operator"],
    )
    assert denied.status_code == 403
    checked = client.post(
        path + "/check",
        json={"expected_version": submitted["version"]},
        headers=h["manager"],
    )
    assert checked.status_code == 200, checked.text
    approved = client.post(
        path + "/approve",
        json={"expected_version": checked.json()["version"]},
        headers=h["admin"],
    )
    assert approved.status_code == 200, approved.text
    original = approved.json()
    locked = client.patch(
        path,
        json={
            "name": original["name"],
            "fields": original["fields"],
            "expected_version": original["version"],
        },
        headers=h["operator"],
    )
    assert locked.status_code == 409
    revised = client.post(
        path + "/revise",
        json={"expected_version": original["version"]},
        headers=h["operator"],
    ).json()
    assert revised["revision"] == 2 and revised["status"] == "DRAFT"
    fields = deepcopy(revised["fields"])
    fields["lines"][0]["quantity"] = "21"
    changed = client.patch(
        f"/api/v1/estimates/{revised['id']}",
        json={
            "name": revised["name"],
            "fields": fields,
            "expected_version": revised["version"],
        },
        headers=h["operator"],
    )
    assert changed.status_code == 200, changed.text
    assert estimate(client, h, original["id"]) == original


def test_supplier_unknown_costs_fx_and_human_verification(env):
    app, client, h = env
    data = demo(env)
    verified_quote(env, data, freight_basis="UNKNOWN")
    verified_quote(
        env, data, price="1", currency="USD", supplier="USD fixture supplier"
    )
    prices = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?quantity=20",
        headers=h["operator"],
    ).json()
    assert not any(r["eligible"] for r in prices["offers"])
    assert any("Unknown freight" in " ".join(r["reasons"]) for r in prices["offers"])
    fx = client.post(
        "/api/v1/prices/exchange-rates",
        json={
            "project_id": data["project_id"],
            "base": "USD",
            "quote": "BDT",
            "factor": "120",
            "observed_date": date.today().isoformat(),
            "source": "Explicit synthetic FX test assumption",
        },
        headers=h["manager"],
    )
    assert fx.status_code == 201, fx.text
    prices = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?quantity=20",
        headers=h["operator"],
    ).json()
    dollar = next(r for r in prices["offers"] if r["payload"]["currency"] == "USD")
    assert dollar["landed_unit_cost"] == "120000.000000" and dollar["recommended"]
    assert any("exchange_rate_id" in r for r in dollar["conversions"])


def test_quote_expiry_wrong_grade_and_attachment_imports(env):
    _, client, h = env
    data = demo(env)
    verified_quote(
        env,
        data,
        specification={"grade": "B420B", "diameter_mm": "16", "standard": "BS 4449"},
    )
    response = client.post(
        "/api/v1/quotations",
        json=quote(
            data,
            quotation_date=(date.today() - timedelta(days=7)).isoformat(),
            valid_until=(date.today() - timedelta(days=1)).isoformat(),
        ),
        headers=h["operator"],
    ).json()
    assert (
        client.post(
            f"/api/v1/quotations/{response['id']}/verify",
            json={"expected_version": 1},
            headers=h["manager"],
        ).status_code
        == 422
    )
    csv_data = "supplier,title,price,unit,currency,spec_grade,spec_diameter_mm,spec_standard\nFixture,Steel,75,kg,BDT,B500B,16,BS 4449\n"
    imported = client.post(
        "/api/v1/quotations/import",
        data={"material_id": data["material_id"]},
        files={"file": ("quote.csv", csv_data, "text/csv")},
        headers=h["operator"],
    )
    assert imported.status_code == 201, imported.text
    record = imported.json()["quotations"][0]
    assert record["status"] == "DRAFT" and record["attachment_hash"]
    assert (
        client.get(
            f"/api/v1/quotations/{record['id']}/attachment", headers=h["auditor"]
        ).status_code
        == 200
    )
    rates = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?quantity=20",
        headers=h["operator"],
    ).json()
    assert all(not r["eligible"] for r in rates["offers"])


def test_measurements_and_estimate_export_import(env):
    _, client, h = env
    data = demo(env)
    profiles = client.get("/api/v1/measurement/profiles", headers=h["operator"]).json()
    profile = next(p for p in profiles if p["code"] == "NRM2")
    measured = client.post(
        "/api/v1/takeoff/sheets",
        json={
            "project_id": data["project_id"],
            "profile_id": profile["id"],
            "name": "20 columns",
            "calculation": "RECTANGULAR_VOLUME",
            "dimensions": {"length": ".4", "width": ".4", "height": "3", "count": "20"},
            "drawing_reference": "D-001 rev A",
        },
        headers=h["operator"],
    )
    assert measured.status_code == 201, measured.text
    saved = measured.json()
    assert (
        saved["result"]["quantity"] == "9.600000"
        and saved["result"]["profile_snapshot"]["verification_status"]
        == "REQUIRES_PROFESSIONAL_REVIEW"
    )
    assert (
        client.post(
            f"/api/v1/takeoff/sheets/{saved['id']}/check",
            json={"expected_version": 1},
            headers=h["operator"],
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/takeoff/sheets/{saved['id']}/check",
            json={"expected_version": 1},
            headers=h["manager"],
        ).status_code
        == 200
    )
    exported = client.get(
        f"/api/v1/estimates/{data['estimate_id']}/export?format=xlsx",
        headers=h["operator"],
    )
    assert exported.status_code == 200 and exported.content.startswith(b"PK")
    current = estimate(client, h, data["estimate_id"])
    imported = client.post(
        f"/api/v1/estimates/{current['id']}/import",
        data={"expected_version": current["version"]},
        files={"file": ("estimate.xlsx", exported.content)},
        headers=h["operator"],
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["total"] == current["total"]


def test_cross_project_scope_versions_and_existing_commitments(env):
    app, client, h = env
    data = demo(env)
    original = client.get("/api/v1/projects", headers=h["operator"]).json()[0]
    created = client.post(
        "/api/v1/estimates",
        json={"project_id": original["id"], "name": "Approved BOQ copy"},
        headers=h["operator"],
    )
    assert created.status_code == 201, created.text
    current = created.json()
    fields = current["fields"]
    for line in fields["lines"]:
        line["due_date"] = date.today().isoformat()
        line["components"][0]["unit_price"] = str(
            decimal(line["components"][0]["unit_price"]) * 2
        )
    changed = client.patch(
        f"/api/v1/estimates/{current['id']}",
        json={"name": current["name"], "fields": fields, "expected_version": 1},
        headers=h["operator"],
    )
    assert changed.status_code == 200, changed.text
    preview = client.get(
        f"/api/v1/estimates/{current['id']}/forecast", headers=h["operator"]
    ).json()
    assert (
        preview["scheduled_costs"] == []
    )  # fully committed original POs are not repriced
    stale = client.patch(
        f"/api/v1/estimates/{current['id']}",
        json={"name": current["name"], "fields": fields, "expected_version": 1},
        headers=h["operator"],
    )
    assert stale.status_code == 409
    with transaction(app.state.engine, True) as session:
        operator = session.scalar(select(m.User).where(m.User.role == "OPERATOR"))
        session.delete(session.get(m.Membership, (operator.id, data["project_id"])))
    assert (
        client.get(
            f"/api/v1/estimates/{data['estimate_id']}", headers=h["operator"]
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/materials/{data['material_id']}/prices", headers=h["operator"]
        ).status_code
        == 404
    )


def test_rate_buildup_rounding_and_source_tamper(env):
    _, client, h = env
    data = demo(env)
    current, _, _ = selection(env, data)
    fields = deepcopy(current["fields"])
    fields["lines"][0]["components"][0]["unit_price"] = "1"
    result = client.patch(
        f"/api/v1/estimates/{current['id']}",
        json={
            "name": current["name"],
            "fields": fields,
            "expected_version": current["version"],
        },
        headers=h["operator"],
    )
    assert result.status_code == 422
    fields["lines"][0]["components"][0]["selection_id"] = None
    fields["lines"][0]["components"][0]["source_note"] = "Explicit new test assumption"
    fields["site_overhead_percent"], fields["profit_percent"], fields["tax_percent"] = (
        "10",
        "10",
        "5",
    )
    result = client.patch(
        f"/api/v1/estimates/{current['id']}",
        json={
            "name": current["name"],
            "fields": fields,
            "expected_version": current["version"],
        },
        headers=h["operator"],
    )
    assert result.status_code == 200, result.text
    assert result.json()["total"] == "25.41"  # 20 × 1 × 1.10 × 1.10 × 1.05


def test_provider_timeout_isolation_and_remote_task_resume(env, monkeypatch):
    import httpx

    app, client, h = env
    data = demo(env)
    app.state.settings.serpapi_key = "test-only-no-network"

    async def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("test timeout")

    monkeypatch.setattr(SerpApiProvider, "search", timeout)
    task = search(env, data, "LIVE")
    current = client.get(
        f"/api/v1/prices/searches/{task['id']}", headers=h["operator"]
    ).json()
    assert current["states"]["serpapi"]["status"] == "TIMEOUT"
    assert client.get("/api/v1/health").status_code == 200


def test_consistent_sqlite_backup_roundtrip(env, tmp_path):
    app, _, _ = env
    path = app.state.settings.data_dir / "buildtrust.db"
    backup = tmp_path / "backup.db"
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as dest:
        source.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        for table in ("users", "memberships", "projects", "audit_events", "payments"):
            assert (
                source.execute(f"SELECT * FROM {table}").fetchall()
                == dest.execute(f"SELECT * FROM {table}").fetchall()
            )


def test_preview_is_exact_and_does_not_write(env):
    app, client, h = env
    data = demo(env)
    task = search(env, data)
    compared = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?search_id={task['id']}",
        headers=h["operator"],
    ).json()
    payload = {
        "estimate_id": data["estimate_id"],
        "expected_version": 1,
        "line_id": "steel-line",
        "component_id": "steel-material",
        "observation_id": compared["recommended_observation_id"],
        "search_id": task["id"],
    }
    preview = client.post(
        f"/api/v1/materials/{data['material_id']}/prices/preview",
        json=payload,
        headers=h["operator"],
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["estimate_difference"] == "80000.00"
    assert preview.json()["forecast_difference"] == "-80000.00"
    assert estimate(client, h, data["estimate_id"])["version"] == 1
    with transaction(app.state.engine) as session:
        assert not list(session.scalars(select(a.PriceSelection)))


def test_new_search_does_not_replace_selected_evidence(env):
    app, client, h = env
    data = demo(env)
    current, _, _ = selection(env, data)
    with transaction(app.state.engine) as session:
        record = session.scalar(select(a.PriceSelection))
        original = record.snapshot_hash
    response = client.post(
        f"/api/v1/materials/{data['material_id']}/prices/refresh",
        json={"mode": "DEMO", "quantity": "30"},
        headers=h["operator"],
    )
    assert response.status_code == 202
    assert estimate(client, h, current["id"]) == current
    with transaction(app.state.engine) as session:
        assert session.scalar(select(a.PriceSelection)).snapshot_hash == original


def test_material_change_and_revoked_checker_block_approval(env):
    app, client, h = env
    data = demo(env)
    current, _, _ = selection(env, data)
    submitted = client.post(
        f"/api/v1/estimates/{current['id']}/submit",
        json={"expected_version": current["version"]},
        headers=h["operator"],
    ).json()
    checked = client.post(
        f"/api/v1/estimates/{current['id']}/check",
        json={"expected_version": submitted["version"]},
        headers=h["manager"],
    ).json()
    with transaction(app.state.engine, True) as session:
        checker = session.get(m.User, checked["checked_by"])
        checker.active = False
    denied = client.post(
        f"/api/v1/estimates/{current['id']}/approve",
        json={"expected_version": checked["version"]},
        headers=h["admin"],
    )
    assert (
        denied.status_code == 409
        and denied.json()["error"]["code"] == "CHECKER_AUTHORITY_CHANGED"
    )
    with transaction(app.state.engine, True) as session:
        checker = session.get(m.User, checked["checked_by"])
        checker.active = True
    material = client.get(
        f"/api/v1/materials/{data['material_id']}", headers=h["operator"]
    ).json()
    changed = client.patch(
        f"/api/v1/materials/{data['material_id']}",
        json={
            "project_id": data["project_id"],
            "name": material["name"],
            "category": material["category"],
            "unit": material["unit"],
            "specification": {**material["specification"], "grade": "B500C"},
            "expected_version": 1,
        },
        headers=h["operator"],
    )
    assert changed.status_code == 200
    denied = client.post(
        f"/api/v1/estimates/{current['id']}/approve",
        json={"expected_version": checked["version"]},
        headers=h["admin"],
    )
    assert (
        denied.status_code == 409 and denied.json()["error"]["code"] == "SOURCE_CHANGED"
    )


def test_remote_task_resume_does_not_resubmit(env, monkeypatch):
    app, client, h = env
    data = demo(env)
    app.state.settings.dataforseo_login = "fixture"
    app.state.settings.dataforseo_password = "fixture"
    submissions = []

    async def submit(*args):
        submissions.append("submitted")
        return "test-task-id"

    async def waiting(*args):
        return None

    async def ready(*args):
        return []

    async def immediate_sleep(*args):
        return None

    import app.pricing as service

    monkeypatch.setattr(DataForSEOProvider, "submit", submit)
    monkeypatch.setattr(DataForSEOProvider, "retrieve", waiting)
    monkeypatch.setattr(service.asyncio, "sleep", immediate_sleep)
    task = search(env, data, "LIVE")
    current = client.get(
        f"/api/v1/prices/searches/{task['id']}", headers=h["operator"]
    ).json()
    assert current["status"] == "WAITING"
    assert current["states"]["dataforseo"]["remote_id"] == "test-task-id"
    monkeypatch.setattr(DataForSEOProvider, "retrieve", ready)
    resumed = client.post(
        f"/api/v1/prices/searches/{task['id']}/retry", headers=h["operator"]
    )
    assert resumed.status_code == 202
    assert len(submissions) == 1


def test_uncertain_paid_submission_is_not_repeated(env, monkeypatch):
    import httpx

    app, client, h = env
    data = demo(env)
    app.state.settings.dataforseo_login = "fixture"
    app.state.settings.dataforseo_password = "fixture"

    async def uncertain(*args):
        raise httpx.ReadTimeout("ambiguous provider POST")

    monkeypatch.setattr(DataForSEOProvider, "submit", uncertain)
    first = search(env, data, "LIVE")
    status = client.get(
        f"/api/v1/prices/searches/{first['id']}", headers=h["operator"]
    ).json()
    assert status["states"]["dataforseo"]["status"] == "UNKNOWN_SUBMISSION"
    repeat = client.post(
        f"/api/v1/materials/{data['material_id']}/prices/refresh",
        json={"mode": "LIVE", "quantity": "20"},
        headers=h["operator"],
    )
    assert repeat.status_code == 409


def test_stale_listing_reference_history_and_sourced_provenance(env):
    app, client, h = env
    data = demo(env)
    record = verified_quote(env, data)
    with transaction(app.state.engine, True) as session:
        observed = session.scalar(
            select(a.PriceObservation).where(
                a.PriceObservation.quotation_id == record["id"]
            )
        )
        raw = json.loads(observed.payload_json)
        raw["source_url"] = "https://example.org/source-backed-fixture"
        online = pricing.observation(
            session,
            session.get(a.Material, data["material_id"]),
            raw,
            "fixture",
            "ONLINE_LISTING",
        )
        online.retrieved_at = "2020-01-01T00:00:00Z"
        pricing.observation(
            session,
            session.get(a.Material, data["material_id"]),
            {**raw, "rate_category": "COMPOSITE", "edition": "2022"},
            "reference",
            "OFFICIAL_REFERENCE",
        )
    compared = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?quantity=20",
        headers=h["operator"],
    ).json()
    stale = next(r for r in compared["offers"] if r["source_type"] == "ONLINE_LISTING")
    assert not stale["eligible"] and any(
        "stale" in reason for reason in stale["reasons"]
    )
    reference = next(
        r for r in compared["offers"] if r["source_type"] == "OFFICIAL_REFERENCE"
    )
    assert reference["compatibility"] == "Incompatible"
    supplier = next(
        r for r in compared["offers"] if r["source_type"] == "SUPPLIER_QUOTE"
    )
    assert supplier["payload"]["verified_by"] and supplier["evidence_hash"]


def test_copilot_sensitivity_uses_real_tools_without_changes(env):
    _, client, h = env
    data = demo(env)
    response = client.post(
        "/api/v1/advanced/ask",
        json={
            "project_id": data["project_id"],
            "estimate_id": data["estimate_id"],
            "question": "What happens if steel increases 10%?",
        },
        headers=h["operator"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["facts"]["increase"] == "140000"
    assert response.json()["tools"] == ["estimate_sensitivity"]
    assert response.json()["audit_event_id"]
    assert estimate(client, h, data["estimate_id"])["total"] == "1400000.00"


def test_quotation_pdf_and_xlsx_content_are_real_and_require_review(env):
    from reportlab.pdfgen.canvas import Canvas
    from openpyxl import Workbook
    from io import BytesIO

    _, client, h = env
    data = demo(env)
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for index, line in enumerate(
        [
            "Supplier: Fictional PDF supplier",
            "Quotation Number: Q-PDF-1",
            "Product: 16 mm B500B steel",
            "Unit Price: BDT 75,000 (needs review)",
            "Currency: BDT",
            "Unit: tonne",
        ]
    ):
        canvas.drawString(40, 800 - index * 20, line)
    canvas.save()
    result = client.post(
        "/api/v1/quotations/import",
        data={"material_id": data["material_id"]},
        files={"file": ("random.pdf", buffer.getvalue(), "application/pdf")},
        headers=h["operator"],
    )
    assert result.status_code == 201, result.text
    record = result.json()["quotations"][0]
    assert record["fields"]["supplier"] == "Fictional PDF supplier"
    assert record["fields"]["price"] is None and record["status"] == "DRAFT"
    assert result.json()["extraction"]["fields"]["price"]["rejected_suggestion"]
    wb = Workbook()
    ws = wb.active
    ws.append(["supplier", "title", "price", "unit", "currency"])
    ws.append(["XLSX fixture supplier", "Steel", 74, "kg", "BDT"])
    stream = BytesIO()
    wb.save(stream)
    wb.close()
    result = client.post(
        "/api/v1/quotations/import",
        data={"material_id": data["material_id"]},
        files={"file": ("other-name.xlsx", stream.getvalue())},
        headers=h["operator"],
    )
    assert result.status_code == 201, result.text
    assert result.json()["quotations"][0]["fields"]["price"] == "74"


def test_spreadsheet_formula_is_rejected_and_unsafe_exports_are_escaped(env):
    from openpyxl import Workbook
    from io import BytesIO
    from app.advanced_imports import safe_cell

    _, client, h = env
    data = demo(env)
    wb = Workbook()
    wb.active.append(["supplier", "title", "price"])
    wb.active.append(["Fixture", "Steel", "=1+1"])
    stream = BytesIO()
    wb.save(stream)
    wb.close()
    response = client.post(
        "/api/v1/quotations/import",
        data={"material_id": data["material_id"]},
        files={"file": ("unsafe.xlsx", stream.getvalue())},
        headers=h["operator"],
    )
    assert response.status_code == 422
    assert safe_cell('=HYPERLINK("https://example.org")').startswith("'=")


def test_parallel_price_selection_has_one_winner_and_one_snapshot(env):
    from concurrent.futures import ThreadPoolExecutor

    app, client, h = env
    data = demo(env)
    task = search(env, data)
    offers = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?search_id={task['id']}",
        headers=h["operator"],
    ).json()
    payload = {
        "estimate_id": data["estimate_id"],
        "expected_version": 1,
        "line_id": "steel-line",
        "component_id": "steel-material",
        "observation_id": offers["recommended_observation_id"],
        "search_id": task["id"],
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: client.post(
                    f"/api/v1/materials/{data['material_id']}/prices/select",
                    json=payload,
                    headers=h["operator"],
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    with transaction(app.state.engine) as session:
        assert len(list(session.scalars(select(a.PriceSelection)))) == 1


def test_full_approval_evidence_and_demo_reset_preserve_old_versions(env):
    _, client, h = env
    data = demo(env)
    current, _, _ = selection(env, data)
    submitted = client.post(
        f"/api/v1/estimates/{current['id']}/submit",
        json={"expected_version": current["version"]},
        headers=h["operator"],
    ).json()
    evidence = client.get(
        f"/api/v1/estimates/{current['id']}/evidence", headers=h["auditor"]
    ).json()
    assert (
        evidence["snapshot_valid"]
        and evidence["snapshot_hash"] == submitted["snapshot_hash"]
    )
    assert evidence["snapshot"]["materials"] and evidence["snapshot"]["selections"]
    assert client.post("/api/v1/demo/reset", headers=h["admin"]).status_code == 200
    new = demo(env)
    assert new["project_id"] != data["project_id"]
    retained = client.get(
        f"/api/v1/estimates/{current['id']}/evidence", headers=h["auditor"]
    ).json()
    assert retained["snapshot_hash"] == evidence["snapshot_hash"]
