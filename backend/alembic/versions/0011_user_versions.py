from alembic import op
revision="0011"
down_revision="0010"


def upgrade():
    op.get_bind().exec_driver_sql("ALTER TABLE users ADD COLUMN version INTEGER NOT NULL DEFAULT 1")


def downgrade():
    raise RuntimeError("Restore consistent backup; destructive downgrade disabled.")
