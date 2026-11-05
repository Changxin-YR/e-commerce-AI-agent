"""Explicit opt-in HTTP adapter. Zero automatic retries, no provider calls on GET."""
from dataclasses import dataclass
import json
import time
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


ALLOWED_PROVIDERS = frozenset({"deepseek", "openai_compatible"})


def authorization_error(settings):
    if not settings.allow_paid_model_calls:
        return "BLOCKED_AUTHORIZATION"
    if min(settings.model_max_total_requests, settings.model_max_total_tokens, settings.model_max_tokens_per_run) <= 0:
        return "BLOCKED_BUDGET"
    if not settings.model_api_key.get_secret_value():
        return "BLOCKED_CREDENTIALS"
    if settings.model_provider not in ALLOWED_PROVIDERS or not settings.model_id.strip():
        return "BLOCKED_PROVIDER_CONFIGURATION"
    base = settings.model_base_url.rstrip('/')
    if not base or not base.startswith('https://'):
        return "BLOCKED_PROVIDER_CONFIGURATION"
    return None


class OpenAICompatibleProvider:
    """Works with DeepSeek, Claude-compatible gateways, and other OpenAI-compatible APIs."""
    is_test = False

    def __init__(self, settings):
        self.settings = settings
        self.name = settings.model_provider
        self.model_id = settings.model_id
        self._client = None

    def _get_client(self):
        # The service has a single executor. Initialize only after authorization,
        # and retain the pool across tool/model rounds to avoid repeated TLS setup.
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=self.settings.model_timeout_seconds, trust_env=False,
                follow_redirects=False, transport=httpx.HTTPTransport(retries=0,
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=1, keepalive_expiry=60)))
        return self._client

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None

    def complete(self, messages, tools, max_tokens):
        return self._complete(messages, tools, max_tokens)

    def stream(self, messages, tools, max_tokens, on_update):
        return self._complete(messages, tools, max_tokens, on_update)

    def _complete(self, messages, tools, max_tokens, on_update=None):
        error = authorization_error(self.settings)
        if error:
            raise AppError(error, "External model access is not configured and authorized.", 409)
        payload = dict(model=self.model_id, messages=messages, temperature=0,
            max_tokens=max_tokens, stream=on_update is not None)
        if tools:
            payload['tools'] = tools
        if on_update is not None:
            payload['stream_options'] = {'include_usage': True}
        started = time.monotonic()
        try:
            client = self._get_client()
            base = self.settings.model_base_url.rstrip('/')
            endpoint = base + '/chat/completions' if base.endswith('/v1') else base + '/v1/chat/completions'
            with client.stream('POST', endpoint,
                headers={'Authorization':'Bearer '+self.settings.model_api_key.get_secret_value()}, json=payload) as response:
                if response.status_code != 200:
                    code = {401: 'MODEL_AUTH_ERROR', 403: 'MODEL_AUTH_ERROR', 404: 'MODEL_ENDPOINT_ERROR',
                            429: 'MODEL_RATE_LIMIT', 400: 'MODEL_REQUEST_REJECTED'}.get(response.status_code, 'MODEL_HTTP_ERROR')
                    raise ProviderFailure(code)
                if on_update is not None and 'text/event-stream' in response.headers.get('content-type', ''):
                    return self._read_stream(response, on_update, started)
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
        except httpx.TimeoutException:
            raise ProviderFailure('MODEL_TIMEOUT') from None
        except httpx.ConnectError:
            raise ProviderFailure('MODEL_CONNECTION_ERROR') from None
        except (httpx.RemoteProtocolError, httpx.ReadError):
            raise ProviderFailure('MODEL_STREAM_INTERRUPTED') from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ProviderFailure('MODEL_INVALID_RESPONSE') from None
        except httpx.HTTPError:
            raise ProviderFailure('MODEL_OUTCOME_UNKNOWN') from None

    def _read_stream(self, response, on_update, started):
        """Assemble indexed tool deltas; expose content only, never reasoning fields."""
        message = {'role': 'assistant', 'content': ''}
        calls = {}; usage = None; request_id = None; finish = None; size = 0
        data_lines = []; done = False

        def consume(data):
            nonlocal usage, request_id, finish
            if data == '[DONE]':
                return True
            item = json.loads(data)
            if item.get('error'):
                raise ProviderFailure('MODEL_STREAM_ERROR')
            request_id = item.get('id') or request_id
            if item.get('usage') is not None:
                usage = item['usage']
            choices = item.get('choices', [])
            if not choices:
                return False
            choice = choices[0]; delta = choice.get('delta') or {}
            if delta.get('content') is not None:
                if not isinstance(delta['content'], str):
                    raise ProviderFailure('MODEL_INVALID_RESPONSE')
                message['content'] += delta['content']
            for part in delta.get('tool_calls') or []:
                index = part['index']
                if type(index) is not int or not 0 <= index < 48:
                    raise ProviderFailure('INVALID_TOOL_CALL')
                call = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                call['id'] += part.get('id') or ''
                for key in ('name', 'arguments'):
                    call['function'][key] += (part.get('function') or {}).get(key) or ''
            if calls:
                message['tool_calls'] = [calls[i] for i in sorted(calls)]
            finish = choice.get('finish_reason') or finish
            on_update(message)
            return False

        for line in response.iter_lines():
            size += len(line.encode('utf-8')) + 1
            if size > 2_000_000:
                raise ProviderFailure('MODEL_RESPONSE_TOO_LARGE')
            if time.monotonic() - started > self.settings.model_timeout_seconds:
                raise ProviderFailure('MODEL_TIMEOUT')
            # Consume the HTTP body through EOF, including the terminal chunk.
            # Breaking at [DONE] closes an unread response and discards keep-alive.
            # The existing read/deadline and size limits also bound this tail.
            if done:
                continue
            if line == '':
                if data_lines and consume('\n'.join(data_lines)):
                    done = True
                data_lines = []
            elif line.startswith('data:'):
                data_lines.append(line[5:].lstrip(' '))
        if data_lines:
            consume('\n'.join(data_lines))
        if not finish:
            raise ProviderFailure('MODEL_STREAM_INTERRUPTED')
        if finish in ('length', 'content_filter'):
            raise ProviderFailure('MODEL_OUTPUT_TRUNCATED')
        return ProviderReply(message, usage, request_id, finish)


# Backward compatibility alias
DeepSeekProvider = OpenAICompatibleProvider


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
