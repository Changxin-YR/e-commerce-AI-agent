"""Versioned source snapshots and recoverable imports (D2)."""
from alembic import op
import sqlalchemy as sa

revision = "0002_import"
down_revision = "0001_bootstrap"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('dataset_snapshots',
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('workbook_sha256', sa.String(length=64), nullable=False),
    sa.Column('transform_version', sa.String(length=32), nullable=False),
    sa.Column('schema_version', sa.String(length=32), nullable=False),
    sa.Column('metric_version', sa.String(length=32), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('acquired_at', sa.String(length=40), nullable=False),
    sa.Column('workbook_path', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('source_time_min', sa.String(length=32), nullable=True),
    sa.Column('source_time_max', sa.String(length=32), nullable=True),
    sa.Column('summary', sa.JSON(), nullable=False),
    sa.CheckConstraint("status IN ('QUEUED','IMPORTING','READY','FAILED')"),
    sa.PrimaryKeyConstraint('dataset_id'),
    sa.UniqueConstraint('workbook_sha256', 'transform_version')
    )
    op.create_table('analysis_runs',
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['dataset_snapshots.dataset_id'], ),
    sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(op.f('ix_analysis_runs_dataset_id'), 'analysis_runs', ['dataset_id'], unique=False)
    op.create_table('import_batches',
    sa.Column('batch_id', sa.String(length=64), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('submitted_file_sha256', sa.String(length=64), nullable=False),
    sa.Column('workbook_sha256', sa.String(length=64), nullable=False),
    sa.Column('transform_version', sa.String(length=32), nullable=False),
    sa.Column('containers', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.Column('imported_at', sa.String(length=40), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('failures', sa.JSON(), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.CheckConstraint("status IN ('QUEUED','IMPORTING','READY','FAILED')"),
    sa.ForeignKeyConstraint(['dataset_id'], ['dataset_snapshots.dataset_id'], ),
    sa.PrimaryKeyConstraint('batch_id'),
    sa.UniqueConstraint('dataset_id')
    )
    op.create_table('quality_issues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('row_ref', sa.Integer(), nullable=False),
    sa.Column('issue_code', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['dataset_snapshots.dataset_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dataset_id', 'row_ref', 'issue_code')
    )
    op.create_index('ix_quality_code', 'quality_issues', ['dataset_id', 'issue_code'], unique=False)
    op.create_table('transaction_rows',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dataset_id', sa.String(length=64), nullable=False),
    sa.Column('source_row_num', sa.Integer(), nullable=False),
    sa.Column('raw_fields', sa.JSON(), nullable=False),
    sa.Column('invoice_no', sa.Text(), nullable=True),
    sa.Column('stock_code', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('quantity', sa.BigInteger(), nullable=True),
    sa.Column('invoice_date_source', sa.String(length=32), nullable=True),
    sa.Column('customer_id', sa.Text(), nullable=True),
    sa.Column('country', sa.Text(), nullable=True),
    sa.Column('unit_price_raw', sa.Text(), nullable=True),
    sa.Column('unit_price_milli_gbp', sa.BigInteger(), nullable=True),
    sa.Column('line_amount_milli_gbp', sa.BigInteger(), nullable=True),
    sa.Column('primary_class', sa.String(length=24), nullable=False),
    sa.Column('quality_flags', sa.JSON(), nullable=False),
    sa.Column('row_fingerprint', sa.String(length=64), nullable=False),
    sa.CheckConstraint("primary_class IN ('INVALID','POSITIVE','CANCELLATION','EXCLUDED_OTHER')"),
    sa.ForeignKeyConstraint(['dataset_id'], ['dataset_snapshots.dataset_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dataset_id', 'source_row_num')
    )
    op.create_index('ix_transactions_country', 'transaction_rows', ['dataset_id', 'country'], unique=False)
    op.create_index('ix_transactions_fingerprint', 'transaction_rows', ['dataset_id', 'row_fingerprint'], unique=False)
    op.create_index('ix_transactions_invoice', 'transaction_rows', ['dataset_id', 'invoice_no'], unique=False)
    op.create_index('ix_transactions_period', 'transaction_rows', ['dataset_id', 'invoice_date_source', 'primary_class'], unique=False)
    op.create_index('ix_transactions_stock', 'transaction_rows', ['dataset_id', 'stock_code'], unique=False)
    op.create_table('reports',
    sa.Column('report_id', sa.String(length=64), nullable=False),
    sa.Column('run_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.String(length=40), nullable=False),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['analysis_runs.run_id'], ),
    sa.PrimaryKeyConstraint('report_id'),
    sa.UniqueConstraint('run_id')
    )

def downgrade():
    op.drop_table('reports')
    op.drop_index('ix_transactions_stock', table_name='transaction_rows')
    op.drop_index('ix_transactions_period', table_name='transaction_rows')
    op.drop_index('ix_transactions_invoice', table_name='transaction_rows')
    op.drop_index('ix_transactions_fingerprint', table_name='transaction_rows')
    op.drop_index('ix_transactions_country', table_name='transaction_rows')
    op.drop_table('transaction_rows')
    op.drop_index('ix_quality_code', table_name='quality_issues')
    op.drop_table('quality_issues')
    op.drop_table('import_batches')
    op.drop_index(op.f('ix_analysis_runs_dataset_id'), table_name='analysis_runs')
    op.drop_table('analysis_runs')
    op.drop_table('dataset_snapshots')
