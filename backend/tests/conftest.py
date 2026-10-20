import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.database import transaction
from app.seed import seed


@pytest.fixture
def env(tmp_path):
    settings = Settings(data_dir=tmp_path, llm_provider="none", background_jobs=False)
    app = create_app(settings)
    with transaction(app.state.engine, True) as session:
        seed(session, settings, test_password="Test-Demo-Password!2026")
    with TestClient(app) as client:
        headers = {}
        for role in ("operator", "manager", "admin", "auditor"):
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"{role}@buildtrust.demo",
                    "password": "Test-Demo-Password!2026",
                },
            )
            assert response.status_code == 200, response.text
            headers[role] = {
                "Authorization": "Bearer " + response.json()["access_token"]
            }
        yield app, client, headers
    app.state.engine.dispose()


def valid_invoice(client, headers):
    return next(
        i
        for i in client.get("/api/v1/invoices", headers=headers).json()
        if i["invoice_number"] == "INV-CEMENT-070"
    )


def prepared(env):
    app, client, h = env
    invoice = valid_invoice(client, h["operator"])
    response = client.post(
        "/api/v1/payments/proposals",
        json={"invoice_id": invoice["id"]},
        headers=h["operator"],
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "PENDING_APPROVAL", response.text
    return response.json()


def approved(env):
    proposal = prepared(env)
    _, client, h = env
    response = client.post(
        f"/api/v1/payments/{proposal['id']}/approve", headers=h["manager"]
    )
    assert response.status_code == 200, response.text
    return proposal


@pytest.fixture
def paid_fixture(env):
    """Explicit fixture-only budgets; callers still supply fake keys and mocks."""
    settings = env[0].state.settings
    settings.paid_providers_enabled = True
    settings.paid_user_daily_calls = 100
    settings.paid_project_daily_calls = 100
    settings.paid_provider_daily_calls = 100
    settings.paid_operation_ceiling = "0.10"
    settings.paid_daily_budget = "10.00"
