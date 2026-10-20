"""Security boundaries through real requests and isolated persistence."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import jwt
import pytest
from sqlalchemy import select, func
from conftest import GuardedTestClient as TestClient
from app import models as m
from app.database import transaction
from app.main import create_app
from app.hardening_models import AuthSession, RecoveryToken, UsageReservation
from app.admission import consume, reserve_usage
from app.security import DomainError, passwords
from app.local_security import backup, restore
from app.private_storage import private_path


def login(client, email="operator@buildtrust.demo", password="Test-Demo-Password!2026"):
    return client.post("/api/v1/auth/login",json={"email":email,"password":password})


def test_logout_revokes_captured_token_after_restart(env):
    app,client,h=env
    assert client.post("/api/v1/auth/logout",headers=h["operator"]).status_code==200
    assert client.get("/api/v1/auth/me",headers=h["operator"]).status_code==401
    second=create_app(app.state.settings)
    with TestClient(second) as restarted:
        assert restarted.get("/api/v1/auth/me",headers=h["operator"]).status_code==401
    second.state.engine.dispose()


def test_expired_and_legacy_tokens_fail(env):
    app,client,h=env
    raw=h["operator"]["Authorization"][7:]
    claims=jwt.decode(raw,app.state.secret,algorithms=["HS256"],audience="buildtrust",issuer="buildtrust-local")
    for payload in ({k:v for k,v in claims.items() if k!="jti"},{**claims,"exp":1}):
        token=jwt.encode(payload,app.state.secret,algorithm="HS256")
        assert client.get("/api/v1/auth/me",headers={"Authorization":"Bearer "+token}).status_code==401


def test_password_change_revokes_all_sessions_and_keeps_hash_private(env):
    app,client,h=env
    other=login(client).json()["access_token"]
    response=client.post("/api/v1/auth/password/change",headers=h["operator"],json={"current_password":"Test-Demo-Password!2026","new_password":"Replacement-Password-2026!"})
    assert response.status_code==200,response.text
    for header in (h["operator"],{"Authorization":"Bearer "+other}):
        assert client.get("/api/v1/auth/me",headers=header).status_code==401
    assert login(client).status_code==401
    assert login(client,password="Replacement-Password-2026!").status_code==200
    with transaction(app.state.engine) as session:
        user=session.scalar(select(m.User).where(m.User.email=="operator@buildtrust.demo"))
        assert user.password_hash.startswith("$argon2")
        assert "Replacement-Password" not in " ".join(e.details_json for e in session.scalars(select(m.AuditEvent)))


def test_recovery_single_use_expiry_and_independence(env):
    app,client,h=env
    users=client.get("/api/v1/administration/users",headers=h["admin"]).json()
    operator=next(u for u in users if u["role"]=="OPERATOR")
    admin=next(u for u in users if u["role"]=="ADMIN")
    route=f"/api/v1/administration/users/{operator['id']}/recovery"
    assert client.post(route,headers=h["operator"]).status_code==403
    assert client.post(f"/api/v1/administration/users/{admin['id']}/recovery",headers=h["admin"]).status_code==403
    r=client.post(route,headers=h["admin"]);assert r.status_code==200,r.text
    token=r.json()["token"];key=hashlib.sha256(token.encode()).hexdigest()
    with transaction(app.state.engine,True) as session:
        row=session.get(RecoveryToken,key);assert row and row.token_hash!=token
        row.expires_at="2000-01-01T00:00:00Z"
    assert client.post("/api/v1/auth/password/reset",json={"token":token,"new_password":"Recovered-Private-2026!"}).status_code==422
    token=client.post(route,headers=h["admin"]).json()["token"]
    body={"token":token,"new_password":"Recovered-Private-2026!"}
    assert client.post("/api/v1/auth/password/reset",json=body).status_code==200
    assert client.post("/api/v1/auth/password/reset",json=body).status_code==422
    assert client.get("/api/v1/auth/me",headers=h["operator"]).status_code==401
    assert login(client,password="Recovered-Private-2026!").status_code==200
    with transaction(app.state.engine) as session:
        assert token not in " ".join(e.details_json for e in session.scalars(select(m.AuditEvent)))


@pytest.mark.parametrize("path",["/invoices","/documents","/payments","/administration/users","/audit","/projects","/prices/providers"])
def test_anonymous_protected_registers(env,path):
    _,client,_=env
    assert client.get("/api/v1"+path).status_code in (401,404)


def test_two_accounts_cannot_cross_project_or_attachment_boundaries(env):
    app,client,h=env
    response=client.post("/api/v1/administration/users",headers=h["admin"],json={"email":"isolated@example.test","name":"Isolated member","role":"OPERATOR","password":"Isolated-Password-2026!"})
    assert response.status_code==201,response.text
    identity=response.json()["id"]
    with transaction(app.state.engine,True) as session:
        project=m.Project(code="PRIVATE-SECOND",name="Separate account project",client="Fictional",currency="BDT",budget_minor=1000000,balance_minor=1000000,reserve_minor=10000,run_id="isolated-security",active=True)
        session.add(project);session.flush();pid=project.id
        session.add(m.Membership(user_id=identity,project_id=pid))
    token=login(client,"isolated@example.test","Isolated-Password-2026!").json()["access_token"]
    outsider={"Authorization":"Bearer "+token}
    assert client.get("/api/v1/projects",headers=outsider).json()[0]["id"]==pid
    doc=client.get("/api/v1/documents",headers=h["operator"]).json()[0]
    for path in (f"/documents/{doc['id']}",f"/documents/{doc['id']}/preview",f"/projects/{doc['project_id']}"):
        assert client.get("/api/v1"+path,headers=outsider).status_code==404
    assert client.post(f"/api/v1/documents/{doc['id']}/confirm",headers=outsider).status_code==404
    assert client.get("/api/v1/administration/users",headers=outsider).status_code==403
    assert client.get(f"/api/v1/projects/{pid}",headers=h["operator"]).status_code==404


def test_durable_limit_atomicity_and_expiry(env):
    app,_,_=env
    def attempt(_):
        try:consume(app.state.engine,[("concurrent-fixture",3,60)],clock=lambda:1000);return True
        except DomainError:return False
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(attempt,range(6)))==3
    with pytest.raises(DomainError):consume(app.state.engine,[("concurrent-fixture",3,60)],clock=lambda:1001)
    consume(app.state.engine,[("concurrent-fixture",3,60)],clock=lambda:1061)


def test_paid_access_requires_explicit_enablement_and_atomic_budget(env):
    app,client,h=env;settings=app.state.settings
    settings.serpapi_key="fixture-no-network"
    status=client.get("/api/v1/prices/providers",headers=h["operator"]).json()
    assert not next(p for p in status if p["id"]=="serpapi")["enabled"]
    with transaction(app.state.engine) as session:
        actor=session.scalar(select(m.User).where(m.User.role=="OPERATOR"));uid=actor.id
        pid=session.scalar(select(m.Membership.project_id).where(m.Membership.user_id==uid))
    with pytest.raises(DomainError):reserve_usage(app.state.engine,settings,"serpapi","blocked",uid,pid)
    settings.paid_providers_enabled=True;settings.paid_user_daily_calls=2;settings.paid_project_daily_calls=2;settings.paid_provider_daily_calls=2
    settings.paid_operation_ceiling="0.50";settings.paid_daily_budget="1.00"
    first=reserve_usage(app.state.engine,settings,"serpapi","one",uid,pid)
    assert reserve_usage(app.state.engine,settings,"serpapi","one",uid,pid)==first
    reserve_usage(app.state.engine,settings,"serpapi","two",uid,pid)
    with pytest.raises(DomainError):reserve_usage(app.state.engine,settings,"serpapi","three",uid,pid)
    with transaction(app.state.engine) as session:
        assert session.scalar(select(func.sum(UsageReservation.reserved_minor)))==100


def test_backup_restores_files_accounts_sessions_and_audit_without_overwrite(env,tmp_path):
    app,client,h=env
    before=client.get("/api/v1/projects",headers=h["operator"]).json()
    file=tmp_path/"private-backup.private.zip"
    assert backup(app.state.settings,file)["passed"]
    target=tmp_path/"restored"
    assert restore(file,target)["audit_valid"]
    with pytest.raises(ValueError):restore(file,app.state.settings.data_dir)
    settings=app.state.settings.model_copy(update={"data_dir":target})
    restored=create_app(settings)
    try:
        with TestClient(restored) as c:
            assert c.get("/api/v1/projects",headers=h["operator"]).status_code==401
            fresh={"Authorization":"Bearer "+login(c).json()["access_token"]}
            assert c.get("/api/v1/projects",headers=fresh).json()==before
            assert c.get("/api/v1/audit/verify",headers=fresh).json()["valid"]
    finally:restored.state.engine.dispose()


def test_private_path_escape_and_unexpected_error_redaction(env,caplog):
    app,client,h=env
    with pytest.raises(ValueError):private_path(app.state.settings.data_dir,"../outside.txt")
    @app.get("/api/v1/security-test-error")
    def broken():raise RuntimeError("synthetic-secret-never-log-987654")
    # The built UI catch-all is already registered; put this injected test route
    # before it so the intended server failure is actually exercised.
    app.router.routes.insert(0, app.router.routes.pop())
    response=client.get("/api/v1/security-test-error")
    assert response.status_code==500
    assert "synthetic-secret" not in response.text+caplog.text
    assert response.headers.get("X-Request-ID")
    assert "frame-ancestors 'none'" in response.headers.get("Content-Security-Policy","")


def test_frontend_claims_cannot_promote_identity_or_role(env):
    app,client,h=env
    raw=h["operator"]["Authorization"][7:]
    claims=jwt.decode(raw,app.state.secret,algorithms=["HS256"],audience="buildtrust")
    forged=jwt.encode({**claims,"role":"ADMIN","user_id":1},app.state.secret,algorithm="HS256")
    assert client.get("/api/v1/administration/users",headers={"Authorization":"Bearer "+forged}).status_code==403
    with transaction(app.state.engine) as session:
        admin=session.scalar(select(m.User.id).where(m.User.role=="ADMIN"))
    forged=jwt.encode({**claims,"sub":str(admin)},app.state.secret,algorithm="HS256")
    assert client.get("/api/v1/administration/users",headers={"Authorization":"Bearer "+forged}).status_code==401
    assert login(client,email="' OR 1=1 --").status_code==401


def test_concurrent_reset_accepts_token_once(env):
    app,client,h=env
    with transaction(app.state.engine) as session:
        identity=session.scalar(select(m.User.id).where(m.User.role=="OPERATOR"))
    token=client.post(f"/api/v1/administration/users/{identity}/recovery",headers=h["admin"]).json()["token"]
    def redeem(_):return client.post("/api/v1/auth/password/reset",json={"token":token,"new_password":"Concurrent-Recovery-Fixture!"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(redeem,range(2)))==[200,422]


def test_model_daily_limit_and_bounded_reader(env,monkeypatch):
    app,_,_=env
    with transaction(app.state.engine) as session:
        actor=session.scalar(select(m.User).where(m.User.role=="OPERATOR"));uid=actor.id
        pid=session.scalar(select(m.Membership.project_id).where(m.Membership.user_id==uid))
    app.state.settings.llm_user_daily_calls=1
    reserve_usage(app.state.engine,app.state.settings,"ollama","one",uid,pid)
    with pytest.raises(DomainError):reserve_usage(app.state.engine,app.state.settings,"ollama","two",uid,pid)
    from app import workflow
    from contextlib import contextmanager
    class Response:
        def raise_for_status(self):pass
        def iter_bytes(self):yield b"x"*(128*1024+1)
    @contextmanager
    def fake(*args,**kwargs):yield Response()
    monkeypatch.setattr(workflow.httpx,"stream",fake)
    with pytest.raises(ValueError,match="bounds"):workflow.model_response(app.state.settings,{})


def test_native_private_permissions_on_database_secret_and_upload_directory(env):
    import os, stat
    app,_,_=env
    paths=[app.state.settings.data_dir/"buildtrust.db",app.state.settings.data_dir/"signing-secret",app.state.settings.data_dir/"uploads"]
    if os.name!="nt":
        for path in paths:assert stat.S_IMODE(path.stat().st_mode)==(0o700 if path.is_dir() else 0o600)
    else:
        import ctypes, re
        from ctypes import wintypes
        from app.private_storage import windows_sid
        api=ctypes.WinDLL("advapi32",use_last_error=True);kernel=ctypes.WinDLL("kernel32")
        get=api.GetFileSecurityW;get.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)];get.restype=wintypes.BOOL
        convert=api.ConvertSecurityDescriptorToStringSecurityDescriptorW;convert.argtypes=[ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p];convert.restype=wintypes.BOOL
        parse=api.ConvertStringSecurityDescriptorToSecurityDescriptorW;parse.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p];parse.restype=wintypes.BOOL
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        def principals(descriptor):
            text=ctypes.c_void_p();assert convert(descriptor,1,4,ctypes.byref(text),None)
            try:return set(re.findall(r";;;([^)]*)",ctypes.wstring_at(text)))
            finally:kernel.LocalFree(text)
        # Windows can render the same account SID as an SDDL alias (for example
        # LA on an Administrator runner). Canonicalize both sides natively.
        expected=ctypes.c_void_p()
        assert parse(f"D:P(A;;FA;;;{windows_sid()})(A;;FA;;;SY)(A;;FA;;;BA)",1,ctypes.byref(expected),None)
        try:expected_principals=principals(expected)
        finally:kernel.LocalFree(expected)
        for path in paths:
            length=wintypes.DWORD();get(str(path),4,None,0,ctypes.byref(length));buffer=ctypes.create_string_buffer(length.value)
            assert get(str(path),4,buffer,length,ctypes.byref(length))
            assert principals(buffer)==expected_principals


def test_local_model_caller_deadline_returns_without_unbounded_workers(env,monkeypatch):
    from app import workflow
    from contextlib import contextmanager
    from threading import Event
    release, finished = Event(), Event()
    class Response:
        def raise_for_status(self):release.wait(1)
        def iter_bytes(self):
            finished.set()
            yield b'{}'
    @contextmanager
    def fake(*args,**kwargs):yield Response()
    monkeypatch.setattr(workflow.httpx,"stream",fake)
    monkeypatch.setattr(workflow,"MODEL_RESPONSE_SECONDS",0.01)
    try:
        with pytest.raises(ValueError,match="deadline"):workflow.model_response(env[0].state.settings,{})
        assert not finished.is_set()
    finally:release.set()
    assert finished.wait(1)


def test_provider_client_diagnostics_do_not_log_query_credentials(env,paid_fixture,monkeypatch,caplog):
    import asyncio, logging, httpx
    from app.price_providers import api_json
    app,_,_=env
    marker="private-provider-fixture-never-log"
    app.state.settings.serpapi_key=marker
    original=httpx.AsyncClient
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={"shopping_results":[]}))
    monkeypatch.setattr(httpx,"AsyncClient",lambda **kwargs:original(transport=transport,**kwargs))
    caplog.set_level(logging.INFO)
    assert asyncio.run(api_json("GET","https://serpapi.com/search.json",app.state.settings,params={"api_key":marker}))=={"shopping_results":[]}
    assert marker not in caplog.text
