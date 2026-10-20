"""Offline password lifecycle. Tokens are shown once, never logged or emailed."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from . import audit, models as m, payments
from .database import transaction
from .hardening_models import AuthSession, RecoveryToken
from .security import DomainError, passwords, revoke_sessions, require_role
from .money import utcnow
from .admission import consume


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class AuthResult(BaseModel):
    message: str


class AuthOptions(BaseModel):
    password_management_enabled: bool
    public_demo: bool
    mfa_required_roles: list[str]


class RecoveryResult(BaseModel):
    token: str
    expires_at: str
    message: str


def fixed_public_account(settings, user):
    from .public_demo import PublicDemoSettings, load_accounts
    return isinstance(settings, PublicDemoSettings) and user.email in {r["email"] for r in load_accounts()}


def recovery_allowed(settings, user):
    if fixed_public_account(settings, user):
        raise DomainError(403, "PUBLIC_DEMO_PASSWORD", "The four documented public demo passwords cannot be changed or recovered.")


def issue_recovery(session, settings, user, actor=None, *, owner=False):
    recovery_allowed(settings, user)
    if not user.active:
        raise DomainError(409, "INACTIVE_ACCOUNT", "Recovery does not reactivate an account.")
    if not owner:
        require_role(actor, "ADMIN")
        if user.role == "ADMIN":
            raise DomainError(403, "OWNER_RECOVERY_REQUIRED", "An Admin account requires the local-owner recovery command.")
    for prior in session.scalars(select(RecoveryToken).where(RecoveryToken.user_id == user.id, RecoveryToken.consumed_at.is_(None))):
        prior.consumed_at = utcnow()
    raw = secrets.token_urlsafe(32)
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    session.add(RecoveryToken(token_hash=hashlib.sha256(raw.encode()).hexdigest(), user_id=user.id,
                              user_version=user.version, expires_at=expiry))
    audit.append(session, actor, "PASSWORD_RECOVERY_ISSUED", "user", user.id,
                 {"expires_at": expiry, "local_owner": owner})
    return {"token": raw, "expires_at": expiry, "message": "Share privately after verifying the recipient. This single-use token is shown once."}


def apply_password(session, user, hashed, actor):
    user.password_hash = hashed
    user.version += 1
    revoke_sessions(session, user.id)
    payments.invalidate_authority(session, actor, user.id)
    audit.append(session, actor, "PASSWORD_CHANGED", "user", user.id)


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Password and session security"])

    @router.get("/auth/options", response_model=AuthOptions)
    def options(request: Request):
        from .public_demo import PublicDemoSettings
        public = isinstance(request.app.state.settings, PublicDemoSettings)
        return {"password_management_enabled": not public, "public_demo": public,'mfa_required_roles':[] if public else ['ADMIN','FINANCE_MANAGER']}

    @router.post("/auth/logout", response_model=AuthResult)
    def logout(request: Request):
        with context(request, True) as (session, actor):
            session.get(AuthSession, session.info["auth_session_id"]).revoked_at = utcnow()
            audit.append(session, actor, "USER_LOGOUT", "user", actor.id)
        return {"message": "Session revoked. Sign in again to continue."}

    @router.post("/auth/password/change", response_model=AuthResult)
    async def change(body: PasswordChange, request: Request):
        with context(request) as (session, actor):
            recovery_allowed(request.app.state.settings, actor)
            user_id, version, old = actor.id, actor.version, actor.password_hash
        consume(request.app.state.engine, [(f"password-change:{user_id}", 5, 60)])
        valid = await run_in_threadpool(passwords.verify, body.current_password, old)
        if not valid:
            raise DomainError(403, "INVALID_PASSWORD", "Current password is incorrect.")
        hashed = await run_in_threadpool(passwords.hash, body.new_password)
        with context(request, True) as (session, actor):
            if actor.version != version or actor.password_hash != old:
                raise DomainError(409, "VERSION_CONFLICT", "Account changed; sign in again.")
            apply_password(session, actor, hashed, actor)
        return {"message": "Password changed and all sessions revoked. Sign in again."}

    @router.post("/administration/users/{identity}/recovery", response_model=RecoveryResult)
    def recovery(identity: int, request: Request):
        with context(request) as (session, actor):
            require_role(actor, "ADMIN")
            actor_id = actor.id
        consume(request.app.state.engine, [(f"recovery-account:{identity}", 5, 3600), (f"recovery-admin:{actor_id}", 10, 3600)])
        with context(request, True) as (session, actor):
            require_role(actor, "ADMIN")
            user = session.get(m.User, identity)
            if not user:
                raise DomainError(404, "NOT_FOUND", "Account is unavailable.")
            return issue_recovery(session, request.app.state.settings, user, actor)

    @router.post("/auth/password/reset", response_model=AuthResult)
    async def reset(body: PasswordReset, request: Request):
        address = request.client.host if request.client else "local"
        engine, settings = request.app.state.engine, request.app.state.settings
        consume(engine, [(f"recovery-redemption:{address}", 10, 60)])
        key = hashlib.sha256(body.token.encode()).hexdigest()
        with transaction(engine) as session:
            row = session.get(RecoveryToken, key)
            user = session.get(m.User, row.user_id) if row else None
            if not row or row.consumed_at or row.expires_at <= utcnow() or not user or not user.active or row.user_version != user.version:
                raise DomainError(422, "INVALID_RECOVERY", "Recovery token is invalid or expired.")
            recovery_allowed(settings, user)
            version, identity = user.version, user.id
        hashed = await run_in_threadpool(passwords.hash, body.new_password)
        with transaction(engine, True) as session:
            row, user = session.get(RecoveryToken, key), session.get(m.User, identity)
            if row.consumed_at or row.expires_at <= utcnow() or not user.active or user.version != version:
                raise DomainError(422, "INVALID_RECOVERY", "Recovery token is invalid or expired.")
            recovery_allowed(settings, user)
            apply_password(session, user, hashed, user)
        return {"message": "Password reset and all sessions revoked. Sign in with your new password."}

    return router
