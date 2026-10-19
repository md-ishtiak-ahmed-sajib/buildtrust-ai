"""Separate customer credits from receipts; keep original receivable amounts."""
from alembic import op
revision='0016'
down_revision='0015'


def upgrade():
    db=op.get_bind()
    db.exec_driver_sql('ALTER TABLE receivable_balances ADD COLUMN credit_minor INTEGER NOT NULL DEFAULT 0 CHECK(credit_minor>=0)')
    db.exec_driver_sql('ALTER TABLE receivable_balances ADD COLUMN customer_credit_minor INTEGER NOT NULL DEFAULT 0 CHECK(customer_credit_minor>=0)')
    op.create_index('ix_control_project_kind_status','control_records',['project_id','kind','status'])


def downgrade():
    raise RuntimeError('Restore the consistent backup; destructive downgrade disabled.')
