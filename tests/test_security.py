"""D8 synthetic security regressions; no external network or live model calls."""
import asyncio
import json
import sqlite3
from zipfile import ZipFile, ZIP_BZIP2

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import create_app
from backend.app.models import Report
from backend.app.agent.budget import redact
from backend.app.imports.source import prepare_source
from backend.app.errors import AppError
from test_backend import settings
from test_metrics import dataset, api, ORIGIN
from test_reports import payload


@pytest.mark.parametrize('headers', [
    [('host', '127.0.0.1'), ('host', 'evil.example')],
    [('origin', 'http://127.0.0.1:5173'), ('origin', 'https://evil.example')],
    [('origin', 'null')], [('origin', 'http://127.0.0.1:5173.evil.example')],
    [('origin', 'http://127.0.0.1:5173/')], [('origin', 'http://localhost:9999')],
])
def test_ambiguous_or_untrusted_boundaries_reject(settings, headers):
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        response = client.post('/api/v1/runs', headers=headers, json={})
    assert response.status_code in (400, 403)
    assert response.json()['error']['code'] in ('UNTRUSTED_HOST', 'UNTRUSTED_ORIGIN')


@pytest.mark.parametrize('path', ['/api/v1/runs', '/api/v1/reports', '/api/v1/runs/missing/input'])
def test_json_limit_before_validation_or_mutation(api, path):
    client, app, _ = api
    with sqlite3.connect(app.state.settings.database_path) as db:
        before = db.execute('select count(*) from analysis_runs').fetchone()
    response = client.post(path, content=b' ' * 65537, headers={**ORIGIN, 'content-type': 'application/json'})
    assert response.status_code == 413
    assert response.json()['error']['code'] == 'REQUEST_TOO_LARGE'
    with sqlite3.connect(app.state.settings.database_path) as db:
        assert db.execute('select count(*) from analysis_runs').fetchone() == before


@pytest.mark.parametrize('headers', [{}, {'host': 'evil.example'}, {'origin': 'null'}])
def test_security_headers_on_success_and_error(settings, headers):
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        response = client.get('/healthz', headers=headers)
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert response.headers['cache-control'] == 'no-store'
    assert 'access-control-allow-origin' not in response.headers


def test_redaction_includes_nested_untrusted_keys():
    secret = 'test_fixture_secret'
    value = {secret: [{'prefix-' + secret: secret}], 'safe': 'retained'}
    cleaned = redact(value, secret)
    assert secret not in json.dumps(cleaned)
    assert cleaned['safe'] == 'retained'


def test_report_export_neutralizes_active_markdown_and_html(api):
    client, app, d = api
    report = client.post('/api/v1/reports', json=payload(d), headers=ORIGIN).json()
    attack = '<img src=x onerror=alert(1)> [link](javascript:alert(1))\r\n# forged\n```html'
    with Session(app.state.import_service.engine) as session:
        row = session.get(Report, report['report_id'])
        content = dict(row.content)
        content['message'] = attack
        content['claims'][0]['label'] = attack[:200]
        row.content = content
        session.commit()
    response = client.get('/api/v1/reports/' + report['report_id'] + '/export?format=markdown')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/plain')
    assert response.headers['content-disposition'].startswith('attachment; filename="report-')
    assert '<img' not in response.text and '[link](' not in response.text
    assert '\n# forged' not in response.text and '\r' not in response.text
    assert '&lt;img' in response.text
    assert client.get('/api/v1/reports/' + report['report_id'] + '/export?format=csv').status_code == 422


@pytest.mark.parametrize('path', ['/api/v1/runs', '/api/v1/reports'])
def test_history_pagination_limits(api, path):
    client, _, _ = api
    for query in ('limit=101', 'limit=0', 'offset=-1', 'offset=10001'):
        assert client.get(path + '?' + query).status_code == 422


def test_archive_unsupported_compression_is_rejected(tmp_path):
    archive = tmp_path / 'test_fixture.zip'
    with ZipFile(archive, 'w', compression=ZIP_BZIP2) as z:
        z.writestr('fixture.xlsx', b'not-a-workbook')
    with pytest.raises(AppError) as exc:
        prepare_source(archive, tmp_path/'raw', tmp_path/'cache', float('inf'))
    assert exc.value.code == 'UNSUPPORTED_COMPRESSION'
    assert not (tmp_path/'raw').exists()


@pytest.mark.parametrize('kind,status', [
    ('chunked-overflow', 413), ('lying-length', 413), ('length-mismatch', 400),
    ('duplicate-length', 400), ('invalid-length', 400), ('slow-body', 408),
    ('valid', 204), ('disconnect', None),
])
def test_streamed_body_limits_before_application(kind, status, monkeypatch):
    from backend.app import security
    from backend.app.main import error_response
    monkeypatch.setattr(security, 'API_BODY_TIMEOUT', 0.02)
    invoked, sent = [], []
    headers = [(b'host', b'127.0.0.1')]
    if kind == 'lying-length': headers.append((b'content-length', b'1'))
    if kind == 'length-mismatch': headers.append((b'content-length', b'10'))
    if kind == 'duplicate-length': headers.extend([(b'content-length', b'2')] * 2)
    if kind == 'invalid-length': headers.append((b'content-length', b'-2'))
    messages = [{'type': 'http.request', 'body': b'{}', 'more_body': False}]
    if kind in ('chunked-overflow', 'lying-length'):
        messages = [{'type': 'http.request', 'body': b' ' * 32768, 'more_body': True}] * 3
    if kind == 'disconnect': messages = [{'type': 'http.disconnect'}]

    async def receive():
        if kind == 'slow-body': await asyncio.sleep(0.1)
        return messages.pop(0)

    async def send(message): sent.append(message)

    async def downstream(scope, receive, send):
        invoked.append((await receive())['body'])
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    scope = dict(type='http', path='/api/v1/runs', method='POST', headers=headers, state={})
    asyncio.run(security.BoundedBodyMiddleware(downstream, error_response)(scope, receive, send))
    assert ([m['status'] for m in sent if m['type'] == 'http.response.start'] or [None]) == [status]
    assert invoked == ([b'{}'] if kind == 'valid' else [])
