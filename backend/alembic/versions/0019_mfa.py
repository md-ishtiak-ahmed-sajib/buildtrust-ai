"""Add encrypted authenticator factors and restricted, replay-protected challenges."""
from alembic import op
import sqlalchemy as sa

revision='0019'
down_revision='0018'
branch_labels=depends_on=None


def upgrade():
    from app.mfa_models import MfaFactor,MfaChallenge,MfaRecoveryCode
    for model in (MfaFactor,MfaChallenge,MfaRecoveryCode):model.__table__.create(bind=op.get_bind())
    if 'mfa_verified' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('auth_sessions')}:
        with op.batch_alter_table('auth_sessions') as batch:
            batch.add_column(sa.Column('mfa_verified',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.execute(sa.text("UPDATE auth_sessions SET revoked_at=:now WHERE revoked_at IS NULL").bindparams(now=__import__('app.money',fromlist=['utcnow']).utcnow()))


def downgrade():
    raise RuntimeError('Restore the consistent backup; destructive downgrade is disabled.')
