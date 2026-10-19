from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import uuid
from sqlalchemy import select
from . import audit
from .models import (
    Proposal,
    Reservation,
    ReceiptAllocation,
    ReceiptLine,
    GoodsReceipt,
    InvoiceLine,
    Invoice,
    Project,
    Supplier,
    Approval,
    Payment,
    LedgerEntry,
    ExecutionAttempt,
    CashMovement,
)
from .money import canonical, digest, money, decimal, normalize, minor, utcnow
from .finance import reconcile, source_snapshot, used_allocations
from .security import DomainError, require_role, project_access
from .authority import conversion


def release(session, proposal):
    for reservation in session.scalars(
        select(Reservation).where(
            Reservation.proposal_id == proposal.id, Reservation.state == "ACTIVE"
        )
    ):
        reservation.state = "RELEASED"
    for allocation in session.scalars(
        select(ReceiptAllocation).where(
            ReceiptAllocation.proposal_id == proposal.id,
            ReceiptAllocation.state == "ACTIVE",
        )
    ):
        allocation.state = "RELEASED"


def invalidate_authority(session, actor, user_id, project_id=None):
    """Role/access changes retire live authority without changing past receipts."""
    from sqlalchemy import or_

    ids = select(Approval.proposal_id).where(
        Approval.approver_id == user_id, Approval.decision == "APPROVED"
    )
    for proposal in session.scalars(
        select(Proposal).where(
            Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
            or_(Proposal.requested_by == user_id, Proposal.id.in_(ids)),
            Proposal.project_id == project_id if project_id is not None else True,
        )
    ):
        proposal.status = "BLOCKED"
        proposal.version += 1
        release(session, proposal)
        audit.append(
            session,
            actor,
            "AUTHORITY_CHANGE_INVALIDATED_APPROVAL",
            "proposal",
            proposal.id,
            {"changed_user_id": user_id},
            proposal.project_id,
        )


def expire(session):
    for proposal in session.scalars(
        select(Proposal).where(
            Proposal.status.in_(["PENDING_APPROVAL", "APPROVED"]),
            Proposal.expires_at <= utcnow(),
        )
    ):
        proposal.status = "EXPIRED"
        release(session, proposal)
        audit.append(
            session,
            None,
            "APPROVAL_EXPIRED",
            "proposal",
            proposal.id,
            project_id=proposal.project_id,
        )


def snapshot(session, invoice, proposal, settings):
    from .control_models import Payable

    if proposal.payable_id:
        from .certified_payables import sources

        result = sources(session, proposal, settings)
        if proposal.currency != "BDT":
            result["authority_fx"] = conversion(
                session, proposal.project_id, proposal.currency, proposal.amount_minor
            )
        return result
    payable = session.scalar(select(Payable).where(Payable.invoice_id == invoice.id))
    result = {
        "invoice_id": invoice.id,
        "supplier_id": proposal.supplier_id,
        "amount_minor": proposal.amount_minor,
        "currency": proposal.currency,
        "beneficiary_fingerprint": proposal.beneficiary_fingerprint,
        "proposal_version": proposal.version,
        "expires_at": proposal.expires_at,
        "sources": source_snapshot(session, invoice, settings),
    }
    if payable:
        result["payable"] = {
            "id": payable.id,
            "version": payable.version,
            "amount_minor": payable.amount_minor,
            "paid_minor": payable.paid_minor,
            "credit_minor": payable.credit_minor,
            "retention_released_minor": payable.retention_released_minor,
        }
    if proposal.currency != "BDT":
        result["authority_fx"] = conversion(
            session, proposal.project_id, proposal.currency, proposal.amount_minor
        )
    return result


def proposal_view(session, proposal):
    invoice = session.get(Invoice, proposal.invoice_id) if proposal.invoice_id else None
    certificate = None
    if proposal.payable_id:
        from .control_models import Payable, ControlRecord

        certificate = session.get(
            ControlRecord, session.get(Payable, proposal.payable_id).record_id
        )
    supplier = (
        session.get(Supplier, proposal.supplier_id) if proposal.supplier_id else None
    )
    approvals = list(
        session.scalars(
            select(Approval)
            .where(Approval.proposal_id == proposal.id)
            .order_by(Approval.id)
        )
    )
    payment = session.scalar(select(Payment).where(Payment.proposal_id == proposal.id))
    return {
        "id": proposal.id,
        "project_id": proposal.project_id,
        "invoice_id": invoice.id if invoice else None,
        **(
            {"payable_id": proposal.payable_id, "certificate_id": certificate.id}
            if certificate
            else {}
        ),
        "invoice_number": invoice.number
        if invoice
        else json.loads(certificate.payload_json)["number"],
        "supplier": supplier.name if supplier else invoice.supplier_code,
        "amount": money(proposal.amount_minor),
        "currency": proposal.currency,
        "status": "EXPIRED"
        if proposal.status in ("PENDING_APPROVAL", "APPROVED")
        and proposal.expires_at <= utcnow()
        else proposal.status,
        "requested_by": proposal.requested_by,
        "beneficiary_fingerprint": proposal.beneficiary_fingerprint,
        "snapshot_hash": proposal.snapshot_hash,
        "expires_at": proposal.expires_at,
        "created_at": proposal.created_at,
        "version": proposal.version,
        "approvals": [
            {
                "approver_id": a.approver_id,
                "decision": a.decision,
                "created_at": a.created_at,
            }
            for a in approvals
        ],
        "payment_id": payment.id if payment else None,
    }


def create_proposal(session, invoice, settings, actor, amount_minor=None):
    project_access(session, actor, invoice.project_id, write=True)
    require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
    expire(session)
    from .control_models import Payable

    payable = session.scalar(select(Payable).where(Payable.invoice_id == invoice.id))
    remaining = (
        payable.amount_minor - payable.paid_minor - payable.credit_minor
        if payable
        else invoice.total_minor
    )
    if amount_minor is not None and not payable:
        raise DomainError(
            409,
            "PAYABLE_REQUIRED",
            "Independently reconcile the invoice before preparing installments.",
        )
    requested = remaining if amount_minor is None else amount_minor
    if requested <= 0 or requested > remaining:
        if not payable:
            requested = invoice.total_minor
        else:
            raise DomainError(
                409,
                "OVERPAYMENT",
                "Installment exceeds the authoritative remaining payable.",
            )
    existing = session.scalar(
        select(Proposal).where(
            Proposal.invoice_id == invoice.id,
            Proposal.status.in_(
                ["PENDING_APPROVAL", "APPROVED"]
                if payable
                else ["PENDING_APPROVAL", "APPROVED", "SETTLED"]
            ),
        )
    )
    if existing:
        if amount_minor is not None and existing.amount_minor != requested:
            raise DomainError(
                409,
                "ACTIVE_INSTALLMENT",
                "One active installment is allowed for this payable.",
            )
        return existing
    report = reconcile(session, invoice, settings, payment_amount_minor=requested)
    expires_at = (
        (datetime.now(timezone.utc) + timedelta(minutes=settings.approval_minutes))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    proposal = Proposal(
        invoice_id=invoice.id,
        project_id=invoice.project_id,
        supplier_id=invoice.supplier_id,
        amount_minor=requested,
        currency=invoice.currency,
        beneficiary_fingerprint=invoice.beneficiary_fingerprint,
        status="CREATED",
        requested_by=actor.id,
        snapshot_json="{}",
        snapshot_hash="",
        expires_at=expires_at,
    )
    session.add(proposal)
    session.flush()
    for stage in ["CREATED", "VALIDATED" if report["payment_eligible"] else "BLOCKED"]:
        audit.append(
            session,
            actor,
            "PAYMENT_" + stage,
            "proposal",
            proposal.id,
            {
                "amount": money(proposal.amount_minor),
                "findings": [f["code"] for f in report["findings"]],
            },
            invoice.project_id,
        )
    proposal.status = "PENDING_APPROVAL" if report["payment_eligible"] else "BLOCKED"
    proposal.snapshot_json = canonical(snapshot(session, invoice, proposal, settings))
    proposal.snapshot_hash = digest(json.loads(proposal.snapshot_json))
    if report["payment_eligible"]:
        session.add(
            Reservation(proposal_id=proposal.id, amount_minor=proposal.amount_minor)
        )
        used = used_allocations(session, invoice.project_id)
        already_allocated = payable and any(
            inv.id == invoice.id and allocation.state == "CONSUMED"
            for allocation, _, inv, _ in used
        )
        for line in session.scalars(
            select(InvoiceLine).where(
                InvoiceLine.invoice_id == invoice.id, InvoiceLine.active.is_(True)
            )
        ):
            if already_allocated:
                break  # Physical entitlement was consumed once by the first settlement.
            needed, unit, _ = normalize(line.quantity, line.unit)
            receipt_rows = session.scalars(
                select(ReceiptLine)
                .join(GoodsReceipt)
                .where(
                    GoodsReceipt.po_id == invoice.po_id,
                    ReceiptLine.item_code == line.item_code,
                )
                .order_by(ReceiptLine.id)
            )
            for receipt_line in receipt_rows:
                received, _, _ = normalize(receipt_line.quantity, receipt_line.unit)
                already_used = sum(
                    (
                        decimal(a.canonical_quantity)
                        for a, _, _, _ in used
                        if a.receipt_line_id == receipt_line.id
                    ),
                    Decimal(0),
                )
                portion = min(needed, max(Decimal(0), received - already_used))
                if portion:
                    session.add(
                        ReceiptAllocation(
                            proposal_id=proposal.id,
                            receipt_line_id=receipt_line.id,
                            invoice_line_id=line.id,
                            canonical_quantity=str(portion),
                        )
                    )
                    needed -= portion
                if not needed:
                    break
            if needed:
                raise DomainError(
                    409,
                    "RECEIPT_REUSE",
                    "Delivery entitlement was allocated concurrently.",
                )
        audit.append(
            session,
            actor,
            "PAYMENT_PENDING_APPROVAL",
            "proposal",
            proposal.id,
            {"snapshot_hash": proposal.snapshot_hash, "expires_at": expires_at},
            invoice.project_id,
        )
    return proposal


def authorize_amount(actor, proposal, settings, session=None):
    require_role(actor, "FINANCE_MANAGER", "ADMIN")
    bound = json.loads(proposal.snapshot_json)
    if bound.get("currency") and bound["currency"] != proposal.currency:
        raise DomainError(
            409,
            "APPROVAL_SNAPSHOT_CHANGED",
            "Payment currency differs from its approval snapshot.",
            proposal.project_id,
            proposal.id,
        )
    limit = (
        10000000 if actor.role == "FINANCE_MANAGER" else minor(settings.admin_ceiling)
    )
    if (
        conversion(
            session, proposal.project_id, proposal.currency, proposal.amount_minor
        )["amount_minor"]
        > limit
    ):
        raise DomainError(
            403,
            "PAYMENT_LIMIT_EXCEEDED",
            "Payment exceeds your approval/execution limit.",
            proposal.project_id,
            proposal.id,
        )


def current_validation(session, proposal, settings):
    from .models import User, Membership

    preparer = session.get(User, proposal.requested_by)
    if (
        not preparer
        or not preparer.active
        or preparer.role not in ("OPERATOR", "FINANCE_MANAGER", "ADMIN")
        or not session.get(Membership, (preparer.id, proposal.project_id))
    ):
        raise DomainError(
            409,
            "PREPARER_AUTHORITY_CHANGED",
            "The preparing account no longer has project authority. Prepare a fresh independently reviewed proposal.",
            proposal.project_id,
            proposal.id,
        )
    invoice = session.get(Invoice, proposal.invoice_id) if proposal.invoice_id else None
    if proposal.expires_at <= utcnow():
        raise DomainError(
            409,
            "APPROVAL_EXPIRED",
            "Approval expired; prepare a new proposal.",
            proposal.project_id,
            proposal.id,
        )
    current_hash = digest(snapshot(session, invoice, proposal, settings))
    if current_hash != proposal.snapshot_hash:
        raise DomainError(
            409,
            "APPROVAL_SNAPSHOT_CHANGED",
            "Approved payment or supporting evidence changed. Fresh approval is required.",
            proposal.project_id,
            proposal.id,
        )
    if proposal.payable_id:
        from .certified_payables import check

        check(session, proposal, settings)
        return None
    from .control_models import Payable

    payable = session.scalar(select(Payable).where(Payable.invoice_id == invoice.id))
    if (
        payable
        and proposal.amount_minor
        > payable.amount_minor - payable.paid_minor - payable.credit_minor
    ):
        raise DomainError(
            409,
            "OVERPAYMENT",
            "Installment exceeds the current remaining balance.",
            proposal.project_id,
            proposal.id,
        )
    report = reconcile(
        session,
        invoice,
        settings,
        exclude_proposal=proposal.id,
        payment_amount_minor=proposal.amount_minor,
    )
    if not report["payment_eligible"]:
        raise DomainError(
            409,
            "PAYMENT_BLOCKED",
            "Current controls block payment: "
            + ", ".join(
                f["code"] for f in report["findings"] if f["severity"] == "BLOCK"
            ),
            proposal.project_id,
            proposal.id,
        )
    reservation = session.scalar(
        select(Reservation).where(
            Reservation.proposal_id == proposal.id, Reservation.state == "ACTIVE"
        )
    )
    if not reservation or reservation.amount_minor != proposal.amount_minor:
        raise DomainError(
            409,
            "RESERVATION_INVALID",
            "An exact active cash reservation is required.",
            proposal.project_id,
            proposal.id,
        )
    return invoice


def approve(session, proposal, settings, actor):
    project_access(session, actor, proposal.project_id, write=True)
    authorize_amount(actor, proposal, settings, session)
    if proposal.requested_by == actor.id:
        raise DomainError(
            403,
            "SEPARATION_OF_DUTIES",
            "The proposal creator cannot approve their own payment.",
            proposal.project_id,
            proposal.id,
        )
    if proposal.status != "PENDING_APPROVAL":
        raise DomainError(
            409, "INVALID_STATE", "Only a pending proposal can be approved."
        )
    current_validation(session, proposal, settings)
    proposal.status = "APPROVED"
    session.add(
        Approval(
            proposal_id=proposal.id,
            approver_id=actor.id,
            decision="APPROVED",
            snapshot_hash=proposal.snapshot_hash,
        )
    )
    audit.append(
        session,
        actor,
        "PAYMENT_APPROVED",
        "proposal",
        proposal.id,
        {"snapshot_hash": proposal.snapshot_hash},
        proposal.project_id,
    )


def reject(session, proposal, settings, actor):
    project_access(session, actor, proposal.project_id, write=True)
    authorize_amount(actor, proposal, settings, session)
    if proposal.status not in ("PENDING_APPROVAL", "APPROVED"):
        raise DomainError(409, "INVALID_STATE", "This proposal cannot be rejected.")
    proposal.status = "REJECTED"
    release(session, proposal)
    session.add(
        Approval(
            proposal_id=proposal.id,
            approver_id=actor.id,
            decision="REJECTED",
            snapshot_hash=proposal.snapshot_hash,
        )
    )
    audit.append(
        session,
        actor,
        "PAYMENT_REJECTED",
        "proposal",
        proposal.id,
        project_id=proposal.project_id,
    )


def execute(session, proposal, settings, actor, key, fail_hook=None):
    project_access(session, actor, proposal.project_id, write=True)
    authorize_amount(actor, proposal, settings, session)
    if not key or len(key) > 200 or not key.strip():
        raise DomainError(
            422,
            "IDEMPOTENCY_KEY_REQUIRED",
            "Supply a nonempty Idempotency-Key header (at most 200 characters).",
        )
    request_hash = digest(
        {
            "proposal_id": proposal.id,
            "version": proposal.version,
            "operation": "execute",
        }
    )
    old = session.scalar(
        select(ExecutionAttempt).where(ExecutionAttempt.idempotency_key == key)
    )
    if old:
        if old.request_hash != request_hash:
            raise DomainError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "Idempotency key was used for a different request.",
                proposal.project_id,
                proposal.id,
            )
        audit.append(
            session,
            actor,
            "PAYMENT_RETRY",
            "proposal",
            proposal.id,
            {"outcome": "ORIGINAL_RESULT_RETURNED"},
            proposal.project_id,
        )
        if old.status_code != 200:
            error = json.loads(old.response_json)["error"]
            raise DomainError(
                old.status_code,
                error["code"],
                error["message"],
                proposal.project_id,
                proposal.id,
            )
        return json.loads(old.response_json)
    if proposal.status != "APPROVED":
        raise DomainError(
            409,
            "APPROVAL_REQUIRED",
            "An explicitly approved proposal is required.",
            proposal.project_id,
            proposal.id,
        )
    invoice = current_validation(session, proposal, settings)
    approval = session.scalar(
        select(Approval)
        .where(Approval.proposal_id == proposal.id, Approval.decision == "APPROVED")
        .order_by(Approval.id.desc())
    )
    if (
        not approval
        or approval.snapshot_hash != proposal.snapshot_hash
        or approval.approver_id == proposal.requested_by
    ):
        raise DomainError(
            409,
            "APPROVAL_INVALID",
            "Exact independent human approval is required.",
            proposal.project_id,
            proposal.id,
        )
    from .models import User, Membership

    approver = session.get(User, approval.approver_id)
    if (
        not approver
        or not approver.active
        or not session.get(Membership, (approver.id, proposal.project_id))
    ):
        raise DomainError(
            409,
            "APPROVAL_INVALID",
            "The approving account no longer has active project access.",
            proposal.project_id,
            proposal.id,
        )
    try:
        authorize_amount(approver, proposal, settings, session)
    except DomainError:
        raise DomainError(
            409,
            "APPROVAL_INVALID",
            "The approving account no longer has sufficient authority.",
            proposal.project_id,
            proposal.id,
        )
    project = session.get(Project, proposal.project_id)
    proposal.status = "EXECUTING"
    audit.append(
        session,
        actor,
        "PAYMENT_EXECUTING",
        "proposal",
        proposal.id,
        {"simulation": True},
        project.id,
    )
    project.balance_minor -= proposal.amount_minor
    if project.balance_minor < 0:
        raise DomainError(
            409,
            "INSUFFICIENT_FUNDS",
            "Current cash balance is insufficient.",
            project.id,
            proposal.id,
        )
    payment = Payment(
        proposal_id=proposal.id,
        invoice_id=invoice.id if invoice else None,
        payable_id=proposal.payable_id,
        mock_transaction_id="MOCK-" + uuid.uuid4().hex.upper(),
        idempotency_key=key,
        amount_minor=proposal.amount_minor,
        currency=proposal.currency,
    )
    session.add(payment)
    session.flush()
    from .accounting import payment_posted

    payment_posted(session, project, invoice, payment)
    if fail_hook:
        fail_hook()  # only dependency injection in tests; never exposed as a public financial parameter
    for account, direction in [("CASH", "CREDIT"), ("ACCOUNTS_PAYABLE", "DEBIT")]:
        session.add(
            LedgerEntry(
                project_id=project.id,
                payment_id=payment.id,
                account=account,
                direction=direction,
                amount_minor=payment.amount_minor,
                currency=payment.currency,
            )
        )
    for reservation in session.scalars(
        select(Reservation).where(Reservation.proposal_id == proposal.id)
    ):
        reservation.state = "CONSUMED"
    for allocation in session.scalars(
        select(ReceiptAllocation).where(ReceiptAllocation.proposal_id == proposal.id)
    ):
        allocation.state = "CONSUMED"
    from .control_models import Payable

    payable = (
        session.get(Payable, proposal.payable_id)
        if proposal.payable_id
        else session.scalar(select(Payable).where(Payable.invoice_id == invoice.id))
    )
    remaining = (
        payable.amount_minor - payable.paid_minor - payable.credit_minor
        if payable
        else 0
    )
    for movement in (
        session.scalars(
            select(CashMovement).where(CashMovement.invoice_id == invoice.id)
        )
        if invoice
        else []
    ):
        movement.amount_minor = remaining if payable else movement.amount_minor
        movement.settled = remaining <= 0
    proposal.status = "SETTLED"
    if invoice:
        invoice.status = "SETTLED" if remaining <= 0 else "PARTIALLY_PAID"
    supplier = session.get(Supplier, proposal.supplier_id)
    from .control_models import ControlRecord

    result = {
        "payment_id": payment.id,
        "proposal_id": proposal.id,
        "invoice_id": invoice.id if invoice else None,
        "invoice_number": invoice.number
        if invoice
        else json.loads(session.get(ControlRecord, payable.record_id).payload_json)[
            "number"
        ],
        **(
            {"payable_id": payable.id, "certificate_id": payable.record_id}
            if not invoice
            else {}
        ),
        "supplier": supplier.name,
        "amount": money(payment.amount_minor),
        "currency": payment.currency,
        "beneficiary_fingerprint": proposal.beneficiary_fingerprint,
        "mock_transaction_id": payment.mock_transaction_id,
        "provider": payment.provider,
        "status": "SETTLED",
        "simulation": True,
        "executed_at": payment.executed_at,
        "balance_after": money(project.balance_minor),
    }
    session.add(
        ExecutionAttempt(
            proposal_id=proposal.id,
            actor_id=actor.id,
            idempotency_key=key,
            request_hash=request_hash,
            status_code=200,
            response_json=canonical(result),
        )
    )
    audit.append(
        session,
        actor,
        "PAYMENT_SETTLED",
        "payment",
        payment.id,
        {
            **result,
            "balance_before": money(project.balance_minor + payment.amount_minor),
        },
        project.id,
    )
    return result
