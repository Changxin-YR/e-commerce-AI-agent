"""Read-only metric routes and explicit history creation."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel

from backend.app.errors import AppError
from backend.app.metrics.contracts import (
    DefinitionParams, DefinitionsResult, HistoryPage, HistoryResult, Identifier,
    MonthlyParams, MonthlyResult, PageParams, SaveQuery, SeriesParams, SeriesResult,
)
from backend.app.metrics.service import definitions
from backend.app.metrics.tools import execute_tool, tool_schemas
from backend.app.schemas import DatasetProfile, ErrorResponse


def no_duplicates(request: Request):
    keys = [key for key, _ in request.query_params.multi_items() if key != "metric_names"]
    if len(keys) != len(set(keys)):
        raise AppError("VALIDATION_ERROR", "Duplicate scalar query parameters are not supported.", 422)


def no_query(request: Request):
    if request.query_params:
        raise AppError("VALIDATION_ERROR", "This endpoint accepts no query parameters.", 422)


router = APIRouter(prefix="/api/v1", dependencies=[Depends(no_duplicates)], responses={
    code: {"model": ErrorResponse} for code in (400, 403, 404, 409, 422, 503)})


class DatasetPage(BaseModel):
    items: list[DatasetProfile]
    total: int
    limit: int
    offset: int


@router.get("/tools", dependencies=[Depends(no_query)])
def tools():
    return {"tools": tool_schemas()}


@router.post("/tools/{tool_name}", dependencies=[Depends(no_query)])
def invoke_tool(tool_name: str, arguments: dict, request: Request):
    """Read-only execution; Origin protection also applies to this POST."""
    return execute_tool(request.app.state.metric_service, tool_name, arguments)


@router.get("/datasets", response_model=DatasetPage)
def datasets(request: Request, params: Annotated[PageParams, Query()]):
    return request.app.state.metric_service.datasets(params)


@router.get("/metric-definitions", response_model=DefinitionsResult)
def metric_definitions(params: Annotated[DefinitionParams, Query()]):
    return definitions(params.metric_names)


@router.get("/datasets/{dataset_id}/metrics/monthly", response_model=MonthlyResult)
def monthly(dataset_id: Identifier, request: Request, params: Annotated[MonthlyParams, Query()]):
    return request.app.state.metric_service.monthly(dataset_id, params)


@router.get("/datasets/{dataset_id}/metrics/series", response_model=SeriesResult)
def series(dataset_id: Identifier, request: Request, params: Annotated[SeriesParams, Query()]):
    return request.app.state.metric_service.series(dataset_id, params)


@router.post("/datasets/{dataset_id}/queries", response_model=HistoryResult, status_code=201,
    dependencies=[Depends(no_query)], responses={200: {"model": HistoryResult, "description": "Previously saved idempotent submission"}})
def save_query(dataset_id: Identifier, payload: SaveQuery, request: Request, response: Response):
    result, created = request.app.state.history_service.save(dataset_id, payload)
    response.status_code = 201 if created else 200
    return result


@router.get("/datasets/{dataset_id}/queries", response_model=HistoryPage)
def queries(dataset_id: Identifier, request: Request, params: Annotated[PageParams, Query()]):
    return request.app.state.history_service.list(dataset_id, params)


@router.get("/queries/{query_id}", response_model=HistoryResult, dependencies=[Depends(no_query)])
def query(query_id: Identifier, request: Request):
    return request.app.state.history_service.get(query_id)
