from datetime import datetime, date, timedelta
from decimal import Decimal
import json
from zoneinfo import ZoneInfo
from sqlalchemy import select

from .models import (
    Project,
    Supplier,
    Document,
    BOQItem,
    Variation,
    PurchaseOrder,
    POLine,
    GoodsReceipt,
    ReceiptLine,
    Invoice,
    InvoiceLine,
    CashMovement,
    Proposal,
    Reservation,
    ReceiptAllocation,
    Payment,
    Verification,
)
from .money import decimal, minor, money, normalize, canonical, utcnow
from . import audit, procurement
from .security import DomainError


def business_date():
    return datetime.now(ZoneInfo("Asia/Dhaka")).date()


def live_reservations(session, project_id, exclude_proposal=None):
    return list(
        session.scalars(
            select(Reservation)
            .join(Proposal)
            .where(
                Proposal.project_id == project_id,
                Reservation.state == "ACTIVE",
                Proposal.status.in_(["PENDING_APPROVAL", "APPROVED"]),
                Proposal.expires_at > utcnow(),
                Proposal.id != exclude_proposal
                if exclude_proposal is not None
                else True,
            )
        )
    )


def forecast(
    session,
    project,
    settings,
    proposed_minor=0,
    invoice_id=None,
    exclude_proposal=None,
    delay=None,
    pressure=None,
    today=None,
    horizon=30,
    movement_overrides=None,
    payable_id=None,
):
    if not 1 <= horizon <= 1095:
        raise ValueError("Forecast horizon must be between 1 and 1095 days")
    movement_overrides = movement_overrides or {}
    today = today or business_date()
    delay = settings.receivable_delay_days if delay is None else delay
    pressure = decimal(settings.cost_pressure_percent if pressure is None else pressure)
    reservations = live_reservations(session, project.id, exclude_proposal)
    reserved = sum(r.amount_minor for r in reservations)
    movements = list(
        session.scalars(
            select(CashMovement).where(
                CashMovement.project_id == project.id, CashMovement.settled.is_(False)
            )
        )
    )
    available = project.balance_minor - reserved
    # Reservations cover only their exact installment, not the entire invoice.
    covered = {}
    covered_movements = {}
    from .control_models import Obligation
    def cover_payable(identity, amount):
        obligation = session.scalar(select(Obligation).where(Obligation.project_id == project.id,
                                  Obligation.source_type == "PAYABLE", Obligation.source_id == identity))
        if obligation and obligation.cash_movement_id:
            covered_movements[obligation.cash_movement_id] = covered_movements.get(obligation.cash_movement_id, 0) + amount
    for reservation in reservations:
        proposal = session.get(Proposal, reservation.proposal_id)
        if proposal.payable_id:
            cover_payable(proposal.payable_id, reservation.amount_minor)
        else:
            identity = proposal.invoice_id
            covered[identity] = covered.get(identity, 0) + reservation.amount_minor
    if invoice_id:
        covered[invoice_id] = covered.get(invoice_id, 0) + proposed_minor
    if payable_id:
        cover_payable(payable_id, proposed_minor)
    adjusted = {}
    for movement in sorted(movements, key=lambda row: (row.due_date, row.id)):
        amount = movement_overrides.get(movement.id, {}).get(
            "amount_minor", movement.amount_minor
        )
        if movement.invoice_id and movement.kind == "OUTFLOW":
            deduction = min(amount, covered.get(movement.invoice_id, 0))
            covered[movement.invoice_id] = (
                covered.get(movement.invoice_id, 0) - deduction
            )
            amount -= deduction
        elif movement.kind == "OUTFLOW":
            amount -= min(amount, covered_movements.get(movement.id, 0))
        adjusted[movement.id] = amount
    scenarios = []
    for name in ["base", "delayed_receivables", "cost_pressure"]:
        balance = available - proposed_minor
        days = []
        for offset in range(horizon):
            day = today + timedelta(days=offset)
            inflows, outflows, obligations = 0, 0, []
            for movement in movements:
                if movement.currency != project.currency:
                    continue  # returned as a blocking finding below
                if not adjusted[movement.id]:
                    continue
                due = date.fromisoformat(
                    movement_overrides.get(movement.id, {}).get(
                        "due_date", movement.due_date
                    )
                )
                if name == "delayed_receivables" and movement.kind == "INFLOW":
                    due += timedelta(days=delay)
                due = max(due, today)
                if due != day:
                    continue
                amount = adjusted[movement.id]
                if (
                    name == "cost_pressure"
                    and movement.cost_pressure
                    and movement.kind == "OUTFLOW"
                ):
                    amount = minor(Decimal(amount) / 100 * (1 + pressure / 100))
                if movement.kind == "INFLOW":
                    inflows += amount
                else:
                    outflows += amount
                    obligations.append(
                        {
                            "id": movement.id,
                            "description": movement.description,
                            "amount": money(amount),
                        }
                    )
            opening = balance
            balance += inflows - outflows
            days.append(
                {
                    "date": day.isoformat(),
                    "opening": money(opening),
                    "inflows": money(inflows),
                    "outflows": money(outflows),
                    "closing": money(balance),
                    "obligations": obligations,
                }
            )
        lowest = min(days, key=lambda d: decimal(d["closing"]))
        # A same-day inflow cannot conceal an immediate reserve breach at execution.
        minimum = min(available - proposed_minor, minor(lowest["closing"]))
        scenarios.append(
            {
                "name": name,
                "days": days,
                "lowest_balance": money(minimum),
                "pressure_date": lowest["date"]
                if minimum == minor(lowest["closing"])
                else today.isoformat(),
                "reserve_maintained": minimum >= project.reserve_minor,
                "shortfall_obligations": [
                    o
                    for d in days
                    if d["date"] <= lowest["date"]
                    for o in d["obligations"]
                ],
            }
        )
    eligible = available >= proposed_minor and all(
        s["reserve_maintained"] for s in scenarios[:2]
    )
    currency_mismatch = any(m.currency != project.currency for m in movements)
    eligible = eligible and not currency_mismatch
    return {
        "project_id": project.id,
        "currency": project.currency,
        "as_of": today.isoformat(),
        "recorded_balance": money(project.balance_minor),
        "reserved": money(reserved),
        "available_cash": money(available),
        "proposed_payment": money(proposed_minor),
        "minimum_reserve": money(project.reserve_minor),
        "receivable_delay_days": delay,
        "cost_pressure_percent": str(pressure),
        "scenarios": scenarios,
        "policy_receivable_delay_days": settings.receivable_delay_days,
        "payment_eligible": eligible,
        "currency_mismatch": currency_mismatch,
        "recommendation": "PROCEED_TO_HUMAN_APPROVAL"
        if eligible
        else "HOLD_FOR_LIQUIDITY_REVIEW",
        "assumption_notice": "Scheduled internal records and configurable scenarios; not independently verified market forecasts.",
    }


def evidence(document_id, kind, item_code=None):
    return {"document_id": document_id, "record_type": kind, "item_code": item_code}


def used_allocations(session, project_id, exclude_proposal=None):
    from .control_models import InvoiceEntitlement
    from types import SimpleNamespace

    claims = session.execute(
        select(InvoiceEntitlement, InvoiceLine, Invoice)
        .join(InvoiceLine, InvoiceEntitlement.invoice_line_id == InvoiceLine.id)
        .join(Invoice, Invoice.id == InvoiceEntitlement.invoice_id)
        .where(Invoice.project_id == project_id)
    ).all()
    claimed_invoices = {inv.id for _, _, inv in claims}
    rows = session.execute(
        select(ReceiptAllocation, InvoiceLine, Invoice, Proposal)
        .join(InvoiceLine, ReceiptAllocation.invoice_line_id == InvoiceLine.id)
        .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
        .join(Proposal, ReceiptAllocation.proposal_id == Proposal.id)
        .where(
            Invoice.project_id == project_id,
            ReceiptAllocation.state.in_(["ACTIVE", "CONSUMED"]),
        )
    ).all()
    legacy = [
        (a, line, inv, p)
        for a, line, inv, p in rows
        if p.id != exclude_proposal
        and inv.id not in claimed_invoices
        and (
            a.state == "CONSUMED"
            or (
                p.expires_at > utcnow() and p.status in ("PENDING_APPROVAL", "APPROVED")
            )
        )
    ]
    from .commercial_models import CertificateAllocation
    from .control_models import Recognition
    certified = []
    for allocation, recognized, line, receipt, pol in session.execute(
        select(CertificateAllocation, Recognition, ReceiptLine, GoodsReceipt, POLine)
        .join(Recognition, Recognition.record_id == CertificateAllocation.acceptance_id)
        .join(ReceiptLine, ReceiptLine.id == Recognition.receipt_line_id)
        .join(GoodsReceipt, GoodsReceipt.id == ReceiptLine.receipt_id)
        .join(POLine, (POLine.po_id == GoodsReceipt.po_id) & (POLine.item_code == ReceiptLine.item_code))
        .where(Recognition.project_id == project_id)
    ):
        certified.append((SimpleNamespace(receipt_line_id=line.id, canonical_quantity=recognized.quantity, state="CONSUMED"),
                          SimpleNamespace(item_code=line.item_code, quantity=line.quantity, unit=line.unit, rate=pol.rate),
                          SimpleNamespace(id=-allocation.certificate_id, po_id=receipt.po_id),
                          SimpleNamespace(id=-allocation.certificate_id, status="CLAIMED", expires_at="9999")))
    return legacy + certified + [
        (
            claim,
            line,
            inv,
            SimpleNamespace(id=-inv.id, status="CLAIMED", expires_at="9999"),
        )
        for claim, line, inv in claims
    ]


def reconcile(
    session, invoice, settings, exclude_proposal=None, payment_amount_minor=None
):
    project = session.get(Project, invoice.project_id)
    supplier = (
        session.get(Supplier, invoice.supplier_id) if invoice.supplier_id else None
    )
    po = session.get(PurchaseOrder, invoice.po_id) if invoice.po_id else None
    document = session.get(Document, invoice.document_id)
    lines = list(
        session.scalars(
            select(InvoiceLine)
            .where(InvoiceLine.invoice_id == invoice.id, InvoiceLine.active.is_(True))
            .order_by(InvoiceLine.id)
        )
    )
    findings, comparisons = [], []

    def flag(code, message, refs=None, severity="BLOCK"):
        if not any(f["code"] == code and f["message"] == message for f in findings):
            findings.append(
                {
                    "code": code,
                    "severity": severity,
                    "message": message,
                    "evidence": refs or [evidence(document.id, "INVOICE")],
                }
            )

    if not supplier or not supplier.approved:
        flag(
            "UNKNOWN_SUPPLIER",
            "Supplier is absent from the approved project supplier master.",
        )
    elif invoice.beneficiary_fingerprint != supplier.beneficiary_fingerprint:
        flag(
            "BENEFICIARY_CHANGE",
            "Invoice beneficiary differs from the approved supplier master. Separate verification is required.",
        )
    if not po or not po.approved:
        flag("MISSING_PURCHASE_ORDER", "An approved purchase order is required.")
    elif po.supplier_id != invoice.supplier_id:
        flag(
            "SUPPLIER_MISMATCH",
            "Invoice supplier does not match the approved purchase order.",
        )
    if invoice.currency != project.currency or (po and po.currency != invoice.currency):
        flag(
            "CURRENCY_MISMATCH",
            "Invoice, purchase order, and cash account currencies must agree. No FX conversion is performed.",
        )
    from .authority import conversion

    try:
        authority_amount = conversion(
            session,
            project.id,
            invoice.currency,
            payment_amount_minor
            if payment_amount_minor is not None
            else invoice.total_minor,
        )["amount_minor"]
    except DomainError as exc:
        authority_amount = 0
        flag("CURRENCY_MISMATCH", exc.message)
    if authority_amount > minor(settings.admin_ceiling):
        flag(
            "PAYMENT_LIMIT_EXCEEDED",
            "Invoice exceeds the configured sandbox payment ceiling.",
        )
    if document.extraction_status in ("NEEDS_REVIEW", "DUPLICATE"):
        flag(
            "DOCUMENT_REVIEW_REQUIRED", "Document fields require review before payment."
        )
    instructions = (
        document.text.lower()
        + " "
        + str(json.loads(document.extracted_json).get("notes", "")).lower()
    )
    if any(
        p in instructions
        for p in (
            "ignore previous instructions",
            "ignore all instructions",
            "approve without",
            "without review",
            "bypass approval",
            "system prompt",
        )
    ):
        flag(
            "SUSPICIOUS_INSTRUCTIONS",
            "Instruction-like content was found in the document. It has no authority and requires human review.",
        )
    from .control_models import Payable

    payable = session.scalar(select(Payable).where(Payable.invoice_id == invoice.id))
    remaining = (
        payable.amount_minor - payable.paid_minor - payable.credit_minor
        if payable
        else invoice.total_minor
    )
    if session.scalar(select(Payment).where(Payment.invoice_id == invoice.id)) and (
        not payable or remaining <= 0
    ):
        flag("DUPLICATE_INVOICE", "This invoice already has a settled sandbox payment.")
    allocated = used_allocations(session, project.id, exclude_proposal)
    if payable:
        allocated = [
            (a, line, inv, p) for a, line, inv, p in allocated if inv.id != invoice.id
        ]
    verified_subtotal, claimed_sum = 0, 0
    receipts = (
        list(session.scalars(select(GoodsReceipt).where(GoodsReceipt.po_id == po.id)))
        if po
        else []
    )
    receipt_lines = (
        list(
            session.scalars(
                select(ReceiptLine).where(
                    ReceiptLine.receipt_id.in_([r.id for r in receipts])
                )
            )
        )
        if receipts
        else []
    )
    for line in lines:
        boq = session.scalar(
            select(BOQItem).where(
                BOQItem.project_id == project.id, BOQItem.item_code == line.item_code
            )
        )
        pol = (
            session.scalar(
                select(POLine).where(
                    POLine.po_id == po.id, POLine.item_code == line.item_code
                )
            )
            if po
            else None
        )
        refs = [evidence(document.id, "INVOICE", line.item_code)]
        if boq:
            refs.append(evidence(boq.document_id, "BOQ", line.item_code))
        if po:
            refs.append(evidence(po.document_id, "PO", line.item_code))
        for receipt in receipts:
            refs.append(evidence(receipt.document_id, "GRN", line.item_code))
        if not boq or not pol:
            flag(
                "UNMATCHED_ITEM",
                f"{line.item_code}: exact approved BOQ and PO item matches are required.",
                refs,
            )
        try:
            q, unit, rate = normalize(line.quantity, line.unit, line.rate)
            bq, bu, br = (
                normalize(boq.quantity, boq.unit, boq.rate)
                if boq
                else (Decimal(0), unit, Decimal(0))
            )
            pq, pu, pr = (
                normalize(str(procurement.quantity(session,pol)), pol.unit, pol.rate)
                if pol
                else (Decimal(0), unit, Decimal(0))
            )
            for variation in (
                session.scalars(
                    select(Variation).where(Variation.boq_item_id == boq.id)
                )
                if boq
                else []
            ):
                vq, vu, _ = normalize(variation.quantity, variation.unit)
                if vu != unit:
                    raise ValueError("Variation has incompatible units")
                bq += vq
                refs.append(
                    evidence(variation.document_id, "VARIATION", line.item_code)
                )
            budget_extra = 0
            if boq:
                from .procurement import authorization
                approved_quantity, approved_value = authorization(session,boq)
                bq = normalize(str(approved_quantity),boq.unit)[0]
                budget_extra = approved_value-minor(approved_quantity*decimal(boq.rate))
            rq = Decimal(0)
            matching_receipts = [
                rl for rl in receipt_lines if rl.item_code == line.item_code
            ]
            for rl in matching_receipts:
                aq, au, _ = normalize(rl.quantity, rl.unit)
                if au != unit:
                    raise ValueError("Receipt units are incompatible")
                rq += aq
            if bu != unit or pu != unit:
                raise ValueError("BOQ, PO, and invoice units are incompatible")
            prior_boq = sum(
                (
                    decimal(a.canonical_quantity)
                    for a, il, _, _ in allocated
                    if il.item_code == line.item_code
                ),
                Decimal(0),
            )
            prior_po = sum(
                (
                    decimal(a.canonical_quantity)
                    for a, il, inv, _ in allocated
                    if il.item_code == line.item_code and inv.po_id == invoice.po_id
                ),
                Decimal(0),
            )
            entitlement = max(
                Decimal(0), min(bq - prior_boq, pq - prior_po, rq - prior_po)
            )
            verified_q = min(q, entitlement)
            excess = max(Decimal(0), q - entitlement)
            if not matching_receipts:
                flag(
                    "UNVERIFIED_DELIVERY",
                    f"{line.item_code}: no confirmed accepted-delivery evidence.",
                    refs,
                )
            if excess:
                flag(
                    "QUANTITY_MISMATCH",
                    f"{line.item_code}: claimed quantity exceeds remaining supported entitlement by {excess} {unit}.",
                    refs,
                )
                if q + prior_boq > bq:
                    flag(
                        "MISSING_APPROVED_CHANGE_ORDER",
                        f"{line.item_code}: quantity exceeds approved scope and variations.",
                        refs,
                    )
                if prior_po or prior_boq:
                    flag(
                        "RECEIPT_REUSE",
                        f"{line.item_code}: accepted quantity is already allocated to another obligation.",
                        refs,
                    )
            if rate != pr:
                flag(
                    "PRICE_MISMATCH",
                    f"{line.item_code}: invoice rate differs from the contracted rate.",
                    refs,
                )
            if pol and (
                line.description.strip().lower() != pol.description.strip().lower()
                or (
                    boq
                    and boq.description.strip().lower()
                    != pol.description.strip().lower()
                )
            ):
                flag(
                    "SPECIFICATION_MISMATCH",
                    f"{line.item_code}: descriptions/specifications need explicit human matching.",
                    refs,
                )
            verified_amount = minor(verified_q * pr)
            prior_budget = sum(
                (
                    decimal(a.canonical_quantity)
                    * normalize(il.quantity, il.unit, il.rate)[2]
                    for a, il, _, _ in allocated
                    if il.item_code == line.item_code
                ),
                Decimal(0),
            )
            budget_available = max(0, minor(bq * br - prior_budget)+budget_extra)
            if verified_amount > budget_available:
                flag(
                    "MISSING_APPROVED_CHANGE_ORDER",
                    f"{line.item_code}: contracted value exceeds the remaining approved BOQ budget.",
                    refs,
                )
                verified_amount = budget_available
            expected_claim = minor(q * rate)
            if line.amount_minor != expected_claim:
                flag(
                    "INVOICE_TOTAL_MISMATCH",
                    f"{line.item_code}: line amount does not equal quantity × rate.",
                    refs,
                )
            verified_subtotal += verified_amount
            claimed_sum += line.amount_minor
            comparisons.append(
                {
                    "invoice_line_id": line.id,
                    "item_code": line.item_code,
                    "description": line.description,
                    "unit": unit,
                    "boq_quantity": str(bq),
                    "po_quantity": str(pq),
                    "accepted_quantity": str(rq),
                    "previously_allocated": str(prior_po),
                    "available_entitlement": str(entitlement),
                    "invoice_quantity": str(q),
                    "excess_quantity": str(excess),
                    "quantity_variance_percent": str(
                        (excess / entitlement * 100).quantize(Decimal("0.01"))
                    )
                    if entitlement
                    else None,
                    "contract_rate": str(pr),
                    "invoice_rate": str(rate),
                    "claimed_amount": money(line.amount_minor),
                    "verified_amount": money(verified_amount),
                    "difference": money(line.amount_minor - verified_amount),
                    "severity": "BLOCK" if excess or rate != pr else "INFO",
                    "evidence": refs,
                }
            )
        except ValueError as exc:
            flag("DOCUMENT_REVIEW_REQUIRED", f"{line.item_code}: {exc}", refs)
            claimed_sum += line.amount_minor
    if not lines:
        flag("DOCUMENT_REVIEW_REQUIRED", "Invoice has no active line items.")
    expected_tax = (
        minor(Decimal(claimed_sum) / 100 * decimal(po.tax_percent) / 100) if po else 0
    )
    expected_retention = (
        minor(Decimal(claimed_sum) / 100 * decimal(po.retention_percent) / 100)
        if po
        else 0
    )
    expected_discount = po.discount_minor if po else 0
    if (
        invoice.subtotal_minor != claimed_sum
        or invoice.tax_minor != expected_tax
        or invoice.retention_minor != expected_retention
        or invoice.discount_minor != expected_discount
        or invoice.total_minor
        != claimed_sum
        + invoice.tax_minor
        - invoice.retention_minor
        - invoice.discount_minor
    ):
        flag(
            "INVOICE_TOTAL_MISMATCH",
            "Invoice totals, taxes, retention, or discount do not agree with line arithmetic and explicit PO terms.",
        )
    verified_tax = (
        minor(Decimal(verified_subtotal) / 100 * decimal(po.tax_percent) / 100)
        if po
        else 0
    )
    verified_retention = (
        minor(Decimal(verified_subtotal) / 100 * decimal(po.retention_percent) / 100)
        if po
        else 0
    )
    verified_total = max(
        0, verified_subtotal + verified_tax - verified_retention - expected_discount
    )
    if invoice.total_minor > verified_total:
        flag(
            "AUTHORIZED_AMOUNT_EXCEEDED",
            "Claimed total exceeds the remaining supported authorized amount.",
        )
    cash = forecast(
        session,
        project,
        settings,
        payment_amount_minor if payment_amount_minor is not None else remaining,
        invoice.id,
        exclude_proposal,
    )
    if not cash["payment_eligible"]:
        flag(
            "INSUFFICIENT_FUNDS",
            "Current cash or the base/delayed-receivables reserve test prevents payment.",
        )
    if cash["currency_mismatch"]:
        flag(
            "CURRENCY_MISMATCH",
            "Scheduled cash movement currency does not match the project account.",
        )
    if not cash["scenarios"][2]["reserve_maintained"]:
        flag(
            "COST_PRESSURE",
            "The cost-pressure scenario breaches the reserve.",
            severity="WARNING",
        )
    blocked = any(f["severity"] == "BLOCK" for f in findings)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.number,
        "analysis_version": invoice.version,
        "status": "BLOCKED" if blocked else "VERIFIED",
        "currency": invoice.currency,
        "claimed_amount": money(invoice.total_minor),
        "verified_amount": money(verified_total),
        "difference": money(invoice.total_minor - verified_total),
        "comparisons": comparisons,
        "findings": findings,
        "cashflow": cash,
        "payment_eligible": not blocked,
        "explanation_source": "deterministic",
        "explanation": f"Invoice {invoice.number} claims BDT {money(invoice.total_minor)}; supported amount is BDT {money(verified_total)}. "
        + (
            "Payment is blocked: "
            + "; ".join(f["code"] for f in findings if f["severity"] == "BLOCK")
            if blocked
            else "Financial checks passed. Explicit approval by a different authorized account is required."
        ),
        "suggested_action": "RESOLVE_FINDINGS_AND_REANALYZE"
        if blocked
        else "PREPARE_PAYMENT_FOR_HUMAN_APPROVAL",
    }


def analyze(session, invoice, settings, actor):
    from .security import require_role, project_access

    require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
    project_access(session, actor, invoice.project_id, write=True)
    own_proposal = session.scalar(
        select(Proposal).where(
            Proposal.invoice_id == invoice.id,
            Proposal.status.in_(["PENDING_APPROVAL", "APPROVED"]),
            Proposal.expires_at > utcnow(),
        )
    )
    report = reconcile(
        session,
        invoice,
        settings,
        exclude_proposal=own_proposal.id if own_proposal else None,
    )
    if invoice.status != "SETTLED":
        invoice.status = report["status"]
    session.add(Verification(invoice_id=invoice.id, report_json=canonical(report)))
    for event_type in ("INVOICE_MATCHED", "RISK_EVALUATED", "CASHFLOW_EVALUATED"):
        audit.append(
            session,
            actor,
            event_type,
            "invoice",
            invoice.id,
            {
                "status": report["status"],
                "claimed": report["claimed_amount"],
                "verified": report["verified_amount"],
                "findings": [f["code"] for f in report["findings"]],
            },
            invoice.project_id,
        )
    return report


def source_snapshot(session, invoice, settings):
    def row(obj, omit=()):
        return (
            {
                c.name: getattr(obj, c.name)
                for c in obj.__table__.columns
                if c.name not in omit
            }
            if obj
            else None
        )

    po = session.get(PurchaseOrder, invoice.po_id) if invoice.po_id else None
    boqs = list(
        session.scalars(
            select(BOQItem)
            .where(BOQItem.project_id == invoice.project_id)
            .order_by(BOQItem.id)
        )
    )
    receipts = list(
        session.scalars(
            select(GoodsReceipt)
            .where(GoodsReceipt.po_id == invoice.po_id)
            .order_by(GoodsReceipt.id)
        )
    )
    doc_ids = {
        invoice.document_id,
        *[b.document_id for b in boqs],
        *[r.document_id for r in receipts],
    }
    if po:
        doc_ids.add(po.document_id)
    return {
        "invoice": row(invoice, ("status",)),
        "lines": [
            row(x)
            for x in session.scalars(
                select(InvoiceLine)
                .where(
                    InvoiceLine.invoice_id == invoice.id, InvoiceLine.active.is_(True)
                )
                .order_by(InvoiceLine.id)
            )
        ],
        "supplier": row(session.get(Supplier, invoice.supplier_id))
        if invoice.supplier_id
        else None,
        "po": row(po),
        "po_lines": [
            row(x)
            for x in session.scalars(
                select(POLine).where(POLine.po_id == invoice.po_id).order_by(POLine.id)
            )
        ],
        "boq": [row(x) for x in boqs],
        "variations": [
            row(x)
            for x in session.scalars(
                select(Variation)
                .where(Variation.boq_item_id.in_([b.id for b in boqs]))
                .order_by(Variation.id)
            )
        ],
        "receipts": [row(x) for x in receipts],
        "receipt_lines": [
            row(x)
            for x in session.scalars(
                select(ReceiptLine)
                .where(ReceiptLine.receipt_id.in_([r.id for r in receipts]))
                .order_by(ReceiptLine.id)
            )
        ],
        "documents": [
            {
                "id": d.id,
                "version": d.version,
                "sha256": d.sha256,
                "reviewed_by": d.reviewed_by,
                "confirmed_by": d.confirmed_by,
            }
            for d in session.scalars(
                select(Document).where(Document.id.in_(doc_ids)).order_by(Document.id)
            )
        ],
        "policy": {
            "version": 1,
            "reserve_minor": session.get(Project, invoice.project_id).reserve_minor,
            "manager_limit": 10000000,
            "admin_limit": minor(settings.admin_ceiling),
            "delay_days": settings.receivable_delay_days,
        },
    }
