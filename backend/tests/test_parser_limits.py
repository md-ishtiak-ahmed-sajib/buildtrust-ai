"""Real child quotas and pre-parser ingress bounds, with isolated inputs."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.bounded_json import loads
from app.diagnostics import RequestBoundary


def test_json_limits_before_decode(env):
    _, client, headers = env
    body = '{"name":' + '[' * 65 + '0' + ']' * 65 + '}'
    response = client.post('/api/v1/materials', content=body,
                           headers={**headers['operator'], 'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'JSON_LIMIT'
    with pytest.raises(ValueError, match='structure'):
        loads('[' + ','.join('0' for _ in range(100_002)) + ']')
    assert loads('{"text":"[\\\"{{{{", "value":[1,2]}')['value'] == [1, 2]


def test_slow_body_and_disconnect_do_not_enter_parser():
    async def run(disconnected=False):
        calls, messages = [], []
        async def app(*args):
            calls.append(True)
        async def receive():
            if disconnected:
                return {'type': 'http.disconnect'}
            await asyncio.sleep(1)
        async def send(message):
            messages.append(message)
        await RequestBoundary(app, 1024, body_timeout=.01)(
            {'type': 'http', 'method': 'POST', 'path': '/upload', 'headers': []}, receive, send)
        assert not calls
        if not disconnected:
            assert messages[0]['status'] == 408
            assert json.loads(messages[1]['body'])['error']['code'] == 'BODY_TIMEOUT'
        else:
            assert not messages
    asyncio.run(run())
    asyncio.run(run(True))


def test_child_memory_quota_is_enforced():
    # Deliberately tiny, bounded allocation in a separate process. Never constrain pytest/API.
    directory = Path(__file__).resolve().parents[1] / 'app'
    code = '''from parser_limits import constrain
import json
limits = constrain(memory_mb=96, cpu_seconds=5)
try:
    allocation = bytearray(192 * 1024 * 1024)
except MemoryError:
    print(json.dumps({"enforced": True, **limits}))
else:
    raise AssertionError("Child memory quota was not enforced")
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=directory,
                            capture_output=True, text=True, timeout=10, check=True)
    observed = json.loads(result.stdout)
    assert observed['enforced'] is True
    assert observed['memory_bytes'] == 96 * 1024 * 1024
