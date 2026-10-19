"""Effective procurement authority from immutable originals plus approved events."""

import json
from decimal import Decimal
from sqlalchemy import select
from . import models as m, commercial_models as cm, control_models as c
from . import audit, cost_coding
from .advanced_math import unit_factor
from .money import decimal, minor, money, published, digest, canonical, normalize
from .security import DomainError

KINDS = {"PROCUREMENT_AUTHORIZATION", "PROCUREMENT_AMENDMENT"}


def quantity(session, line):
    retired = sum(
        (
            decimal(r.retired_quantity)
            for r in session.scalars(
                select(cm.ProcurementAmendment).where(
                    cm.ProcurementAmendment.po_line_id == line.id
                )
            )
        ),
        Decimal(0),
    )
    return decimal(line.quantity) - retired


def authorization(session, boq):
    total, extra = decimal(boq.quantity), 0
    for variation in session.scalars(
        select(m.Variation).where(m.Variation.boq_item_id == boq.id)
    ):
        total += decimal(variation.quantity) * unit_factor(variation.unit, boq.unit)
    for event in session.scalars(
        select(cm.ProcurementAuthorization).where(
            cm.ProcurementAuthorization.boq_item_id == boq.id
        )
    ):
        total += decimal(event.quantity)
        extra += event.extra_value_minor
    return total, minor(total * decimal(boq.rate)) + extra


def commitments(session, project, boq):
    total, amount = Decimal(0), 0
    for line, po in session.execute(
        select(m.POLine, m.PurchaseOrder)
        .join(m.PurchaseOrder)
        .where(
            m.PurchaseOrder.project_id == project.id,
            m.PurchaseOrder.approved.is_(True),
            m.POLine.item_code == boq.item_code,
        )
    ):
        if (
            line.description.strip().casefold() != boq.description.strip().casefold()
            or po.currency != project.currency
        ):
            raise ValueError(
                "Resolve incompatible procurement evidence before changing authorization"
            )
        current = quantity(session, line)
        total += current * unit_factor(line.unit, boq.unit)
        amount += minor(current * decimal(line.rate))
    return total, amount


def protected_quantity(session, po, line):
    received = sum(
        (
            decimal(r.quantity) * unit_factor(r.unit, line.unit)
            for r in session.scalars(
                select(m.ReceiptLine)
                .join(m.GoodsReceipt)
                .where(
                    m.GoodsReceipt.po_id == po.id,
                    m.ReceiptLine.item_code == line.item_code,
                )
            )
        ),
        Decimal(0),
    )
    from . import finance

    allocated = sum(
        (
            decimal(allocation.canonical_quantity) / normalize("1", line.unit)[0]
            for allocation, item, invoice, _ in finance.used_allocations(
                session, po.project_id
            )
            if invoice.po_id == po.id and item.item_code == line.item_code
        ),
        Decimal(0),
    )
    return max(received, allocated)


def build(session, project, values):
    from .accounting import scoped

    boq = scoped(session, m.BOQItem, values.boq_item_id, project.id)
    authorized, value = authorization(session, boq)
    committed, committed_value = commitments(session, project, boq)
    if values.kind == "PROCUREMENT_AUTHORIZATION":
        if boq.version != values.expected_boq_version:
            raise DomainError(
                409,
                "VERSION_CONFLICT",
                "Procurement scope changed; reload before review.",
            )
        additional, extra = (
            decimal(values.additional_quantity),
            minor(values.extra_value),
        )
        if not additional and not extra:
            raise ValueError(
                "An authorization must change quantity or explicitly approved value"
            )
        revised, revised_value = (
            authorized + additional,
            value + minor(additional * decimal(boq.rate)) + extra,
        )
        if (
            revised < committed
            or revised_value < committed_value
            or revised < 0
            or revised_value < 0
        ):
            raise ValueError(
                "Authorization cannot fall below existing approved commitments"
            )
        return {
            "quantity": published(revised),
            "authorized_value": money(revised_value),
            "boq_version": boq.version,
            "current_quantity": published(authorized),
            "current_value": money(value),
            "policy": "procurement-v1",
            "notice": "Procurement authority only; estimate budgets remain unchanged.",
        }
    line = session.get(m.POLine, values.po_line_id)
    po = session.get(m.PurchaseOrder, line.po_id) if line else None
    if not po or po.project_id != project.id or not po.approved:
        raise ValueError("An approved project PO line is required")
    if po.version != values.expected_po_version:
        raise DomainError(
            409, "VERSION_CONFLICT", "Purchase order changed; reload before review."
        )
    if (
        line.item_code != boq.item_code
        or line.description.strip().casefold() != boq.description.strip().casefold()
        or po.currency != project.currency
    ):
        raise ValueError(
            "Amendment source must match the procurement BOQ specification and currency"
        )
    retire, replacement, rate = (
        decimal(values.retire_quantity),
        decimal(values.replacement_quantity),
        decimal(values.replacement_rate),
    )
    remaining, protected = (
        quantity(session, line),
        protected_quantity(session, po, line),
    )
    if retire <= 0 or retire > remaining - protected:
        raise ValueError(
            "Only unreceived, unallocated quantity may be retired; protected historical rates remain unchanged"
        )
    if replacement < 0 or rate < 0 or (replacement and not rate):
        raise ValueError(
            "Replacement quantity/rate must be nonnegative and a priced replacement must have a positive rate"
        )
    for key in ("tax_percent", "retention_percent"):
        if not 0 <= decimal(getattr(values, key)) <= 100:
            raise ValueError("Tax/retention percentages must be between 0 and 100")
    if minor(values.discount) < 0 or minor(values.discount) > minor(replacement * rate):
        raise ValueError(
            "Successor discount must be explicitly supported and within its base value"
        )
    revised = committed + (replacement - retire) * unit_factor(line.unit, boq.unit)
    revised_value = (
        committed_value - minor(retire * decimal(line.rate)) + minor(replacement * rate)
    )
    if revised > authorized or revised_value > value:
        raise ValueError(
            "Amendment exceeds procurement quantity/value authority; obtain separate authorization first"
        )
    if replacement and (
        not values.successor_po_number
        or session.scalar(
            select(m.PurchaseOrder.id).where(
                m.PurchaseOrder.project_id == project.id,
                m.PurchaseOrder.number == values.successor_po_number,
            )
        )
    ):
        raise ValueError("Supply an unused successor purchase-order number")
    supplier = session.get(m.Supplier, po.supplier_id)
    if not supplier.approved:
        raise ValueError("The supplier master must remain approved")
    return {
        "boq_version": boq.version,
        "po_version": po.version,
        "supplier_version": supplier.version,
        "beneficiary": supplier.beneficiary_fingerprint,
        "retired_quantity": published(retire),
        "protected_quantity": published(protected),
        "remaining_original_quantity": published(remaining - retire),
        "replacement_quantity": published(replacement),
        "replacement_rate": published(rate),
        "unit": line.unit,
        "revised_commitment": money(revised_value),
        "source_hash": digest([line.id, line.quantity, line.rate, line.description]),
        "policy": "procurement-v1",
    }


def apply(session, actor, project, record, values, result):
    boq = session.get(m.BOQItem, values.boq_item_id)
    if values.kind == "PROCUREMENT_AUTHORIZATION":
        session.add(
            cm.ProcurementAuthorization(
                control_id=record.id,
                boq_item_id=boq.id,
                quantity=values.additional_quantity,
                extra_value_minor=minor(values.extra_value),
            )
        )
        boq.version += 1
        affected = set(
            session.scalars(
                select(m.PurchaseOrder.id)
                .join(m.POLine)
                .where(
                    m.PurchaseOrder.project_id == project.id,
                    m.POLine.item_code == boq.item_code,
                )
            )
        )
    else:
        line = session.get(m.POLine, values.po_line_id)
        po = session.get(m.PurchaseOrder, line.po_id)
        successor = None
        if decimal(values.replacement_quantity):
            body = {
                "amendment_control": record.id,
                "source_po": po.id,
                "item_code": line.item_code,
                "quantity": values.replacement_quantity,
                "rate": values.replacement_rate,
                "unit": line.unit,
            }
            document = m.Document(
                project_id=project.id,
                document_type="PO",
                original_filename=f"{values.successor_po_number}.json",
                storage_name="",
                sha256=digest(body),
                extraction_status="CONFIRMED",
                extracted_json=canonical(body),
                text=canonical(body),
                confirmed_by=actor.id,
                reviewed_by=actor.id,
            )
            session.add(document)
            session.flush()
            successor = m.PurchaseOrder(
                project_id=project.id,
                document_id=document.id,
                supplier_id=po.supplier_id,
                number=values.successor_po_number,
                currency=po.currency,
                tax_percent=values.tax_percent,
                retention_percent=values.retention_percent,
                discount_minor=minor(values.discount),
                approved=True,
            )
            session.add(successor)
            session.flush()
            new_line = m.POLine(
                po_id=successor.id,
                item_code=line.item_code,
                description=line.description,
                quantity=values.replacement_quantity,
                unit=line.unit,
                rate=values.replacement_rate,
            )
            session.add(new_line)
            session.flush()
            mapped = cost_coding.link(session, project.id, "PO_LINE", line.id)
            if mapped:
                cost_coding.ensure(
                    session, project.id, "PO_LINE", new_line.id, mapped.cost_code_id
                )
            session.add(
                cm.CommercialPublication(
                    project_id=project.id,
                    control_id=record.id,
                    source_type="PO",
                    source_id=successor.id,
                )
            )
        session.add(
            cm.ProcurementAmendment(
                control_id=record.id,
                po_line_id=line.id,
                retired_quantity=values.retire_quantity,
                successor_po_id=successor.id if successor else None,
            )
        )
        po.version += 1
        affected = {po.id}
    session.flush()
    from . import coverage
    from .review_models import CommitmentCoverage

    for pol, po in session.execute(
        select(m.POLine, m.PurchaseOrder)
        .join(m.PurchaseOrder)
        .where(
            m.PurchaseOrder.project_id == project.id,
            m.POLine.item_code == boq.item_code,
        )
    ):
        if not coverage.compatible(boq, po, pol, project):
            continue
        mapped = session.scalar(
            select(CommitmentCoverage).where(CommitmentCoverage.po_line_id == pol.id)
        )
        if mapped is None:
            mapped = CommitmentCoverage(
                project_id=project.id,
                boq_item_id=boq.id,
                po_line_id=pol.id,
                source_hash=coverage.source(boq, po, pol),
                quantity=str(quantity(session, pol)),
                unit=pol.unit,
                method="APPROVED_PROCUREMENT_CONTROL",
            )
            session.add(mapped)
        else:
            mapped.source_hash = coverage.source(boq, po, pol)
            mapped.quantity = str(quantity(session, pol))
    from . import payments

    for proposal in session.scalars(
        select(m.Proposal)
        .join(m.Invoice, m.Proposal.invoice_id == m.Invoice.id)
        .where(
            m.Invoice.po_id.in_(affected),
            m.Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
        )
    ):
        proposal.status = "BLOCKED"
        proposal.version += 1
        payments.release(session, proposal)
    audit.append(
        session,
        actor,
        "PROCUREMENT_AUTHORITY_CHANGED",
        "control",
        record.id,
        {"kind": values.kind, "snapshot_hash": record.snapshot_hash},
        project.id,
    )
