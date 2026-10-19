"""Allocate an accepted cost across invoices without recognizing cost again."""
from alembic import op

revision = "0014"
down_revision = "0013"


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql("""CREATE TABLE recognition_allocations (
      id INTEGER PRIMARY KEY, recognition_id INTEGER NOT NULL REFERENCES cost_recognitions(id),
      invoice_id INTEGER NOT NULL REFERENCES invoices(id), invoice_line_id INTEGER NOT NULL REFERENCES invoice_lines(id),
      quantity VARCHAR NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0),
      UNIQUE(recognition_id, invoice_line_id))""")
    op.create_index("ix_recognition_allocations_recognition_id", "recognition_allocations", ["recognition_id"])
    db.exec_driver_sql("""INSERT INTO recognition_allocations(recognition_id,invoice_id,invoice_line_id,quantity,amount_minor)
      SELECT r.id,r.invoice_id,e.invoice_line_id,e.canonical_quantity,r.amount_minor
      FROM cost_recognitions r JOIN invoice_entitlements e ON e.invoice_id=r.invoice_id AND e.receipt_line_id=r.receipt_line_id
      WHERE r.invoice_id IS NOT NULL""")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
