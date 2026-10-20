"""Durable authentication, admission limits and external usage reservations."""
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base
from .money import utcnow


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_version: Mapped[int]
    expires_at: Mapped[str]
    revoked_at: Mapped[str | None]
    mfa_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class RecoveryToken(Base):
    __tablename__ = "recovery_tokens"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_version: Mapped[int]
    expires_at: Mapped[str]
    consumed_at: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=utcnow)


class AdmissionBucket(Base):
    __tablename__ = "admission_buckets"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    events_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[int] = mapped_column(Integer)


class UsageReservation(Base):
    __tablename__ = "usage_reservations"
    __table_args__ = (UniqueConstraint("provider", "operation_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(index=True)
    operation_key: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    day: Mapped[str] = mapped_column(index=True)
    reserved_minor: Mapped[int]
    state: Mapped[str] = mapped_column(default="RESERVED")
    created_at: Mapped[str] = mapped_column(default=utcnow)

