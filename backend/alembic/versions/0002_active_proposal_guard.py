"""Backfill the active proposal guard for early local development databases."""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.get_bind().exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_invoice_proposal ON payment_proposals (invoice_id) WHERE status IN ('PENDING_APPROVAL','APPROVED','EXECUTING','SETTLED')"
    )


def downgrade():
    op.drop_index("uq_active_invoice_proposal", table_name="payment_proposals")
