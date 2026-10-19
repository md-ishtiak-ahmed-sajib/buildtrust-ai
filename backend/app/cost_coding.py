"""Reviewed cost-code lineage. Historical journals are never reclassified in place."""

import json
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from . import models as m, control_models as c
from .money import digest, money
from .security import DomainError


def source(session, project_id, kind, identity):
    classes = {
        "BOQ_ITEM": m.BOQItem,
        "PO_LINE": m.POLine,
        "RECEIPT_LINE": m.ReceiptLine,
        "INVOICE_LINE": m.InvoiceLine,
    }
    if kind not in classes:
        raise ValueError("Unsupported cost-code source")
    row = session.get(classes[kind], identity)
    if not row:
        raise ValueError("Cost-code source is unavailable")
    parent = row
    if kind == "PO_LINE":
        parent = session.get(m.PurchaseOrder, row.po_id)
    if kind == "RECEIPT_LINE":
        parent = session.get(m.GoodsReceipt, row.receipt_id)
    if kind == "INVOICE_LINE":
        parent = session.get(m.Invoice, row.invoice_id)
    owner = (
        session.get(m.PurchaseOrder, parent.po_id) if kind == "RECEIPT_LINE" else parent
    )
    if owner.project_id != project_id:
        raise DomainError(
            422, "INVALID_SOURCE", "Cost-code source belongs to another project."
        )
    fields = {
        column.name: getattr(row, column.name) for column in row.__table__.columns
    }
    return row, parent.version, digest(fields)


def link(session, project_id, kind, identity):
    return session.scalar(
        select(c.CostCodeLink).where(
            c.CostCodeLink.project_id == project_id,
            c.CostCodeLink.source_type == kind,
            c.CostCodeLink.source_id == identity,
        )
    )


def ensure(session, project_id, kind, identity, code):
    existing = link(session, project_id, kind, identity)
    if existing and existing.cost_code_id != code:
        raise DomainError(
            409,
            "COST_CODE_CONFLICT",
            "Independently resolve the cost-code mapping before this posting.",
        )
    if not existing:
        session.add(
            c.CostCodeLink(
                project_id=project_id,
                cost_code_id=code,
                source_type=kind,
                source_id=identity,
            )
        )
        session.flush()


def weights(session, payable):
    totals = defaultdict(int)
    if payable.invoice_id:
        for allocation, recognition in session.execute(
            select(c.RecognitionAllocation, c.Recognition)
            .join(
                c.Recognition,
                c.Recognition.id == c.RecognitionAllocation.recognition_id,
            )
            .where(c.RecognitionAllocation.invoice_id == payable.invoice_id)
        ):
            totals[recognition.cost_code_id] += allocation.amount_minor
    else:
        from .commercial_models import CertificateAllocation

        for allocation in session.scalars(
            select(CertificateAllocation).where(
                CertificateAllocation.certificate_id == payable.record_id
            )
        ):
            record = session.get(c.ControlRecord, allocation.acceptance_id)
            payload = json.loads(record.payload_json)
            code = payload.get("cost_code_id")
            if record.kind == "WORK_ACCEPTANCE":
                code = json.loads(record.calculated_json)["cost_code_id"]
            totals[code] += allocation.amount_minor
    return dict(totals)


def spread(amount, amounts):
    """Allocate cash/tax/retention by accepted cost weights; final code gets residue."""
    amounts = {key: value for key, value in amounts.items() if value > 0}
    if not amounts:
        return [(None, amount)] if amount else []
    total, remaining = sum(amounts.values()), amount
    result = []
    items = sorted(amounts.items(), key=lambda row: row[0] or 0)
    for index, (code, weight) in enumerate(items):
        value = (
            remaining
            if index == len(items) - 1
            else min(
                remaining,
                int(
                    (Decimal(amount) * weight / total).quantize(
                        Decimal(1), rounding=ROUND_HALF_UP
                    )
                ),
            )
        )
        remaining -= value
        if value:
            result.append((code, value))
    return result


def position(session, project):
    from . import procurement
    from . import advanced_models as a
    from .money import decimal, minor

    rows = {
        code.id: {
            "id": code.id,
            "code": code.code,
            "name": code.name,
            "budget_minor": None,
            "commitment_minor": 0,
            "recognized_commitment_minor": 0,
            "cost_minor": 0,
            "accrual_minor": 0,
            "payable_minor": 0,
            "paid_minor": 0,
        }
        for code in session.scalars(
            select(c.CostCode).where(c.CostCode.project_id == project.id)
        )
    }
    by_code = {row["code"]: row for row in rows.values()}
    baseline = session.scalar(
        select(a.BudgetBaseline)
        .where(a.BudgetBaseline.project_id == project.id)
        .order_by(a.BudgetBaseline.id.desc())
    )
    approved = session.get(a.Estimate, baseline.estimate_id) if baseline else None
    exceptions = []
    if approved:
        payload, calculated = (
            json.loads(approved.fields_json),
            json.loads(approved.calculated_json),
        )
        amounts = {line["id"]: line.get("cost_amount") for line in calculated["lines"]}
        for line in payload["lines"]:
            target = by_code.get(line.get("cost_code"))
            if target and amounts.get(line["id"]) is not None:
                target["budget_minor"] = (target["budget_minor"] or 0) + minor(
                    amounts[line["id"]]
                )
            else:
                exceptions.append(
                    f"Estimate {approved.id} line {line['code']} has no relational cost-code budget mapping"
                )
    for pol in session.scalars(
        select(m.POLine)
        .join(m.PurchaseOrder)
        .where(
            m.PurchaseOrder.project_id == project.id, m.PurchaseOrder.approved.is_(True)
        )
    ):
        mapped = link(session, project.id, "PO_LINE", pol.id)
        if mapped and mapped.cost_code_id in rows:
            rows[mapped.cost_code_id]["commitment_minor"] += minor(
                procurement.quantity(session,pol) * decimal(pol.rate)
            )
        else:
            exceptions.append(
                f"Approved PO line {pol.id} has no reviewed cost-code mapping"
            )
    for line, journal in session.execute(
        select(c.JournalLine, c.Journal)
        .join(c.Journal)
        .where(c.Journal.project_id == project.id)
    ):
        if line.cost_code_id not in rows:
            if line.account in (
                "PROJECT_COST",
                "ACCRUED_LIABILITY",
                "ACCOUNTS_PAYABLE",
            ):
                exceptions.append(
                    f"Journal {journal.id} {line.account} has no historical cost code"
                )
            continue
        target = rows[line.cost_code_id]
        if line.account == "PROJECT_COST":
            target["cost_minor"] += line.debit_minor - line.credit_minor
        if line.account == "ACCRUED_LIABILITY":
            target["accrual_minor"] += line.credit_minor - line.debit_minor
        if line.account == "ACCOUNTS_PAYABLE":
            target["payable_minor"] += line.credit_minor - line.debit_minor
        if line.account == "CASH" and journal.source_key.startswith("payment:"):
            target["paid_minor"] += line.credit_minor - line.debit_minor
    for recognition, pol in session.execute(
        select(c.Recognition, m.POLine)
        .join(m.ReceiptLine, m.ReceiptLine.id == c.Recognition.receipt_line_id)
        .join(m.GoodsReceipt, m.GoodsReceipt.id == m.ReceiptLine.receipt_id)
        .join(
            m.POLine,
            (m.POLine.po_id == m.GoodsReceipt.po_id)
            & (m.POLine.item_code == m.ReceiptLine.item_code),
        )
        .where(c.Recognition.project_id == project.id)
    ):
        mapped = link(session, project.id, "PO_LINE", pol.id)
        if mapped and mapped.cost_code_id in rows:
            rows[mapped.cost_code_id]["recognized_commitment_minor"] += (
                recognition.amount_minor
            )
            if mapped.cost_code_id != recognition.cost_code_id:
                exceptions.append(
                    f"PO line {pol.id} was recoded after acceptance {recognition.record_id}; historical cost retains its original code"
                )
    return {
        "currency": project.currency,
        "rows": [
            {
                "id": row["id"],
                "code": row["code"],
                "name": row["name"],
                **{
                    key.removesuffix("_minor"): money(value)
                    if value is not None
                    else None
                    for key, value in row.items()
                    if key.endswith("_minor")
                },
                "remaining_commitment": money(
                    max(0, row["commitment_minor"] - row["recognized_commitment_minor"])
                ),
            }
            for row in rows.values()
        ],
        "exceptions": sorted(set(exceptions)),
        "notice": "Cost budgets, before-tax PO commitments, recognized costs and cash are distinct. Cash/tax/retention are allocated by original accepted-cost weights. Missing historical codes are reported, never silently reconstructed.",
    }
