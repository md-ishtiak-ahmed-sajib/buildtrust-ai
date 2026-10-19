"""Replace invoice-wide settlement uniqueness with authoritative payable controls."""
from alembic import op
from sqlalchemy import CheckConstraint
revision="0008"
down_revision="0007"


def upgrade():
    # migrate() uses a consistent backup, disables FK enforcement only around
    # this controlled SQLite table rebuild, and checks every FK before commit.
    with op.batch_alter_table("payments",recreate="always",
            table_args=(CheckConstraint("amount_minor > 0",name="ck_payments_positive_amount"),),
            naming_convention={"uq":"uq_%(table_name)s_%(column_0_name)s"}) as batch:
        batch.drop_constraint("uq_payments_invoice_id",type_="unique")
    op.create_index("ix_payments_invoice_id","payments",["invoice_id"])
    db=op.get_bind()
    db.exec_driver_sql("DROP INDEX uq_active_invoice_proposal")
    db.exec_driver_sql("""CREATE UNIQUE INDEX uq_active_invoice_proposal ON payment_proposals(invoice_id)
        WHERE status IN ('PENDING_APPROVAL','APPROVED','EXECUTING')""")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
