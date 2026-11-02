"""Three deterministic D3 tools. No model, arbitrary SQL, filesystem or URL access."""
from pydantic import ValidationError

from backend.app.errors import AppError
from backend.app.metrics.contracts import DefinitionParams, METRIC_VERSION, ProfileArguments, SeriesArguments, SeriesParams
from backend.app.metrics.service import definitions, digest

ARGUMENTS = {"get_dataset_profile": ProfileArguments, "get_metric_definitions": DefinitionParams,
             "query_metric_series": SeriesArguments}


def tool_schemas():
    return [{"type": "function", "function": {"name": name, "parameters": model.model_json_schema()}}
            for name, model in ARGUMENTS.items()]


def execute_tool(service, name: str, arguments: dict) -> dict:
    if name not in ARGUMENTS:
        raise AppError("UNSUPPORTED_TOOL", "This tool is not implemented.", 422)
    try:
        args = ARGUMENTS[name].model_validate(arguments)
    except ValidationError:
        raise AppError("VALIDATION_ERROR", "Tool arguments failed validation.", 422) from None
    if name == "get_dataset_profile":
        result = service.profile(args.dataset_id)
    elif name == "get_metric_definitions":
        result = definitions(args.metric_names).model_dump(mode="json")
    else:
        result = service.series(args.dataset_id, SeriesParams(**args.model_dump(exclude={"dataset_id"}))).model_dump(mode="json")
    envelope = dict(tool=name, snapshot_hash=result.get("data_hash"), metric_version=METRIC_VERSION,
        arguments=args.model_dump(mode="json"), filter=result.get("filters", {}),
        period={key: result[key] for key in ("date_from", "date_to") if key in result},
        result=result, warnings=result.get("warnings", []))
    return dict(tool_call_id="tc_" + digest(envelope), **envelope)
