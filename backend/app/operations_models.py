"""Operational state and evidence; no financial transaction ownership here."""

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base
from .money import utcnow


class EvidenceRevision(Base):
    __tablename__ = "evidence_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    entity_type: Mapped[str]
    entity_id: Mapped[int]
    version: Mapped[int]
    evidence_json: Mapped[str] = mapped_column(Text)
    snapshot_hash: Mapped[str]
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    entity_id: Mapped[int]
    attempt: Mapped[int]
    lease_token: Mapped[str]
    status: Mapped[str]
    started_at: Mapped[str]
    heartbeat_at: Mapped[str]
    lease_until: Mapped[str]
    next_attempt_at: Mapped[str | None]
    finished_at: Mapped[str | None]
    __table_args__ = (UniqueConstraint("kind", "entity_id", "attempt"),)
