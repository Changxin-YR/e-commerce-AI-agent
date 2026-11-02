"""D0 infrastructure tests. Temporary databases contain no trading data."""

import hashlib
from pathlib import Path
import sqlite3
from uuid import UUID

from alembic import command
from alembic.config import Config
from fastapi import Query
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.config import PROJECT_ROOT, Settings
from backend.app.database import create_database_engine, create_session_factory
from backend.app.main import create_app
from backend.app.models import AppMetadata


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'app.sqlite3').as_posix()}", app_env="test")


def migration_config(settings: Settings) -> Config:
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.attributes["settings"] = settings
    return config


@pytest.fixture
def migrated(settings: Settings) -> Settings:
    command.upgrade(migration_config(settings), "head")
    return settings


def test_migration_upgrade_idempotence_and_round_trip(settings: Settings):
    config = migration_config(settings)
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_database_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            assert session.scalars(select(AppMetadata)).one().value == "ecommerce-agent-thesis"
        with sqlite3.connect(settings.database_path) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [("0004_agent_runtime",)]
            assert set(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")) == {"alembic_version", "app_metadata", "dataset_snapshots", "import_batches", "transaction_rows", "quality_issues", "analysis_runs", "reports", "query_history", "model_attempts", "agent_tool_calls", "run_submissions", "model_budget", "agent_reviews"}
        command.downgrade(config, "base")
        with sqlite3.connect(settings.database_path) as connection:
            assert connection.execute("SELECT name FROM sqlite_master WHERE name='app_metadata'").fetchall() == []
        command.upgrade(config, "head")
        with create_session_factory(engine)() as session:
            assert session.get(AppMetadata, "project_id").value == "ecommerce-agent-thesis"
    finally:
        engine.dispose()


def test_health_checks_real_database_and_has_no_write_side_effect(migrated: Settings):
    before = hashlib.sha256(migrated.database_path.read_bytes()).hexdigest()
    with TestClient(create_app(migrated), base_url="http://127.0.0.1") as client:
        for _ in range(2):
            response = client.get("/healthz")
            assert response.status_code == 200
            payload = response.json()
            assert payload == {
                "status": "ok", "service": "ecommerce-agent", "version": "0.9.0", "stage": "D9",
                "database": {"status": "ok", "engine": "sqlite", "sqlite_version": sqlite3.sqlite_version, "schema_revision": "0004_agent_runtime"},
            }
            UUID(response.headers["X-Request-ID"])
            assert response.headers["cache-control"] == "no-store"
            assert str(migrated.database_path) not in response.text
    assert hashlib.sha256(migrated.database_path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("condition,code", [
    ("missing", "DATABASE_NOT_INITIALIZED"),
    ("empty", "DATABASE_MIGRATION_REQUIRED"),
    ("corrupt", "DATABASE_UNAVAILABLE"),
])
def test_unready_database_is_503_without_creation(settings: Settings, condition: str, code: str):
    if condition == "empty":
        settings.database_path.touch()
    elif condition == "corrupt":
        settings.database_path.write_bytes(b"test_fixture: not a sqlite database")
    with TestClient(create_app(settings), base_url="http://localhost") as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] == {}
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert str(settings.database_path) not in response.text
    if condition == "missing":
        assert not settings.database_path.exists()


def test_wrong_migration_revision_is_not_healthy(migrated: Settings):
    with sqlite3.connect(migrated.database_path) as connection:
        connection.execute("UPDATE alembic_version SET version_num = 'test_fixture_old_revision'")
    with TestClient(create_app(migrated), base_url="http://localhost") as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_MIGRATION_REQUIRED"


def test_stamped_revision_without_real_schema_is_not_healthy(migrated: Settings):
    with sqlite3.connect(migrated.database_path) as connection:
        connection.execute("DROP TABLE app_metadata")
    with TestClient(create_app(migrated), base_url="http://localhost") as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_MIGRATION_REQUIRED"


def test_unknown_route_and_http_method_have_error_envelopes(migrated: Settings):
    with TestClient(create_app(migrated), base_url="http://127.0.0.1") as client:
        missing = client.get("/api/v1/not-implemented")
        method = client.post("/healthz", headers={"Origin": "http://127.0.0.1:5173"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert method.status_code == 405
    assert method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in method.headers["allow"]


def test_host_and_origin_boundaries(settings: Settings):
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        bad_host = client.get("/healthz", headers={"Host": "evil.example"})
        bad_origin = client.post("/healthz", headers={"Origin": "https://evil.example"})
    assert bad_host.status_code == 400
    assert bad_host.json()["error"]["code"] == "UNTRUSTED_HOST"
    assert bad_origin.status_code == 403
    assert bad_origin.json()["error"]["code"] == "UNTRUSTED_ORIGIN"


def test_validation_and_unexpected_errors_are_sanitized(settings: Settings, caplog):
    application = create_app(settings)

    @application.get("/_test/validation")
    def fixture_validation(count: int = Query()):
        return {"count": count}

    @application.get("/_test/error")
    def fixture_error():
        raise RuntimeError("test_fixture_secret C:/private/database.sqlite3")

    with TestClient(application, base_url="http://localhost") as client:
        invalid = client.get("/_test/validation", params={"count": "test_fixture_secret"})
        internal = client.get("/_test/error")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert internal.status_code == 500
    assert internal.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "test_fixture_secret" not in invalid.text + internal.text + caplog.text
    assert "C:/private" not in internal.text + caplog.text


def test_relative_database_path_is_independent_of_working_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    configuration = Settings(_env_file=None, database_url="sqlite:///./data/app.sqlite3")
    assert configuration.database_path == (PROJECT_ROOT / "data/app.sqlite3").resolve()


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "postgresql://localhost/app", "sqlite:///db?mode=rwc"])
def test_unsupported_database_configuration_fails_early(url: str):
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url=url)
