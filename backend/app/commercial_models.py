"""Relations published only by independent commercial approval."""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base


class CommercialPublication(Base):
    __tablename__ = "commercial_publications"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    control_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    source_type: Mapped[str]
    source_id: Mapped[int]
    __table_args__ = (UniqueConstraint("source_type", "source_id"),)


class CertificateAllocation(Base):
    __tablename__ = "certificate_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("control_records.id"))
    acceptance_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    amount_minor: Mapped[int]


class ProcurementAuthorization(Base):
    __tablename__ = "procurement_authorizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    boq_item_id: Mapped[int] = mapped_column(ForeignKey("boq_items.id"), index=True)
    quantity: Mapped[str]
    extra_value_minor: Mapped[int]


class ProcurementAmendment(Base):
    __tablename__ = "procurement_amendments"
    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    po_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_lines.id"), index=True
    )
    retired_quantity: Mapped[str]
    successor_po_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id")
    )
