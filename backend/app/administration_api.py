"""Local team administration with current authority and last-Admin protection."""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import Field
from sqlalchemy import func, select

from . import audit, payments
from . import models as m
from .advanced_schemas import Contract
from .security import DomainError, passwords, project_access, require_role


class UserCreate(Contract):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=200)
    role: Literal["OPERATOR", "FINANCE_MANAGER", "ADMIN", "AUDITOR"]
    password: str = Field(min_length=12, max_length=128)


class UserChange(Contract):
    expected_version: int
    role: Literal["OPERATOR", "FINANCE_MANAGER", "ADMIN", "AUDITOR"]
    active: bool


class MemberChange(Contract):
    user_id: int
    member: bool


def user_view(row):
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "role": row.role,
        "active": row.active,
        "version": row.version,
    }


def create_router(context):
    router = APIRouter(
        prefix="/api/v1/administration", tags=["Local team administration"]
    )

    @router.get("/users")
    def users(request: Request):
        with context(request) as (session, actor):
            require_role(actor, "ADMIN")
            return [user_view(row) for row in session.scalars(select(m.User))]

    @router.post("/users", status_code=201)
    async def create(data: UserCreate, request: Request):
        with context(request) as (session, actor):
            require_role(actor, "ADMIN")
        hashed = await run_in_threadpool(passwords.hash, data.password)
        with context(request, True) as (session, actor):
            require_role(actor, "ADMIN")
            row = m.User(
                email=data.email.strip().lower(),
                name=data.name,
                role=data.role,
                password_hash=hashed,
            )
            session.add(row)
            session.flush()
            audit.append(
                session, actor, "LOCAL_USER_CREATED", "user", row.id, {"role": row.role}
            )
            return user_view(row)

    @router.patch("/users/{identity}")
    def change(identity: int, data: UserChange, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "ADMIN")
            row = session.get(m.User, identity)
            if not row:
                raise DomainError(404, "NOT_FOUND", "User is unavailable.")
            if row.version != data.expected_version:
                raise DomainError(
                    409, "VERSION_CONFLICT", "User changed; reload before saving."
                )
            authority_changed = row.role != data.role or row.active != data.active
            if (
                row.role == "ADMIN"
                and row.active
                and (not data.active or data.role != "ADMIN")
            ):
                count = session.scalar(
                    select(func.count())
                    .select_from(m.User)
                    .where(m.User.role == "ADMIN", m.User.active.is_(True))
                )
                if count <= 1:
                    raise DomainError(
                        409,
                        "LAST_ADMIN",
                        "The last active Admin must remain available.",
                    )
                for membership in session.scalars(
                    select(m.Membership).where(m.Membership.user_id == row.id)
                ):
                    others = session.scalar(
                        select(func.count())
                        .select_from(m.Membership)
                        .join(m.User)
                        .where(
                            m.Membership.project_id == membership.project_id,
                            m.User.id != row.id,
                            m.User.role == "ADMIN",
                            m.User.active.is_(True),
                        )
                    )
                    if not others:
                        raise DomainError(
                            409,
                            "LAST_PROJECT_ADMIN",
                            "Assign another active Admin to every affected project first.",
                        )
            row.role, row.active = data.role, data.active
            row.version += 1
            if authority_changed:
                from .security import revoke_sessions
                revoke_sessions(session, row.id)
                payments.invalidate_authority(session, actor, row.id)
            audit.append(
                session,
                actor,
                "LOCAL_USER_UPDATED",
                "user",
                row.id,
                {"role": row.role, "active": row.active, "version": row.version},
            )
            return user_view(row)

    @router.get("/members")
    def members(request: Request, project_id: int):
        with context(request) as (session, actor):
            require_role(actor, "ADMIN")
            project_access(session, actor, project_id)
            return [
                user_view(row)
                for row in session.scalars(
                    select(m.User)
                    .join(m.Membership)
                    .where(m.Membership.project_id == project_id)
                )
            ]

    @router.post("/members")
    def membership(data: MemberChange, request: Request, project_id: int):
        with context(request, True) as (session, actor):
            require_role(actor, "ADMIN")
            project_access(session, actor, project_id, write=True)
            user = session.get(m.User, data.user_id)
            if not user or not user.active:
                raise ValueError("An active existing account is required")
            member = session.get(m.Membership, (user.id, project_id))
            if data.member and not member:
                session.add(m.Membership(user_id=user.id, project_id=project_id))
            elif not data.member and member:
                count = session.scalar(
                    select(func.count())
                    .select_from(m.Membership)
                    .join(m.User)
                    .where(
                        m.Membership.project_id == project_id,
                        m.User.role == "ADMIN",
                        m.User.active.is_(True),
                    )
                )
                if user.role == "ADMIN" and count <= 1:
                    raise DomainError(
                        409,
                        "LAST_PROJECT_ADMIN",
                        "Retain an active Admin assigned to this project.",
                    )
                session.delete(member)
                payments.invalidate_authority(session, actor, user.id, project_id)
            audit.append(
                session,
                actor,
                "PROJECT_MEMBER_CHANGED",
                "project",
                project_id,
                {"user_id": user.id, "member": data.member},
                project_id,
            )
            return {"user_id": user.id, "project_id": project_id, "member": data.member}

    return router
