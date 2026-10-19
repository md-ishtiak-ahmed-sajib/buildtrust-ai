"""Accounting is opt-in with explicit dated recognition, never invented history."""
from alembic import op
revision = "0007"
down_revision = "0006"


def upgrade():
    from pathlib import Path
    for statement in Path(__file__).with_name("0007_schema.sql").read_text(encoding="utf-8").split(";\n"):
        if statement.strip(): op.get_bind().exec_driver_sql(statement)


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
