"""Create D0 infrastructure metadata, without transaction or model data.

Revision ID: 0001_bootstrap
Revises: None
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_bootstrap"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(256), nullable=False),
    )
    op.bulk_insert(table, [{"key": "project_id", "value": "ecommerce-agent-thesis"}])


def downgrade() -> None:
    op.drop_table("app_metadata")
