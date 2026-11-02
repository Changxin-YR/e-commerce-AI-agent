"""Durable runs, attempts, tool evidence, replies and a project-wide budget."""
from alembic import op
import sqlalchemy as sa

revision = "0004_agent_runtime"
down_revision = "0003_query_history"
branch_labels = None
depends_on = None


def upgrade():
    # This migration only adds metadata; transaction rows and earlier history stay intact.
    string_fields = {"thread_id":64, "parent_run_id":64, "submission_key":128,
        "request_hash":64, "config_hash":64, "checkpoint_id":64, "result_ref":64,
        "error_code":64, "started_at":40, "updated_at":40, "ended_at":40}
    for name, length in string_fields.items():
        op.add_column("analysis_runs", sa.Column(name, sa.String(length), nullable=True))
    for name, default in (("variant","B0"),("phase","received")):
        op.add_column("analysis_runs", sa.Column(name, sa.String(32), nullable=False, server_default=default))
    for name in ("revision", "requests_consumed", "tokens_occupied", "cancel_requested"):
        op.add_column("analysis_runs", sa.Column(name, sa.BigInteger(), nullable=False, server_default="0"))
    for name in ("input", "data_version", "config"):
        op.add_column("analysis_runs", sa.Column(name, sa.JSON(), nullable=False, server_default="{}"))
    for name in ("pending_input", "resume_payload"):
        op.add_column("analysis_runs", sa.Column(name, sa.JSON(), nullable=True))
    op.create_index("uq_analysis_thread", "analysis_runs", ["thread_id"], unique=True)
    op.create_index("uq_analysis_submission", "analysis_runs", ["submission_key"], unique=True)
    # Copy metadata definitions for new tables; no create_all against the existing database.
    from backend.app.models import ModelAttempt, AgentToolCall, RunSubmission, ModelBudget, AgentReview
    for model in (ModelAttempt, AgentToolCall, RunSubmission, ModelBudget, AgentReview):
        model.__table__.create(op.get_bind())


def downgrade():
    for table in ("agent_reviews", "model_budget", "run_submissions", "agent_tool_calls", "model_attempts"):
        op.drop_table(table)
    op.drop_index("uq_analysis_submission", table_name="analysis_runs")
    op.drop_index("uq_analysis_thread", table_name="analysis_runs")
    with op.batch_alter_table("analysis_runs") as batch:
        for name in ("thread_id", "parent_run_id", "submission_key", "request_hash", "config_hash",
            "checkpoint_id", "result_ref", "error_code", "started_at", "updated_at", "ended_at",
            "variant", "phase", "revision", "requests_consumed", "tokens_occupied", "cancel_requested",
            "input", "data_version", "config", "pending_input", "resume_payload"):
            batch.drop_column(name)
