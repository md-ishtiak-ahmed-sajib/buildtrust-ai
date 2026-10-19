from copy import deepcopy
import json
from sqlalchemy import select

from app import advanced_models as a, models as m
from app.database import transaction
from conftest import approved
from test_accounting_controls import control
from test_advanced_upgrade import demo, estimate


def test_history_refresh_is_append_only_and_settlement_is_invoice_context(env):
    app, client, h = env
    proposal = approved(env)
    with transaction(app.state.engine) as session:
        invoice = session.get(m.Invoice, proposal['invoice_id'])
        line = session.scalar(select(m.POLine).where(m.POLine.po_id == invoice.po_id))
        name, unit = line.description, line.unit
    material = client.post('/api/v1/materials', headers=h['operator'], json={
        'project_id': proposal['project_id'], 'name': name, 'unit': unit, 'specification': {}}).json()
    def snapshots():
        with transaction(app.state.engine) as session:
            return [(row.id, row.payload_json, row.evidence_hash) for row in session.scalars(
                select(a.PriceObservation).where(a.PriceObservation.material_id == material['id'],
                    a.PriceObservation.source_type == 'HISTORICAL_INTERNAL').order_by(a.PriceObservation.id))]
    original = snapshots()
    assert len(original) == 1
    response = client.post(f"/api/v1/materials/{material['id']}/history/refresh", headers=h['operator'])
    assert response.status_code == 200 and snapshots() == original
    payment = client.post(f"/api/v1/payments/{proposal['id']}/execute", headers={**h['manager'], 'Idempotency-Key': 'history-example'})
    assert payment.status_code == 200, payment.text
    response = client.post(f"/api/v1/materials/{material['id']}/history/refresh", headers=h['operator'])
    assert response.status_code == 200
    updated = snapshots()
    assert len(updated) == 2 and updated[0] == original[0]
    payload = json.loads(updated[1][1])
    assert payload['settlement_evidence'][0]['invoice_total_paid_amount'] == '70000.00'
    assert payload['specification'] == {} and 'whole-invoice' in payload['notice']
    client.post(f"/api/v1/materials/{material['id']}/history/refresh", headers=h['operator'])
    assert snapshots() == updated


def test_maturity_comparison_keeps_approved_sources_and_flags_changed_specs(env):
    _, client, h = env
    data = demo(env)
    historical = estimate(client, h, data['estimate_id'])
    for action, role in [('submit', 'operator'), ('check', 'manager'), ('approve', 'admin')]:
        response = client.post(f"/api/v1/estimates/{historical['id']}/{action}", headers=h[role],
                               json={'expected_version': historical['version']})
        assert response.status_code == 200, response.text
        historical = response.json()
    revised = client.post(f"/api/v1/estimates/{historical['id']}/revise", headers=h['operator'],
                         json={'expected_version': historical['version']}).json()
    fields = deepcopy(revised['fields'])
    fields['lines'][0]['components'][0]['unit_price'] = '74000'
    changed = client.patch(f"/api/v1/estimates/{revised['id']}", headers=h['operator'],
                          json={'expected_version': revised['version'], 'name': 'Current maturity comparison', 'fields': fields})
    assert changed.status_code == 200, changed.text
    revised = changed.json()
    payload = {'kind': 'ESTIMATE_MATURITY', 'estimate_id': revised['id'],
        'design_definition': 'Recorded drawings and scope definition only', 'input_evidence': ['Drawing revision SIM-01'],
        'uncertainty_basis': 'No inferred accuracy range or AACE classification', 'historical_estimate_ids': [historical['id']]}
    maturity = control(env, data['project_id'], payload)
    comparison = maturity['calculated']['historical_comparisons'][0]
    assert comparison['snapshot_hash'] == historical['snapshot_hash']
    assert comparison['lines'][0]['rate_difference'] == '4000.000000'
    assert comparison['lines'][0]['rate_change_percent'] == '5.714286'
    assert maturity['calculated']['claimed_classification'] is None
    fields['lines'][0]['description'] += ' changed specification'
    response = client.patch(f"/api/v1/estimates/{revised['id']}", headers=h['operator'],
        json={'expected_version': revised['version'], 'name': revised['name'], 'fields': fields})
    assert response.status_code == 200
    other = control(env, data['project_id'], payload)
    result = other['calculated']['historical_comparisons'][0]['lines'][0]
    assert result['comparison'] == 'REQUIRES_REVIEW' and result['rate_difference'] is None
    # The approved maturity snapshot and historical estimate were not refreshed in place.
    records = client.get(f"/api/v1/controls?project_id={data['project_id']}", headers=h['auditor']).json()
    assert next(r for r in records if r['id'] == maturity['id'])['calculated'] == maturity['calculated']
