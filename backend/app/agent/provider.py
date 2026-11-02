"""Explicit opt-in HTTP adapter. Zero automatic retries, no provider calls on GET."""
from dataclasses import dataclass
import json
from typing import Protocol
import httpx
from backend.app.errors import AppError


@dataclass
class ProviderReply:
    message: dict
    usage: dict | None = None
    request_id: str | None = None
    finish_reason: str | None = None

    def as_dict(self):
        return dict(message=self.message, usage=self.usage, request_id=self.request_id, finish_reason=self.finish_reason)


class ProviderFailure(Exception):
    def __init__(self, code, *, unknown=True):
        self.code, self.unknown = code, unknown


class Provider(Protocol):
    name: str
    model_id: str
    is_test: bool
    def complete(self, messages: list, tools: list, max_tokens: int) -> ProviderReply: ...


def authorization_error(settings):
    if not settings.allow_paid_model_calls:
        return "BLOCKED_AUTHORIZATION"
    if min(settings.model_max_total_requests, settings.model_max_total_tokens, settings.model_max_tokens_per_run) <= 0:
        return "BLOCKED_BUDGET"
    if not settings.model_api_key.get_secret_value():
        return "BLOCKED_CREDENTIALS"
    if (settings.model_provider != "deepseek" or not settings.model_id.strip()
        or settings.model_base_url.rstrip('/') != 'https://api.deepseek.com'):
        return "BLOCKED_PROVIDER_CONFIGURATION"
    return None


class DeepSeekProvider:
    name = "deepseek"
    is_test = False

    def __init__(self, settings):
        self.settings = settings
        self.model_id = settings.model_id

    def complete(self, messages, tools, max_tokens):
        error = authorization_error(self.settings)
        if error:
            raise AppError(error, "External model access is not configured and authorized.", 409)
        payload = dict(model=self.model_id, messages=messages, tools=tools, temperature=0,
            max_tokens=max_tokens, stream=False)
        try:
            with httpx.Client(timeout=self.settings.model_timeout_seconds, trust_env=False,
                              follow_redirects=False, transport=httpx.HTTPTransport(retries=0)) as client:
                with client.stream('POST', self.settings.model_base_url.rstrip('/')+'/chat/completions',
                    headers={'Authorization':'Bearer '+self.settings.model_api_key.get_secret_value()}, json=payload) as response:
                    if response.status_code != 200:
                        # Even HTTP errors are not evidence of zero billed usage.
                        raise ProviderFailure('MODEL_HTTP_ERROR')
                    chunks=[]; size=0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 2_000_000:
                            raise ProviderFailure('MODEL_RESPONSE_TOO_LARGE')
                        chunks.append(chunk)
            data=json.loads(b''.join(chunks)); choice=data['choices'][0]
            message=choice['message']
            if not isinstance(message,dict) or message.get('role') != 'assistant':
                raise ValueError('invalid message')
            return ProviderReply(message, data.get('usage'), data.get('id'), choice.get('finish_reason'))
        except ProviderFailure:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderFailure('MODEL_OUTCOME_UNKNOWN') from None


class ScriptedProvider:
    """Explicit test_fixture injection only; never selectable through API/config."""
    name = 'test_fixture'
    model_id = 'scripted-no-network'
    is_test = True

    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def complete(self, messages, tools, max_tokens):
        self.calls.append(dict(messages=messages, tools=tools))
        reply = self.replies(messages, len(self.calls)) if callable(self.replies) else self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, ProviderReply):
            return reply
        return ProviderReply(reply, dict(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                             'test_fixture_request_'+str(len(self.calls)), 'tool_calls' if reply.get('tool_calls') else 'stop')
