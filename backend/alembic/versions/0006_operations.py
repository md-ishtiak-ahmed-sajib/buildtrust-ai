"""Durable extraction revisions and bounded worker attempts."""
from alembic import op
revision = "0006"
down_revision = "0005"


def upgrade():
    db = op.get_bind()
    db.exec_driver_sql("""CREATE TABLE evidence_revisions (
        id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
        entity_type VARCHAR NOT NULL, entity_id INTEGER NOT NULL, version INTEGER NOT NULL,
        evidence_json TEXT NOT NULL, snapshot_hash VARCHAR NOT NULL,
        actor_id INTEGER NOT NULL REFERENCES users(id), created_at VARCHAR NOT NULL)""")
    db.exec_driver_sql("CREATE INDEX ix_evidence_entity ON evidence_revisions(entity_type, entity_id)")
    db.exec_driver_sql("""CREATE TABLE job_attempts (
        id INTEGER PRIMARY KEY, kind VARCHAR NOT NULL, entity_id INTEGER NOT NULL,
        attempt INTEGER NOT NULL, lease_token VARCHAR NOT NULL, status VARCHAR NOT NULL,
        started_at VARCHAR NOT NULL, heartbeat_at VARCHAR NOT NULL, lease_until VARCHAR NOT NULL,
        next_attempt_at VARCHAR, finished_at VARCHAR, UNIQUE(kind,entity_id,attempt))""")


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade disabled.")
