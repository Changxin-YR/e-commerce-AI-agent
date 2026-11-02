"""Read-only business calculations; all sums use SQLite INTEGER and Decimal."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from backend.app.errors import AppError
from backend.app.models import QualityIssue, TransactionRow as Row
from backend.app.metrics.contracts import Filters
from backend.app.metrics.service import CLASSES, digest, money


def percentage(numerator, denominator):
    if denominator == 0:
        return None
    return format((Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP), ".6f")


def exact(value, metric):
    return str(value) if metric == "positive_invoice_count" else money(value)[0]


class AnalyticsService:
    def __init__(self, metrics):
        self.metrics = metrics

    def _where(self, args, period=None, *, filtered=True):
        clauses = [Row.dataset_id == args.dataset_id]
        period = period or args
        if getattr(period, "date_from", None) is not None:
            clauses += [Row.invoice_date_source >= period.date_from.isoformat() + " 00:00:00",
                        Row.invoice_date_source < period.date_to.isoformat() + " 00:00:00"]
        if filtered:
            clauses += [getattr(Row, name) == getattr(args, name) for name in ("country", "stock_code")
                        if getattr(args, name) is not None]
        return clauses

    def _expression(self, metric):
        positive = Row.primary_class == "POSITIVE"
        cancellation = Row.primary_class == "CANCELLATION"
        if metric == "positive_invoice_count":
            return func.count(func.distinct(case((positive, Row.invoice_no))))
        value = {"positive_amount": case((positive, Row.line_amount_milli_gbp), else_=0),
                 "cancellation_amount": case((cancellation, -Row.line_amount_milli_gbp), else_=0),
                 "net_amount": case((Row.primary_class.in_(["POSITIVE", "CANCELLATION"]), Row.line_amount_milli_gbp), else_=0)}[metric]
        return func.coalesce(func.sum(value), 0)

    def _identity(self, dataset, args):
        identity = dict(dataset_id=dataset.dataset_id, data_hash=dataset.workbook_sha256,
                        metric_version=dataset.metric_version, transform_version=dataset.transform_version)
        return dict(**identity, filters=Filters(country=args.country, stock_code=args.stock_code).model_dump(),
                    query_fingerprint=digest(dict(**identity, arguments=args.model_dump(mode="json"))))

    def _summary(self, session, dataset, args, period=None):
        period = period or args
        source = session.scalar(select(func.count()).select_from(Row).where(*self._where(args, period, filtered=False)))
        classes = {name: 0 for name in CLASSES}
        classes.update(dict(session.execute(select(Row.primary_class, func.count()).where(
            *self._where(args, period)).group_by(Row.primary_class)).all()))
        matched = sum(classes.values())
        lower = date.fromisoformat(dataset.source_time_min[:10])
        upper = date.fromisoformat(dataset.source_time_max[:10]) + timedelta(days=1)
        start, end = getattr(period, "date_from", None), getattr(period, "date_to", None)
        coverage = "FULL" if start is None or (start >= lower and end <= upper) else (
            "NONE" if end <= lower or start >= upper else "PARTIAL")
        status = "NO_DATA" if not source else ("EMPTY_RESULT" if not matched else (
            "PARTIAL_PERIOD" if coverage != "FULL" else "PASS"))
        warnings = list(dataset.summary.get("warnings", [])) + ["SOURCE_TIMEZONE_UNSPECIFIED", "TRANSACTION_AMOUNTS_INCLUDE_CHARGES"]
        if coverage != "FULL":
            warnings.append("PERIOD_NOT_FULLY_COVERED")
        if status in {"NO_DATA", "EMPTY_RESULT"}:
            warnings.append(status)
        return dict(status=status, source_row_count=source, matched_row_count=matched,
                    excluded_row_count=classes["INVALID"] + classes["EXCLUDED_OTHER"],
                    primary_class_counts=classes, date_from=start.isoformat() if start else None,
                    date_to=end.isoformat() if end else None,
                    coverage=dict(status=coverage, basis="observed_source_day_bounds",
                                  source_start=lower.isoformat(), source_end_exclusive=upper.isoformat()),
                    warnings=list(dict.fromkeys(warnings)))

    def _total(self, session, args, period=None):
        return session.scalar(select(self._expression(args.metric)).where(*self._where(args, period)))

    def _groups(self, session, args, period=None):
        entity = Row.stock_code if args.dimension == "product" else Row.country
        eligible = ["POSITIVE"] if args.metric in {"positive_amount", "positive_invoice_count"} else (
            ["CANCELLATION"] if args.metric == "cancellation_amount" else ["POSITIVE", "CANCELLATION"])
        return dict(session.execute(select(entity, self._expression(args.metric)).where(
            *self._where(args, period), Row.primary_class.in_(eligible)).group_by(entity)).all())

    @staticmethod
    def _key(entity):
        # Missing dimension remains null, distinct from a literal "Unknown" entity.
        return (entity is None, entity or "")

    def quality(self, args):
        with Session(self.metrics.engine) as session:
            dataset = self.metrics._dataset(session, args.dataset_id)
            summary = self._summary(session, dataset, args)
            flags = dict(session.execute(select(QualityIssue.issue_code, func.count()).join(Row, and_(
                Row.dataset_id == QualityIssue.dataset_id, Row.source_row_num == QualityIssue.row_ref))
                .where(*self._where(args)).group_by(QualityIssue.issue_code)).all())
            return dict(**self._identity(dataset, args), **summary, raw_row_count=summary["matched_row_count"],
                        quality_flags=flags, quality_flags_overlap=True, duplicates_retained=True,
                        scope="snapshot" if args.date_from is None else "period",
                        invalid_dates_included=args.date_from is None,
                        snapshot_summary=dataset.summary if args.date_from is None and not args.country and not args.stock_code else None)

    def rank(self, args):
        with Session(self.metrics.engine) as session:
            dataset = self.metrics._dataset(session, args.dataset_id)
            summary = self._summary(session, dataset, args)
            groups, total = self._groups(session, args), self._total(session, args)
            ordered = sorted(groups, key=lambda key: ((-1 if args.order == "desc" else 1) * groups[key], self._key(key)))
            group_total, selected, items, previous, rank = sum(groups.values()), ordered[:args.top_k], [], None, 0
            for index, key in enumerate(selected, 1):
                value = groups[key]
                if value != previous:
                    rank = index
                items.append(dict(rank=rank, entity=key, entity_label=key if key is not None else "未知",
                                  value_exact=exact(value, args.metric), share_percent=percentage(value, group_total)))
                previous = value
            if args.metric == "positive_invoice_count":
                summary["warnings"].append("DISTINCT_INVOICES_ACROSS_ENTITIES_ARE_NOT_ADDITIVE")
            available = summary["status"] != "NO_DATA"
            return dict(**self._identity(dataset, args), **summary, metric=args.metric, dimension=args.dimension,
                        items=items, total_exact=exact(total, args.metric) if available else None,
                        group_total_exact=exact(group_total, args.metric) if available else None,
                        other_exact=exact(group_total-sum(groups[k] for k in selected), args.metric) if available else None,
                        entity_count=len(groups), returned_count=len(items), order=args.order,
                        tie_rule="competition_rank_then_entity_binary_ascending_null_last; top_k_is_hard_row_limit",
                        share_basis="sum_of_entity_values", reconciliation_exact=exact(group_total-total, args.metric) if available else None)

    def _comparison(self, session, dataset, args):
        baseline = self._summary(session, dataset, args, args.baseline)
        current = self._summary(session, dataset, args, args.current)
        before, after = self._total(session, args, args.baseline), self._total(session, args, args.current)
        available = baseline["status"] != "NO_DATA" and current["status"] != "NO_DATA"
        comparable = available and baseline["coverage"]["status"] == current["coverage"]["status"] == "FULL"
        warnings = list(dict.fromkeys(baseline["warnings"]+current["warnings"]))
        if (args.baseline.date_to-args.baseline.date_from) != (args.current.date_to-args.current.date_from):
            warnings.append("UNEQUAL_PERIOD_LENGTHS")
        if max(args.baseline.date_from, args.current.date_from) < min(args.baseline.date_to, args.current.date_to):
            warnings.append("OVERLAPPING_PERIODS")
        reason = "NO_DATA" if not available else ("ZERO_BASELINE" if before == 0 else ("NEGATIVE_BASELINE" if before < 0 else None))
        if reason:
            warnings.append(reason)
        status = "NO_DATA" if not available else ("PARTIAL_PERIOD" if not comparable else (
            "EMPTY_RESULT" if baseline["status"] == current["status"] == "EMPTY_RESULT" else "PASS"))
        return dict(**self._identity(dataset, args), status=status, metric=args.metric,
                    baseline=dict(**baseline, value_exact=exact(before,args.metric) if baseline["status"] != "NO_DATA" else None),
                    current=dict(**current, value_exact=exact(after,args.metric) if current["status"] != "NO_DATA" else None),
                    delta_exact=exact(after-before,args.metric) if available else None,
                    growth_percent=percentage(after-before,before) if reason is None else None,
                    growth_reason=reason, comparable=comparable, warnings=list(dict.fromkeys(warnings))), before, after

    def compare(self, args):
        with Session(self.metrics.engine) as session:
            dataset = self.metrics._dataset(session, args.dataset_id)
            return self._comparison(session, dataset, args)[0]

    def decompose(self, args):
        with Session(self.metrics.engine) as session:
            dataset = self.metrics._dataset(session, args.dataset_id)
            result, before, after = self._comparison(session, dataset, args)
            if result["status"] == "NO_DATA":
                return dict(**result, dimension=args.dimension, items=[], other_delta_exact=None,
                            sum_delta_exact=None, reconciliation_exact=None, reconciled=None)
            baseline, current = self._groups(session,args,args.baseline), self._groups(session,args,args.current)
            changes = {key: current.get(key,0)-baseline.get(key,0) for key in baseline.keys() | current.keys()}
            keys = sorted(changes, key=lambda key: (-abs(changes[key]), self._key(key)))[:args.top_k]
            total_delta, grouped_delta = after-before, sum(changes.values())
            if grouped_delta != total_delta:
                raise AppError("RECONCILIATION_FAILED", "Entity changes do not reconcile with the total.", 409)
            return dict(**result, dimension=args.dimension, entity_count=len(changes),
                        items=[dict(entity=key, entity_label=key if key is not None else "未知",
                                    baseline_exact=exact(baseline.get(key,0),args.metric),
                                    current_exact=exact(current.get(key,0),args.metric), delta_exact=exact(changes[key],args.metric),
                                    contribution_percent=percentage(changes[key],total_delta)) for key in keys],
                        other_delta_exact=exact(grouped_delta-sum(changes[k] for k in keys),args.metric),
                        sum_delta_exact=exact(grouped_delta,args.metric), reconciliation_exact="0.000", reconciled=True,
                        contribution_reason="ZERO_TOTAL_CHANGE" if total_delta == 0 else None,
                        order="absolute_delta_desc_then_entity_binary_ascending_null_last")

    def inspect(self, args):
        with Session(self.metrics.engine) as session:
            dataset = self.metrics._dataset(session,args.dataset_id)
            summary = self._summary(session,dataset,args)
            clauses = self._where(args)
            if args.primary_class:
                clauses.append(Row.primary_class == args.primary_class)
            total = session.scalar(select(func.count()).select_from(Row).where(*clauses))
            order = Row.source_row_num.asc() if args.order == "source_row_asc" else Row.source_row_num.desc()
            rows = session.scalars(select(Row).where(*clauses).order_by(order).limit(args.limit))
            items = [dict(source_row_num=r.source_row_num, invoice_no=r.invoice_no, stock_code=r.stock_code,
                          description=r.description, quantity=str(r.quantity) if r.quantity is not None else None,
                          invoice_date_source=r.invoice_date_source, country=r.country,
                          unit_price_raw=r.unit_price_raw, unit_price_exact=money(r.unit_price_milli_gbp)[0] if r.unit_price_milli_gbp is not None else None,
                          line_amount_exact=money(r.line_amount_milli_gbp)[0] if r.line_amount_milli_gbp is not None else None,
                          primary_class=r.primary_class, quality_flags=r.quality_flags) for r in rows]
            if not total and summary["status"] != "NO_DATA":
                summary["status"] = "EMPTY_RESULT"
                summary["warnings"] = list(dict.fromkeys(summary["warnings"]+["EMPTY_RESULT"]))
            return dict(**self._identity(dataset,args), **summary, total_matches=total, items=items,
                        limit=args.limit, returned_count=len(items), truncated=total>len(items),
                        primary_class_filter=args.primary_class, order=args.order,
                        field_meanings={"source_row_num":"Original workbook row, including header offset",
                                        "unit_price_raw":"Original OOXML price text", "line_amount_exact":"Signed source quantity * price in GBP; may be excluded from metrics"},
                        customer_identifier_policy="not_exposed_to_model")
