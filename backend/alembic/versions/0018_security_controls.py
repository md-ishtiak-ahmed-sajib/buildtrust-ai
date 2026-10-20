"""Add revocable sessions, single-use recovery, admission and provider budgets."""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = depends_on = None


def upgrade():
    from app.hardening_models import AuthSession, RecoveryToken, AdmissionBucket, UsageReservation
    for model in (AuthSession, RecoveryToken, AdmissionBucket, UsageReservation):
        model.__table__.create(bind=op.get_bind())


def downgrade():
    raise RuntimeError("Restore the consistent backup; destructive downgrade is disabled.")
