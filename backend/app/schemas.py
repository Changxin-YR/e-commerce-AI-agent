"""Public D0 response models."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: Literal["ok"] = "ok"
    engine: Literal["sqlite"] = "sqlite"
    sqlite_version: str
    schema_revision: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["ecommerce-agent"] = "ecommerce-agent"
    version: Literal["0.1.0"] = "0.1.0"
    stage: Literal["D0"] = "D0"
    database: DatabaseHealth


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str
