"""A single local writer, batched persistence and atomic READY publication."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import Settings
from backend.app.database import create_database_engine, create_session_factory, current_schema_revision
from backend.app.errors import AppError
from backend.app.imports.locks import WriterLease
from backend.app.imports.rows import INT64_MAX, read_rows, transform_row
from backend.app.imports.source import OFFICIAL_SHA, SOURCE_URL, check_time, prepare_source, sha256
from backend.app.models import Base, DatasetSnapshot, ImportBatch, QualityIssue, TransactionRow

TRANSFORM_VERSION = "uci352-ooxml-milligbp-v1"
CLASSES = ("INVALID", "POSITIVE", "CANCELLATION", "EXCLUDED_OTHER")
BATCH_SIZE = 2000


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ImportService:
    def __init__(self, settings: Settings, *, test_hashes: frozenset[str] | None = None):
        if test_hashes is not None and settings.app_env != "test":
            raise ValueError("Fixture hashes require the test environment")
        self.settings = settings
        self.allowed_hashes = test_hashes if test_hashes is not None else frozenset({OFFICIAL_SHA})
        self.engine = create_database_engine(settings)
        self.sessions = create_session_factory(self.engine)
        self.read_engine = create_database_engine(settings, readonly=True)
        self.read_sessions = create_session_factory(self.read_engine)
        self.lease = WriterLease(settings.database_path.with_suffix(".import.lock"))
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dataset-import")
        self.ready = False
        self.expected_revision = current_schema_revision()

    def start(self):
        if not self.settings.database_path.is_file():
            return
        try:
            with self.engine.connect() as connection:
                version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                tables = set(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
                if version != self.expected_revision or not set(Base.metadata.tables).issubset(tables):
                    return
                marker = connection.execute(text("SELECT value FROM app_metadata WHERE key='project_id'")).scalar_one_or_none()
                if marker != "ecommerce-agent-thesis":
                    return
            self.ready = True
            if self.lease.acquire():
                with self.sessions() as session:
                    interrupted = session.scalars(select(ImportBatch).where(ImportBatch.status.in_(["QUEUED", "IMPORTING"]))).all()
                    for batch in interrupted:
                        self._fail(session, batch, "IMPORT_INTERRUPTED")
                    if interrupted:
                        session.commit()
        except (SQLAlchemyError, OSError):
            self.ready = False
            self.lease.close()

    def close(self):
        self.executor.shutdown(wait=True)
        self.lease.close()
        self.engine.dispose()
        self.read_engine.dispose()

    def require_database(self):
        if not self.ready:
            raise AppError("DATABASE_MIGRATION_REQUIRED", "Run the database migration before using data APIs.")

    def submit(self, path: Path, *, background: bool = True) -> dict:
        self.require_database()
        deadline = time.monotonic() + self.settings.import_timeout_seconds
        source = prepare_source(path, self.settings.raw_data_dir, self.settings.import_cache_dir,
                                deadline, self.allowed_hashes)
        identity = hashlib.sha256((source.workbook_sha256 + ":" + TRANSFORM_VERSION).encode()).hexdigest()[:32]
        dataset_id, batch_id = "ds_" + identity, "ib_" + identity
        container = {"sha256": source.submitted_file_sha256, "bytes": source.submitted_bytes, "kind": source.container_kind}
        launch = False
        with self.sessions() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            batch = session.get(ImportBatch, batch_id)
            if batch:
                if container not in batch.containers:
                    batch.containers = [*batch.containers, container]
                if batch.status == "FAILED":
                    if not self.lease.stream:
                        raise AppError("IMPORTER_BUSY", "Retry through the running local importer.", 409)
                    batch.status, batch.error_code, batch.row_count, batch.imported_at = "QUEUED", None, 0, None
                    batch.attempt += 1
                    dataset = session.get(DatasetSnapshot, dataset_id)
                    dataset.status, dataset.summary, dataset.row_count = "QUEUED", {}, 0
                    launch = True
            else:
                if not self.lease.stream:
                    raise AppError("IMPORTER_BUSY", "Another local importer owns the writer.", 409)
                dataset = DatasetSnapshot(
                    dataset_id=dataset_id, workbook_sha256=source.workbook_sha256,
                    transform_version=TRANSFORM_VERSION, schema_version="uci-8-v1",
                    metric_version="retail-v1.2", source_url=SOURCE_URL if source.workbook_sha256 == OFFICIAL_SHA else "test_fixture",
                    acquired_at=now(), workbook_path=str(source.workbook_path.resolve()), status="QUEUED", row_count=0, summary={})
                session.add(dataset)
                session.flush()
                batch = ImportBatch(batch_id=batch_id, dataset_id=dataset_id,
                    submitted_file_sha256=source.submitted_file_sha256, workbook_sha256=source.workbook_sha256,
                    transform_version=TRANSFORM_VERSION, containers=[container], status="QUEUED",
                    row_count=0, created_at=now(), failures=[], attempt=1)
                session.add(batch)
                launch = True
            session.commit()
            result = self._batch_dict(batch)
        if launch:
            if background:
                self.executor.submit(self._run, batch_id)
            else:
                self._run(batch_id)
                result = self.batch(batch_id)
        return result

    def _batch_dict(self, batch: ImportBatch) -> dict:
        return {"batch_id": batch.batch_id, "dataset_id": batch.dataset_id, "status": batch.status,
                "raw_sha256": batch.workbook_sha256, "workbook_sha256": batch.workbook_sha256,
                "submitted_file_sha256": batch.submitted_file_sha256, "containers": batch.containers,
                "transform_version": batch.transform_version, "processed_rows": batch.row_count,
                "attempt": batch.attempt, "error_code": batch.error_code, "failures": batch.failures,
                "created_at": batch.created_at, "imported_at": batch.imported_at}

    def batch(self, batch_id: str) -> dict:
        self.require_database()
        with self.read_sessions() as session:
            batch = session.get(ImportBatch, batch_id)
            if not batch:
                raise AppError("NOT_FOUND", "Import batch not found.", 404)
            return self._batch_dict(batch)

    def profile(self, dataset_id: str, *, quality: bool = False) -> dict:
        self.require_database()
        with self.read_sessions() as session:
            dataset = session.get(DatasetSnapshot, dataset_id)
            if not dataset:
                raise AppError("NOT_FOUND", "Dataset not found.", 404)
            if quality and dataset.status != "READY":
                raise AppError("DATASET_NOT_READY", "Quality results are unavailable until the complete import is READY.", 409)
            result = {"dataset_id": dataset.dataset_id, "status": dataset.status,
                      "data_hash": dataset.workbook_sha256, "raw_sha256": dataset.workbook_sha256,
                      "transform_version": dataset.transform_version, "schema_version": dataset.schema_version,
                      "metric_version": dataset.metric_version, "source_url": dataset.source_url,
                      "acquired_at": dataset.acquired_at, "currency": "GBP",
                      "source_timezone": "UNSPECIFIED_LOCAL_TIME",
                      "row_count": dataset.row_count if dataset.status == "READY" else None,
                      "source_time_min": dataset.source_time_min if dataset.status == "READY" else None,
                      "source_time_max": dataset.source_time_max if dataset.status == "READY" else None}
            if quality:
                result.update(dataset.summary)
            return result

    def _fail(self, session, batch: ImportBatch, code: str):
        batch.status, batch.error_code = "FAILED", code
        batch.failures = [*batch.failures, {"attempt": batch.attempt, "code": code, "at": now(), "processed_rows": batch.row_count}]
        session.get(DatasetSnapshot, batch.dataset_id).status = "FAILED"

    def _write_chunk(self, dataset_id: str, batch_id: str, rows: list[dict], total: int):
        issues = [{"dataset_id": dataset_id, "row_ref": row["source_row_num"], "issue_code": code}
                  for row in rows for code in row["quality_flags"]]
        with self.engine.begin() as connection:
            connection.execute(insert(TransactionRow), rows)
            if issues:
                connection.execute(insert(QualityIssue), issues)
            connection.execute(update(ImportBatch).where(ImportBatch.batch_id == batch_id).values(row_count=total))

    def _run(self, batch_id: str):
        try:
            started = time.monotonic()
            deadline = started + self.settings.import_timeout_seconds
            with self.sessions() as session:
                batch = session.get(ImportBatch, batch_id)
                if not batch or batch.status != "QUEUED":
                    return
                dataset = session.get(DatasetSnapshot, batch.dataset_id)
                dataset_id, path, expected_hash = dataset.dataset_id, Path(dataset.workbook_path), dataset.workbook_sha256
                batch.status = dataset.status = "IMPORTING"
                # Only the failed/current snapshot is cleared; READY snapshots are immutable.
                session.execute(delete(QualityIssue).where(QualityIssue.dataset_id == dataset_id))
                session.execute(delete(TransactionRow).where(TransactionRow.dataset_id == dataset_id))
                session.commit()
            if not path.is_file() or sha256(path) != expected_hash:
                raise AppError("ARCHIVED_SOURCE_CORRUPT", "Archived source is missing or changed.", 422)
            counts, quality_counts, seen = Counter({k: 0 for k in CLASSES}), Counter(), set()
            rows, total, sum_abs = [], 0, 0
            for number, cells in read_rows(path, deadline):
                row = transform_row(dataset_id, number, cells)
                if row["row_fingerprint"] in seen:
                    row["quality_flags"].append("DUPLICATE_CANDIDATE_AFTER_FIRST")
                seen.add(row["row_fingerprint"])
                counts[row["primary_class"]] += 1
                quality_counts.update(row["quality_flags"])
                sum_abs += abs(row["line_amount_milli_gbp"] or 0)
                if sum_abs > INT64_MAX:
                    raise AppError("AGGREGATE_OVERFLOW", "Aggregate amount exceeds the supported integer range.", 422)
                rows.append(row)
                total += 1
                if len(rows) == BATCH_SIZE:
                    self._write_chunk(dataset_id, batch_id, rows, total)
                    rows = []
            if rows:
                self._write_chunk(dataset_id, batch_id, rows, total)
            with self.sessions() as session:
                actual_counts = dict(session.execute(select(TransactionRow.primary_class, func.count()).where(TransactionRow.dataset_id == dataset_id).group_by(TransactionRow.primary_class)).all())
                actual_quality = dict(session.execute(select(QualityIssue.issue_code, func.count()).where(QualityIssue.dataset_id == dataset_id).group_by(QualityIssue.issue_code)).all())
                if sum(counts.values()) != total or any(actual_counts.get(k, 0) != v for k, v in counts.items()) or actual_quality != dict(quality_counts):
                    raise AppError("RECONCILIATION_FAILED", "Persisted rows failed reconciliation.", 422)
                range_row = session.execute(select(func.min(TransactionRow.invoice_date_source), func.max(TransactionRow.invoice_date_source),
                    func.count(func.distinct(TransactionRow.invoice_no)), func.count(func.distinct(TransactionRow.stock_code)),
                    func.count(func.distinct(TransactionRow.country))).where(TransactionRow.dataset_id == dataset_id)).one()
                duplicate_sizes = session.execute(text("SELECT COUNT(*) AS n FROM transaction_rows WHERE dataset_id=:d GROUP BY row_fingerprint HAVING COUNT(*)>1"), {"d": dataset_id}).scalars().all()
                anomalies = session.execute(text("SELECT COUNT(DISTINCT invoice_date_source), COUNT(DISTINCT substr(invoice_date_source,1,10)), COUNT(DISTINCT substr(invoice_date_source,1,7)) FROM transaction_rows WHERE dataset_id=:d GROUP BY invoice_no HAVING COUNT(DISTINCT invoice_date_source)>1"), {"d": dataset_id}).all()
                dataset, batch = session.get(DatasetSnapshot, dataset_id), session.get(ImportBatch, batch_id)
                dataset.row_count, dataset.source_time_min, dataset.source_time_max = total, range_row[0], range_row[1]
                dataset.summary = {"raw_row_count": total, "primary_class_counts": dict(counts), "quality_flags": dict(quality_counts),
                    "quality_flags_overlap": True, "duplicates_retained": True, "duplicate_group_rows": sum(duplicate_sizes),
                    "duplicate_candidates_after_first": sum(n - 1 for n in duplicate_sizes),
                    "distinct_invoices": range_row[2], "distinct_stock_codes": range_row[3], "distinct_countries": range_row[4],
                    "invoices_multiple_timestamps": len(anomalies), "invoices_multiple_days": sum(a[1] > 1 for a in anomalies),
                    "invoices_multiple_months": sum(a[2] > 1 for a in anomalies), "absolute_amount_milli_gbp": str(sum_abs),
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "warnings": ["SOURCE_TIMEZONE_UNSPECIFIED", "DUPLICATE_CANDIDATES_RETAINED", "TRANSACTION_AMOUNTS_INCLUDE_CHARGES"]}
                check_time(deadline)
                if counts["INVALID"]:
                    self._fail(session, batch, "INVALID_ROWS_PRESENT")
                else:
                    dataset.status = batch.status = "READY"
                    batch.imported_at = now()
                session.commit()
        except Exception as exc:
            code = exc.code if isinstance(exc, AppError) else "IMPORT_FAILED"
            with self.sessions() as session:
                batch = session.get(ImportBatch, batch_id)
                if batch:
                    self._fail(session, batch, code)
                    session.commit()
