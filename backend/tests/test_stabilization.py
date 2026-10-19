"""Reproductions from the application review, using isolated databases."""

import pytest
from app import models as m
from app.advanced_imports import boq_import, table_rows
from app.database import transaction
from app.money import decimal
from sqlalchemy import select
from test_advanced_upgrade import demo, estimate, verified_quote


@pytest.mark.parametrize("value", ["1e-20000", "1e+20000", "0." + "0" * 200 + "1"])
def test_pathological_decimal_is_rejected_before_expansion(value):
    with pytest.raises(ValueError):
        decimal(value)


@pytest.mark.parametrize(
    "contents",
    [
        b"description,unit,quantity,unit_rate\nCement,bag,1,700\n",
        b"code,code,description,unit,quantity,unit_rate\nA,B,Cement,bag,1,700\n",
    ],
)
def test_boq_headers_are_validated(contents):
    with pytest.raises(ValueError, match="[Hh]eader|[Cc]olumn"):
        boq_import(contents, ".csv")


def test_csv_iterator_stops_at_import_limit():
    with pytest.raises(ValueError, match="500"):
        table_rows(b"a\n" + b"1\n" * 501, ".csv")


def test_retained_estimate_contributor_cannot_approve(env):
    _, client, h = env
    data = demo(env)
    record = estimate(client, h, data["estimate_id"])
    for role in ("admin", "operator"):
        fields = record["fields"]
        fields["basis"] = (
            "Reviewed manual rate with explicit zero tax and markup. " + role
        )
        if role == "admin":
            fields["lines"][0]["components"][0]["unit_price"] = "76000"
        response = client.patch(
            f"/api/v1/estimates/{record['id']}",
            headers=h[role],
            json={
                "name": record["name"],
                "fields": fields,
                "expected_version": record["version"],
            },
        )
        assert response.status_code == 200, response.text
        record = response.json()
    for action, role in (("submit", "operator"), ("check", "manager")):
        response = client.post(
            f"/api/v1/estimates/{record['id']}/{action}",
            headers=h[role],
            json={"expected_version": record["version"]},
        )
        assert response.status_code == 200, response.text
        record = response.json()
    response = client.post(
        f"/api/v1/estimates/{record['id']}/approve",
        headers=h["admin"],
        json={"expected_version": record["version"]},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "SEPARATION_OF_DUTIES"


def test_login_whitespace_variants_share_throttle(env):
    _, client, _ = env
    for _ in range(10):
        result = client.post(
            "/api/v1/auth/login",
            json={"email": "operator@buildtrust.demo", "password": "incorrect"},
        )
        assert result.status_code == 401
    result = client.post(
        "/api/v1/auth/login",
        json={"email": " operator@buildtrust.demo ", "password": "incorrect"},
    )
    assert result.status_code == 429
    assert int(result.headers["Retry-After"]) > 0


def test_incompatible_commitment_does_not_hide_cost(env):
    app, client, h = env
    with transaction(app.state.engine, True) as session:
        boq = session.scalar(
            select(m.BOQItem).where(m.BOQItem.item_code == "CEMENT-50")
        )
        if not boq:
            boq = session.scalars(select(m.BOQItem)).first()
        project_id, code = boq.project_id, boq.item_code
    result = client.post(
        "/api/v1/estimates",
        headers=h["operator"],
        json={
            "project_id": project_id,
            "name": "Coverage reproduction",
            "import_boq": True,
        },
    )
    assert result.status_code == 201, result.text
    with transaction(app.state.engine, True) as session:
        pol = session.scalar(
            select(m.POLine)
            .join(m.PurchaseOrder)
            .where(m.PurchaseOrder.project_id == project_id, m.POLine.item_code == code)
        )
        assert pol
        pol.description = "INCOMPATIBLE SPECIFICATION"
    preview = client.get(
        f"/api/v1/estimates/{result.json()['id']}/forecast", headers=h["operator"]
    )
    assert preview.status_code == 200, preview.text
    assert decimal(preview.json()["unscheduled_estimated_cost"]) > 0
    assert any(
        "Unresolved commitment" in warning for warning in preview.json()["warnings"]
    )


def test_price_tie_publishes_half_up(env):
    _, client, h = env
    data = demo(env)
    verified_quote(env, data, price="0.0012345665")
    result = client.get(
        f"/api/v1/materials/{data['material_id']}/prices?quantity=20",
        headers=h["operator"],
    )
    assert result.status_code == 200, result.text
    row = result.json()["offers"][0]
    assert row["normalized_unit_price"] == "1.234567"
    assert row["landed_unit_cost"] == "1.234567"


def test_bad_import_is_422_and_does_not_change_estimate(env):
    _, client, h = env
    data = demo(env)
    before = estimate(client, h, data["estimate_id"])
    response = client.post(
        f"/api/v1/estimates/{before['id']}/import",
        headers=h["operator"],
        data={"expected_version": before["version"]},
        files={
            "file": (
                "bad.csv",
                b"description,unit,quantity,unit_rate\nCement,bag,1,700\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 422, response.text
    assert "code" in response.json()["error"]["message"]
    assert estimate(client, h, before["id"]) == before


def test_quotation_previous_contributor_cannot_verify(env):
    from test_advanced_upgrade import quote

    _, client, h = env
    data = demo(env)
    response = client.post("/api/v1/quotations", headers=h["admin"], json=quote(data))
    assert response.status_code == 201, response.text
    record = response.json()
    response = client.patch(
        f"/api/v1/quotations/{record['id']}",
        headers=h["operator"],
        json=quote(
            data,
            expected_version=record["version"],
            notes="Operator reviewed the narrative",
        ),
    )
    assert response.status_code == 200, response.text
    response = client.post(
        f"/api/v1/quotations/{record['id']}/verify",
        headers=h["admin"],
        json={"expected_version": response.json()["version"]},
    )
    assert response.status_code == 403, response.text
