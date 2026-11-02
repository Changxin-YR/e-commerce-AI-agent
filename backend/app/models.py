"""Only infrastructure metadata is created in D0."""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AppMetadata(Base):
    __tablename__ = "app_metadata"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"
    __table_args__ = (
        UniqueConstraint("workbook_sha256", "transform_version"),
        CheckConstraint("status IN ('QUEUED','IMPORTING','READY','FAILED')"),
    )
    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    transform_version: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[str] = mapped_column(String(32))
    metric_version: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[str] = mapped_column(Text)
    acquired_at: Mapped[str] = mapped_column(String(40))
    workbook_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    source_time_min: Mapped[str | None] = mapped_column(String(32))
    source_time_max: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (CheckConstraint("status IN ('QUEUED','IMPORTING','READY','FAILED')"),)
    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.dataset_id"), unique=True)
    submitted_file_sha256: Mapped[str] = mapped_column(String(64))
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    transform_version: Mapped[str] = mapped_column(String(32))
    containers: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))
    imported_at: Mapped[str | None] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(64))
    failures: Mapped[list] = mapped_column(JSON, default=list)
    attempt: Mapped[int] = mapped_column(Integer, default=1)


class TransactionRow(Base):
    __tablename__ = "transaction_rows"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_row_num"),
        CheckConstraint("primary_class IN ('INVALID','POSITIVE','CANCELLATION','EXCLUDED_OTHER')"),
        Index("ix_transactions_period", "dataset_id", "invoice_date_source", "primary_class"),
        Index("ix_transactions_invoice", "dataset_id", "invoice_no"),
        Index("ix_transactions_stock", "dataset_id", "stock_code"),
        Index("ix_transactions_country", "dataset_id", "country"),
        Index("ix_transactions_fingerprint", "dataset_id", "row_fingerprint"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.dataset_id"))
    source_row_num: Mapped[int] = mapped_column(Integer)
    raw_fields: Mapped[list] = mapped_column(JSON)
    invoice_no: Mapped[str | None] = mapped_column(Text)
    stock_code: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int | None] = mapped_column(BigInteger)
    invoice_date_source: Mapped[str | None] = mapped_column(String(32))
    customer_id: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    unit_price_raw: Mapped[str | None] = mapped_column(Text)
    unit_price_milli_gbp: Mapped[int | None] = mapped_column(BigInteger)
    line_amount_milli_gbp: Mapped[int | None] = mapped_column(BigInteger)
    primary_class: Mapped[str] = mapped_column(String(24))
    quality_flags: Mapped[list] = mapped_column(JSON)
    row_fingerprint: Mapped[str] = mapped_column(String(64))


class QualityIssue(Base):
    __tablename__ = "quality_issues"
    __table_args__ = (UniqueConstraint("dataset_id", "row_ref", "issue_code"),
                     Index("ix_quality_code", "dataset_id", "issue_code"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.dataset_id"))
    row_ref: Mapped[int] = mapped_column(Integer)
    issue_code: Mapped[str] = mapped_column(String(64))


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.dataset_id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40))


class Report(Base):
    __tablename__ = "reports"
    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id"), unique=True)
    created_at: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSON)


class QueryHistory(Base):
    __tablename__ = "query_history"
    __table_args__ = (
        UniqueConstraint("dataset_id", "idempotency_key"),
        Index("ix_query_history_dataset_created", "dataset_id", "created_at", "query_id"),
        CheckConstraint("query_kind IN ('monthly','series')"),
    )
    query_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.dataset_id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_sha256: Mapped[str] = mapped_column(String(64))
    query_kind: Mapped[str] = mapped_column(String(16))
    parameters: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    result_sha256: Mapped[str] = mapped_column(String(64))
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    transform_version: Mapped[str] = mapped_column(String(32))
    metric_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(40))
