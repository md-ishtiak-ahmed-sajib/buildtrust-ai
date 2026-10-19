"""Versioned commercial controls and balanced accounting, on the original Base."""

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base
from .money import utcnow


class ControlRecord(Base):
    __tablename__ = "control_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str]
    name: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(default="DRAFT")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("control_records.id"))
    payload_json: Mapped[str] = mapped_column(Text)
    calculated_json: Mapped[str] = mapped_column(Text, default="{}")
    contributors_json: Mapped[str]
    prepared_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    checked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    snapshot_hash: Mapped[str | None]
    snapshot_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class CostCode(Base):
    __tablename__ = "cost_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    code: Mapped[str]
    name: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class CostCodeLink(Base):
    __tablename__ = "cost_code_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    cost_code_id: Mapped[int] = mapped_column(ForeignKey("cost_codes.id"))
    source_type: Mapped[str]
    source_id: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("source_type", "source_id"),)


class Journal(Base):
    __tablename__ = "accounting_journals"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source_key: Mapped[str]
    record_id: Mapped[int | None] = mapped_column(ForeignKey("control_records.id"))
    business_date: Mapped[str]
    currency: Mapped[str]
    evidence_json: Mapped[str] = mapped_column(Text)
    snapshot_hash: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "source_key"),)


class JournalLine(Base):
    __tablename__ = "accounting_journal_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    journal_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_journals.id"), index=True
    )
    account: Mapped[str]
    debit_minor: Mapped[int] = mapped_column(default=0)
    credit_minor: Mapped[int] = mapped_column(default=0)
    cost_code_id: Mapped[int | None] = mapped_column(ForeignKey("cost_codes.id"))
    __table_args__ = (
        CheckConstraint(
            "debit_minor >= 0 AND credit_minor >= 0 AND NOT (debit_minor > 0 AND credit_minor > 0)"
        ),
    )


class Recognition(Base):
    __tablename__ = "cost_recognitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    record_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    receipt_line_id: Mapped[int] = mapped_column(
        ForeignKey("receipt_lines.id"), unique=True
    )
    cost_code_id: Mapped[int] = mapped_column(ForeignKey("cost_codes.id"))
    amount_minor: Mapped[int]
    quantity: Mapped[str]
    unit: Mapped[str]
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    source_hash: Mapped[str]


class Payable(Base):
    # Installments settle a balance; physical entitlement belongs to the invoice.
    __tablename__ = "payable_balances"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id"), unique=True
    )
    record_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    amount_minor: Mapped[int]
    paid_minor: Mapped[int] = mapped_column(default=0)
    credit_minor: Mapped[int] = mapped_column(default=0)
    retention_minor: Mapped[int] = mapped_column(default=0)
    retention_released_minor: Mapped[int] = mapped_column(default=0)
    supplier_credit_minor: Mapped[int] = mapped_column(default=0)
    currency: Mapped[str]
    due_date: Mapped[str | None]
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        CheckConstraint(
            "paid_minor >= 0 AND credit_minor >= 0 AND paid_minor+credit_minor <= amount_minor"
        ),
    )


class InvoiceEntitlement(Base):
    __tablename__ = "invoice_entitlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    receipt_line_id: Mapped[int] = mapped_column(ForeignKey("receipt_lines.id"))
    invoice_line_id: Mapped[int] = mapped_column(ForeignKey("invoice_lines.id"))
    canonical_quantity: Mapped[str]
    state: Mapped[str] = mapped_column(default="CONSUMED")
    __table_args__ = (UniqueConstraint("invoice_line_id", "receipt_line_id"),)


class RecognitionAllocation(Base):
    __tablename__ = "recognition_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    recognition_id: Mapped[int] = mapped_column(
        ForeignKey("cost_recognitions.id"), index=True
    )
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    invoice_line_id: Mapped[int] = mapped_column(ForeignKey("invoice_lines.id"))
    quantity: Mapped[str]
    amount_minor: Mapped[int]
    __table_args__ = (
        UniqueConstraint("recognition_id", "invoice_line_id"),
        CheckConstraint("amount_minor >= 0"),
    )


class Receivable(Base):
    __tablename__ = "receivable_balances"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    certificate_id: Mapped[int] = mapped_column(
        ForeignKey("control_records.id"), unique=True
    )
    amount_minor: Mapped[int]
    received_minor: Mapped[int] = mapped_column(default=0)
    credit_minor: Mapped[int] = mapped_column(default=0)
    customer_credit_minor: Mapped[int] = mapped_column(default=0)
    retention_minor: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[str | None]
    currency: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        CheckConstraint("received_minor >= 0 AND received_minor <= amount_minor"),
    )


class Obligation(Base):
    __tablename__ = "obligations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source_type: Mapped[str]
    source_id: Mapped[int]
    category: Mapped[str]
    direction: Mapped[str]
    amount_minor: Mapped[int]
    currency: Mapped[str]
    due_date: Mapped[str | None]
    cash_movement_id: Mapped[int | None] = mapped_column(
        ForeignKey("cash_movements.id"), unique=True
    )
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        UniqueConstraint("project_id", "source_type", "source_id"),
        CheckConstraint("amount_minor >= 0"),
    )
