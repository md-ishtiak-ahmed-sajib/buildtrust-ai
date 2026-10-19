from alembic import op
revision="0009"
down_revision="0008"


def upgrade():
    op.get_bind().exec_driver_sql("""CREATE TABLE invoice_entitlements (
        id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id),
        receipt_line_id INTEGER NOT NULL REFERENCES receipt_lines(id),
        invoice_line_id INTEGER NOT NULL REFERENCES invoice_lines(id), canonical_quantity VARCHAR NOT NULL,
        state VARCHAR NOT NULL, UNIQUE(invoice_line_id,receipt_line_id))""")
    op.get_bind().exec_driver_sql("CREATE INDEX ix_invoice_entitlements_invoice_id ON invoice_entitlements(invoice_id)")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
