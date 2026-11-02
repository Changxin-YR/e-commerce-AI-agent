"""D3 test_fixture transactions, never used as real UCI business evidence."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import sqlite3
import subprocess
import sys
import time

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.app.config import PROJECT_ROOT, Settings
from backend.app.errors import AppError
from backend.app.imports.service import ImportService
from backend.app.imports.locks import WriterLease
from backend.app.imports.source import HEADERS, sha256
from backend.app.main import create_app
from backend.app.metrics.contracts import MonthlyParams, SaveQuery, SeriesParams
from backend.app.metrics.service import money
from backend.app.metrics.tools import execute_tool, tool_schemas

ORIGIN = {"Origin": "http://127.0.0.1:5173"}


@pytest.fixture
def dataset(tmp_path):
    settings = Settings(_env_file=None, app_env="test", database_url=f"sqlite:///{(tmp_path/'fixture.db').as_posix()}",
                        raw_data_dir=tmp_path/'raw', import_cache_dir=tmp_path/'uploads')
    cfg = Config(str(PROJECT_ROOT/'backend/alembic.ini'))
    cfg.attributes['settings'] = settings
    command.upgrade(cfg, 'head')
    wb = Workbook()
    ws = wb.active
    ws.title = 'Online Retail'
    ws.append(HEADERS)
    def row(invoice, when, price, quantity=1, country='UK', stock='fixture'):
        return [invoice, stock, 'test_fixture', quantity, datetime.fromisoformat(when), price, None, country]
    duplicate = row('1', '2011-09-01', .005)
    for record in [row('before', '2011-08-31T23:59:59', 99), duplicate, duplicate,
        row('C1', '2011-09-02', .001, -1), row('2', '2011-09-30T23:59:59', 1),
        row('F', '2011-09-15', 2, country='France'),
        row('Cpositive', '2011-09-03', 4), row('zero', '2011-09-04', 0),
        row('negqty', '2011-09-05', 0, -1), row('negprice', '2011-09-06', -1),
        row('1', '2011-10-01', 3), row('last', '2011-12-09', 1)]:
        ws.append(record)
    source = tmp_path/'test_fixture.xlsx'
    wb.save(source)
    service = ImportService(settings, test_hashes=frozenset({sha256(source)}))
    service.start()
    try:
        imported = service.submit(source, background=False)
        assert imported['status'] == 'READY'
    finally:
        service.close()
    return settings, imported['dataset_id']


@pytest.fixture
def api(dataset):
    settings, dataset_id = dataset
    app = create_app(settings)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        yield client, app, dataset_id


def monthly(client, dataset_id, **params):
    return client.get(f'/api/v1/datasets/{dataset_id}/metrics/monthly', params={'month': '2011-09', **params})


@pytest.mark.parametrize('value,exact,display', [(1,'0.001','0.00'),(5,'0.005','0.01'),
    (1009,'1.009','1.01'),(-5,'-0.005','-0.01'),(-1,'-0.001','0.00'),
    (9223372036854775807,'9223372036854775.807','9223372036854775.81')])
def test_exact_money(value, exact, display):
    assert money(value) == (exact, display)


def test_monthly_integer_totals_filters_boundaries_and_quality(api):
    client, app, d = api
    result = monthly(client, d).json()
    assert result['status'] == 'PASS'
    assert (result['positive_amount_exact'],result['cancellation_amount_exact'],result['net_amount_exact']) == ('3.010','0.001','3.009')
    assert (result['positive_amount_display'],result['net_amount_display']) == ('3.01','3.01')
    assert result['positive_invoice_count'] == 3
    assert result['primary_class_counts'] == {'POSITIVE':4, 'CANCELLATION':1, 'EXCLUDED_OTHER':4, 'INVALID':0}
    assert sum(result['primary_class_counts'].values()) == result['matched_row_count'] == result['source_row_count'] == 9
    assert 'INVOICES_SPAN_MONTHS' in result['warnings']
    assert 'MISSING_CUSTOMER_ID_RETAINED' in result['warnings']
    uk = monthly(client, d, country='UK').json()
    assert uk['positive_amount_exact'] == '1.010' and uk['positive_invoice_count'] == 2
    assert uk['source_row_count'] == 9 and uk['matched_row_count'] == 8
    assert monthly(client, d, month='2011-10').json()['net_amount_exact'] == '3.000'
    quality = client.get(f'/api/v1/datasets/{d}/quality').json()
    assert quality['duplicates_retained'] and quality['duplicate_candidates_after_first'] == 1
    assert quality['quality_flags']['MISSING_CUSTOMER_ID'] == 12


@pytest.mark.parametrize('month,status,amount,coverage', [
    ('2011-11','NO_DATA',None,'FULL'), ('2012-01','NO_DATA',None,'NONE'),
    ('2011-12','PARTIAL_PERIOD','1.000','PARTIAL'), ('2011-08','PARTIAL_PERIOD','99.000','PARTIAL')])
def test_no_data_gap_and_partial_period(api, month, status, amount, coverage):
    client, _, d = api
    result = monthly(client, d, month=month).json()
    assert (result['status'],result['net_amount_exact'],result['coverage']['status']) == (status,amount,coverage)
    if status == 'NO_DATA':
        assert result['positive_invoice_count'] is None


def test_empty_filter_is_zero_and_literal_not_sql(api):
    client, _, d = api
    for country in ['NoSuchCountry', "' OR 1=1 --", 'uk', ' UK']:
        result = monthly(client,d,country=country).json()
        assert result['status'] == 'EMPTY_RESULT' and result['net_amount_exact'] == '0.000'
        assert result['positive_invoice_count'] == 0 and result['source_row_count'] == 9
    assert monthly(client,d,month='2012-01',country='UK').json()['status'] == 'NO_DATA'
    result = monthly(client,d,month='2011-12',country='France').json()
    assert result['status'] == 'EMPTY_RESULT' and result['coverage']['status'] == 'PARTIAL'


@pytest.mark.parametrize('query', ['month=2011-13','month=0000-01','month=9999-12', 'month=2011-9',
    'month=2011-09&sql=SELECT+1','month=2011-09&file=C:/private','month=2011-09&country=',
    'month=2011-09&month=2011-10','month=2011-09&country=UK&country=France'])
def test_bad_monthly_parameters(api, query):
    client, _, d = api
    result = client.get(f'/api/v1/datasets/{d}/metrics/monthly?{query}')
    assert result.status_code == 422
    assert result.json()['error']['code'] == 'VALIDATION_ERROR'


def test_series_gaps_clipped_months_and_invoice_counts(api):
    client, _, d = api
    path=f'/api/v1/datasets/{d}/metrics/series'
    result = client.get(path,params=dict(metric='net_amount',date_from='2011-09-01',date_to='2012-01-01')).json()
    assert result['status'] == 'PARTIAL_PERIOD'
    assert [p['value_exact'] for p in result['points']] == ['3.009','3.000',None,'1.000']
    assert [p['status'] for p in result['points']] == ['PASS','PASS','NO_DATA','PARTIAL_PERIOD']
    clipped = client.get(path,params=dict(metric='positive_invoice_count',date_from='2011-09-01',date_to='2011-09-02')).json()
    assert len(clipped['points']) == 1
    assert clipped['status'] == 'PARTIAL_PERIOD' and clipped['points'][0]['value_exact'] == '1'
    assert clipped['points'][0]['included_row_count'] == 2
    assert clipped['points'][0]['period_end_exclusive'] == '2011-09-02'
    assert 'CALENDAR_MONTH_TRUNCATED' in clipped['warnings']


@pytest.mark.parametrize('overrides,code', [({'metric':'profit'},'UNSUPPORTED_METRIC'),
    ({'granularity':'day'},'VALIDATION_ERROR'), ({'date_to':'2011-09-01'},'VALIDATION_ERROR'),
    ({'date_from':'2011-02-29'},'VALIDATION_ERROR'), ({'date_from':'2011-09-01T00:00:00Z'},'VALIDATION_ERROR'),
    ({'date_to':'2015-01-01'},'VALIDATION_ERROR'), ({'region':'UK'},'VALIDATION_ERROR')])
def test_series_rejects_unsupported_inputs(api, overrides, code):
    client, _, d = api
    result = client.get(f'/api/v1/datasets/{d}/metrics/series',params={
        'metric':'net_amount','date_from':'2011-09-01','date_to':'2011-10-01',**overrides})
    assert result.status_code == 422 and result.json()['error']['code'] == code


@pytest.mark.parametrize('state', ['QUEUED','IMPORTING','FAILED'])
def test_non_ready_rejected_and_metadata_is_honest(api, dataset, state):
    client, app, d = api
    with sqlite3.connect(dataset[0].database_path) as db:
        db.execute('UPDATE dataset_snapshots SET status=?',(state,))
    assert monthly(client,d).status_code == 409
    assert client.get(f'/api/v1/datasets/{d}').json()['row_count'] is None
    assert client.get(f'/api/v1/datasets/{d}/quality').status_code == 409
    with pytest.raises(AppError,match='DATASET_NOT_READY'):
        execute_tool(app.state.metric_service,'get_dataset_profile',{'dataset_id':d})


def test_unknown_dataset_and_metric_version(api, dataset):
    client, _, d = api
    assert monthly(client,'missing').status_code == 404
    with sqlite3.connect(dataset[0].database_path) as db:
        db.execute("UPDATE dataset_snapshots SET metric_version='future'")
    assert monthly(client,d).json()['error']['code'] == 'UNSUPPORTED_METRIC_VERSION'


def test_tools_whitelist_schemas_and_equivalence(api):
    client, app, d = api
    service=app.state.metric_service
    assert len(tool_schemas()) == 8
    assert all(s['function']['parameters']['additionalProperties'] is False for s in tool_schemas())
    profile=execute_tool(service,'get_dataset_profile',{'dataset_id':d})
    assert profile['snapshot_hash'] == client.get(f'/api/v1/datasets/{d}').json()['data_hash']
    assert execute_tool(service,'get_metric_definitions',{})['result'] == client.get('/api/v1/metric-definitions').json()
    args=dict(metric='net_amount',date_from='2011-09-01',date_to='2011-10-01')
    result=execute_tool(service,'query_metric_series',dict(dataset_id=d,**args))
    assert result['result'] == client.get(f'/api/v1/datasets/{d}/metrics/series',params=args).json()
    assert result == execute_tool(service,'query_metric_series',dict(dataset_id=d,**args))
    with pytest.raises(AppError,match='UNSUPPORTED_TOOL'):
        execute_tool(service,'execute_sql',{'sql':'SELECT 1'})
    with pytest.raises(AppError,match='VALIDATION_ERROR'):
        execute_tool(service,'get_dataset_profile',{'dataset_id':d,'path':'secret'})


def test_history_idempotence_restart_no_reexecution_and_readonly(api, dataset, monkeypatch):
    client, app, d = api
    path=f'/api/v1/datasets/{d}/queries'
    payload={'idempotency_key':'test_fixture','query':{'kind':'monthly','month':'2011-09'}}
    response=client.post(path,json=payload,headers=ORIGIN)
    assert response.status_code == 201
    saved=response.json()
    def forbidden(*args,**kwargs):
        pytest.fail('History read or idempotent retry must not execute metrics/imports')
    monkeypatch.setattr(app.state.metric_service,'monthly',forbidden)
    monkeypatch.setattr(app.state.import_service,'submit',forbidden)
    retry=client.post(path,json=payload,headers=ORIGIN)
    assert retry.status_code == 200 and retry.json() == saved
    payload['query']['month']='2011-10'
    assert client.post(path,json=payload,headers=ORIGIN).status_code == 409
    assert client.post(path,json=payload).status_code == 403
    before=sha256(dataset[0].database_path)
    assert client.get('/api/v1/queries/'+saved['query_id']).json() == saved
    assert client.get(path).json()['total'] == 1
    assert client.get(path+'?limit=1&offset=1').json()['items'] == []
    assert client.get('/api/v1/queries/missing').status_code == 404
    assert client.get('/api/v1/datasets').json()['total'] == 1
    assert sha256(dataset[0].database_path) == before
    with app.state.engine.connect() as connection, pytest.raises(OperationalError):
        connection.execute(text("UPDATE app_metadata SET value='bad'"))
    restarted=create_app(dataset[0])
    with TestClient(restarted,base_url='http://127.0.0.1') as other:
        monkeypatch.setattr(restarted.state.metric_service,'monthly',forbidden)
        assert other.get('/api/v1/queries/'+saved['query_id']).json() == saved
    assert sha256(dataset[0].database_path) == before


def test_concurrent_save_and_series_history(api, dataset):
    client, app, d = api
    payload=SaveQuery(idempotency_key='concurrent',query=dict(kind='series',metric='net_amount',date_from='2011-09-01',date_to='2011-11-01'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _: app.state.history_service.save(d,payload),range(4)))
    assert sum(created for _,created in results) == 1
    assert len({r.query_id for r,_ in results}) == 1
    assert results[0][0].result.points[0].value_exact == '3.009'
    query_id=results[0][0].query_id
    with sqlite3.connect(dataset[0].database_path) as db:
        db.execute("UPDATE query_history SET result_sha256=?",('0'*64,))
    response=client.get('/api/v1/queries/'+query_id)
    assert response.status_code == 409 and response.json()['error']['code'] == 'HISTORY_INTEGRITY_ERROR'


def test_openapi_describes_real_contract_and_errors(api):
    client,_,d=api
    schema=client.get('/openapi.json').json()
    monthly_route=schema['paths']['/api/v1/datasets/{dataset_id}/metrics/monthly']['get']
    assert {p['name'] for p in monthly_route['parameters']} == {'dataset_id','month','country','stock_code'}
    assert monthly_route['responses']['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse')
    assert schema['info']['version'] == '0.9.0'
    assert client.get('/api/v1/datasets?sql=SELECT+1').status_code == 422
    assert client.get('/api/v1/datasets?limit=101').status_code == 422
    assert client.get('/api/v1/metric-definitions?metric_names=profit').status_code == 422


def test_missing_database_does_not_create_success(tmp_path):
    settings=Settings(_env_file=None,database_url=f"sqlite:///{(tmp_path/'missing.db').as_posix()}")
    with TestClient(create_app(settings),base_url='http://127.0.0.1') as client:
        assert client.get('/api/v1/datasets').status_code == 503
        assert monthly(client,'missing').status_code == 503
    assert not settings.database_path.exists()


@pytest.mark.parametrize('condition',['missing','empty','corrupt'])
def test_verifier_fails_without_real_imported_database(tmp_path,condition):
    path=tmp_path/'not_real.sqlite3'
    if condition=='empty':
        path.touch()
    elif condition=='corrupt':
        path.write_bytes(b'test_fixture_invalid_database')
    before=path.read_bytes() if path.exists() else None
    output=tmp_path/'verification'
    result=subprocess.run([sys.executable,str(PROJECT_ROOT/'scripts/verify_metrics.py'),
        '--database',str(path),'--output',str(output)],capture_output=True)
    assert result.returncode==2
    report=json.loads((output/'verification.json').read_text('utf-8'))
    assert report['status']=='FAIL' and 'servers' not in report
    assert (path.read_bytes() if path.exists() else None)==before


def test_empty_lock_file_contenders_never_initialize_without_ownership(tmp_path):
    path=tmp_path/'test_fixture.lock'
    # Exercise first creation repeatedly, then existing locks, with real OS locks.
    state={'active':0,'entered':0}
    def contender(_):
        for _ in range(12):
            lease=WriterLease(path)
            deadline=time.monotonic()+5
            while not lease.acquire():
                assert time.monotonic()<deadline
                time.sleep(.001)
            try:
                state['active']+=1
                assert state['active']==1
                time.sleep(.001)
                state['entered']+=1
                state['active']-=1
            finally:
                lease.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(contender,range(8)))
    assert state=={'active':0,'entered':96}
