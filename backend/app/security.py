from datetime import datetime, timedelta, timezone
import jwt
import secrets
import hashlib
from sqlalchemy import select
from pwdlib import PasswordHash
from .models import User, Membership, Project

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("dummy-account-timing-protection")


class DomainError(Exception):
    def __init__(
        self,
        status,
        code,
        message,
        project_id=None,
        entity_id=None,
        *,
        fields=None,
        retry_after=None,
    ):
        self.status, self.code, self.message = status, code, message
        self.project_id, self.entity_id = project_id, entity_id
        self.fields, self.retry_after = fields or [], retry_after


def token_for(user, secret, session):
    now = datetime.now(timezone.utc)
    from .hardening_models import AuthSession
    identity = secrets.token_urlsafe(32)
    session.add(AuthSession(id=hashlib.sha256(identity.encode()).hexdigest(), user_id=user.id,
                            user_version=user.version, expires_at=(now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")))
    return jwt.encode(
        {
            "sub": str(user.id),
            "jti": identity,
            "iat": now,
            "exp": now + timedelta(minutes=30),
            "iss": "buildtrust-local",
            "aud": "buildtrust",
        },
        secret,
        algorithm="HS256",
    )


def authenticate(session, token, secret):
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer="buildtrust-local",
            audience="buildtrust",
            options={"require": ["sub", "jti", "exp", "iat"]},
        )
        user = session.get(User, int(claims["sub"]))
        from .hardening_models import AuthSession
        from .money import utcnow
        auth = session.get(AuthSession, hashlib.sha256(claims["jti"].encode()).hexdigest())
        if not auth or auth.user_id != int(claims["sub"]) or auth.revoked_at or auth.expires_at <= utcnow() or not user or auth.user_version != user.version:
            raise DomainError(401, "UNAUTHENTICATED", "Sign in again.")
        session.info["auth_session_id"] = auth.id
    except (jwt.PyJWTError, KeyError, ValueError, TypeError, AttributeError):
        raise DomainError(401, "UNAUTHENTICATED", "Sign in again.")
    if not user or not user.active:
        raise DomainError(401, "UNAUTHENTICATED", "Account is inactive or unavailable.")
    return user


def revoke_sessions(session, user_id):
    from .hardening_models import AuthSession, RecoveryToken
    from .money import utcnow
    for row in session.scalars(select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))):
        row.revoked_at = utcnow()
    for row in session.scalars(select(RecoveryToken).where(RecoveryToken.user_id == user_id, RecoveryToken.consumed_at.is_(None))):
        row.consumed_at = utcnow()


def require_role(user, *roles):
    if not user or not user.active:
        raise DomainError(
            401, "UNAUTHENTICATED", "An active authenticated account is required."
        )
    if user.role not in roles:
        raise DomainError(
            403, "UNAUTHORIZED_ACTION", "Your role cannot perform this action."
        )


def project_access(session, user, project_id, *, write=False):
    if not user or not user.active:
        raise DomainError(
            401, "UNAUTHENTICATED", "An active authenticated account is required."
        )
    project = session.get(Project, project_id)
    if not project or not session.get(Membership, (user.id, project_id)):
        raise DomainError(404, "NOT_FOUND", "Project or resource is unavailable.")
    if (write or session.info.get("api_write")) and not project.active:
        raise DomainError(
            409, "ARCHIVED_PROJECT", "Archived demonstration runs are read-only."
        )
    return project
