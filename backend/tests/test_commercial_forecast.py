from datetime import timedelta
from app.finance import business_date
from test_accounting_controls import control
from test_advanced_upgrade import demo, estimate


def test_reviewed_variation_forecast_mapping_changes_projection_not_cash(env):
    _, client, h = env
    data = demo(env)
    project = data['project_id']
    current = estimate(client, h, data['estimate_id'])
    line = current['fields']['lines'][0]
    policy = control(env, project, {'kind': 'ACCOUNTING_POLICY', 'effective_date': str(business_date())})
    code = client.post('/api/v1/accounting/cost-codes', headers=h['operator'], json={
        'project_id': project, 'code': 'STEEL.DIRECT', 'name': 'Direct steel scope'}).json()
    control(env, project, {'kind': 'SUPPLIER_CHANGE', 'code': 'FICTIONAL-STEEL', 'name': 'Fictional Steel Supplier',
        'beneficiary_token': 'SANDBOX-STEEL-ACCOUNT', 'verification_reference': 'Fictional independent callback evidence', 'verification_attested': True})
    supplier = client.get(f'/api/v1/suppliers?project_id={project}', headers=h['operator']).json()[0]
    contract = control(env, project, {'kind': 'COMMERCIAL_CONTRACT', 'number': 'STEEL-SCOPE-01',
        'direction': 'SUPPLIER', 'supplier_id': supplier['id'], 'policy_id': policy['id'],
        'effective_date': str(business_date()), 'payment_terms_days': 30,
        'lines': [{'code': line['code'], 'description': line['description'], 'quantity': '20', 'unit': 'tonne',
                   'rate': '70000', 'cost_code_id': code['id']}]})
    link_payload = {'kind': 'CONTRACT_ESTIMATE_LINK', 'contract_id': contract['id'], 'item_code': line['code'],
        'estimate_id': current['id'], 'estimate_line_id': line['id'], 'complete_cost_scope_confirmed': True,
        'due_date': str(business_date() + timedelta(days=20))}
    first = control(env, project, link_payload)
    route = f'/api/v1/finance/extended-forecast?project_id={project}&estimate_id={current["id"]}&use_contract_links=true'
    result = client.get(route, headers=h['auditor'])
    assert result.status_code == 200, result.text
    assert result.json()['scenarios'][0]['days'][20]['closing'] == '600000.00'
    control(env, project, {'kind': 'CONTRACT_VARIATION', 'contract_id': contract['id'], 'number': 'STEEL-RATE-01',
        'item_code': line['code'], 'additional_quantity': '0', 'reprice_quantity': '20', 'proposed_rate': '74000',
        'claimed_value': '80000', 'reason': 'Reviewed future rate adjustment'})
    stale = client.get(route, headers=h['auditor']).json()
    assert stale['scenarios'][0]['days'][20]['closing'] == '600000.00'
    assert any('Sources changed' in w for w in stale['warnings'])
    updated = control(env, project, link_payload)
    result = client.get(route, headers=h['auditor']).json()
    assert result['scenarios'][0]['days'][20]['closing'] == '520000.00'
    assert result['recorded_balance'] == '2000000.00'
    assert result['estimated_overlay'][0]['contract_link_id'] == updated['id']
    assert result['estimated_overlay'][0]['amount'] == '1480000.00'
    # Projection and mapping never amend the cost budget or original estimate.
    assert estimate(client, h, current['id'])['cost_total'] == '1400000.00'
    assert first['calculated']['amount'] == '1400000.00'
    escalation = client.get(route + '&scenario=MATERIAL_ESCALATION&material_percent=10', headers=h['auditor']).json()
    assert escalation['scenarios'][0]['days'][20]['closing'] == '520000.00'
