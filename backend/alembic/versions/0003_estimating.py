"""Additive price intelligence and estimating, frozen schema."""
from pathlib import Path
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    for statement in Path(__file__).with_name("0003_schema.sql").read_text(encoding="utf-8").split(";"):
        if statement.strip():
            op.get_bind().exec_driver_sql(statement)


def downgrade():
    raise RuntimeError("Restore a consistent backup; destructive downgrade is disabled.")
