"""Real MFA/request boundaries over isolated persistence; no production bypass."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import asyncio
import pyotp
import pytest
from sqlalchemy import select
from app import models as m,mfa
from app.database import transaction
from app.mfa_models import MfaFactor,MfaChallenge,MfaRecoveryCode
from app.security import token_for


def new_manager(env):
    _,c,h=env
    r=c.post('/api/v1/administration/users',headers=h['admin'],json={'email':'mfa-subject@example.test','name':'MFA subject','role':'FINANCE_MANAGER','password':'Subject-Private-2026!'})
    assert r.status_code==201
    return r.json()['id']


def pending(c,email='mfa-subject@example.test',password='Subject-Private-2026!'):
    r=c.post('/api/v1/auth/login',json={'email':email,'password':password},complete_mfa=False)
    assert r.status_code==200
    return r.json()


def test_mfa_enrollment_is_restricted_encrypted_and_revocable(env):
    app,c,_=env;identity=new_manager(env);step=pending(c)
    assert step['status']=='MFA_SETUP_REQUIRED' and 'access_token' not in step
    assert c.get('/api/v1/projects',headers={'Authorization':'Bearer '+step['challenge_token']}).status_code==401
    start=c.post('/api/v1/auth/mfa/enroll/start',json={'challenge_token':step['challenge_token']});assert start.status_code==200
    data=start.json();assert data['qr_png_base64'] and data['provisioning_uri'].startswith('otpauth://')
    with transaction(app.state.engine) as s:
        row=s.get(MfaChallenge,hashlib.sha256(step['challenge_token'].encode()).hexdigest());assert row.pending_secret and data['secret'] not in row.pending_secret
    result=c.post('/api/v1/auth/mfa/enroll/confirm',json={'challenge_token':step['challenge_token'],'code':pyotp.TOTP(data['secret']).now()})
    assert result.status_code==200 and len(result.json()['recovery_codes'])==10
    h={'Authorization':'Bearer '+result.json()['access_token']};assert c.get('/api/v1/auth/me',headers=h).status_code==200
    with transaction(app.state.engine) as s:
        assert data['secret'] not in s.get(MfaFactor,identity).encrypted_secret
        assert all('-' not in r.code_hash for r in s.scalars(select(MfaRecoveryCode).where(MfaRecoveryCode.user_id==identity)))
        audit=' '.join(r.details_json for r in s.scalars(select(m.AuditEvent)));assert data['secret'] not in audit and step['challenge_token'] not in audit
    assert c.post('/api/v1/auth/mfa/enroll/confirm',json={'challenge_token':step['challenge_token'],'code':pyotp.TOTP(data['secret']).now()}).status_code==401
    assert pending(c)['status']=='MFA_REQUIRED'


def test_mfa_challenge_five_attempts_commit_and_expiry(env):
    app,c,_=env;new_manager(env);step=pending(c);token=step['challenge_token']
    c.post('/api/v1/auth/mfa/enroll/start',json={'challenge_token':token})
    for _ in range(5):assert c.post('/api/v1/auth/mfa/enroll/confirm',json={'challenge_token':token,'code':'invalid-code'}).status_code==401
    with transaction(app.state.engine,True) as s:
        row=s.get(MfaChallenge,hashlib.sha256(token.encode()).hexdigest());assert row.attempts==5
    assert c.post('/api/v1/auth/mfa/enroll/confirm',json={'challenge_token':token,'code':'123456'}).status_code==401
    step=pending(c)
    with transaction(app.state.engine,True) as s:s.get(MfaChallenge,hashlib.sha256(step['challenge_token'].encode()).hexdigest()).expires_at='2000-01-01T00:00:00Z'
    assert c.post('/api/v1/auth/mfa/enroll/start',json={'challenge_token':step['challenge_token']}).status_code==401


def test_mfa_replay_and_concurrent_recovery_accept_once(env):
    app,c,_=env;email='manager@buildtrust.demo';step=pending(c,email,'Test-Demo-Password!2026')
    state=c.mfa_cache[email];code=pyotp.TOTP(state['secret']).at(state['counter']*30)
    assert c.post('/api/v1/auth/mfa/verify',json={'challenge_token':step['challenge_token'],'code':code}).status_code==401
    step=pending(c,email,'Test-Demo-Password!2026');body={'challenge_token':step['challenge_token'],'code':state['codes'].pop(0)}
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(lambda _:c.post('/api/v1/auth/mfa/verify',json=body).status_code,range(2)))
    assert sorted(statuses)==[200,401]
    another=pending(c,email,'Test-Demo-Password!2026')
    assert c.post('/api/v1/auth/mfa/verify',json={**body,'challenge_token':another['challenge_token']}).status_code==401


def test_password_recovery_does_not_remove_mfa_and_required_role_cannot_disable(env):
    app,c,h=env;email='manager@buildtrust.demo'
    assert c.post('/api/v1/auth/mfa/disable',headers=h['manager'],json={'current_password':'Test-Demo-Password!2026','code':'123456'}).status_code==403
    users=c.get('/api/v1/administration/users',headers=h['admin']).json();identity=next(u['id'] for u in users if u['email']==email)
    issued=c.post(f'/api/v1/administration/users/{identity}/recovery',headers=h['admin']).json()['token']
    assert c.post('/api/v1/auth/password/reset',json={'token':issued,'new_password':'Recovered-MFA-2026!'}).status_code==200
    assert pending(c,email,'Recovered-MFA-2026!')['status']=='MFA_REQUIRED'
    with transaction(app.state.engine) as s:assert s.get(MfaFactor,identity)
    assert c.get('/api/v1/auth/me',headers=h['manager']).status_code==401


def test_optional_factor_enrollment_regeneration_and_disable_revoke_old_sessions(env):
    app,c,h=env
    password='Test-Demo-Password!2026'
    start=c.post('/api/v1/auth/mfa/enroll/start',headers=h['operator'],json={'current_password':password})
    assert start.status_code==200
    setup=start.json()
    confirmed=c.post('/api/v1/auth/mfa/enroll/confirm',json={'challenge_token':setup['challenge_token'],'code':pyotp.TOTP(setup['secret']).now()})
    assert confirmed.status_code==200
    enrolled=confirmed.json();first={'Authorization':'Bearer '+enrolled['access_token']}
    assert c.get('/api/v1/auth/me',headers=h['operator']).status_code==401
    renewed=c.post('/api/v1/auth/mfa/recovery-codes/regenerate',headers=first,json={'current_password':password,'code':enrolled['recovery_codes'][0]})
    assert renewed.status_code==200
    new=renewed.json();second={'Authorization':'Bearer '+new['access_token']}
    assert len(new['recovery_codes'])==10 and set(new['recovery_codes']).isdisjoint(enrolled['recovery_codes'])
    assert c.get('/api/v1/auth/me',headers=first).status_code==401
    disabled=c.post('/api/v1/auth/mfa/disable',headers=second,json={'current_password':password,'code':new['recovery_codes'][0]})
    assert disabled.status_code==200 and c.get('/api/v1/auth/me',headers=second).status_code==401
    assert 'access_token' in pending(c,'operator@buildtrust.demo',password)
    with transaction(app.state.engine) as session:
        user=session.scalar(select(m.User).where(m.User.email=='operator@buildtrust.demo'))
        assert session.get(MfaFactor,user.id) is None


def test_current_role_and_session_assurance_cannot_be_forged(env):
    app,c,h=env
    with transaction(app.state.engine,True) as s:
        user=s.scalar(select(m.User).where(m.User.role=='FINANCE_MANAGER'));weak=token_for(user,app.state.secret,s)
    assert c.get('/api/v1/projects',headers={'Authorization':'Bearer '+weak}).status_code==401
    assert c.post('/api/v1/auth/mfa/reset',headers=h['admin'],json={}).status_code in (404,405)


def test_owner_mfa_reset_revokes_authority_and_requires_reenrollment(env):
    app,c,h=env
    with transaction(app.state.engine,True) as s:
        user=s.scalar(select(m.User).where(m.User.role=='FINANCE_MANAGER'));mfa.reset_factor(s,user,owner=True)
    assert c.get('/api/v1/auth/me',headers=h['manager']).status_code==401
    assert pending(c,'manager@buildtrust.demo','Test-Demo-Password!2026')['status']=='MFA_SETUP_REQUIRED'


def test_missing_mfa_key_never_generates_over_existing_factors(env):
    app,c,_=env;path=app.state.settings.data_dir/'mfa-encryption-key';original=path.read_bytes();path.unlink()
    try:
        with pytest.raises(Exception) as exc:mfa.key(app.state.settings,create=True)
        assert getattr(exc.value,'code',None)=='MFA_KEY_UNAVAILABLE' and not path.exists()
    finally:path.write_bytes(original)


def test_csrf_host_metadata_and_source_map_boundaries(env):
    _,c,h=env
    assert c.post('/api/v1/auth/login',headers={'Origin':'https://evil.example'},json={}).status_code==403
    assert c.post('/api/v1/auth/logout',headers={**h['operator'],'Sec-Fetch-Site':'cross-site','Origin':'http://127.0.0.1:8000'}).status_code==403
    assert c.get('/api/v1/projects',headers={**h['operator'],'Host':'evil.example'}).status_code==400
    marker=c.headers.pop('X-BuildTrust-Request')
    try:assert c.post('/api/v1/auth/logout',headers=h['operator']).status_code==403
    finally:c.headers['X-BuildTrust-Request']=marker
    assert c.get('/assets/missing.js.map').status_code==404
    assert c.post('/api/v1/auth/logout',headers={**h['operator'],'Origin':'http://127.0.0.1:8000','Sec-Fetch-Site':'same-origin'}).status_code==200


@pytest.mark.parametrize('url',['http://api.frankfurter.dev/v2','https://api.frankfurter.dev:8443/v2','https://u:p@api.frankfurter.dev/v2','https://127.0.0.1/','file:///etc/passwd','gopher://api.frankfurter.dev/','https://api.frankfurter.dev/#private'])
def test_ssrf_provider_origin_rejects_noncanonical_destinations(env,url):
    from app.price_providers import api_json
    with pytest.raises(ValueError):asyncio.run(api_json('GET',url,env[0].state.settings))


def test_local_model_url_is_pinned_loopback_and_has_no_proxy(env):
    from app.workflow import local_model_url
    settings=env[0].state.settings;settings.ollama_url='http://localhost:11434';assert local_model_url(settings)=='http://127.0.0.1:11434/api/chat'
    for value in ['http://169.254.169.254','http://10.0.0.1','http://localhost:11434/?url=x','http://u:p@localhost:11434']:
        settings.ollama_url=value
        with pytest.raises(ValueError):local_model_url(settings)


def test_provider_ignores_proxy_environment_and_does_not_follow_redirects(env,monkeypatch):
    import httpx
    from app.price_providers import api_json
    original=httpx.AsyncClient
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302,headers={'Location':'http://127.0.0.1/private'})
    def guarded_client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(handler),**kwargs)
    monkeypatch.setenv('HTTPS_PROXY','http://127.0.0.1:9')
    monkeypatch.setattr(httpx,'AsyncClient',guarded_client)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(api_json('GET','https://api.frankfurter.dev/v2/currencies',env[0].state.settings))
    assert calls==['https://api.frankfurter.dev/v2/currencies']


def test_weak_signing_key_fails_without_replacing_existing_material(tmp_path):
    from app.config import Settings
    settings=Settings(data_dir=tmp_path)
    path=tmp_path/'signing-secret';path.write_text('too-short')
    with pytest.raises(ValueError,match='too short'):settings.signing_secret()
    assert path.read_text()=='too-short'
    strong='synthetic-test-key-with-at-least-32-bytes'
    path.write_text(strong)
    assert settings.signing_secret()==strong and path.read_text()==strong


def test_sql_payload_is_data_and_apostrophes_stay_usable(env):
    _,c,h=env;pid=c.get('/api/v1/projects',headers=h['operator']).json()[0]['id']
    before=c.get(f'/api/v1/registers/invoices?project_id={pid}',headers=h['operator']).json()['total']
    for text in ["' OR 1=1 --","'; DROP TABLE invoices; --","O'Brien"]:
        r=c.get('/api/v1/registers/invoices',params={'project_id':pid,'q':text},headers=h['operator']);assert r.status_code==200 and r.json()['total']==0
    assert c.get('/api/v1/registers/invoices',params={'project_id':pid,'order':'desc; DROP TABLE invoices; --'},headers=h['operator']).status_code==422
    from app.seed import demo_payloads
    payload={**demo_payloads()['scenario-b-valid'],'invoice_number':"O'Brien-2026"}
    uploaded=c.post('/api/v1/documents/upload',data={'project_id':str(pid)},files={'file':('ordinary.json',json.dumps(payload).encode(),'application/json')},headers=h['operator'])
    assert uploaded.status_code==201
    assert c.get('/api/v1/registers/invoices',params={'project_id':pid,'q':"O'Brien"},headers=h['operator']).json()['total']==1
    assert c.get(f'/api/v1/registers/invoices?project_id={pid}',headers=h['operator']).json()['total']==before+1


def test_current_database_role_requires_mfa_even_without_claim_changes(env):
    app,c,h=env
    with transaction(app.state.engine,True) as s:
        user=s.scalar(select(m.User).where(m.User.email=='operator@buildtrust.demo'));user.role='FINANCE_MANAGER'
    assert c.get('/api/v1/projects',headers=h['operator']).status_code==401


def test_mfa_backup_restores_key_and_factors_but_not_old_sessions(env,tmp_path):
    from app.local_security import backup,restore
    from app.config import Settings
    from app.main import create_app
    from conftest import GuardedTestClient
    app,c,h=env;archive=tmp_path/'mfa.private.zip';target=tmp_path/'restored-mfa'
    assert backup(app.state.settings,archive)['passed'];assert restore(archive,target)['passed']
    assert (target/'mfa-encryption-key').read_bytes()==(app.state.settings.data_dir/'mfa-encryption-key').read_bytes()
    recovered=create_app(Settings(data_dir=target,background_jobs=False))
    try:
        with GuardedTestClient(recovered) as other:
            assert other.get('/api/v1/auth/me',headers=h['manager']).status_code==401
            step=pending(other,'manager@buildtrust.demo','Test-Demo-Password!2026');assert step['status']=='MFA_REQUIRED'
            result=other.post('/api/v1/auth/mfa/verify',json={'challenge_token':step['challenge_token'],'code':c.mfa_cache['manager@buildtrust.demo']['codes'][-1]})
            assert result.status_code==200
            assert other.get('/api/v1/projects',headers={'Authorization':'Bearer '+result.json()['access_token']}).status_code==200
    finally:recovered.state.engine.dispose()


@pytest.mark.parametrize('name,content,mime',[('payload.svg',b'<svg onload="alert(1)"/>','image/svg+xml'),('fake.pdf',b'<html><script>alert(1)</script></html>','application/pdf'),('fake.xlsx',b'not-a-zip','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')])
def test_upload_disguised_executable_content_is_not_accepted(env,name,content,mime):
    _,c,h=env;pid=c.get('/api/v1/projects',headers=h['operator']).json()[0]['id']
    before=len(c.get('/api/v1/documents',params={'project_id':pid},headers=h['operator']).json())
    result=c.post('/api/v1/documents/upload',data={'project_id':str(pid)},files={'file':(name,content,mime)},headers=h['operator'])
    assert result.status_code in (400,413,415,422)
    assert len(c.get('/api/v1/documents',params={'project_id':pid},headers=h['operator']).json())==before
