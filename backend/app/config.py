"""Typed local configuration. Relative database paths use the project root."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_host: Literal["127.0.0.1", "localhost"] = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    frontend_port: int = Field(default=5173, ge=1, le=65535)
    app_env: Literal["development", "test"] = "development"
    database_url: str = "sqlite:///./data/app.sqlite3"

    @field_validator("database_url")
    @classmethod
    def require_local_sqlite(cls, value: str) -> str:
        url = make_url(value)
        if (
            url.drivername not in {"sqlite", "sqlite+pysqlite"}
            or not url.database
            or url.database == ":memory:"
            or url.host
            or url.username
            or url.password
            or url.query
        ):
            raise ValueError("D0 requires a file-based SQLite URL without query options")
        return value

    @property
    def database_path(self) -> Path:
        path = Path(make_url(self.database_url).database or "")
        return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

    @property
    def trusted_origins(self) -> set[str]:
        return {
            f"http://{host}:{port}"
            for host in ("127.0.0.1", "localhost")
            for port in (self.app_port, self.frontend_port)
        }
