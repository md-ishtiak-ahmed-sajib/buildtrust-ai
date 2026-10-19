import pytest
from app.finance import business_date
from test_accounting_controls import control
from test_commercial import commercial_setup


def taxable_payable(env, treatment='RECOVERABLE', retention='5'):
    _, client, h = env
    project, original, line, *_ = commercial_setup(env)
    policy = control(env, project, {'kind': 'ACCOUNTING_POLICY', 'effective_date': str(business_date()),
        'tax_treatment': treatment, 'tax_percent': '10'})
    contract = control(env, project, {**original['payload'], 'number': 'TAX-CREDIT-CONTRACT',
        'policy_id': policy['id'], 'tax_percent': '10', 'retention_percent': retention})
    sources = client.get(f'/api/v1/accounting/sources?project_id={project}', headers=h['operator']).json()
    receipt = next(r for r in sources['receipt_lines'] if r['item_code'] == line['code'])
    acceptance = control(env, project, {'kind': 'ACCEPTANCE', 'policy_id': policy['id'], 'receipt_line_id': receipt['id'],
        'cost_code_id': line['cost_code_id'], 'recognition_date': str(business_date())})
    control(env, project, {'kind': 'INTERIM_CERTIFICATE', 'contract_id': contract['id'], 'number': 'TAX-CREDIT-IPC',
        'recognition_date': str(business_date()), 'lines': [{'item_code': line['code'], 'cumulative_quantity': '100'}],
        'acceptance_ids': [acceptance['id']]})
    payable = client.get(f'/api/v1/accounting/balances?project_id={project}', headers=h['auditor']).json()['payables'][0]
    return project, payable, line['cost_code_id']


def credit(payable, code, amount='11000', tax='1000', reference='TAX-CN-001', **extra):
    return {'kind': 'CREDIT_NOTE', 'payable_id': payable['id'], 'expected_payable_version': payable['version'],
        'cost_code_id': code, 'recognition_date': str(business_date()), 'reference': reference,
        'amount': amount, 'tax_amount': tax, 'allocation_evidence': 'Fictional supplier tax-credit and retention allocation evidence', **extra}


@pytest.mark.parametrize('treatment', ['RECOVERABLE', 'NONRECOVERABLE'])
def test_tax_and_retention_credit_reconcile_and_do_not_release_quantity(env, treatment):
    _, client, h = env
    project, payable, code = taxable_payable(env, treatment)
    first = control(env, project, credit(payable, code))
    assert first['calculated']['base_minor'] == 1_000_000
    summary = client.get(f'/api/v1/accounting/summary?project_id={project}', headers=h['auditor']).json()
    assert summary['incurred_cost'] == ('60000.00' if treatment == 'RECOVERABLE' else '66000.00')
    assert summary['recorded_cash'] == '1000000.00'
    payable = client.get(f'/api/v1/accounting/balances?project_id={project}', headers=h['auditor']).json()['payables'][0]
    assert payable['remaining'] == '62500.00' and payable['retention'] == '3500.00'
    control(env, project, credit(payable, code, amount='3500', tax='0', reference='RET-CN-002', retention_credit='3500'))
    after = client.get(f'/api/v1/accounting/balances?project_id={project}', headers=h['auditor']).json()['payables'][0]
    assert after['remaining'] == '62500.00' and after['retention'] == '0.00'
    # A return/cancellation is still required to free the accepted physical quantity.
    sources = client.get(f'/api/v1/accounting/sources?project_id={project}', headers=h['auditor']).json()
    assert any(row['recognized'] for row in sources['receipt_lines'])
    missing = credit(after, code, amount='1', tax=None, reference='UNALLOCATED')
    response = client.post('/api/v1/controls', headers=h['operator'], json={
        'project_id': project, 'name': 'Missing tax allocation', 'payload': {**missing, 'evidence': 'Explicit tax basis is required'}})
    assert response.status_code == 422 and 'explicit tax allocation' in response.text


def test_competing_credit_approvals_cannot_overrun_tax_balance(env):
    _, client, h = env
    project, payable, code = taxable_payable(env)
    waiting = control(env, project, credit(payable, code, reference='CONCURRENT-02'), finish=False)
    for action, role in [('submit', 'operator'), ('check', 'manager')]:
        response = client.post(f'/api/v1/controls/{waiting["id"]}/{action}', headers=h[role],
            json={'expected_version': waiting['version']})
        assert response.status_code == 200, response.text
        waiting = response.json()
    control(env, project, credit(payable, code, reference='CONCURRENT-01'))
    denied = client.post(f'/api/v1/controls/{waiting["id"]}/approve', headers=h['admin'],
        json={'expected_version': waiting['version']})
    assert denied.status_code == 409
    current = client.get(f'/api/v1/accounting/balances?project_id={project}', headers=h['auditor']).json()['payables'][0]
    excessive = credit(current, code, amount='7000', tax='7000', reference='EXCESS-TAX')
    denied = client.post('/api/v1/controls', headers=h['operator'], json={
        'project_id': project, 'name': 'Excess tax credit', 'payload': {**excessive, 'evidence': 'Cumulative tax boundary'}})
    assert denied.status_code == 422 and 'supported base cost or tax' in denied.text


def test_post_settlement_tax_credit_creates_supplier_asset_without_cash_refund(env):
    _, client, h = env
    project, payable, code = taxable_payable(env, retention='0')
    proposal = client.post(f'/api/v1/payables/{payable["id"]}/installments', headers=h['operator'],
        json={'expected_version': payable['version'], 'amount': '77000'}).json()
    approved = client.post(f'/api/v1/payments/{proposal["id"]}/approve', headers=h['manager'])
    assert approved.status_code == 200, approved.text
    result = client.post(f'/api/v1/payments/{proposal["id"]}/execute', headers={**h['manager'], 'Idempotency-Key': 'tax-credit-paid'})
    assert result.status_code == 200, result.text
    assert result.json()['balance_after'] == '923000.00'
    payable = client.get(f'/api/v1/accounting/balances?project_id={project}', headers=h['auditor']).json()['payables'][0]
    control(env, project, credit(payable, code))
    result = client.get(f'/api/v1/accounting/balances?project_id={project}', headers=h['auditor']).json()['payables'][0]
    assert result['remaining'] == '0.00' and result['supplier_credit'] == '11000.00'
    summary = client.get(f'/api/v1/accounting/summary?project_id={project}', headers=h['auditor']).json()
    assert summary['recorded_cash'] == '923000.00'
