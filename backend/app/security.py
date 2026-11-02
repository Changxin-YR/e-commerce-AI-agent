"""Bound small API bodies before JSON decoding; uploads have their own streaming cap."""
import asyncio
import time
from starlette.requests import Request

MAX_API_BODY = 64 * 1024
API_BODY_TIMEOUT = 15
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "frame-ancestors 'none'",
    'Referrer-Policy': 'no-referrer',
}


class BoundedBodyMiddleware:
    def __init__(self, app, error_response):
        self.app, self.error_response = app, error_response

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or (scope['path'].rstrip('/') == '/api/v1/datasets/imports'
                                      and scope['method'] == 'POST'):
            return await self.app(scope, receive, send)
        request = Request(scope)

        async def reject(code, status):
            response = self.error_response(request, code, 'Request body rejected by local resource limits.', status)
            await response(scope, receive, send)

        lengths = request.headers.getlist('content-length')
        if len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdecimal())):
            return await reject('INVALID_CONTENT_LENGTH', 400)
        if lengths and (len(lengths[0]) > 10 or int(lengths[0]) > MAX_API_BODY):
            return await reject('REQUEST_TOO_LARGE', 413)
        # Do not rely on Content-Length: streamed/chunked requests get the same bound.
        body = bytearray()
        deadline = time.monotonic() + API_BODY_TIMEOUT
        while True:
            try:
                message = await asyncio.wait_for(receive(), max(0.001, deadline - time.monotonic()))
            except TimeoutError:
                return await reject('REQUEST_TIMEOUT', 408)
            if time.monotonic() >= deadline:
                return await reject('REQUEST_TIMEOUT', 408)
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > MAX_API_BODY:
                return await reject('REQUEST_TOO_LARGE', 413)
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        if lengths and int(lengths[0]) != len(body):
            return await reject('INVALID_CONTENT_LENGTH', 400)
        delivered = False

        async def buffered_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, buffered_receive, send)
