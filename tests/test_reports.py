"""D7 report fixtures; synthetic data is not real model/business validation."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.main import create_app
from backend.app.models import Report
from backend.app.reports import CreateReport
from backend.app.agent.provider import ScriptedProvider
from test_metrics import dataset, api, ORIGIN
from test_agent import agent_settings, create, wait, tool, cited, period


def payload(d, **query):
    return dict(dataset_id=d, idempotency_key=uuid4().hex,
                query=dict(metric='net_amount', date_from='2011-09-01', date_to='2011-10-01', **query))


def test_b0_exact_evidence_exports_idempotence_readonly_restart(dataset):
    settings, d = dataset
    body = payload(d)
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        response = client.post('/api/v1/reports', json=body, headers=ORIGIN)
        assert response.status_code == 201, response.text
        report = response.json(); rid = report['report_id']; run_id = report['run_id']
        assert report['content']['variant'] == 'B0'
        claims = report['content']['claims']
        assert next(c['value'] for c in claims if c['label'] == '2011-09 · 净交易金额') == '3.009'
        assert len(report['evidence']) == 6
        assert client.post('/api/v1/reports', json=body, headers=ORIGIN).json() == report
        assert client.post('/api/v1/reports', json=dict(body, query=dict(body['query'], country='UK')), headers=ORIGIN).status_code == 409
        run = client.get('/api/v1/runs/' + run_id).json()
        assert run['usage']['requests_reserved'] == 0 and run['attempts'] == []
        assert run['usage']['basis'] == 'deterministic_no_model'
        md = client.get(f'/api/v1/reports/{rid}/export?format=markdown')
        assert md.status_code == 200 and '3\\.009' in md.text and 'Content-Disposition' in md.headers
        assert client.get(f'/api/v1/reports/{rid}/export').json() == report
    # Subsequent startup/GETs neither calculate new results nor request the provider.
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        with sqlite3.connect(settings.database_path) as db:
            before = db.execute('select count(*) from reports').fetchone()
        for _ in range(3):
            assert client.get('/api/v1/reports/' + rid).json() == report
            assert client.get('/api/v1/runs/' + run_id).json() == run
        with sqlite3.connect(settings.database_path) as db:
            assert db.execute('select count(*) from reports').fetchone() == before
            assert db.execute('select count(*) from model_attempts').fetchone()[0] == 0


@pytest.mark.parametrize('query,status', [
    ({'date_from':'2012-01-01','date_to':'2012-02-01'}, 'NO_DATA'),
    ({'date_from':'2011-12-01','date_to':'2012-01-01'}, 'PARTIAL_PERIOD'),
    ({'country':'absent'}, 'EMPTY_RESULT'),
])
def test_report_no_data_partial_empty(api, query, status):
    client, app, d = api
    body = payload(d); body['query'].update(query)
    response = client.post('/api/v1/reports', json=body, headers=ORIGIN)
    assert response.status_code == 201, response.text
    report = response.json(); assert report['content']['business_result'] == status
    if status == 'NO_DATA': assert not report['content']['claims']
    if status == 'EMPTY_RESULT': assert all(c['value'] in ('0.000', '0') for c in report['content']['claims'])


def test_b0_comparison_and_rerun_parent(api):
    client, app, d = api
    body = payload(d); body['query'].update(date_from='2011-10-01', date_to='2011-11-01')
    body['baseline'] = dict(date_from='2011-09-01', date_to='2011-10-01')
    report = client.post('/api/v1/reports', json=body, headers=ORIGIN).json()
    assert next(c['value'] for c in report['content']['claims'] if c['label'] == '期间差额') == '-0.009'
    assert len(report['evidence']) == 8
    run = client.get('/api/v1/runs/' + report['run_id']).json()
    reply = dict(revision=run['revision'], idempotency_key='rerun-b0')
    response = client.post('/api/v1/runs/' + run['run_id'] + '/rerun', json=reply, headers=ORIGIN)
    assert response.status_code == 201, response.text
    new = response.json()
    assert new['parent_run_id'] == run['run_id'] and new['thread_id'] != run['thread_id']
    assert new['result_ref'] != report['report_id']
    assert client.post('/api/v1/runs/' + run['run_id'] + '/rerun', json=reply, headers=ORIGIN).json() == new


def test_report_concurrent_same_key_and_no_model(api):
    client, app, d = api
    request = CreateReport(**payload(d))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: app.state.report_service.create(request), range(2)))
    assert len({r[0]['report_id'] for r in results}) == 1
    assert sum(r[1] for r in results) == 1


def test_missing_baseline_marks_only_partial_result(api):
    client, app, d = api
    body = payload(d); body['baseline'] = dict(date_from='2012-01-01', date_to='2012-02-01')
    response = client.post('/api/v1/reports', json=body, headers=ORIGIN)
    assert response.status_code == 201, response.text
    assert response.json()['content']['business_result'] == 'PARTIAL_RESULT'
    assert any(c['value'] == '3.009' for c in response.json()['content']['claims'])


def test_tampered_report_fails_closed_without_repair(api):
    client, app, d = api
    report = client.post('/api/v1/reports', json=payload(d), headers=ORIGIN).json()
    with Session(app.state.import_service.engine) as session:
        row = session.get(Report, report['report_id']); content = json.loads(json.dumps(row.content))
        content['claims'][0]['value'] = '999.000'; row.content = content; session.commit()
    for suffix in ('', '/export', '/export?format=markdown'):
        response = client.get('/api/v1/reports/' + report['report_id'] + suffix)
        assert response.status_code == 409 and response.json()['error']['code'] == 'REPORT_EVIDENCE_MISMATCH'


@pytest.mark.parametrize('variant', ['B1', 'B2'])
def test_agent_report_shared_details_no_extra_model_calls(dataset, variant):
    settings, d = dataset
    provider = ScriptedProvider(lambda messages, n: tool('query_metric_series', period(d)) if n == 1 else cited(messages))
    with TestClient(create_app(agent_settings(settings), test_provider=provider), base_url='http://127.0.0.1') as client:
        run_id, _ = create(client, d, variant); run = wait(client, run_id)
        assert run['run_status'] == 'PASS', run
        report = client.get('/api/v1/reports/' + run['result_ref']).json()
        assert report['content']['claims'][0]['value'] == '3.009'
        assert report['content']['test_fixture']
        assert report['content']['provenance']['data_hash'] == run['data_version']['data_hash']
        for _ in range(3):
            assert client.get('/api/v1/reports/' + run['result_ref'] + '/export').json() == report
        assert len(provider.calls) == 2


@pytest.mark.parametrize('change', [dict(metric='profit'), dict(date_to='2011-09-01'), dict(country="' OR 1=1 --")])
def test_report_parameter_boundary(api, change):
    client, app, d = api
    body = payload(d); body['query'].update(change)
    response = client.post('/api/v1/reports', json=body, headers=ORIGIN)
    if 'country' in change:
        assert response.status_code == 201 and response.json()['content']['business_result'] == 'EMPTY_RESULT'
    else: assert response.status_code == 422


def test_report_origin_and_missing_and_export_format(api):
    client, app, d = api
    assert client.post('/api/v1/reports', json=payload(d)).status_code == 403
    assert client.get('/api/v1/reports/missing').status_code == 404
    assert client.get('/api/v1/reports?limit=1000').status_code == 422
    assert client.get('/api/v1/reports/missing/export?format=html').status_code == 422
