"""Local health/import APIs. GET never writes; startup recovers interrupted imports."""

from contextlib import asynccontextmanager
from http import HTTPStatus
import logging
import re
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from backend.app.config import PROJECT_ROOT, Settings
from backend.app.database import create_database_engine
from backend.app.errors import AppError
from backend.app.imports.routes import router as import_router
from backend.app.imports.service import ImportService
from backend.app.models import Base
from backend.app.schemas import DatabaseHealth, ErrorDetail, ErrorResponse, HealthResponse

logger = logging.getLogger(__name__)


def error_response(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message), request_id=request_id
    )
    return JSONResponse(
        body.model_dump(),
        status_code=status_code,
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


def create_app(settings: Settings | None = None, *, test_hashes: frozenset[str] | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_database_engine(settings, readonly=True)
    migration_config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    expected_revision = ScriptDirectory.from_config(migration_config).get_current_head()
    import_service = ImportService(settings, test_hashes=test_hashes)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        import_service.start()
        try:
            yield
        finally:
            import_service.close()
            engine.dispose()

    application = FastAPI(
        title="Ecommerce Agent — D2",
        version="0.2.0",
        description="Local source ingestion. raw_sha256/data_hash always identify the XLSX workbook; container hashes are separate.",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.engine = engine
    application.state.import_service = import_service
    application.include_router(import_router)

    @application.middleware("http")
    async def request_boundary(request: Request, call_next):
        # Generate our own identifier; never reflect untrusted header content.
        request.state.request_id = str(uuid4())
        host = request.headers.get("host", "").lower()
        if not re.fullmatch(r"(?:127\.0\.0\.1|localhost)(?::\d{1,5})?", host):
            return error_response(request, "UNTRUSTED_HOST", "Local host required.", 400)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") not in settings.trusted_origins:
                return error_response(request, "UNTRUSTED_ORIGIN", "Trusted local origin required.", 403)
        try:
            response = await call_next(request)
        except Exception as exc:
            # Exception messages may contain paths, SQL or credentials.
            logger.error("request_failed request_id=%s type=%s", request.state.request_id, type(exc).__name__)
            response = error_response(request, "INTERNAL_ERROR", "Internal server error.", 500)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(request, exc.code, exc.message, exc.status_code)

    @application.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, _exc: RequestValidationError):
        return error_response(request, "VALIDATION_ERROR", "Request validation failed.", 422)

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "Request failed."
        response = error_response(request, code, message, exc.status_code)
        if exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    @application.get(
        "/healthz",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse, "description": "Database unavailable or migration required"}},
    )
    def healthz() -> HealthResponse:
        if not settings.database_path.is_file():
            raise AppError("DATABASE_NOT_INITIALIZED", "Run the database migration before starting the application.")
        try:
            with engine.connect() as connection:
                sqlite_version = connection.execute(text("SELECT sqlite_version()" )).scalar_one()
                tables = set(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
                if not {"alembic_version", *Base.metadata.tables}.issubset(tables):
                    raise AppError("DATABASE_MIGRATION_REQUIRED", "Database migration is required.")
                revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                marker = connection.execute(
                    text("SELECT value FROM app_metadata WHERE key = :key"), {"key": "project_id"}
                ).scalar_one_or_none()
                if revisions != [expected_revision] or marker != "ecommerce-agent-thesis":
                    raise AppError("DATABASE_MIGRATION_REQUIRED", "Database migration is required.")
        except SQLAlchemyError:
            raise AppError("DATABASE_UNAVAILABLE", "Database health check failed.") from None
        return HealthResponse(database=DatabaseHealth(sqlite_version=sqlite_version, schema_revision=revisions[0]))

    return application


app = create_app()
