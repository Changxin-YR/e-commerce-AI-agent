"""Explicit POST persists a result; GET only reads and verifies saved JSON."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app.errors import AppError
from backend.app.metrics.contracts import HistoryItem, HistoryPage, HistoryResult, MonthlyParams, SeriesParams
from backend.app.metrics.service import digest
from backend.app.models import QueryHistory


def history_result(row) -> HistoryResult:
    if digest(row.result) != row.result_sha256:
        raise AppError("HISTORY_INTEGRITY_ERROR", "Saved result failed integrity verification.", 409)
    return HistoryResult(query_id=row.query_id, dataset_id=row.dataset_id, kind=row.query_kind,
        parameters=row.parameters, result=row.result, result_sha256=row.result_sha256,
        data_hash=row.workbook_sha256, transform_version=row.transform_version,
        metric_version=row.metric_version, created_at=row.created_at)


class HistoryService:
    def __init__(self, metric_service, write_engine):
        self.metrics = metric_service
        self.write_engine = write_engine

    def get(self, query_id):
        self.metrics.require_database()
        with Session(self.metrics.engine) as session:
            row = session.get(QueryHistory, query_id)
            if row is None:
                raise AppError("NOT_FOUND", "Saved query not found.", 404)
            return history_result(row)

    def list(self, dataset_id, params):
        with Session(self.metrics.engine) as session:
            self.metrics._dataset(session, dataset_id, require_ready=False)
            predicate = QueryHistory.dataset_id == dataset_id
            total = session.scalar(select(func.count()).select_from(QueryHistory).where(predicate))
            rows = session.scalars(select(QueryHistory).where(predicate).order_by(
                QueryHistory.created_at.desc(), QueryHistory.query_id).limit(params.limit).offset(params.offset))
            items = [HistoryItem(query_id=r.query_id, dataset_id=r.dataset_id, kind=r.query_kind,
                parameters=r.parameters, status=r.result["status"], data_hash=r.workbook_sha256, created_at=r.created_at) for r in rows]
            return HistoryPage(items=items, total=total, **params.model_dump())

    def save(self, dataset_id, request):
        self.metrics.require_database()
        parameters = request.query.model_dump(mode="json")
        request_hash = digest(parameters)
        predicate = (QueryHistory.dataset_id == dataset_id, QueryHistory.idempotency_key == request.idempotency_key)

        def existing(session):
            row = session.scalar(select(QueryHistory).where(*predicate))
            if row and row.request_sha256 != request_hash:
                raise AppError("IDEMPOTENCY_CONFLICT", "Submission key was already used with different parameters.", 409)
            return row

        with Session(self.metrics.engine) as session:
            row = existing(session)
            if row:
                return history_result(row), False
        args = {k: v for k, v in parameters.items() if k != "kind"}
        result = (self.metrics.monthly(dataset_id, MonthlyParams(**args)) if request.query.kind == "monthly"
                  else self.metrics.series(dataset_id, SeriesParams(**args))).model_dump(mode="json")
        # Compute outside the write lock; a concurrent submission wins without a duplicate row.
        with Session(self.write_engine) as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = existing(session)
            if row:
                return history_result(row), False
            row = QueryHistory(query_id="q_" + uuid4().hex, dataset_id=dataset_id,
                idempotency_key=request.idempotency_key, request_sha256=request_hash,
                query_kind=request.query.kind, parameters=parameters, result=result, result_sha256=digest(result),
                workbook_sha256=result["data_hash"], transform_version=result["transform_version"],
                metric_version=result["metric_version"], created_at=datetime.now(timezone.utc).isoformat())
            session.add(row)
            session.flush()
            response = history_result(row)
            session.commit()
            return response, True
