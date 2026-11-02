"""Persist explicit deterministic query snapshots, never as a GET side effect."""
from alembic import op
import sqlalchemy as sa

revision = "0003_query_history"
down_revision = "0002_import"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "query_history",
        sa.Column("query_id", sa.String(64), primary_key=True),
        sa.Column("dataset_id", sa.String(64), sa.ForeignKey("dataset_snapshots.dataset_id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("query_kind", sa.String(16), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("workbook_sha256", sa.String(64), nullable=False),
        sa.Column("transform_version", sa.String(32), nullable=False),
        sa.Column("metric_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("dataset_id", "idempotency_key"),
        sa.CheckConstraint("query_kind IN ('monthly','series')"),
    )
    op.create_index("ix_query_history_dataset_created", "query_history", ["dataset_id", "created_at", "query_id"])


def downgrade():
    op.drop_index("ix_query_history_dataset_created", table_name="query_history")
    op.drop_table("query_history")
