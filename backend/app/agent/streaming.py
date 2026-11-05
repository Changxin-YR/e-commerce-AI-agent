"""Read-only conversation projections and SSE; no provider requests on reconnect."""
import asyncio
import json
import re
import time
from starlette.concurrency import run_in_threadpool
from backend.app.errors import AppError
from backend.app.metrics.service import digest


def visible_message(content):
    """Extract the public message from partial structured output, never its claims/JSON."""
    if not isinstance(content, str):
        return ''
    if not content.lstrip().startswith('{'):
        # A model may send a short introduction before calling tools.
        return '' if content.lstrip().startswith('```') else content
    match = re.search(r'"message"\s*:\s*"', content)
    if not match:
        return ''
    raw = content[match.end():]
    result = ''; i = 0
    while i < len(raw):
        char = raw[i]
        if char == '"':
            break
        if char == '\\':
            if i + 1 >= len(raw):
                break
            end = i + (6 if raw[i+1] == 'u' else 2)
            if end > len(raw):
                break
            try:
                result += json.loads('"' + raw[i:end] + '"')
            except (ValueError, TypeError):
                break
            i = end
        else:
            result += char; i += 1
    # Incomplete UTF-16 surrogate pairs must not break JSON/UTF-8 SSE encoding.
    return result.encode('utf-16', 'surrogatepass').decode('utf-16', 'replace')


async def run_events(service, run_id, request):
    previous = None; heartbeat = time.monotonic()
    try:
        while not await request.is_disconnected():
            run = await run_in_threadpool(service.get, run_id)
            version = digest(run)
            if version != previous:
                yield 'event: snapshot\nid: ' + version + '\ndata: ' + json.dumps(run, ensure_ascii=False) + '\n\n'
                previous = version; heartbeat = time.monotonic()
            if run['run_status'] not in ('QUEUED', 'RUNNING'):
                yield 'event: settled\ndata: {}\n\n'
                return
            if time.monotonic() - heartbeat >= 10:
                yield ': heartbeat\n\n'; heartbeat = time.monotonic()
            await asyncio.sleep(.15)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        code = error.code if isinstance(error, AppError) else 'STREAM_UNAVAILABLE'
        yield 'event: stream-error\ndata: ' + json.dumps({'code': code}) + '\n\n'
