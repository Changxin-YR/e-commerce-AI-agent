"""Bounded multipart upload and asynchronous import status endpoints."""
import asyncio
from pathlib import Path
import time
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool

from backend.app.imports.source import MAX_UPLOAD, fail
from backend.app.schemas import DatasetProfile, ErrorResponse, ImportBatchResponse, QualitySummary

router = APIRouter(prefix="/api/v1/datasets", responses={code: {"model": ErrorResponse} for code in (400, 403, 404, 409, 413, 415, 422, 503)})
MIME_TYPES = {
    ".xlsx": {b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".zip": {b"application/zip", b"application/x-zip-compressed"},
}


async def receive_file(request: Request) -> Path:
    content_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary or len(boundary) > 200:
        fail("EXPECTED_MULTIPART_FILE", 400)
    length = request.headers.get("content-length")
    if length is not None:
        if not length.isdecimal():
            fail("INVALID_CONTENT_LENGTH", 400)
        if len(length) > 20 or int(length) > MAX_UPLOAD + 65536:
            fail("UPLOAD_TOO_LARGE", 413)
    cache = request.app.state.settings.import_cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    path, stream = None, None
    headers: dict[bytes, bytes] = {}
    field, value = bytearray(), bytearray()
    parts, size, header_size, ended = 0, 0, 0, False

    def part_begin():
        nonlocal parts
        parts += 1
        if parts != 1:
            fail("EXPECTED_SINGLE_FILE", 400)

    def header_field(data, start, end):
        nonlocal header_size
        header_size += end - start
        if header_size > 8192:
            fail("UPLOAD_HEADER_LIMIT", 400)
        field.extend(data[start:end])

    def header_value(data, start, end):
        nonlocal header_size
        header_size += end - start
        if header_size > 8192:
            fail("UPLOAD_HEADER_LIMIT", 400)
        value.extend(data[start:end])

    def header_end():
        key = bytes(field).lower()
        if key in headers:
            fail("DUPLICATE_UPLOAD_HEADER", 400)
        headers[key] = bytes(value)
        field.clear()
        value.clear()

    def headers_finished():
        nonlocal path, stream
        disposition, params = parse_options_header(headers.get(b"content-disposition", b""))
        name = params.get(b"filename", b"")
        if disposition != b"form-data" or params.get(b"name") != b"file" or not name:
            fail("EXPECTED_SINGLE_FILE", 400)
        if len(name) > 255 or any(c in name for c in (b"/", b"\\", b":", b"\x00")) or name in (b".", b".."):
            fail("UNSAFE_UPLOAD_NAME", 400)
        suffix = Path(name.decode("utf-8", errors="strict")).suffix.lower()
        if suffix not in MIME_TYPES:
            fail("UNSUPPORTED_FILE_TYPE", 400)
        if headers.get(b"content-type", b"").lower() not in MIME_TYPES[suffix]:
            fail("UNSUPPORTED_MIME_TYPE", 415)
        path = cache / (uuid4().hex + suffix)
        stream = path.open("xb")

    def part_data(data, start, end):
        nonlocal size
        size += end - start
        if size > MAX_UPLOAD:
            fail("UPLOAD_TOO_LARGE", 413)
        if stream is None:
            fail("MALFORMED_MULTIPART", 400)
        stream.write(data[start:end])

    def end():
        nonlocal ended
        ended = True

    parser = MultipartParser(boundary, {
        "on_part_begin": part_begin, "on_header_field": header_field, "on_header_value": header_value,
        "on_header_end": header_end, "on_headers_finished": headers_finished,
        "on_part_data": part_data, "on_end": end,
    })
    total, deadline = 0, time.monotonic() + 60
    try:
        iterator = request.stream().__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(iterator.__anext__(), max(0.001, deadline - time.monotonic()))
            except StopAsyncIteration:
                break
            total += len(chunk)
            if total > MAX_UPLOAD + 65536:
                fail("UPLOAD_TOO_LARGE", 413)
            if time.monotonic() >= deadline:
                fail("UPLOAD_TIMEOUT", 408)
            parser.write(chunk)
        parser.finalize()
        if not ended or parts != 1 or not size or path is None:
            fail("MALFORMED_MULTIPART", 400)
        stream.close()
        return path
    except BaseException as exc:
        if stream:
            stream.close()
        if path:
            path.unlink(missing_ok=True)
        if isinstance(exc, (MultipartParseError, UnicodeError, ValueError)):
            fail("MALFORMED_MULTIPART", 400)
        if isinstance(exc, TimeoutError):
            fail("UPLOAD_TIMEOUT", 408)
        raise


@router.post("/imports", status_code=202, response_model=ImportBatchResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file"], "additionalProperties": False,
        "properties": {"file": {"type": "string", "format": "binary"}}}}}}},
    responses={200: {"model": ImportBatchResponse, "description": "Existing READY import; raw_sha256 is the workbook hash"},
               202: {"description": "Stable batch identity; poll GET /imports/{batch_id}"},
               400: {"description": "Malformed or unsupported input"}, 409: {"description": "Writer busy"},
               413: {"description": "Size or compression limit"}, 415: {"description": "Unsupported MIME"},
               422: {"description": "Invalid, corrupt or unaudited workbook"}, 503: {"description": "Database unavailable"}})
async def import_file(request: Request):
    service = request.app.state.import_service
    service.require_database()
    path = await receive_file(request)
    try:
        result = await run_in_threadpool(service.submit, path)
        return JSONResponse(result, status_code=200 if result["status"] == "READY" else 202)
    finally:
        path.unlink(missing_ok=True)


@router.get("/imports/{batch_id}", response_model=ImportBatchResponse)
def import_status(batch_id: str, request: Request):
    return request.app.state.import_service.batch(batch_id)


@router.get("/{dataset_id}", response_model=DatasetProfile)
def dataset_profile(dataset_id: str, request: Request):
    return request.app.state.import_service.profile(dataset_id)


@router.get("/{dataset_id}/quality", response_model=QualitySummary, responses={409: {"description": "Dataset not READY"}})
def dataset_quality(dataset_id: str, request: Request):
    return request.app.state.import_service.profile(dataset_id, quality=True)
