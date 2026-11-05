"""Syntax-only recovery tests: tolerant quotes must never bypass evidence checks."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.app.agent.provider import ScriptedProvider
from backend.app.agent.tolerant_json import loads_tolerant, parse_decision
from backend.app.main import create_app
from test_agent import agent_settings, create, decision, last_tool, period, tool, wait
from test_metrics import dataset


def malformed_cited(messages, *, field_path='points.0.value_exact', value=None):
    """A complete decision object whose message contains unescaped double quotes."""
    data = last_tool(messages)
    claim = dict(tool_call_id=data['tool_call_id'], field_path=field_path, label='净交易金额',
                 value=data['data']['points'][0]['value_exact'] if value is None else value)
    content = ('{"action":"answer","message":"结论是"净交易金额"已核验，'
               '换行也能保留。","claims":[' + json.dumps(claim, ensure_ascii=False) + '],"fields":[]}')
    return {'role': 'assistant', 'content': content}


def test_tolerant_parser_recovers_unescaped_quotes_newlines_and_fences():
    text = ('先说明一下：\n```json\n{"action":"answer","message":"他说"确认过了"，\n第二行",'
            '"claims":[{"tool_call_id":"tc_1","field_path":"row_count","label":"行数","value":541909}],'
            '"fields":[]}\n```')
    parsed = loads_tolerant(text)
    assert parsed['action'] == 'answer'
    assert parsed['message'] == '他说"确认过了"，\n第二行'
    assert parsed['claims'][0]['value'] == 541909


def test_tolerant_parser_combines_surrogate_pairs_like_json_loads():
    text = ('{"action":"answer","message":"表情 \\ud83d\\ude00 保留",'
            '"claims":[],"fields":[]}')
    parsed = loads_tolerant(text)
    assert parsed['message'] == '表情 😀 保留'
    assert json.loads(text)['message'] == parsed['message']


def test_strict_contract_is_preferred_and_unchanged():
    strict = decision(message='普通文本')['content']
    parsed = parse_decision(strict)
    assert parsed.action == 'answer' and parsed.message == '普通文本'
    # Genuinely invalid schemas are still rejected after syntax recovery.
    with pytest.raises(ValueError):
        parse_decision('{"action":"bogus","message":"x","claims":[],"fields":[]}')
    with pytest.raises(ValueError):
        parse_decision('{"action":"answer","claims":[],"fields":[]}')


def test_unescaped_quotes_are_recovered_without_extra_model_request(dataset):
    settings, d = dataset
    provider = ScriptedProvider(lambda messages, n: tool('query_metric_series', period(d)) if n == 1
                                else malformed_cited(messages))
    with TestClient(create_app(agent_settings(settings), test_provider=provider), base_url='http://127.0.0.1') as client:
        run_id, _ = create(client, d)
        result = wait(client, run_id)
        assert result['run_status'] == 'PASS', result['error_code']
        assert len(provider.calls) == 2  # no repair round was needed
        assert result['reviews'][1]['errors'] == []
        exact = result['tool_calls'][0]['result']['data']['points'][0]['value_exact']
        assert result['result']['claims'][0]['value'] == exact
        assert '"净交易金额"' in result['result']['message']


def test_tolerant_syntax_still_rejects_wrong_evidence_values(dataset):
    settings, d = dataset
    provider = ScriptedProvider(lambda messages, n: tool('query_metric_series', period(d)) if n == 1
                                else malformed_cited(messages, value='999.000'))
    with TestClient(create_app(agent_settings(settings), test_provider=provider), base_url='http://127.0.0.1') as client:
        run_id, _ = create(client, d)
        result = wait(client, run_id)
        assert result['run_status'] == 'FAIL'
        assert result['error_code'] == 'CLAIM_VALUE_MISMATCH'
        assert len(provider.calls) == 4  # original + two recovery rounds, no evidence bypass
