"""Typed local configuration. Relative database paths use the project root."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    import_cache_dir: Path = Path("D:/codex产出/电商智能体_本地运行/缓存/imports")
    raw_data_dir: Path = PROJECT_ROOT / "data/raw"
    import_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    model_provider: str = ""
    model_id: str = ""
    model_base_url: str = ""
    model_api_key: SecretStr = SecretStr("")
    allow_paid_model_calls: bool = False
    model_timeout_seconds: int = Field(default=45, ge=1, le=180)
    model_max_requests_per_run: int = Field(default=8, ge=1, le=32)
    model_max_tool_calls_per_run: int = Field(default=12, ge=1, le=48)
    model_max_tokens_per_run: int = Field(default=0, ge=0)
    model_max_total_requests: int = Field(default=0, ge=0)
    model_max_total_tokens: int = Field(default=0, ge=0)
    model_max_tokens_per_request: int = Field(default=32768, ge=4096, le=131072)
    model_max_output_tokens: int = Field(default=2048, ge=256, le=8192)

    @property
    def checkpoint_path(self) -> Path:
        return self.database_path.with_suffix(".checkpoints.sqlite3")

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
            raise ValueError("A file-based SQLite URL without query options is required")
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
