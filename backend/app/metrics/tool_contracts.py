"""Bounded arguments shared by HTTP, B0 and the agent tool registry."""
from typing import Literal

from pydantic import Field, model_validator

from backend.app.errors import AppError
from backend.app.metrics.contracts import (
    DefinitionParams, Filters, Identifier, ISODate, SeriesParams, StrictModel,
)


class Period(StrictModel):
    date_from: ISODate
    date_to: ISODate = Field(description="Exclusive end; source local date, no timezone conversion")

    @model_validator(mode="after")
    def bounds(self):
        SeriesParams(metric="net_amount", **self.model_dump())
        return self


class DefinitionArguments(DefinitionParams):
    dataset_id: Identifier | None = None


class OptionalPeriodArguments(Filters):
    dataset_id: Identifier
    date_from: ISODate | None = None
    date_to: ISODate | None = None

    @model_validator(mode="after")
    def paired_dates(self):
        if (self.date_from is None) != (self.date_to is None):
            raise ValueError("Supply both dates or neither")
        if self.date_from is not None:
            Period(date_from=self.date_from, date_to=self.date_to)
        return self


class RankArguments(SeriesParams):
    dataset_id: Identifier
    dimension: Literal["product", "country"]
    top_k: int = Field(default=10, strict=True, ge=1, le=50)
    order: Literal["desc", "asc"] = "desc"


class CompareArguments(Filters):
    dataset_id: Identifier
    metric: Literal["positive_amount", "cancellation_amount", "net_amount", "positive_invoice_count"]
    baseline: Period
    current: Period


class DecomposeArguments(CompareArguments):
    dimension: Literal["product", "country"]
    top_k: int = Field(default=10, strict=True, ge=1, le=50)

    @model_validator(mode="after")
    def additive_metric(self):
        if self.metric == "positive_invoice_count":
            raise AppError("NON_ADDITIVE_METRIC", "Distinct invoice counts cannot be decomposed across entities.", 422)
        return self


class InspectArguments(OptionalPeriodArguments):
    primary_class: Literal["INVALID", "POSITIVE", "CANCELLATION", "EXCLUDED_OTHER"] | None = None
    limit: int = Field(default=20, strict=True, ge=1, le=50)
    order: Literal["source_row_asc", "source_row_desc"] = "source_row_asc"
