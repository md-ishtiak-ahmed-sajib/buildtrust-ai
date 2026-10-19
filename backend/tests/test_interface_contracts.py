from datetime import datetime, timedelta, timezone
from app.interface_schemas import ErrorResponse, RegisterPage, CommercialSources
from conftest import prepared


def test_error_register_and_source_envelopes_validate(env):
    _, client, h = env
    denied = client.post('/api/v1/controls', headers=h['auditor'], json={})
    assert denied.status_code == 422
    parsed = ErrorResponse.model_validate(denied.json())
    assert parsed.error.request_id == denied.headers['x-request-id']
    assert parsed.error.fields
    project = client.get('/api/v1/projects', headers=h['auditor']).json()[0]['id']
    RegisterPage.model_validate(client.get(f'/api/v1/registers/documents?project_id={project}', headers=h['auditor']).json())
    CommercialSources.model_validate(client.get(f'/api/v1/commercial/sources?project_id={project}', headers=h['auditor']).json())
    schema = client.get('/openapi.json').json()
    assert schema['paths']['/api/v1/controls']['post']['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse')


def test_review_inbox_expiry_is_derived_from_authoritative_approval(env, monkeypatch):
    _, client, h = env
    proposal = prepared(env)
    expires = datetime.fromisoformat(proposal['expires_at'])
    monkeypatch.setattr('app.operations_api.utcnow', lambda: (expires-timedelta(minutes=4)).isoformat().replace('+00:00','Z'))
    def item():
        rows = client.get(f'/api/v1/work-items?project_id={proposal["project_id"]}', headers=h['manager']).json()
        return next(r for r in rows if r['kind']=='payment' and r['id']==proposal['id'])
    assert item()['expiry_state'] == 'EXPIRING' and item()['actionable']
    monkeypatch.setattr('app.operations_api.utcnow', lambda: (expires+timedelta(seconds=1)).isoformat().replace('+00:00','Z'))
    assert item()['expiry_state'] == 'EXPIRED' and not item()['actionable']
