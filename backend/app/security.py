from datetime import datetime, timedelta, timezone
import jwt
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


def token_for(user, secret):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
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
        )
        user = session.get(User, int(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise DomainError(401, "UNAUTHENTICATED", "Sign in again.")
    if not user or not user.active:
        raise DomainError(401, "UNAUTHENTICATED", "Account is inactive or unavailable.")
    return user


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
