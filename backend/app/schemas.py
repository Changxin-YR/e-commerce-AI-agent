"""Public health and import response contracts."""

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
    version: Literal["0.7.0"] = "0.7.0"
    stage: Literal["D7"] = "D7"
    database: DatabaseHealth


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str


ImportStatus = Literal["QUEUED", "IMPORTING", "READY", "FAILED"]


class ContainerRecord(BaseModel):
    sha256: str
    bytes: int
    kind: Literal["zip", "xlsx"]


class FailureRecord(BaseModel):
    attempt: int
    code: str
    at: str
    processed_rows: int


class ImportBatchResponse(BaseModel):
    batch_id: str
    dataset_id: str
    status: ImportStatus
    raw_sha256: str = Field(description="SHA-256 of XLSX bytes; never the outer ZIP hash")
    workbook_sha256: str
    submitted_file_sha256: str = Field(description="First submitted container; all container variants are in containers")
    containers: list[ContainerRecord]
    transform_version: str
    processed_rows: int
    attempt: int
    error_code: str | None
    failures: list[FailureRecord]
    created_at: str
    imported_at: str | None


class DatasetProfile(BaseModel):
    dataset_id: str
    status: ImportStatus
    data_hash: str
    raw_sha256: str = Field(description="SHA-256 of the workbook")
    transform_version: str
    schema_version: str
    metric_version: str
    source_url: str
    acquired_at: str
    currency: Literal["GBP"]
    source_timezone: Literal["UNSPECIFIED_LOCAL_TIME"]
    row_count: int | None
    source_time_min: str | None
    source_time_max: str | None


class QualitySummary(DatasetProfile):
    raw_row_count: int
    primary_class_counts: dict[str, int]
    quality_flags: dict[str, int]
    quality_flags_overlap: bool
    duplicates_retained: bool
    duplicate_group_rows: int
    duplicate_candidates_after_first: int
    distinct_invoices: int
    distinct_stock_codes: int
    distinct_countries: int
    invoices_multiple_timestamps: int
    invoices_multiple_days: int
    invoices_multiple_months: int
    absolute_amount_milli_gbp: str
    duration_seconds: float
    warnings: list[str]
