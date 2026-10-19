"""Allow a certified payable as an explicit settlement source; preserve legacy IDs."""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"


def upgrade():
    for table in ("payment_proposals", "payments"):
        with op.batch_alter_table(table, recreate="always", table_args=(
            sa.CheckConstraint("amount_minor > 0", name=f"ck_{table}_positive"),
            sa.CheckConstraint("(invoice_id IS NOT NULL AND payable_id IS NULL) OR (invoice_id IS NULL AND payable_id IS NOT NULL)", name=f"ck_{table}_source"),
        )) as batch:
            batch.alter_column("invoice_id", existing_type=sa.Integer(), nullable=True)
            batch.add_column(sa.Column("payable_id", sa.Integer(), sa.ForeignKey("payable_balances.id", name=f"fk_{table}_payable")))
        op.create_index(f"ix_{table}_payable_id", table, ["payable_id"])
    op.execute("""CREATE UNIQUE INDEX uq_active_certificate_proposal ON payment_proposals(payable_id)
        WHERE status IN ('PENDING_APPROVAL','APPROVED','EXECUTING')""")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
