"""Retain complete submission evidence alongside its bound hash."""
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.get_bind().exec_driver_sql("ALTER TABLE estimate_versions ADD COLUMN approval_snapshot_json TEXT")


def downgrade():
    raise RuntimeError("Restore a consistent backup; destructive downgrade is disabled.")
