"""Additive review-control records sharing the original SQLAlchemy Base."""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base
from .money import utcnow


class Contributor(Base):
    __tablename__ = "record_contributors"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str]
    entity_id: Mapped[int]
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    evidence: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "actor_id"),)


class CommitmentCoverage(Base):
    __tablename__ = "commitment_coverage"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    boq_item_id: Mapped[int] = mapped_column(ForeignKey("boq_items.id"))
    po_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_lines.id"), unique=True
    )
    source_hash: Mapped[str]
    quantity: Mapped[str]
    unit: Mapped[str]
    method: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)
