from app.finance import business_date


def test_expanded_provider_objects_are_compactly_attributed_and_persisted(
    env, monkeypatch
):
    _, client, h = env
    from app import price_api

    async def fixture(*args, **kwargs):
        return {
            "date": str(business_date()),
            "rate": "123.27",
            "providers": [
                {"key": f"BANK{i}", "date": str(business_date()), "rate": "123.25"}
                for i in range(30)
            ],
        }

    monkeypatch.setattr(price_api, "api_json", fixture)
    project = client.get("/api/v1/projects", headers=h["manager"]).json()[0]["id"]
    response = client.post(
        "/api/v1/prices/exchange-rates/fetch",
        headers=h["manager"],
        json={"project_id": project, "base": "USD", "quote": "BDT"},
    )
    assert response.status_code == 201, response.text
    row = response.json()
    assert (
        "BANK29@" in row["source"]
        and "rate" not in row["source"].split("providers=")[1]
    )
    saved = client.get(
        f"/api/v1/prices/exchange-rates?project_id={project}", headers=h["manager"]
    ).json()[0]
    assert (
        saved["date"] == row["observed_date"]
        and saved["factor"] == "123.27"
        and saved["source"] == row["source"]
    )
