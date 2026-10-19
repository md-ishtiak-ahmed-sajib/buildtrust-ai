"""Add approved commercial publication and acceptance-allocation links."""
from alembic import op

revision = "0012"
down_revision = "0011"


def upgrade():
    op.get_bind().exec_driver_sql("""CREATE TABLE commercial_publications (
        id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
        control_id INTEGER NOT NULL UNIQUE REFERENCES control_records(id),
        source_type VARCHAR NOT NULL, source_id INTEGER NOT NULL,
        UNIQUE(source_type, source_id))""")
    op.get_bind().exec_driver_sql("""CREATE TABLE certificate_allocations (
        id INTEGER PRIMARY KEY, certificate_id INTEGER NOT NULL REFERENCES control_records(id),
        acceptance_id INTEGER NOT NULL UNIQUE REFERENCES control_records(id), amount_minor INTEGER NOT NULL)""")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
