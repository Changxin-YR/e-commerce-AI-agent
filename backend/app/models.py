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
    thread_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(64))
    submission_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    request_hash: Mapped[str | None] = mapped_column(String(64))
    variant: Mapped[str] = mapped_column(String(8), default="B0", server_default="B0")
    phase: Mapped[str] = mapped_column(String(32), default="received", server_default="received")
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    data_version: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    config: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    config_hash: Mapped[str | None] = mapped_column(String(64))
    checkpoint_id: Mapped[str | None] = mapped_column(String(64))
    pending_input: Mapped[dict | None] = mapped_column(JSON)
    resume_payload: Mapped[dict | None] = mapped_column(JSON)
    requests_consumed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_occupied: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    result_ref: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[str | None] = mapped_column(String(40))
    ended_at: Mapped[str | None] = mapped_column(String(40))


class ModelAttempt(Base):
    __tablename__ = "model_attempts"
    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(32))
    request_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(String(128))
    reserved_tokens: Mapped[int] = mapped_column(BigInteger)
    usage: Mapped[dict | None] = mapped_column(JSON)
    response: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40))


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"
    __table_args__ = (UniqueConstraint("run_id", "step", "position"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    model_call_id: Mapped[str] = mapped_column(String(128))
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))


class RunSubmission(Base):
    __tablename__ = "run_submissions"
    __table_args__ = (UniqueConstraint("run_id", "submission_key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id"))
    submission_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40))


class ModelBudget(Base):
    __tablename__ = "model_budget"
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    requests_consumed: Mapped[int] = mapped_column(Integer, default=0)
    tokens_occupied: Mapped[int] = mapped_column(BigInteger, default=0)


class AgentReview(Base):
    __tablename__ = "agent_reviews"
    __table_args__ = (UniqueConstraint("run_id", "step", "kind"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.run_id"))
    step: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    result: Mapped[dict] = mapped_column(JSON)
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
