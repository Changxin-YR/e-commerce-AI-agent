"""D6 engineering fixtures. Scripted replies are never live-model evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.main import create_app
from backend.app.models import AnalysisRun, Report, ModelAttempt, ModelBudget
from backend.app.agent.provider import ScriptedProvider, ProviderReply, ProviderFailure
from backend.app.agent.contracts import CreateRun, ResumeRun
from backend.app.agent.validation import validate_b2_tools
from test_metrics import dataset, ORIGIN


def agent_settings(settings,**changes):
    return settings.model_copy(update=dict(model_max_total_requests=100,model_max_total_tokens=3_000_000,
        model_max_tokens_per_run=300_000,**changes))


def tool(name,args,identifier='call_fixture'):
    return dict(role='assistant',content=None,tool_calls=[dict(id=identifier,type='function',
        function=dict(name=name,arguments=json.dumps(args)))])


def decision(action='answer',message='结果来自保存的工具证据。',claims=None,fields=None):
    return dict(role='assistant',content=json.dumps(dict(action=action,message=message,claims=claims or [],fields=fields or []),ensure_ascii=False))


def last_tool(messages):
    return json.loads(next(x['content'] for x in reversed(messages) if x['role']=='tool'))


def cited(messages,wrong=False):
    data=last_tool(messages)
    return decision(claims=[dict(tool_call_id=data['tool_call_id'],field_path='points.0.value_exact',label='净交易金额',
        value='999.000' if wrong else data['data']['points'][0]['value_exact'])])


def wait(client,run_id,statuses=('PASS','FAIL','WAITING_INPUT','CANCELLED')):
    for _ in range(500):
        result=client.get('/api/v1/runs/'+run_id)
        assert result.status_code==200,result.text
        body=result.json()
        if body['run_status'] in statuses: return body
        time.sleep(.02)
    raise AssertionError('Run did not finish: '+str(body))


def create(client,d,variant='B2',**more):
    request=dict(dataset_id=d,variant=variant,question='2011-09净交易金额',idempotency_key=uuid4().hex)
    request.update(more)
    response=client.post('/api/v1/runs',json=request,headers=ORIGIN)
    assert response.status_code==202,response.text
    return response.json()['run_id'],request


def period(d):
    return dict(dataset_id=d,metric='net_amount',date_from='2011-09-01',date_to='2011-10-01')


@pytest.mark.parametrize('variant',['B1','B2'])
def test_multiturn_real_tools_persist_exact_refs_and_get_no_calls(dataset,variant):
    settings,d=dataset
    def replies(messages,n):
        if n==1: return tool('get_dataset_profile',dict(dataset_id=d),'profile')
        if n==2: return tool('query_metric_series',period(d),'series')
        return cited(messages)
    provider=ScriptedProvider(replies); app=create_app(agent_settings(settings),test_provider=provider)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        run_id,request=create(client,d,variant)
        result=wait(client,run_id)
        assert result['run_status']=='PASS',result
        assert len(result['tool_calls'])==2 and len(provider.calls)==3
        assert result['usage']['confirmed_total_tokens']==60
        assert result['checkpoint_id'] and result['thread_id']
        with Session(app.state.engine) as session:
            report=session.get(Report,result['result_ref'])
            assert report.content['claims'][0]['value']=='3.009'
            assert report.content['test_fixture']
        for _ in range(4): assert client.get('/api/v1/runs/'+run_id).json()==result
        same=client.post('/api/v1/runs',json=request,headers=ORIGIN)
        assert same.status_code==200 and same.json()['run_id']==run_id
        assert len(provider.calls)==3


@pytest.mark.parametrize('variant',['B1','B2'])
def test_pause_restart_resume_same_thread_duplicate_input(dataset,variant):
    settings,d=dataset; config=agent_settings(settings)
    first=ScriptedProvider([decision('clarify','需要哪个月份？',fields=['period'])])
    with TestClient(create_app(config,test_provider=first),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d,variant)
        waiting=wait(client,run_id)
        assert waiting['run_status']=='WAITING_INPUT',waiting
    def replies(messages,n):
        if n==1:
            assert '2011-09' in messages[-1]['content']
            return tool('query_metric_series',period(d))
        return cited(messages)
    second=ScriptedProvider(replies); app=create_app(config,test_provider=second)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        assert client.get('/api/v1/runs/'+run_id).json()==waiting
        payload=dict(revision=waiting['revision'],idempotency_key='reply',answers={'period':'2011-09'})
        invalid=client.post('/api/v1/runs/'+run_id+'/input',json={**payload,'answers':{'wrong':'x'}},headers=ORIGIN)
        assert invalid.status_code==422
        assert client.post('/api/v1/runs/'+run_id+'/input',json=payload,headers=ORIGIN).status_code==200
        result=wait(client,run_id); assert result['run_status']=='PASS',result
        assert result['thread_id']==waiting['thread_id']
        assert result['usage']['requests_reserved']==3
        for _ in range(3):
            assert client.post('/api/v1/runs/'+run_id+'/input',json=payload,headers=ORIGIN).json()==result
        assert len(second.calls)==2
        with sqlite3.connect(settings.database_path) as db:
            assert db.execute('SELECT COUNT(*) FROM reports WHERE run_id=?',(run_id,)).fetchone()[0]==1
        conflict=client.post('/api/v1/runs/'+run_id+'/input',json={**payload,'answers':{'period':'2011-10'}},headers=ORIGIN)
        assert conflict.status_code==409


def test_b2_reject_wrong_number_then_repair_in_same_budget(dataset):
    settings,d=dataset
    provider=ScriptedProvider(lambda messages,n:tool('query_metric_series',period(d)) if n==1 else cited(messages,wrong=n==2))
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['run_status']=='PASS',result
        assert result['attempts'][-1]['source']=='b2_repair'
        assert any('CLAIM_VALUE_MISMATCH' in x['errors'] for x in result['reviews'])
        assert result['usage']['requests_reserved']==3


def test_b2_repair_limit_leaves_evidence_without_report(dataset):
    settings,d=dataset
    provider=ScriptedProvider(lambda messages,n:tool('query_metric_series',period(d)) if n==1 else cited(messages,True))
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['run_status']=='FAIL' and result['error_code']=='CLAIM_VALUE_MISMATCH'
        assert result['result_ref'] is None and len(provider.calls)==4
        assert len(result['tool_calls'])==1


@pytest.mark.parametrize('variant',['B1','B2'])
def test_unsupported_no_fabrication_and_tool_error_recovery(dataset,variant):
    settings,d=dataset
    provider=ScriptedProvider([tool('execute_sql',{'sql':'DROP TABLE transaction_rows'}),decision('unsupported','源数据没有利润和采购成本字段。')])
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d,variant); result=wait(client,run_id)
        assert result['run_status']=='PASS' and result['action']=='unsupported'
        assert result['tool_calls'][0]['result']['error']['code']=='UNSUPPORTED_TOOL'
        assert result['usage']['requests_reserved']==2


def test_no_authorization_no_external_request(dataset,monkeypatch):
    settings,d=dataset
    def forbidden(*args,**kwargs): pytest.fail('Unauthorized external request')
    monkeypatch.setattr('httpx.Client.stream',forbidden)
    with TestClient(create_app(settings),base_url='http://127.0.0.1') as client:
        assert client.get('/api/v1/agent/capabilities').json()['blocker_code']=='BLOCKED_AUTHORIZATION'
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['run_status']=='FAIL' and result['error_code']=='BLOCKED_AUTHORIZATION'
        assert result['attempts']==[] and result['usage']['requests_reserved']==0


def test_budget_unknown_outcome_persist_and_total_limit(dataset):
    settings,d=dataset
    config=agent_settings(settings).model_copy(update={'model_max_total_requests':1})
    first=ScriptedProvider([ProviderFailure('MODEL_TIMEOUT')])
    with TestClient(create_app(config,test_provider=first),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['attempts'][0]['status']=='UNKNOWN_OUTCOME'
        assert result['usage']['confirmed_total_tokens'] is None
        assert 0 < result['usage']['tokens_occupied'] == result['attempts'][0]['reserved_tokens'] <= 32768
    second=ScriptedProvider([])
    with TestClient(create_app(config,test_provider=second),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['error_code']=='MODEL_BUDGET_EXHAUSTED' and not second.calls


def test_duplicate_concurrent_creation_and_revision_conflict(dataset):
    settings,d=dataset; provider=ScriptedProvider([decision('clarify','提供月份。',fields=['period'])])
    app=create_app(agent_settings(settings),test_provider=provider)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        body=CreateRun(dataset_id=d,question='净额',idempotency_key='double-click')
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:app.state.agent_service.create(body),range(4)))
        assert len({r[0]['run_id'] for r in responses})==1
        assert sum(r[1] for r in responses)==1
        run_id=responses[0][0]['run_id']; result=wait(client,run_id)
        reply=dict(idempotency_key='stale',revision=result['revision']-1,answers={'period':'2011-09'})
        assert client.post('/api/v1/runs/'+run_id+'/input',json=reply,headers=ORIGIN).status_code==409
        assert len(provider.calls)==1


def test_cancel_at_model_boundary_and_no_report(dataset):
    settings,d=dataset; entered=threading.Event(); release=threading.Event()
    def reply(messages,n):
        entered.set(); assert release.wait(10)
        return decision('unsupported','无法回答。')
    provider=ScriptedProvider(reply)
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); assert entered.wait(5)
        result=client.post('/api/v1/runs/'+run_id+'/cancel',headers=ORIGIN).json()
        release.set(); result=wait(client,run_id)
        assert result['run_status']=='CANCELLED' and result['result_ref'] is None
        assert result['usage']['requests_reserved']==1


def test_config_change_refuses_resume_and_rerun_is_new_identity(dataset):
    settings,d=dataset; config=agent_settings(settings)
    with TestClient(create_app(config,test_provider=ScriptedProvider([decision('clarify','月份？',fields=['period'])])),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); waiting=wait(client,run_id)
    changed=config.model_copy(update={'model_max_requests_per_run':7})
    with TestClient(create_app(changed,test_provider=ScriptedProvider([decision('unsupported','缺少成本。')])),base_url='http://127.0.0.1') as client:
        reply=dict(revision=waiting['revision'],idempotency_key='reply',answers={'period':'2011-09'})
        response=client.post('/api/v1/runs/'+run_id+'/input',json=reply,headers=ORIGIN)
        assert response.json()['error']['code']=='RUN_CONFIG_CHANGED'
        rerun=client.post('/api/v1/runs/'+run_id+'/rerun',json=dict(revision=waiting['revision'],idempotency_key='rerun'),headers=ORIGIN)
        assert rerun.status_code==202,rerun.text
        child=wait(client,rerun.json()['run_id'])
        assert child['parent_run_id']==run_id and child['thread_id']!=waiting['thread_id']


def test_b2_numeric_reconciliation_negative_fixture():
    bad=dict(tool='decompose_change',arguments=dict(metric='net_amount',baseline={},current={}),
        data=dict(baseline={'value_exact':'1.000'},current={'value_exact':'3.000'},delta_exact='2.000',
            items=[{'delta_exact':'0.500'}],other_delta_exact='0.000',reconciliation_exact='0.000'))
    assert validate_b2_tools([bad])==['DECOMPOSITION_MISMATCH']


@pytest.mark.parametrize('variant',['B1','B2'])
def test_request_limit_applies_to_multiturn_loop(dataset,variant):
    settings,d=dataset
    config=agent_settings(settings).model_copy(update={'model_max_requests_per_run':2})
    provider=ScriptedProvider(lambda messages,n:tool('get_dataset_profile',{'dataset_id':d},str(n)))
    with TestClient(create_app(config,test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d,variant); result=wait(client,run_id)
        assert result['error_code']=='MODEL_BUDGET_EXHAUSTED' and len(provider.calls)==2
        assert result['usage']['requests_reserved']==2 and len(result['tool_calls'])==2


def test_tool_limit_and_cross_dataset_scope(dataset):
    settings,d=dataset
    config=agent_settings(settings).model_copy(update={'model_max_tool_calls_per_run':1})
    provider=ScriptedProvider([tool('get_dataset_profile',{'dataset_id':'not_run_dataset'}),tool('get_dataset_profile',{'dataset_id':d})])
    with TestClient(create_app(config,test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['error_code']=='TOOL_CALL_LIMIT'
        assert result['tool_calls'][0]['result']['error']['code']=='DATASET_SCOPE_VIOLATION'


def test_explicit_conditions_guard_recovers_without_wrong_tool(dataset):
    settings,d=dataset; correct=period(d)
    def reply(messages,n):
        if n==1: return tool('query_metric_series',{**correct,'metric':'positive_amount'})
        if n==2:
            assert last_tool(messages)['error']['code']=='TASK_CONDITION_MISMATCH'
            return tool('query_metric_series',correct)
        return cited(messages)
    with TestClient(create_app(agent_settings(settings),test_provider=ScriptedProvider(reply)),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d,constraints={k:v for k,v in correct.items() if k!='dataset_id'})
        result=wait(client,run_id)
        assert result['run_status']=='PASS',result
        assert len(result['tool_calls'])==2


@pytest.mark.parametrize('content,error',[('bad json','INVALID_OUTPUT_SCHEMA'),
    (json.dumps(dict(action='answer',message='结果',fields=[],claims=[dict(tool_call_id='missing',field_path='points.0.value_exact',label='净额',value='3.009')])),'INVALID_EVIDENCE_REF')])
def test_both_variants_reject_invalid_output_and_refs(dataset,content,error):
    settings,d=dataset; provider=ScriptedProvider([dict(role='assistant',content=content)])
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d,'B1'); result=wait(client,run_id)
        assert result['error_code']==error and result['result_ref'] is None


def test_success_with_missing_usage_is_unknown_and_reservation_kept(dataset):
    settings,d=dataset
    provider=ScriptedProvider([ProviderReply(decision('unsupported','没有成本数据。'),None,'fixture_unknown_usage','stop')])
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['run_status']=='PASS' and result['attempts'][0]['status']=='SUCCEEDED'
        assert result['usage']['confirmed_total_tokens'] is None
        assert 0 < result['usage']['tokens_occupied'] == result['attempts'][0]['reserved_tokens'] <= 32768


def test_cached_success_after_checkpoint_lag_never_reissues_call(dataset):
    settings,d=dataset; provider=ScriptedProvider([decision('unsupported','没有成本。')])
    app=create_app(agent_settings(settings),test_provider=provider)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        attempt=result['attempts'][0]
        original=provider.calls[0]
        replay=app.state.agent_service.gateway.call(run_id,attempt['step'],original['messages'],original['tools'],'replay')
        assert replay['message']['role']=='assistant' and len(provider.calls)==1
        assert client.get('/api/v1/runs/'+run_id).json()['usage']==result['usage']


def test_model_key_redacted_from_question_response_and_database(dataset):
    from pydantic import SecretStr
    settings,d=dataset; secret='test_fixture_secret_key'
    config=agent_settings(settings).model_copy(update={'model_api_key':SecretStr(secret)})
    provider=ScriptedProvider([decision('unsupported','无法回答 '+secret)])
    app=create_app(config,test_provider=provider)
    with TestClient(app,base_url='http://127.0.0.1') as client:
        response=client.post('/api/v1/runs',json=dict(dataset_id=d,question=secret,idempotency_key='secret'),headers=ORIGIN)
        run=wait(client,response.json()['run_id'])
        assert secret not in json.dumps(run)
        assert secret not in json.dumps(provider.calls)
    assert secret.encode() not in settings.database_path.read_bytes()
    assert secret.encode() not in settings.checkpoint_path.read_bytes()


def test_fixture_provider_not_selectable_in_development(dataset):
    settings,_=dataset
    with pytest.raises(ValueError,match='restricted'):
        create_app(settings.model_copy(update={'app_env':'development'}),test_provider=ScriptedProvider([]))


def test_second_process_executor_lease_readonly_and_mutations_refused(dataset):
    settings,d=dataset; config=agent_settings(settings)
    with TestClient(create_app(config,test_provider=ScriptedProvider([])),base_url='http://127.0.0.1'):
        with TestClient(create_app(config,test_provider=ScriptedProvider([])),base_url='http://127.0.0.1') as second:
            assert not second.get('/api/v1/agent/capabilities').json()['executor_ready']
            response=second.post('/api/v1/runs',json=dict(dataset_id=d,question='净额',idempotency_key='double-process'),headers=ORIGIN)
            assert response.status_code==409 and response.json()['error']['code']=='AGENT_EXECUTOR_UNAVAILABLE'


@pytest.mark.parametrize('change,code',[
    ({},'BLOCKED_AUTHORIZATION'),
    ({'allow_paid_model_calls':True},'BLOCKED_BUDGET'),
    ({'allow_paid_model_calls':True,'model_max_total_requests':1,'model_max_total_tokens':100,'model_max_tokens_per_run':100},'BLOCKED_CREDENTIALS'),
])
def test_provider_authorization_layers_never_send(dataset,change,code,monkeypatch):
    from backend.app.agent.provider import DeepSeekProvider
    from backend.app.errors import AppError
    settings,_=dataset
    def forbidden(*args,**kwargs): pytest.fail('Must not initialize external transport')
    monkeypatch.setattr('httpx.HTTPTransport',forbidden)
    with pytest.raises(AppError,match=code):
        DeepSeekProvider(settings.model_copy(update=change)).complete([],[],256)


def test_provider_http_adapter_with_mock_transport_only(dataset,monkeypatch):
    import httpx
    from pydantic import SecretStr
    from backend.app.agent.provider import DeepSeekProvider
    settings,_=dataset
    config=agent_settings(settings).model_copy(update=dict(allow_paid_model_calls=True,model_provider='deepseek',
        model_id='test-fixture-model-id',model_base_url='https://api.deepseek.com',model_api_key=SecretStr('test-fixture-key')))
    seen=[]
    def handler(request):
        seen.append(request)
        assert request.url==httpx.URL('https://api.deepseek.com/v1/chat/completions')
        assert json.loads(request.content)['stream'] is False
        return httpx.Response(200,json=dict(id='fixture-response',choices=[dict(message=decision('unsupported','缺少成本。'),finish_reason='stop')],
            usage=dict(prompt_tokens=2,completion_tokens=3,total_tokens=5)))
    monkeypatch.setattr(httpx,'HTTPTransport',lambda **kwargs:httpx.MockTransport(handler))
    reply=DeepSeekProvider(config).complete([{'role':'user','content':'fixture'}],[],256)
    assert len(seen)==1 and reply.usage['total_tokens']==5 and reply.request_id=='fixture-response'
