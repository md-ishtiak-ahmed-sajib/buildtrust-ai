"""Separate second-factor evidence; never store raw challenges or recovery codes."""
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base
from .money import utcnow


class MfaFactor(Base):
    __tablename__ = 'mfa_factors'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),primary_key=True)
    encrypted_secret: Mapped[str] = mapped_column(Text)
    last_counter: Mapped[int] = mapped_column(default=-1)
    enabled_at: Mapped[str] = mapped_column(default=utcnow)


class MfaChallenge(Base):
    __tablename__ = 'mfa_challenges'
    id: Mapped[str] = mapped_column(String,primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),index=True)
    user_version: Mapped[int]
    purpose: Mapped[str]
    expires_at: Mapped[str]
    attempts: Mapped[int] = mapped_column(default=0)
    consumed_at: Mapped[str | None]
    pending_secret: Mapped[str | None] = mapped_column(Text)


class MfaRecoveryCode(Base):
    __tablename__ = 'mfa_recovery_codes'
    code_hash: Mapped[str] = mapped_column(String,primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'),index=True)
    consumed_at: Mapped[str | None]
