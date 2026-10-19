"""Opt-in free FX acceptance through the actual API and a private SQLite database."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.database import transaction
from app.seed import seed
from app import advanced_models as a, audit
from sqlalchemy import select


def main():
    folder = ROOT / "data" / ("live-fx-" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    settings = Settings(
        data_dir=folder,
        background_jobs=False,
        llm_provider="none",
        serpapi_key="",
        dataforseo_login="",
        dataforseo_password="",
    )
    app = create_app(settings)
    with transaction(app.state.engine, True) as session:
        seed(session, settings, test_password="Isolated-Free-FX-2026!")
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "manager@buildtrust.demo",
                "password": "Isolated-Free-FX-2026!",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        project = client.get("/api/v1/projects", headers=headers).json()[0]["id"]
        response = client.post(
            "/api/v1/prices/exchange-rates/fetch",
            headers=headers,
            json={"project_id": project, "base": "USD", "quote": "BDT"},
        )
        result = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": response.status_code,
            "response": response.json(),
            "database": str(folder / "buildtrust.db"),
            "provider": "Frankfurter v2 free API",
            "paid_requests": False,
        }
        if response.status_code == 201:
            with transaction(app.state.engine) as session:
                row = session.get(a.ExchangeRate, response.json()["id"])
                assert (
                    row.base == "USD"
                    and row.quote == "BDT"
                    and row.factor
                    and row.observed_date
                    and "frankfurter.dev" in row.source
                    and "providers=" in row.source
                )
                result["persisted"] = {
                    "id": row.id,
                    "base": row.base,
                    "quote": row.quote,
                    "factor": row.factor,
                    "observed_date": row.observed_date,
                    "source": row.source,
                }
                result["audit_integrity"] = audit.verify(session)
                assert result["audit_integrity"]["valid"]
        (folder / "acceptance.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        (ROOT / "data" / "latest-live-fx.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, indent=2))
        if response.status_code != 201:
            raise SystemExit(1)
    app.state.engine.dispose()


if __name__ == "__main__":
    main()
