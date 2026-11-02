"""Eight deterministic tools. No model, arbitrary SQL, filesystem or URL access."""
from pydantic import ValidationError

from backend.app.errors import AppError
from backend.app.metrics.contracts import METRICS, METRIC_VERSION, ProfileArguments, SeriesArguments, SeriesParams
from backend.app.metrics.service import definitions, digest
from backend.app.metrics.analytics import AnalyticsService
from backend.app.metrics.tool_contracts import (
    CompareArguments, DecomposeArguments, DefinitionArguments, InspectArguments,
    OptionalPeriodArguments, RankArguments,
)

ARGUMENTS = {"get_dataset_profile": ProfileArguments, "get_metric_definitions": DefinitionArguments,
             "get_quality_summary": OptionalPeriodArguments, "query_metric_series": SeriesArguments,
             "rank_entities": RankArguments, "compare_periods": CompareArguments,
             "decompose_change": DecomposeArguments, "inspect_transactions": InspectArguments}

DESCRIPTIONS = {
    "get_dataset_profile": "Read snapshot identity, source coverage and available metrics.",
    "get_metric_definitions": "Read exact metric formulas and exclusions; dataset_id optionally binds the snapshot.",
    "get_quality_summary": "Read mutually exclusive row classes and overlapping quality flags; optional bounded dates.",
    "query_metric_series": "Read exact monthly values within a left-closed right-open date interval.",
    "rank_entities": "Rank products or countries, at most 50 rows; competition ties, deterministic entity order.",
    "compare_periods": "Compare two explicit periods; zero or negative baseline has no growth percentage.",
    "decompose_change": "Reconcile additive monetary changes by entity including an other remainder; not causal analysis.",
    "inspect_transactions": "Read at most 50 source rows with exact prices and quality flags, without customer identifiers.",
}


def tool_schemas():
    return [{"type": "function", "function": {"name": name, "description": DESCRIPTIONS[name], "parameters": model.model_json_schema()}}
            for name, model in ARGUMENTS.items()]


def exact_fields(value, prefix=""):
    """JSON field paths used by report validators; only stored numeric strings."""
    fields = {}
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, str) and (key.endswith("_exact") or key.endswith("_percent")):
                fields[path] = item
            elif isinstance(item, (dict, list)):
                fields.update(exact_fields(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            fields.update(exact_fields(item, f"{prefix}.{index}"))
    return fields


def execute_tool(service, name: str, arguments: dict) -> dict:
    if name not in ARGUMENTS:
        raise AppError("UNSUPPORTED_TOOL", "This tool is not implemented.", 422)
    try:
        args = ARGUMENTS[name].model_validate(arguments)
    except ValidationError:
        raise AppError("VALIDATION_ERROR", "Tool arguments failed validation.", 422) from None
    if name == "get_dataset_profile":
        result = service.profile(args.dataset_id)
        result.update(available_metrics=list(METRICS), fields=["invoice_no", "stock_code", "description", "quantity",
            "invoice_date_source", "unit_price_raw", "country", "primary_class", "quality_flags"],
            source_kind="historical_transactions")
    elif name == "get_metric_definitions":
        result = definitions(args.metric_names).model_dump(mode="json")
        if args.dataset_id:
            profile = service.profile(args.dataset_id)
            result.update({key:profile[key] for key in ("dataset_id", "data_hash", "transform_version")})
    elif name == "query_metric_series":
        result = service.series(args.dataset_id, SeriesParams(**args.model_dump(exclude={"dataset_id"}))).model_dump(mode="json")
    else:
        method = {"get_quality_summary":"quality", "rank_entities":"rank", "compare_periods":"compare",
                  "decompose_change":"decompose", "inspect_transactions":"inspect"}[name]
        result = getattr(AnalyticsService(service), method)(args)
    period = {key: result[key] for key in ("date_from", "date_to") if key in result}
    if name in {"compare_periods", "decompose_change"}:
        period = {key:getattr(args,key).model_dump(mode="json") for key in ("baseline", "current")}
    envelope = dict(tool=name, dataset_id=result.get("dataset_id"), snapshot_hash=result.get("data_hash"), metric_version=METRIC_VERSION,
        arguments=args.model_dump(mode="json"), filter=result.get("filters", {}),
        period=period,
        result=result, warnings=result.get("warnings", []))
    tool_call_id = "tc_" + digest(envelope)
    evidence = dict(tool_call_id=tool_call_id, dataset_id=result.get("dataset_id"),
        snapshot_hash=result.get("data_hash"), metric_version=METRIC_VERSION,
        transform_version=result.get("transform_version"), period=period, filters=envelope["filter"],
        query_fingerprint=result.get("query_fingerprint"), matched_row_count=result.get("matched_row_count"),
        excluded_row_count=result.get("excluded_row_count"), exact_values=exact_fields(result),
        scope="snapshot" if result.get("data_hash") else "global_metric_definitions")
    return dict(tool_call_id=tool_call_id, **envelope, status="PASS" if result.get("status") == "READY" else result.get("status", "PASS"),
                data=result, evidence=evidence, error=None)
