"""Shared typed parameters for HTTP, the three tools and saved queries."""
from datetime import date
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator

from backend.app.errors import AppError

METRIC_VERSION = "retail-v1.2"
METRICS = ("positive_amount", "cancellation_amount", "net_amount", "positive_invoice_count")
MetricName = Literal["positive_amount", "cancellation_amount", "net_amount", "positive_invoice_count"]
Status = Literal["PASS", "NO_DATA", "EMPTY_RESULT", "PARTIAL_PERIOD"]
Month = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$", min_length=7, max_length=7)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


def iso_date(value):
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use an ISO calendar date")
    return value


ISODate = Annotated[date, BeforeValidator(iso_date)]


def next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def month_range(month: str) -> tuple[date, date]:
    first = date.fromisoformat(month + "-01")
    return first, next_month(first)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Filters(StrictModel):
    country: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128)] | None = None
    stock_code: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128)] | None = None

    @field_validator("country", "stock_code")
    @classmethod
    def literal_filter(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("Filter must be a nonempty literal without control characters")
        # Do not strip/casefold source identifiers; comparisons are exact and parameterized.
        return value


class MonthlyParams(Filters):
    month: Month

    @field_validator("month")
    @classmethod
    def actual_month(cls, value):
        month_range(value)
        return value


class SeriesParams(Filters):
    metric: MetricName
    date_from: ISODate
    date_to: ISODate = Field(description="Exclusive end, ISO date; source local time with unspecified timezone")
    granularity: Literal["month"] = "month"

    @field_validator("metric", mode="before")
    @classmethod
    def supported_metric(cls, value):
        if value not in METRICS:
            raise AppError("UNSUPPORTED_METRIC", "This metric is not supported.", 422)
        return value

    @model_validator(mode="after")
    def bounded_interval(self):
        if self.date_from >= self.date_to or self.date_to.year > 9998:
            raise ValueError("A nonempty left-closed right-open interval is required")
        months = (self.date_to.year-self.date_from.year)*12 + self.date_to.month-self.date_from.month + (self.date_to.day > 1)
        if months > 36:
            raise ValueError("At most 36 monthly buckets are supported")
        return self


class PageParams(StrictModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)


class DefinitionParams(StrictModel):
    metric_names: list[MetricName] = Field(default_factory=lambda: list(METRICS), min_length=1, max_length=4)


class MonthlySavedQuery(MonthlyParams):
    kind: Literal["monthly"]


class SeriesSavedQuery(SeriesParams):
    kind: Literal["series"]


class SaveQuery(StrictModel):
    idempotency_key: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-zA-Z0-9._-]{1,128}$")]
    query: Annotated[MonthlySavedQuery | SeriesSavedQuery, Field(discriminator="kind")]


class ProfileArguments(StrictModel):
    dataset_id: Identifier


class SeriesArguments(SeriesParams):
    dataset_id: Identifier


class Coverage(BaseModel):
    status: Literal["FULL", "PARTIAL", "NONE"]
    basis: Literal["observed_source_day_bounds"] = "observed_source_day_bounds"
    source_start: str
    source_end_exclusive: str


class MonthlyResult(BaseModel):
    dataset_id: str
    data_hash: str
    metric_version: str
    transform_version: str
    currency: Literal["GBP"] = "GBP"
    source_timezone: Literal["UNSPECIFIED_LOCAL_TIME"] = "UNSPECIFIED_LOCAL_TIME"
    month: str
    period_start: str
    period_end_exclusive: str
    filters: Filters
    status: Status
    coverage: Coverage
    calendar_month_complete: bool
    source_row_count: int
    matched_row_count: int
    primary_class_counts: dict[str, int]
    positive_row_count: int
    cancel_row_count: int
    excluded_row_count: int
    positive_invoice_count: int | None
    positive_amount_exact: str | None
    cancellation_amount_exact: str | None
    net_amount_exact: str | None
    positive_amount_display: str | None
    cancellation_amount_display: str | None
    net_amount_display: str | None
    warnings: list[str]
    query_fingerprint: str


class SeriesPoint(BaseModel):
    month: str
    period_start: str
    period_end_exclusive: str
    status: Status
    coverage: Coverage
    value_exact: str | None
    value_display: str | None
    source_row_count: int
    matched_row_count: int
    included_row_count: int
    warnings: list[str]


class SeriesResult(BaseModel):
    dataset_id: str
    data_hash: str
    metric_version: str
    transform_version: str
    metric: MetricName
    unit: Literal["GBP", "invoice_count"]
    granularity: Literal["month"] = "month"
    date_from: str
    date_to: str
    filters: Filters
    status: Status
    points: list[SeriesPoint]
    warnings: list[str]
    query_fingerprint: str


class MetricDefinition(BaseModel):
    metric: MetricName
    label: str
    unit: Literal["GBP", "invoice_count"]
    formula: str
    inclusion: str
    exclusions: str


class DefinitionsResult(BaseModel):
    metric_version: str
    definitions: list[MetricDefinition]
    exact_scale: int = 3
    display_scale: int = 2
    display_rounding: Literal["ROUND_HALF_UP"] = "ROUND_HALF_UP"
    source_timezone: Literal["UNSPECIFIED_LOCAL_TIME"] = "UNSPECIFIED_LOCAL_TIME"
    duplicate_policy: Literal["retain_all_source_rows"] = "retain_all_source_rows"
    filters: list[str] = ["country", "stock_code"]
    warnings: list[str]


class HistoryResult(BaseModel):
    query_id: str
    dataset_id: str
    kind: Literal["monthly", "series"]
    parameters: dict[str, Any]
    result: MonthlyResult | SeriesResult
    result_sha256: str
    data_hash: str
    transform_version: str
    metric_version: str
    created_at: str


class HistoryItem(BaseModel):
    query_id: str
    dataset_id: str
    kind: Literal["monthly", "series"]
    parameters: dict[str, Any]
    status: Status
    data_hash: str
    created_at: str


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int
