"""Append procurement scope authority and PO amendments; retain original records."""
from alembic import op
revision = "0015"
down_revision = "0014"


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql('''CREATE TABLE procurement_authorizations (
        id INTEGER PRIMARY KEY, control_id INTEGER NOT NULL UNIQUE REFERENCES control_records(id),
        boq_item_id INTEGER NOT NULL REFERENCES boq_items(id), quantity VARCHAR NOT NULL,
        extra_value_minor INTEGER NOT NULL)''')
    op.create_index('ix_procurement_authorizations_boq_item_id','procurement_authorizations',['boq_item_id'])
    db.exec_driver_sql('''CREATE TABLE procurement_amendments (
        id INTEGER PRIMARY KEY, control_id INTEGER NOT NULL UNIQUE REFERENCES control_records(id),
        po_line_id INTEGER NOT NULL REFERENCES purchase_order_lines(id), retired_quantity VARCHAR NOT NULL,
        successor_po_id INTEGER REFERENCES purchase_orders(id))''')
    op.create_index('ix_procurement_amendments_po_line_id','procurement_amendments',['po_line_id'])


def downgrade():
    raise RuntimeError('Restore the consistent backup; destructive downgrade disabled.')
