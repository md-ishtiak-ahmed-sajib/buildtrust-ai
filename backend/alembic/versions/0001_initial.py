"""Initial sandbox financial schema."""

from alembic import op
from pathlib import Path

revision = "0001"
down_revision = None


def upgrade():
    # Frozen schema: later model changes must receive their own migration.
    sql = Path(__file__).with_name("0001_schema.sql").read_text(encoding="utf-8")
    for statement in sql.split(";"):
        if statement.strip():
            op.get_bind().exec_driver_sql(statement)


def downgrade():
    raise RuntimeError(
        "Destructive downgrade is intentionally disabled; restore a backed-up sandbox database."
    )
