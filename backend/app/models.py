from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .money import utcnow


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str]
    role: Mapped[str]
    password_hash: Mapped[str]
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    client: Mapped[str] = mapped_column(default="Fictional demo client")
    currency: Mapped[str] = mapped_column(default="BDT")
    budget_minor: Mapped[int] = mapped_column(Integer)
    balance_minor: Mapped[int] = mapped_column(Integer)
    reserve_minor: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(default=1)
    run_id: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        CheckConstraint("balance_minor >= 0"),
        CheckConstraint("reserve_minor >= 0"),
    )


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    code: Mapped[str]
    name: Mapped[str]
    approved: Mapped[bool] = mapped_column(default=True)
    beneficiary_token: Mapped[str]
    beneficiary_fingerprint: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("project_id", "code"),)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    document_type: Mapped[str]
    original_filename: Mapped[str]
    storage_name: Mapped[str]
    sha256: Mapped[str] = mapped_column(index=True)
    extraction_status: Mapped[str]
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    text: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(default=1)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)


class ExtractionRevision(Base):
    __tablename__ = "extraction_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    version: Mapped[int]
    fields_json: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("document_id", "version"),)


class BOQItem(Base):
    __tablename__ = "boq_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    item_code: Mapped[str]
    description: Mapped[str]
    unit: Mapped[str]
    quantity: Mapped[str]
    rate: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("project_id", "item_code"),)


class Variation(Base):
    __tablename__ = "variations"
    id: Mapped[int] = mapped_column(primary_key=True)
    boq_item_id: Mapped[int] = mapped_column(ForeignKey("boq_items.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    quantity: Mapped[str]
    unit: Mapped[str]
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    number: Mapped[str]
    currency: Mapped[str] = mapped_column(default="BDT")
    tax_percent: Mapped[str] = mapped_column(default="0")
    retention_percent: Mapped[str] = mapped_column(default="0")
    discount_minor: Mapped[int] = mapped_column(default=0)
    approved: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("project_id", "number"),)


class POLine(Base):
    __tablename__ = "purchase_order_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    item_code: Mapped[str]
    description: Mapped[str]
    quantity: Mapped[str]
    unit: Mapped[str]
    rate: Mapped[str]
    __table_args__ = (UniqueConstraint("po_id", "item_code"),)


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    number: Mapped[str]
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (UniqueConstraint("po_id", "number"),)


class ReceiptLine(Base):
    __tablename__ = "receipt_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id"))
    item_code: Mapped[str]
    quantity: Mapped[str]
    unit: Mapped[str]
    __table_args__ = (UniqueConstraint("receipt_id", "item_code"),)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    po_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    supplier_code: Mapped[str]
    number: Mapped[str]
    invoice_date: Mapped[str]
    currency: Mapped[str]
    subtotal_minor: Mapped[int]
    tax_minor: Mapped[int] = mapped_column(default=0)
    retention_minor: Mapped[int] = mapped_column(default=0)
    discount_minor: Mapped[int] = mapped_column(default=0)
    total_minor: Mapped[int]
    beneficiary_fingerprint: Mapped[str]
    status: Mapped[str] = mapped_column(default="PENDING_REVIEW")
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        UniqueConstraint("project_id", "supplier_code", "number"),
        CheckConstraint("total_minor > 0"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    item_code: Mapped[str]
    description: Mapped[str]
    quantity: Mapped[str]
    unit: Mapped[str]
    rate: Mapped[str]
    amount_minor: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)


class Verification(Base):
    __tablename__ = "verification_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    report_json: Mapped[str] = mapped_column(Text)
    analyzed_at: Mapped[str] = mapped_column(default=utcnow)


class CashMovement(Base):
    __tablename__ = "cash_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str]
    amount_minor: Mapped[int]
    currency: Mapped[str]
    due_date: Mapped[str]
    description: Mapped[str]
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    settled: Mapped[bool] = mapped_column(default=False)
    cost_pressure: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (CheckConstraint("amount_minor >= 0"),)


class Proposal(Base):
    __tablename__ = "payment_proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    payable_id: Mapped[int | None] = mapped_column(ForeignKey("payable_balances.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    amount_minor: Mapped[int]
    currency: Mapped[str]
    beneficiary_fingerprint: Mapped[str]
    status: Mapped[str]
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(default=1)
    snapshot_json: Mapped[str] = mapped_column(Text)
    snapshot_hash: Mapped[str]
    expires_at: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (CheckConstraint("amount_minor > 0"),)


Index(
    "uq_active_invoice_proposal",
    Proposal.invoice_id,
    unique=True,
    sqlite_where=Proposal.status.in_(["PENDING_APPROVAL", "APPROVED", "EXECUTING"]),
)

Index("uq_active_certificate_proposal", Proposal.payable_id, unique=True,
      sqlite_where=Proposal.status.in_(["PENDING_APPROVAL", "APPROVED", "EXECUTING"]))


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("payment_proposals.id"), unique=True
    )
    amount_minor: Mapped[int]
    state: Mapped[str] = mapped_column(default="ACTIVE")


class ReceiptAllocation(Base):
    __tablename__ = "receipt_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("payment_proposals.id"))
    receipt_line_id: Mapped[int] = mapped_column(ForeignKey("receipt_lines.id"))
    invoice_line_id: Mapped[int] = mapped_column(ForeignKey("invoice_lines.id"))
    canonical_quantity: Mapped[str]
    state: Mapped[str] = mapped_column(default="ACTIVE")
    __table_args__ = (
        UniqueConstraint("proposal_id", "receipt_line_id", "invoice_line_id"),
    )


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("payment_proposals.id"))
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str]
    snapshot_hash: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("payment_proposals.id"), unique=True
    )
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    payable_id: Mapped[int | None] = mapped_column(ForeignKey("payable_balances.id"), index=True)
    mock_transaction_id: Mapped[str] = mapped_column(unique=True)
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    amount_minor: Mapped[int]
    currency: Mapped[str]
    provider: Mapped[str] = mapped_column(default="BuildTrust Local Sandbox")
    executed_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (CheckConstraint("amount_minor > 0"),)


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("payment_proposals.id"))
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    request_hash: Mapped[str]
    status_code: Mapped[int]
    response_json: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"))
    account: Mapped[str]
    direction: Mapped[str]
    amount_minor: Mapped[int]
    currency: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("payment_id", "account"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str]
    role: Mapped[str]
    event_type: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    details_json: Mapped[str] = mapped_column(Text)
    previous_hash: Mapped[str]
    event_hash: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="QUEUED")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=utcnow)


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"))
    name: Mapped[str]
    tool: Mapped[str]
    status: Mapped[str]
    input_json: Mapped[str] = mapped_column(Text)
    output_json: Mapped[str] = mapped_column(Text)
    started_at: Mapped[str]
    finished_at: Mapped[str | None]
