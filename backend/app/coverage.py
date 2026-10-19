"""Explicit, source-bound procurement coverage for estimate forecasts."""

from decimal import Decimal

from sqlalchemy import select

from .advanced_math import unit_factor
from .models import BOQItem, POLine, Project, PurchaseOrder
from .money import decimal, digest
from .review_models import CommitmentCoverage
from . import procurement


def source(boq, po, line):
    return digest(
        {
            "boq": [boq.id, boq.version, boq.item_code, boq.description, boq.unit],
            "po": [po.id, po.version, po.project_id, po.approved, po.currency],
            "line": [
                line.id,
                line.item_code,
                line.description,
                line.quantity,
                line.unit,
                line.rate,
            ],
        }
    )


def compatible(boq, po, line, project):
    if (
        not po.approved
        or po.project_id != boq.project_id
        or po.currency != project.currency
    ):
        return False
    # Descriptions are evidence, not a license to infer a superior specification.
    normalize = lambda text: " ".join(text.casefold().split())
    if line.item_code != boq.item_code or normalize(line.description) != normalize(
        boq.description
    ):
        return False
    try:
        unit_factor(line.unit, boq.unit)
    except ValueError:
        return False
    return True


def sync(session, project_id, fields):
    project = session.get(Project, project_id)
    for row in fields.lines:
        if not row.legacy_boq_item_id:
            continue
        boq = session.get(BOQItem, row.legacy_boq_item_id)
        for pol, po in session.execute(
            select(POLine, PurchaseOrder)
            .join(PurchaseOrder)
            .where(
                PurchaseOrder.project_id == project_id,
                POLine.item_code == boq.item_code,
            )
        ):
            existing = session.scalar(
                select(CommitmentCoverage).where(
                    CommitmentCoverage.po_line_id == pol.id
                )
            )
            if compatible(boq, po, pol, project) and not existing:
                session.add(
                    CommitmentCoverage(
                        project_id=project_id,
                        boq_item_id=boq.id,
                        po_line_id=pol.id,
                        source_hash=source(boq, po, pol),
                        quantity=str(procurement.quantity(session,pol)),
                        unit=pol.unit,
                        method="EXACT_SPECIFICATION_UNIT_CURRENCY",
                    )
                )
    session.flush()


def quantity(session, project_id, row):
    if not row.legacy_boq_item_id:
        return Decimal(0), []
    boq = session.get(BOQItem, row.legacy_boq_item_id)
    project = session.get(Project, project_id)
    total, warnings = Decimal(0), []
    for pol, po in session.execute(
        select(POLine, PurchaseOrder)
        .join(PurchaseOrder)
        .where(
            PurchaseOrder.project_id == project_id,
            PurchaseOrder.approved.is_(True),
            POLine.item_code == boq.item_code,
        )
    ):
        link = session.scalar(
            select(CommitmentCoverage).where(
                CommitmentCoverage.po_line_id == pol.id,
                CommitmentCoverage.boq_item_id == boq.id,
            )
        )
        if (
            not link
            or not compatible(boq, po, pol, project)
            or link.source_hash != source(boq, po, pol)
        ):
            warnings.append(
                f"Unresolved commitment: BOQ {boq.item_code}, PO {po.number} line {pol.id}; estimated cost retained."
            )
            continue
        total += procurement.quantity(session,pol) * unit_factor(link.unit, row.unit)
    return total, warnings
