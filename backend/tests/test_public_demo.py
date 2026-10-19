import json
import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.config import Settings
from app.database import make_engine, transaction
from app.main import create_app
from app.migrations import migrate
from app.models import User
from app.public_demo import (
    check_port,
    load_accounts,
    prepare_public_demo,
    profile_settings,
)
from app.security import passwords
from app.seed import seed


def test_public_passwords_login_with_real_permissions_and_independent_payment(tmp_path):
    settings, _ = prepare_public_demo(tmp_path / "public-demo")
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            headers = {}
            for account in load_accounts():
                r = client.post(
                    "/api/v1/auth/login",
                    json={"email": account["email"], "password": account["password"]},
                )
                assert r.status_code == 200
                headers[account["role"]] = {
                    "Authorization": "Bearer " + r.json()["access_token"]
                }
            operator, manager, auditor = (
                headers[r] for r in ("OPERATOR", "FINANCE_MANAGER", "AUDITOR")
            )
            invoice = next(
                i
                for i in client.get("/api/v1/invoices", headers=operator).json()
                if i["invoice_number"] == "INV-CEMENT-070"
            )
            assert (
                client.post(
                    "/api/v1/payments/proposals",
                    json={"invoice_id": invoice["id"]},
                    headers=auditor,
                ).status_code
                == 403
            )
            r = client.post(
                "/api/v1/payments/proposals",
                json={"invoice_id": invoice["id"]},
                headers=operator,
            )
            assert r.status_code == 201
            proposal = r.json()
            assert (
                client.post(
                    f"/api/v1/payments/{proposal['id']}/approve", headers=operator
                ).status_code
                == 403
            )
            assert (
                client.post(
                    f"/api/v1/payments/{proposal['id']}/approve", headers=manager
                ).status_code
                == 200
            )
            r = client.post(
                f"/api/v1/payments/{proposal['id']}/execute",
                headers={**manager, "Idempotency-Key": "public-demo-payment"},
            )
            assert r.status_code == 200 and r.json()["balance_after"] == "930000.00"
            assert client.get("/api/v1/audit/verify", headers=auditor).json()["valid"]
    finally:
        app.state.engine.dispose()


def test_repeat_public_preparation_preserves_accounts_projects_and_audit(tmp_path):
    path = tmp_path / "public-demo"
    settings, _ = prepare_public_demo(path)
    engine = make_engine(path / "buildtrust.db")

    def snapshot():
        with transaction(engine) as session:
            return {
                table: list(
                    session.execute(text(f'SELECT * FROM "{table}" ORDER BY id'))
                )
                for table in ("users", "projects", "audit_events")
            }

    before = snapshot()
    try:
        _, result = prepare_public_demo(path)
        assert result["already_seeded"] and snapshot() == before
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", ["unrelated", "invalid_marker", "working_folder"])
def test_public_demo_refuses_unrelated_data_before_writing(tmp_path, kind):
    path = tmp_path / ("data" if kind == "working_folder" else "public-demo")
    path.mkdir()
    source = path / (
        "public-demo-profile.json" if kind == "invalid_marker" else "private-record.txt"
    )
    source.write_text("keep this original file", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in path.iterdir()}
    with pytest.raises(ValueError):
        prepare_public_demo(path)
    assert before == {p.name: p.read_bytes() for p in path.iterdir()}


@pytest.mark.parametrize("change", ["password", "role", "inactive"])
def test_public_demo_refuses_changed_accounts_without_overwriting(tmp_path, change):
    path = tmp_path / "public-demo"
    prepare_public_demo(path)
    engine = make_engine(path / "buildtrust.db")
    try:
        with transaction(engine, write=True) as session:
            user = session.scalar(
                select(User).where(User.email == "operator@buildtrust.demo")
            )
            if change == "password":
                user.password_hash = passwords.hash("Locally-Changed-Password!")
            elif change == "role":
                user.role = "AUDITOR"
            else:
                user.active = False
            state = (user.password_hash, user.role, user.active)
        with pytest.raises(ValueError, match="changed"):
            prepare_public_demo(path)
        with transaction(engine) as session:
            user = session.scalar(
                select(User).where(User.email == "operator@buildtrust.demo")
            )
            assert (user.password_hash, user.role, user.active) == state
    finally:
        engine.dispose()


def test_private_setup_keeps_random_passwords_and_public_seed_requires_marker(tmp_path):
    settings = Settings(data_dir=tmp_path / "private", llm_provider="none")
    settings.prepare()
    engine = make_engine(settings.data_dir / "buildtrust.db")
    migrate(engine)
    try:
        with transaction(engine, write=True) as session:
            seed(session, settings)
        actual = json.loads((settings.data_dir / "demo-credentials.json").read_text())
        public = {a["email"]: a["password"] for a in load_accounts()}
        assert set(actual) == set(public)
        assert all(
            actual[email].startswith("Demo-") and actual[email] != public[email]
            for email in actual
        )
        with transaction(engine, write=True) as session, pytest.raises(ValueError):
            seed(session, settings, public_demo=True)
        assert actual == json.loads(
            (settings.data_dir / "demo-credentials.json").read_text()
        )
    finally:
        engine.dispose()


def test_public_settings_ignore_private_paid_keys_and_llm(monkeypatch, tmp_path):
    for name, value in {
        "SERPAPI_KEY": "private-key",
        "DATAFORSEO_LOGIN": "private-login",
        "DATAFORSEO_PASSWORD": "private-password",
        "LLM_PROVIDER": "ollama",
        "DATA_DIR": str(tmp_path / "working"),
        "MINIMUM_RESERVE": "999999999",
        "APPROVAL_MINUTES": "1",
        "BACKGROUND_JOBS": "false",
        "MAX_UPLOAD_BYTES": "1",
    }.items():
        monkeypatch.setenv("BUILDTRUST_" + name, value)
    settings = profile_settings(tmp_path / "public-demo")
    assert settings.data_dir == tmp_path / "public-demo"
    assert settings.llm_provider == "none" and settings.demo_mode
    assert not any(
        (settings.serpapi_key, settings.dataforseo_login, settings.dataforseo_password)
    )
    assert settings.minimum_reserve == "100000.00"
    assert settings.approval_minutes == 30 and settings.background_jobs
    assert settings.max_upload_bytes == 10 * 1024 * 1024


def test_public_port_errors_are_clear():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(ValueError, match="already in use"):
            check_port(listener.getsockname()[1])
    with pytest.raises(ValueError, match="separate"):
        check_port(8000)


def test_public_profile_cannot_be_used_without_demo_mode(tmp_path):
    settings, _ = prepare_public_demo(tmp_path / "public-demo")
    settings.demo_mode = False
    engine = make_engine(settings.data_dir / "buildtrust.db")
    try:
        with (
            transaction(engine, write=True) as session,
            pytest.raises(ValueError, match="separate demo profile"),
        ):
            seed(session, settings, public_demo=True)
    finally:
        engine.dispose()
