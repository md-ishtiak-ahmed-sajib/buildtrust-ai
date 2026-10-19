"""Bound project-scoped register scans and common source lookups."""
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None

INDEXES = [
    ('invoices', ['project_id','id']),
    ('estimate_versions', ['project_id','status','id']),
    ('supplier_quotations', ['project_id','status','id']),
    ('audit_events', ['project_id','id']),
    ('control_records', ['project_id','id']),
    ('purchase_orders', ['project_id','approved','id']),
    ('price_observations', ['project_id','retrieved_at','id']),
    ('obligations', ['project_id','due_date']),
]

def upgrade():
    for table, columns in INDEXES:
        op.create_index('ix_register_'+table, table, columns)

def downgrade():
    for table, _ in reversed(INDEXES):
        op.drop_index('ix_register_'+table, table_name=table)
