"""Streaming fixtures are offline transport/engineering evidence, never live-model evidence."""
import asyncio
import json
import threading
import time
import httpx
import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient
from backend.app.agent.provider import OpenAICompatibleProvider, ProviderReply, ProviderFailure, ScriptedProvider
from backend.app.agent.streaming import visible_message, run_events
from backend.app.main import create_app
from test_agent import agent_settings, create, wait, tool, decision, cited, period
from test_metrics import dataset, ORIGIN


def configured(settings):
    return agent_settings(settings).model_copy(update=dict(allow_paid_model_calls=True,
        model_provider='openai_compatible', model_id='fixture', model_base_url='https://fixture.invalid/v1',
        model_api_key=SecretStr('fixture-secret')))


def sse(delta=None, finish=None, usage=None):
    body={'id':'fixture-request','choices':[{'index':0,'delta':delta or {},'finish_reason':finish}]}
    if usage:
        body.update(usage=usage,choices=[])
    return 'data: '+json.dumps(body,ensure_ascii=False)+'\r\n\r\n'


def test_provider_streams_content_and_assembles_split_tool_arguments(dataset,monkeypatch):
    settings,_=dataset; updates=[]; requests=[]
    body=sse({'content':'正在'})+sse({'content':'查询。','reasoning_content':'hidden-chain'})
    body+=sse({'tool_calls':[{'index':0,'id':'call_a','function':{'name':'get_dataset_profile','arguments':'{"dataset'}}]})
    body+=sse({'tool_calls':[{'index':0,'function':{'arguments':'_id":"ds_fixture"}'}}]},'tool_calls')
    body+=sse(usage=dict(prompt_tokens=2,completion_tokens=3,total_tokens=5))+'data: [DONE]\n\n'
    def handler(request):
        requests.append(request); payload=json.loads(request.content)
        assert payload['stream'] is True and payload['stream_options']['include_usage'] is True
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=body.encode())
    monkeypatch.setattr(httpx,'HTTPTransport',lambda **kw:httpx.MockTransport(handler))
    reply=OpenAICompatibleProvider(configured(settings)).stream([],[],256,lambda m:updates.append(json.loads(json.dumps(m))))
    assert updates[0]['content']=='正在' and reply.message['content']=='正在查询。'
    assert json.loads(reply.message['tool_calls'][0]['function']['arguments'])=={'dataset_id':'ds_fixture'}
    assert reply.usage['total_tokens']==5 and len(requests)==1
    assert 'hidden-chain' not in json.dumps(updates)


@pytest.mark.parametrize('status,code',[(401,'MODEL_AUTH_ERROR'),(429,'MODEL_RATE_LIMIT'),(404,'MODEL_ENDPOINT_ERROR')])
def test_provider_http_failure_is_actionable_and_never_retried(dataset,monkeypatch,status,code):
    settings,_=dataset; calls=[]
    def handler(request):
        calls.append(request); return httpx.Response(status,json={'secret':'never expose upstream body'})
    monkeypatch.setattr(httpx,'HTTPTransport',lambda **kw:httpx.MockTransport(handler))
    with pytest.raises(ProviderFailure) as failure:
        OpenAICompatibleProvider(configured(settings)).stream([],[],256,lambda _:None)
    assert failure.value.code==code and len(calls)==1


def test_truncated_stream_is_not_a_success(dataset,monkeypatch):
    settings,_=dataset
    monkeypatch.setattr(httpx,'HTTPTransport',lambda **kw:httpx.MockTransport(lambda request:
        httpx.Response(200,headers={'content-type':'text/event-stream'},content=sse({'content':'partial'}))))
    with pytest.raises(ProviderFailure) as failure:
        OpenAICompatibleProvider(configured(settings)).stream([],[],256,lambda _:None)
    assert failure.value.code=='MODEL_STREAM_INTERRUPTED'


def test_partial_json_projects_only_public_message():
    assert visible_message('{"action":"answer","message":"你好，正在')=='你好，正在'
    assert visible_message('{"message":"第一行\\n第二行\\u4f')=='第一行\n第二行'
    assert visible_message('{"message":"已完成","claims":[{"value":"999"')=='已完成'
    assert visible_message('{"action":"answer","claims":[')==''


def test_fixed_task_budget_supports_multiple_model_turns_without_increasing_limit(dataset):
    settings,d=dataset
    provider=ScriptedProvider(lambda messages,n:tool('query_metric_series',period(d)) if n==1 else cited(messages))
    cfg=agent_settings(settings).model_copy(update={'model_max_tokens_per_run':32768})
    with TestClient(create_app(cfg,test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); result=wait(client,run_id)
        assert result['run_status']=='PASS',result['error_code']
        assert len(provider.calls)==2
        assert all(0<a['reserved_tokens']<32768 for a in result['attempts'])
        assert result['usage']['confirmed_total_tokens']==40


def test_stream_draft_is_persisted_before_completion_and_cancel_keeps_unknown_usage(dataset):
    settings,d=dataset; entered=threading.Event(); release=threading.Event()
    class StreamingFixture(ScriptedProvider):
        def stream(self,messages,tools,max_tokens,on_update):
            on_update({'role':'assistant','content':'{"message":"正在查询'})
            entered.set(); assert release.wait(5)
            time.sleep(.11)
            on_update({'role':'assistant','content':'{"message":"正在查询数据。"}'})
            return ProviderReply(decision('unsupported','缺少成本。'))
    provider=StreamingFixture([])
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        run_id,_=create(client,d); assert entered.wait(5)
        draft=client.get('/api/v1/runs/'+run_id).json()
        assert draft['messages'][-1]['text']=='正在查询' and draft['messages'][-1]['status']=='draft'
        assert draft['result_ref'] is None and draft['attempts'][0]['status']=='SENT'
        client.post('/api/v1/runs/'+run_id+'/cancel',headers=ORIGIN)
        release.set(); result=wait(client,run_id)
        assert result['run_status']=='CANCELLED' and result['result_ref'] is None
        assert result['usage']['confirmed_total_tokens'] is None
        assert result['messages'][-1]['status']=='interrupted'


def test_followup_preserves_conversation_and_history_stream_is_read_only(dataset):
    settings,d=dataset; provider=ScriptedProvider([decision('unsupported','缺少成本数据。'),decision('unsupported','仍缺少成本数据。')])
    with TestClient(create_app(agent_settings(settings),test_provider=provider),base_url='http://127.0.0.1') as client:
        parent,_=create(client,d,question='利润是多少？'); wait(client,parent)
        child,_=create(client,d,question='那利润率呢？',conversation_parent_run_id=parent)
        result=wait(client,child)
        assert result['run_status']=='PASS' and result['parent_run_id']==parent
        assert result['conversation_history'][0]['question']=='利润是多少？'
        assert '利润是多少' in json.dumps(provider.calls[-1],ensure_ascii=False)
        for _ in range(2):
            response=client.get('/api/v1/runs/'+child+'/events')
            assert 'event: snapshot' in response.text and 'event: settled' in response.text
        assert len(provider.calls)==2
        assert client.get('/api/v1/runs/unknown/events').status_code==404


def test_sse_yields_changed_snapshots_and_stops_on_disconnect():
    class Service:
        count=0
        def get(self,_):
            self.count+=1
            return {'run_id':'fixture','run_status':'RUNNING','text':str(self.count)}
    class Request:
        checks=0
        async def is_disconnected(self):
            self.checks+=1
            return self.checks>2
    async def collect():
        return [item async for item in run_events(Service(),'fixture',Request())]
    events=asyncio.run(collect())
    assert len(events)==2 and '"text": "1"' in events[0] and '"text": "2"' in events[1]


def test_provider_reuses_real_connection_after_done_and_reopens_after_close(dataset, monkeypatch):
    """A local HTTP server verifies socket reuse; no provider credentials/network."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    settings, _ = dataset
    ports = []; transports = []; original_transport = httpx.HTTPTransport

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert 'tools' not in payload  # optional field omitted on format-only calls
            ports.append(self.client_address[1])
            self.send_response(200)
            self.send_header('Transfer-Encoding', 'chunked')
            self.send_header('Content-Type', 'text/event-stream' if payload['stream'] else 'application/json')
            self.end_headers()
            body = (sse({'content': '完成'}, 'stop') + 'data: [DONE]\n\n' if payload['stream'] else
                json.dumps({'choices': [{'message': {'role': 'assistant', 'content': '完成'}, 'finish_reason': 'stop'}]}))
            raw = body.encode()
            self.wfile.write(f'{len(raw):x}\r\n'.encode() + raw + b'\r\n')
            self.wfile.flush()
            # HTTP EOF arrives after [DONE], in a separate network read.
            time.sleep(.02)
            self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()

    class LocalTransport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs['retries'] == 0
            self.inner = original_transport(**kwargs); self.closed = False
            transports.append(self)

        def handle_request(self, request):
            request.url = httpx.URL(f'http://127.0.0.1:{server.server_port}/v1/chat/completions')
            return self.inner.handle_request(request)

        def close(self):
            self.closed = True; self.inner.close()

    monkeypatch.setattr(httpx, 'HTTPTransport', LocalTransport)
    provider = OpenAICompatibleProvider(configured(settings))
    try:
        assert not transports  # construction is lazy
        for _ in range(2):
            assert provider.stream([], [], 256, lambda _: None).message['content'] == '完成'
        assert provider.complete([], [], 256).message['content'] == '完成'
        assert len(set(ports)) == 1 and len(transports) == 1
        provider.close(); provider.close()
        assert transports[0].closed
        provider.stream([], [], 256, lambda _: None)
        assert len(transports) == 2 and ports[-1] != ports[0]
    finally:
        provider.close(); server.shutdown(); server.server_close(); worker.join(2)


def test_connection_failure_does_not_retry_and_next_explicit_call_can_succeed(dataset, monkeypatch):
    settings, _ = dataset; calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError('fixture TLS failure')
        return httpx.Response(200, headers={'content-type': 'text/event-stream'},
            content=sse({'content': '恢复'}, 'stop') + 'data: [DONE]\n\n')

    monkeypatch.setattr(httpx, 'HTTPTransport', lambda **kw: httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(configured(settings))
    try:
        with pytest.raises(ProviderFailure) as failure:
            provider.stream([], [], 256, lambda _: None)
        assert failure.value.code == 'MODEL_CONNECTION_ERROR' and len(calls) == 1
        assert provider.stream([], [], 256, lambda _: None).message['content'] == '恢复'
        assert len(calls) == 2
    finally:
        provider.close()


def test_service_shutdown_closes_provider_after_executor(dataset):
    settings, _ = dataset; states = []

    class ClosingFixture(ScriptedProvider):
        def close(self):
            states.append(app.state.agent_service.pool)

    app = create_app(agent_settings(settings), test_provider=ClosingFixture([]))
    with TestClient(app, base_url='http://127.0.0.1'):
        assert app.state.agent_service.pool is not None
    assert states == [None]


def test_format_repair_reuses_evidence_without_resending_tool_definitions(dataset):
    settings, d = dataset

    def replies(messages, count):
        if count == 1:
            return tool('query_metric_series', period(d))
        if count == 2:
            # Missing required "message": syntax recovery cannot repair a schema error.
            return {'role': 'assistant', 'content': '{"action":"answer","claims":[],"fields":[]}'}
        return cited(messages)

    provider = ScriptedProvider(replies)
    with TestClient(create_app(agent_settings(settings), test_provider=provider), base_url='http://127.0.0.1') as client:
        run_id, _ = create(client, d)
        result = wait(client, run_id)
        assert result['run_status'] == 'PASS', result['error_code']
        assert len(provider.calls) == 3
        assert provider.calls[0]['tools'] and provider.calls[1]['tools']
        assert provider.calls[2]['tools'] == []
        assert any(m['role'] == 'tool' for m in provider.calls[2]['messages'])
        assert len(result['tool_calls']) == 1 and result['result']['claims']
        assert result['reviews'][1]['errors'] == ['INVALID_OUTPUT_SCHEMA']
        assert result['attempts'][2]['reserved_tokens'] < result['attempts'][1]['reserved_tokens']
