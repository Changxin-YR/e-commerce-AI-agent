"""Deterministic bounded queries. All monetary SQL aggregation uses integers."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from backend.app.errors import AppError
from backend.app.models import DatasetSnapshot, TransactionRow as Row
from backend.app.metrics.contracts import (
    Coverage, DefinitionsResult, Filters, METRIC_VERSION, MonthlyParams, MonthlyResult,
    PageParams, SeriesParams, SeriesPoint, SeriesResult, month_range, next_month,
)

CLASSES = ("INVALID", "POSITIVE", "CANCELLATION", "EXCLUDED_OTHER")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def money(value: int) -> tuple[str, str]:
    if type(value) is not int:
        raise AppError("NON_INTEGER_AMOUNT", "Stored amounts must be integers.")
    amount = Decimal(value) / Decimal(1000)
    display = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if display == 0:
        display = abs(display)
    return format(amount, ".3f"), format(display, ".2f")


def profile_dict(dataset: DatasetSnapshot) -> dict:
    ready = dataset.status == "READY"
    return dict(dataset_id=dataset.dataset_id, status=dataset.status,
        data_hash=dataset.workbook_sha256, raw_sha256=dataset.workbook_sha256,
        transform_version=dataset.transform_version, schema_version=dataset.schema_version,
        metric_version=dataset.metric_version, source_url=dataset.source_url, acquired_at=dataset.acquired_at,
        currency="GBP", source_timezone="UNSPECIFIED_LOCAL_TIME",
        row_count=dataset.row_count if ready else None,
        source_time_min=dataset.source_time_min if ready else None,
        source_time_max=dataset.source_time_max if ready else None)


def definitions(names) -> DefinitionsResult:
    specifications = {
        "positive_amount": ("正向交易行金额", "GBP", "SUM(POSITIVE.line_amount_milli_gbp) / 1000", "POSITIVE"),
        "cancellation_amount": ("取消类金额", "GBP", "-SUM(CANCELLATION.line_amount_milli_gbp) / 1000", "CANCELLATION"),
        "net_amount": ("净交易金额", "GBP", "positive_amount - cancellation_amount", "POSITIVE + CANCELLATION"),
        "positive_invoice_count": ("有效发票数", "invoice_count", "COUNT(DISTINCT POSITIVE.InvoiceNo) within each period", "POSITIVE"),
    }
    return DefinitionsResult(metric_version=METRIC_VERSION, definitions=[dict(
        metric=name, label=specifications[name][0], unit=specifications[name][1],
        formula=specifications[name][2], inclusion=specifications[name][3],
        exclusions="INVALID and EXCLUDED_OTHER; quality flags do not remove otherwise eligible rows")
        for name in dict.fromkeys(names)], warnings=[
            "TRANSACTION_AMOUNTS_INCLUDE_CHARGES", "NOT_FINANCIAL_REVENUE_OR_PAID_REFUNDS",
            "MONTHLY_DISTINCT_INVOICE_COUNTS_ARE_NOT_ADDITIVE",
        ])


class MetricService:
    def __init__(self, readonly_engine, require_database):
        self.engine = readonly_engine
        self.require_database = require_database

    def _dataset(self, session, dataset_id, *, require_ready=True):
        self.require_database()
        dataset = session.get(DatasetSnapshot, dataset_id)
        if dataset is None:
            raise AppError("NOT_FOUND", "Dataset not found.", 404)
        if require_ready and dataset.status != "READY":
            raise AppError("DATASET_NOT_READY", "Metrics require a complete READY snapshot.", 409)
        if require_ready and dataset.metric_version != METRIC_VERSION:
            raise AppError("UNSUPPORTED_METRIC_VERSION", "Snapshot metric version is unsupported.", 409)
        return dataset

    def profile(self, dataset_id):
        with Session(self.engine) as session:
            return profile_dict(self._dataset(session, dataset_id))

    def datasets(self, params: PageParams):
        self.require_database()
        with Session(self.engine) as session:
            total = session.scalar(select(func.count()).select_from(DatasetSnapshot))
            items = session.scalars(select(DatasetSnapshot).order_by(
                DatasetSnapshot.acquired_at.desc(), DatasetSnapshot.dataset_id).limit(params.limit).offset(params.offset))
            return dict(items=[profile_dict(d) for d in items], total=total, **params.model_dump())

    def _aggregate(self, session, dataset_id, start, end, filters):
        matches = and_(True, *[getattr(Row, key) == value for key, value in filters.model_dump().items() if value is not None])
        positive = and_(matches, Row.primary_class == "POSITIVE")
        cancellation = and_(matches, Row.primary_class == "CANCELLATION")
        month = func.substr(Row.invoice_date_source, 1, 7)
        statement = select(month.label("month"), func.count().label("source"),
            func.sum(case((matches, 1), else_=0)).label("matched"),
            *[func.sum(case((and_(matches, Row.primary_class == name), 1), else_=0)).label(name) for name in CLASSES],
            func.sum(case((positive, Row.line_amount_milli_gbp), else_=0)).label("positive"),
            func.sum(case((cancellation, -Row.line_amount_milli_gbp), else_=0)).label("cancellation"),
            func.count(func.distinct(case((positive, Row.invoice_no)))).label("invoices"),
        ).where(Row.dataset_id == dataset_id, Row.invoice_date_source >= start.isoformat() + " 00:00:00",
                Row.invoice_date_source < end.isoformat() + " 00:00:00").group_by(month)
        return {row["month"]: dict(row) for row in session.execute(statement).mappings()}

    def _period(self, dataset, start, end, filters, aggregate):
        # Observed day bounds, not a claim that every intervening day has transactions.
        if not dataset.source_time_min or not dataset.source_time_max:
            raise AppError("INVALID_SNAPSHOT", "READY snapshot has no observed date bounds.", 409)
        lower = date.fromisoformat(dataset.source_time_min[:10])
        upper = date.fromisoformat(dataset.source_time_max[:10]) + timedelta(days=1)
        coverage = "NONE" if end <= lower or start >= upper else ("FULL" if start >= lower and end <= upper else "PARTIAL")
        month_first = start.replace(day=1)
        complete = coverage == "FULL" and start == month_first and end == next_month(month_first)
        source, matched = aggregate.get("source", 0), aggregate.get("matched", 0)
        status = "NO_DATA" if source == 0 else ("EMPTY_RESULT" if matched == 0 else ("PASS" if complete else "PARTIAL_PERIOD"))
        warnings = list(dataset.summary.get("warnings", []))
        if "SOURCE_TIMEZONE_UNSPECIFIED" not in warnings:
            warnings.append("SOURCE_TIMEZONE_UNSPECIFIED")
        if dataset.summary.get("quality_flags", {}).get("MISSING_CUSTOMER_ID", 0):
            warnings.append("MISSING_CUSTOMER_ID_RETAINED")
        if dataset.summary.get("invoices_multiple_months", 0):
            warnings.append("INVOICES_SPAN_MONTHS")
        if not complete:
            warnings.append("PERIOD_NOT_FULLY_COVERED" if coverage != "FULL" else "CALENDAR_MONTH_TRUNCATED")
        if status in {"NO_DATA", "EMPTY_RESULT"}:
            warnings.append(status)
        positive, cancel = aggregate.get("positive", 0), aggregate.get("cancellation", 0)
        amounts = {}
        for key, value in (("positive", positive), ("cancellation", cancel), ("net", positive - cancel)):
            exact, display = money(value)
            amounts[key + "_amount_exact"] = None if status == "NO_DATA" else exact
            amounts[key + "_amount_display"] = None if status == "NO_DATA" else display
        identity = dict(dataset_id=dataset.dataset_id, data_hash=dataset.workbook_sha256,
                        metric_version=dataset.metric_version, transform_version=dataset.transform_version)
        fingerprint = digest(dict(**identity, start=start.isoformat(), end=end.isoformat(), filters=filters.model_dump(), kind="monthly"))
        return MonthlyResult(**identity, month=start.isoformat()[:7], period_start=start.isoformat(),
            period_end_exclusive=end.isoformat(), filters=filters, status=status,
            coverage=Coverage(status=coverage, source_start=lower.isoformat(), source_end_exclusive=upper.isoformat()),
            calendar_month_complete=complete, source_row_count=source, matched_row_count=matched,
            primary_class_counts={key: aggregate.get(key, 0) for key in CLASSES},
            positive_row_count=aggregate.get("POSITIVE", 0), cancel_row_count=aggregate.get("CANCELLATION", 0),
            excluded_row_count=aggregate.get("EXCLUDED_OTHER", 0) + aggregate.get("INVALID", 0),
            positive_invoice_count=None if status == "NO_DATA" else aggregate.get("invoices", 0),
            warnings=list(dict.fromkeys(warnings)), query_fingerprint=fingerprint, **amounts)

    def monthly(self, dataset_id, params: MonthlyParams) -> MonthlyResult:
        start, end = month_range(params.month)
        filters = Filters(country=params.country, stock_code=params.stock_code)
        with Session(self.engine) as session:
            dataset = self._dataset(session, dataset_id)
            groups = self._aggregate(session, dataset_id, start, end, filters)
            return self._period(dataset, start, end, filters, groups.get(params.month, {}))

    def series(self, dataset_id, params: SeriesParams) -> SeriesResult:
        filters = Filters(country=params.country, stock_code=params.stock_code)
        with Session(self.engine) as session:
            dataset = self._dataset(session, dataset_id)
            groups = self._aggregate(session, dataset_id, params.date_from, params.date_to, filters)
            points, warnings = [], []
            cursor = params.date_from.replace(day=1)
            while cursor < params.date_to:
                start, end = max(cursor, params.date_from), min(next_month(cursor), params.date_to)
                item = self._period(dataset, start, end, filters, groups.get(cursor.isoformat()[:7], {}))
                if params.metric == "positive_invoice_count":
                    exact = str(item.positive_invoice_count) if item.positive_invoice_count is not None else None
                    display = exact
                else:
                    exact, display = getattr(item, params.metric + "_exact"), getattr(item, params.metric + "_display")
                included = item.positive_row_count if params.metric in {"positive_amount", "positive_invoice_count"} else (
                    item.cancel_row_count if params.metric == "cancellation_amount" else item.positive_row_count + item.cancel_row_count)
                points.append(SeriesPoint(month=item.month, period_start=item.period_start, period_end_exclusive=item.period_end_exclusive,
                    status=item.status, coverage=item.coverage, value_exact=exact, value_display=display,
                    source_row_count=item.source_row_count, matched_row_count=item.matched_row_count,
                    included_row_count=included, warnings=item.warnings))
                warnings.extend(item.warnings)
                cursor = next_month(cursor)
            source, matched = sum(p.source_row_count for p in points), sum(p.matched_row_count for p in points)
            status = "NO_DATA" if source == 0 else ("EMPTY_RESULT" if matched == 0 else (
                "PARTIAL_PERIOD" if any(p.status in {"NO_DATA", "PARTIAL_PERIOD"} or p.coverage.status != "FULL"
                    or "CALENDAR_MONTH_TRUNCATED" in p.warnings for p in points) else "PASS"))
            identity = dict(dataset_id=dataset_id, data_hash=dataset.workbook_sha256,
                metric_version=dataset.metric_version, transform_version=dataset.transform_version)
            return SeriesResult(**identity, metric=params.metric,
                unit="invoice_count" if params.metric == "positive_invoice_count" else "GBP",
                date_from=params.date_from.isoformat(), date_to=params.date_to.isoformat(), filters=filters,
                status=status, points=points, warnings=list(dict.fromkeys(warnings)),
                query_fingerprint=digest(dict(**identity, kind="series", parameters=params.model_dump(mode="json"))))
