"""Acceptance-based costs and certificate-based revenue. All posting is deterministic."""

import json
from decimal import Decimal

from sqlalchemy import func, select

from . import control_models as c
from . import finance, cost_coding
from . import models as m
from .money import canonical, decimal, digest, minor, money, normalize
from .security import DomainError


def scoped(session, cls, identity, project_id):
    record = session.get(cls, identity)
    if not record or record.project_id != project_id:
        raise DomainError(
            422, "INVALID_SOURCE", "Supporting record is unavailable in this project."
        )
    return record


def code(session, identity, project_id):
    row = scoped(session, c.CostCode, identity, project_id)
    if not row.active:
        raise ValueError("Cost code is inactive")
    return row


def positive(value):
    amount = minor(value)
    if amount <= 0:
        raise ValueError("Amount must be positive at monetary precision")
    return amount


def policy(session, identity, project, business_date):
    record = scoped(session, c.ControlRecord, identity, project.id)
    values = json.loads(record.payload_json)
    if record.kind != "ACCOUNTING_POLICY" or record.status != "APPROVED":
        raise ValueError("An approved accounting policy is required")
    if values["currency"] != project.currency or values["effective_date"] > str(
        business_date
    ):
        raise ValueError("Policy currency/date is incompatible with this recognition")
    return record, values


def build(session, project, values):
    """Calculate from current sources; the same evidence is rechecked at approval."""
    kind = values.kind
    if kind in ("CUSTOMER_RECEIPT", "CREDIT_NOTE"):
        duplicate = session.scalar(
            select(c.ControlRecord.id).where(
                c.ControlRecord.project_id == project.id,
                c.ControlRecord.kind == kind,
                c.ControlRecord.status == "APPROVED",
                func.json_extract(c.ControlRecord.payload_json, "$.reference")
                == values.reference,
            )
        )
        if duplicate:
            raise DomainError(
                409,
                "DUPLICATE_ACCOUNTING_REFERENCE",
                "This external accounting reference was already posted.",
            )
    actual_date = getattr(
        values, "recognition_date", getattr(values, "received_date", None)
    )
    if actual_date and actual_date > finance.business_date():
        raise ValueError(
            "Actual recognition and receipt dates cannot be in the future; use forecasts for planned events"
        )
    result = {"currency": project.currency, "policy": "acceptance-accounting-v1"}
    if kind == "ACCOUNTING_POLICY":
        if values.currency != project.currency:
            raise ValueError("Policy currency must match the project")
        if (
            not 0 <= decimal(values.tax_percent) <= 100
            or not 0 <= decimal(values.retention_percent) <= 100
        ):
            raise ValueError("Tax and retention must be between zero and 100 percent")
        if values.tax_treatment == "ZERO" and decimal(values.tax_percent):
            raise ValueError("Zero-tax policy requires zero tax")
        return result
    if kind == "ACCEPTANCE":
        selected_policy, terms = policy(
            session, values.policy_id, project, values.recognition_date
        )
        cost_code = code(session, values.cost_code_id, project.id)
        line = session.get(m.ReceiptLine, values.receipt_line_id)
        if not line:
            raise ValueError("Accepted receipt line is unavailable")
        receipt = session.get(m.GoodsReceipt, line.receipt_id)
        po = scoped(session, m.PurchaseOrder, receipt.po_id, project.id)
        pol = session.scalar(
            select(m.POLine).where(
                m.POLine.po_id == po.id, m.POLine.item_code == line.item_code
            )
        )
        if (
            not pol
            or not po.approved
            or not receipt.approved_by
            or po.currency != project.currency
        ):
            raise ValueError(
                "Confirmed receipt and compatible approved PO are required"
            )
        received, unit, _ = normalize(line.quantity, line.unit)
        _, po_unit, rate = normalize(pol.quantity, pol.unit, pol.rate)
        if unit != po_unit:
            raise ValueError("Receipt unit differs from the contractual item")
        recognized = session.scalar(
            select(c.Recognition).where(c.Recognition.receipt_line_id == line.id)
        )
        if recognized:
            raise DomainError(
                409, "ALREADY_RECOGNIZED", "Receipt cost was already recognized."
            )
        settled = session.scalar(
            select(m.Payment.id)
            .join(m.Invoice)
            .where(m.Invoice.po_id == po.id)
            .limit(1)
        )
        if settled:
            raise ValueError(
                "Historical settled procurement needs reviewed opening balances; recognition cannot be reconstructed automatically"
            )
        amount = minor(received * rate)
        result.update(
            amount=money(amount),
            amount_minor=amount,
            quantity=str(received),
            unit=unit,
            source={
                "receipt_line": line.id,
                "receipt_version": receipt.version,
                "quantity": line.quantity,
                "unit": line.unit,
                "po_id": po.id,
                "po_version": po.version,
                "po_rate": pol.rate,
                "po_unit": pol.unit,
                "policy_hash": selected_policy.snapshot_hash,
                "cost_code_version": cost_code.version,
            },
        )
    elif kind == "INVOICE_RECONCILIATION":
        from .commercial_models import CertificateAllocation

        selected_policy, terms = policy(
            session, values.policy_id, project, values.recognition_date
        )
        invoice = scoped(session, m.Invoice, values.invoice_id, project.id)
        if invoice.currency != project.currency:
            raise ValueError(
                "Cross-currency accounting requires a separate reporting conversion"
            )
        if session.scalar(
            select(c.Payable.id).where(c.Payable.invoice_id == invoice.id)
        ):
            raise DomainError(
                409, "ALREADY_RECONCILED", "Invoice already has a payable balance."
            )
        if session.scalar(
            select(m.Payment.id).where(m.Payment.invoice_id == invoice.id)
        ):
            raise ValueError("Paid historical invoices need reviewed opening balances")
        if len(set(values.acceptance_ids)) != len(values.acceptance_ids):
            raise ValueError("Duplicate acceptance references")
        acceptances, total = [], 0
        invoice_lines = list(
            session.scalars(
                select(m.InvoiceLine).where(
                    m.InvoiceLine.invoice_id == invoice.id,
                    m.InvoiceLine.active.is_(True),
                )
            )
        )
        remaining_by_line = {
            line.id: normalize(line.quantity, line.unit)[0] for line in invoice_lines
        }
        for identity in values.acceptance_ids:
            recognition = scoped(session, c.Recognition, identity, project.id)
            if session.scalar(
                select(CertificateAllocation.id).where(
                    CertificateAllocation.acceptance_id == recognition.record_id
                )
            ):
                raise ValueError(
                    "Acceptance already certified to a payable; it cannot also fund an invoice"
                )
            allocations = list(
                session.scalars(
                    select(c.RecognitionAllocation).where(
                        c.RecognitionAllocation.recognition_id == recognition.id
                    )
                )
            )
            used_quantity = sum(
                (decimal(row.quantity) for row in allocations), Decimal(0)
            )
            used_amount = sum(row.amount_minor for row in allocations)
            if used_quantity >= decimal(recognition.quantity):
                raise ValueError("Acceptance quantity is already fully reconciled")
            receipt_line = session.get(m.ReceiptLine, recognition.receipt_line_id)
            receipt = session.get(m.GoodsReceipt, receipt_line.receipt_id)
            if receipt.po_id != invoice.po_id:
                raise ValueError("Acceptance belongs to a different PO")
            item = session.scalar(
                select(m.InvoiceLine).where(
                    m.InvoiceLine.invoice_id == invoice.id,
                    m.InvoiceLine.item_code == receipt_line.item_code,
                    m.InvoiceLine.active.is_(True),
                )
            )
            if not item:
                raise ValueError("Acceptance item is absent from the invoice")
            claimed, unit, _ = normalize(item.quantity, item.unit)
            if unit != recognition.unit:
                raise ValueError(
                    "Acceptance and invoice quantities use incompatible units"
                )
            quantity = min(
                remaining_by_line[item.id],
                decimal(recognition.quantity) - used_quantity,
            )
            if quantity <= 0:
                raise ValueError(
                    "Selected acceptance is unnecessary for this invoice line"
                )
            allocated_amount = (
                recognition.amount_minor - used_amount
                if used_quantity + quantity == decimal(recognition.quantity)
                else minor(
                    Decimal(recognition.amount_minor)
                    / 100
                    * quantity
                    / decimal(recognition.quantity)
                )
            )
            remaining_by_line[item.id] -= quantity
            total += allocated_amount
            acceptances.append(
                {
                    "id": recognition.id,
                    "source_hash": recognition.source_hash,
                    "amount_minor": allocated_amount,
                    "quantity": str(quantity),
                    "invoice_line_id": item.id,
                    "previous_quantity": str(used_quantity),
                    "previous_amount_minor": used_amount,
                }
            )
        if any(quantity > 0 for quantity in remaining_by_line.values()):
            raise ValueError("Selected acceptances do not cover every invoice quantity")
        if total != invoice.subtotal_minor - invoice.discount_minor:
            raise ValueError(
                "Accepted cost and invoice subtotal differ; an independently approved adjustment is required"
            )
        if terms["tax_treatment"] == "ZERO" and invoice.tax_minor:
            raise ValueError("Invoice tax conflicts with the explicit zero-tax policy")
        result.update(
            amount=money(invoice.total_minor),
            amount_minor=invoice.total_minor,
            accepted_cost=money(total),
            accepted_minor=total,
            tax_minor=invoice.tax_minor,
            retention_minor=invoice.retention_minor,
            tax_treatment=terms["tax_treatment"],
            source={
                "invoice_version": invoice.version,
                "invoice_total": invoice.total_minor,
                "policy_hash": selected_policy.snapshot_hash,
                "acceptances": acceptances,
            },
        )
    elif kind == "CUSTOMER_CERTIFICATE":
        selected_policy, terms = policy(
            session, values.policy_id, project, values.recognition_date
        )
        revenue, tax, retention = (
            positive(values.revenue),
            minor(values.output_tax),
            minor(values.retention),
        )
        if tax < 0 or retention < 0 or retention > revenue:
            raise ValueError("Invalid certificate tax or retention")
        if terms["tax_treatment"] == "ZERO" and tax:
            raise ValueError("Output tax conflicts with the zero-tax policy")
        duplicate = session.scalar(
            select(c.ControlRecord.id).where(
                c.ControlRecord.project_id == project.id,
                c.ControlRecord.kind == kind,
                c.ControlRecord.status == "APPROVED",
                func.json_extract(c.ControlRecord.payload_json, "$.certificate_number")
                == values.certificate_number,
            )
        )
        if duplicate:
            raise DomainError(
                409,
                "DUPLICATE_CERTIFICATE",
                "Certificate number was already recognized.",
            )
        result.update(
            revenue_minor=revenue,
            tax_minor=tax,
            retention_minor=retention,
            amount_minor=revenue + tax - retention,
            amount=money(revenue + tax - retention),
            source={"policy_hash": selected_policy.snapshot_hash},
        )
    elif kind == "CUSTOMER_RECEIPT":
        receivable = scoped(session, c.Receivable, values.receivable_id, project.id)
        if receivable.version != values.expected_receivable_version:
            raise DomainError(409, "VERSION_CONFLICT", "Receivable changed.")
        amount = positive(values.amount)
        if amount > receivable.amount_minor - receivable.received_minor - receivable.credit_minor:
            raise ValueError("Receipt exceeds the outstanding receivable")
        if receivable.currency != project.currency:
            raise ValueError("Receipt currency differs from project currency")
        result.update(
            amount_minor=amount,
            amount=money(amount),
            source={"receivable_version": receivable.version},
        )
    elif kind in ("CREDIT_NOTE", "RETENTION_RELEASE"):
        payable = scoped(session, c.Payable, values.payable_id, project.id)
        if payable.version != values.expected_payable_version:
            raise DomainError(409, "VERSION_CONFLICT", "Payable changed.")
        amount = positive(values.amount)
        if (
            kind == "RETENTION_RELEASE"
            and amount > payable.retention_minor - payable.retention_released_minor
        ):
            raise ValueError("Release exceeds held retention")
        if kind == "CREDIT_NOTE":
            code(session, values.cost_code_id, project.id)
            accepted_codes = cost_coding.weights(session, payable)
            if accepted_codes and values.cost_code_id not in accepted_codes:
                raise ValueError(
                    "Credit cost code must belong to this payable's accepted cost sources"
                )
            source = session.get(c.ControlRecord, payable.record_id)
            source_payload, source_result = json.loads(source.payload_json), json.loads(source.calculated_json)
            source_tax = source_result.get("tax_minor", 0)
            if values.tax_amount is None and source_tax:
                raise ValueError("Tax-bearing credits need an explicit tax allocation and its evidence")
            tax = minor(values.tax_amount or "0")
            retention = minor(values.retention_credit)
            if (tax < 0 or tax > amount or retention < 0 or retention > amount
                    or retention > payable.retention_minor - payable.retention_released_minor):
                raise ValueError("Tax and retention credit allocations exceed their supported balances")
            if (source_tax or retention) and len(values.allocation_evidence.strip()) < 10:
                raise ValueError("Tax or retention allocation requires independently reviewable source evidence")
            if str(values.recognition_date) < source_payload["recognition_date"]:
                raise ValueError("A credit cannot precede the source payable recognition")
            previous_base, previous_tax = 0, 0
            for record in session.scalars(select(c.ControlRecord).where(
                    c.ControlRecord.project_id == project.id, c.ControlRecord.kind == "CREDIT_NOTE",
                    c.ControlRecord.status == "APPROVED")):
                payload, calculated = json.loads(record.payload_json), json.loads(record.calculated_json)
                if payload["payable_id"] != payable.id:
                    continue
                previous_tax += calculated.get("tax_minor", 0)
                if payload["cost_code_id"] == values.cost_code_id:
                    previous_base += calculated.get("base_minor", calculated["amount_minor"])
            base = amount - tax
            if not payable.invoice_id:
                from .corrections import events
                for _, payload, calculated in events(session,project.id,'CERTIFICATE_CORRECTION'):
                    if payload['certificate_id']==payable.record_id:
                        previous_tax+=calculated['tax_minor']
                        previous_base+=sum(v['amount_minor'] for v in calculated['base_by_code'] if v['cost_code_id']==values.cost_code_id)
            if tax + previous_tax > source_tax or base + previous_base > accepted_codes.get(values.cost_code_id, 0):
                raise ValueError("Cumulative credits exceed the supported base cost or tax")
            if payable.invoice_id:
                treatment = source_result["tax_treatment"]
            else:
                contract = json.loads(session.get(c.ControlRecord, source_payload["contract_id"]).payload_json)
                treatment = json.loads(session.get(c.ControlRecord, contract["policy_id"]).payload_json)["tax_treatment"]
            result.update(base_minor=base, tax_minor=tax, retention_credit_minor=retention,
                          tax_account="RECOVERABLE_TAX" if treatment == "RECOVERABLE" else "PROJECT_COST",
                          source_posting_hash=source.snapshot_hash)
        result.update(
            amount_minor=amount,
            amount=money(amount),
            source={"payable_version": payable.version},
        )
    elif kind == "OPENING_BALANCE":
        entries = []
        for entry in values.entries:
            debit, credit = minor(entry.debit), minor(entry.credit)
            if debit < 0 or credit < 0 or (debit and credit):
                raise ValueError("Each journal line has one nonnegative side")
            if entry.cost_code_id:
                code(session, entry.cost_code_id, project.id)
            entries.append((entry.account, debit, credit, entry.cost_code_id))
        if sum(r[1] for r in entries) != sum(r[2] for r in entries) or not sum(
            r[1] for r in entries
        ):
            raise ValueError("Opening journal must balance with positive totals")
        result.update(
            entries=entries,
            notice="Reviewed opening balances do not invent underlying historical recognition dates or change recorded sandbox cash.",
        )
    else:
        raise ValueError("Unsupported accounting control")
    return result


def post(session, project, key, entries, evidence, business_date, record_id=None):
    if sum(r[1] for r in entries) != sum(r[2] for r in entries):
        raise ValueError("Accounting journal is not balanced")
    existing = session.scalar(
        select(c.Journal).where(
            c.Journal.project_id == project.id, c.Journal.source_key == key
        )
    )
    if existing:
        raise DomainError(
            409, "DUPLICATE_POSTING", "This source already has a journal."
        )
    journal = c.Journal(
        project_id=project.id,
        source_key=key,
        record_id=record_id,
        business_date=str(business_date),
        currency=project.currency,
        evidence_json=canonical(evidence),
        snapshot_hash=digest(evidence),
    )
    session.add(journal)
    session.flush()
    for account, debit, credit, cost_code in entries:
        if debit < 0 or credit < 0 or (debit and credit):
            raise ValueError("Invalid journal side")
        if debit or credit:
            session.add(
                c.JournalLine(
                    journal_id=journal.id,
                    account=account,
                    debit_minor=debit,
                    credit_minor=credit,
                    cost_code_id=cost_code,
                )
            )
    session.flush()
    return journal


def apply(session, actor, project, record, values, result):
    kind = values.kind
    if kind == "ACCOUNTING_POLICY":
        return
    amount = result.get("amount_minor", 0)
    entries = []
    if kind == "ACCEPTANCE":
        entries = [
            ("PROJECT_COST", amount, 0, values.cost_code_id),
            ("ACCRUED_LIABILITY", 0, amount, values.cost_code_id),
        ]
        session.add(
            c.Recognition(
                project_id=project.id,
                record_id=record.id,
                receipt_line_id=values.receipt_line_id,
                cost_code_id=values.cost_code_id,
                amount_minor=amount,
                quantity=result["quantity"],
                unit=result["unit"],
                source_hash=digest(result["source"]),
            )
        )
        receipt_line = session.get(m.ReceiptLine, values.receipt_line_id)
        receipt = session.get(m.GoodsReceipt, receipt_line.receipt_id)
        pol = session.scalar(
            select(m.POLine).where(
                m.POLine.po_id == receipt.po_id,
                m.POLine.item_code == receipt_line.item_code,
            )
        )
        cost_coding.ensure(session, project.id, "PO_LINE", pol.id, values.cost_code_id)
        cost_coding.ensure(
            session, project.id, "RECEIPT_LINE", receipt_line.id, values.cost_code_id
        )
        boq = session.scalar(
            select(m.BOQItem).where(
                m.BOQItem.project_id == project.id, m.BOQItem.item_code == pol.item_code
            )
        )
        if (
            boq
            and boq.description.strip().casefold() == pol.description.strip().casefold()
        ):
            cost_coding.ensure(
                session, project.id, "BOQ_ITEM", boq.id, values.cost_code_id
            )
    elif kind == "INVOICE_RECONCILIATION":
        invoice = session.get(m.Invoice, values.invoice_id)
        weights = {}
        for allocation in result["source"]["acceptances"]:
            cost_id = session.get(c.Recognition, allocation["id"]).cost_code_id
            weights[cost_id] = weights.get(cost_id, 0) + allocation["amount_minor"]
            cost_coding.ensure(
                session,
                project.id,
                "INVOICE_LINE",
                allocation["invoice_line_id"],
                cost_id,
            )
        entries = [
            ("ACCRUED_LIABILITY", value, 0, cost_id)
            for cost_id, value in weights.items()
        ]
        entries += [
            ("ACCOUNTS_PAYABLE", 0, value, cost_id)
            for cost_id, value in cost_coding.spread(amount, weights)
        ]
        entries += [
            ("RETENTION_PAYABLE", 0, value, cost_id)
            for cost_id, value in cost_coding.spread(result["retention_minor"], weights)
        ]
        if result["tax_minor"]:
            entries += [
                (
                    "RECOVERABLE_TAX"
                    if result["tax_treatment"] == "RECOVERABLE"
                    else "PROJECT_COST",
                    value,
                    0,
                    cost_id,
                )
                for cost_id, value in cost_coding.spread(
                    result["tax_minor"],
                    {} if result["tax_treatment"] == "RECOVERABLE" else weights,
                )
            ]
        from .payments import release

        for proposal in session.scalars(
            select(m.Proposal).where(
                m.Proposal.invoice_id == invoice.id,
                m.Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
            )
        ):
            proposal.status = "BLOCKED"
            release(session, proposal)
        used = finance.used_allocations(session, project.id)
        for allocation in result["source"]["acceptances"]:
            recognized = session.get(c.Recognition, allocation["id"])
            receipt_line = session.get(m.ReceiptLine, recognized.receipt_line_id)
            line = session.get(m.InvoiceLine, allocation["invoice_line_id"])
            occupied = sum(
                (
                    decimal(a.canonical_quantity)
                    for a, _, inv, _ in used
                    if a.receipt_line_id == receipt_line.id and inv.id != invoice.id
                ),
                Decimal(0),
            )
            if (
                occupied + decimal(allocation["quantity"])
                > normalize(receipt_line.quantity, receipt_line.unit)[0]
            ):
                raise DomainError(
                    409,
                    "RECEIPT_REUSE",
                    "Accepted receipt is already allocated to another invoice.",
                )
            session.add(
                c.InvoiceEntitlement(
                    invoice_id=invoice.id,
                    receipt_line_id=receipt_line.id,
                    invoice_line_id=line.id,
                    canonical_quantity=allocation["quantity"],
                )
            )
            session.add(
                c.RecognitionAllocation(
                    recognition_id=recognized.id,
                    invoice_id=invoice.id,
                    invoice_line_id=line.id,
                    quantity=allocation["quantity"],
                    amount_minor=allocation["amount_minor"],
                )
            )
            if decimal(allocation["previous_quantity"]) == 0 and decimal(
                allocation["quantity"]
            ) == decimal(recognized.quantity):
                recognized.invoice_id = (
                    invoice.id
                )  # Preserve the legacy whole-invoice reference.
        session.add(
            c.Payable(
                project_id=project.id,
                supplier_id=invoice.supplier_id,
                invoice_id=invoice.id,
                record_id=record.id,
                amount_minor=amount,
                retention_minor=result["retention_minor"],
                currency=project.currency,
                due_date=str(values.due_date) if values.due_date else None,
            )
        )
    elif kind == "CUSTOMER_CERTIFICATE":
        entries = [
            ("ACCOUNTS_RECEIVABLE", amount, 0, None),
            ("RETENTION_RECEIVABLE", result["retention_minor"], 0, None),
            ("REVENUE", 0, result["revenue_minor"], None),
            ("OUTPUT_TAX", 0, result["tax_minor"], None),
        ]
        session.add(
            c.Receivable(
                project_id=project.id,
                certificate_id=record.id,
                amount_minor=amount,
                retention_minor=result["retention_minor"],
                currency=project.currency,
                due_date=str(values.due_date) if values.due_date else None,
            )
        )
    elif kind == "CUSTOMER_RECEIPT":
        receivable = session.get(c.Receivable, values.receivable_id)
        receivable.received_minor += amount
        receivable.version += 1
        project.balance_minor += amount
        project.version += 1
        entries = [("CASH", amount, 0, None), ("ACCOUNTS_RECEIVABLE", 0, amount, None)]
    elif kind == "CREDIT_NOTE":
        payable = session.get(c.Payable, values.payable_id)
        unpaid = payable.amount_minor - payable.paid_minor - payable.credit_minor
        retention = result["retention_credit_minor"]
        applied = min(unpaid, amount - retention)
        excess = amount - applied - retention
        payable.credit_minor += applied
        payable.supplier_credit_minor += excess
        payable.retention_minor -= retention
        payable.version += 1
        entries = [
            ("ACCOUNTS_PAYABLE", applied, 0, values.cost_code_id),
            ("SUPPLIER_CREDIT", excess, 0, None),
            ("RETENTION_PAYABLE", retention, 0, values.cost_code_id),
            ("PROJECT_COST", 0, result["base_minor"], values.cost_code_id),
            (result["tax_account"], 0, result["tax_minor"], values.cost_code_id if result["tax_account"] == "PROJECT_COST" else None),
        ]
    elif kind == "RETENTION_RELEASE":
        payable = session.get(c.Payable, values.payable_id)
        payable.amount_minor += amount
        payable.retention_released_minor += amount
        payable.version += 1
        entries = [
            (
                account,
                value if account == "RETENTION_PAYABLE" else 0,
                value if account == "ACCOUNTS_PAYABLE" else 0,
                code_id,
            )
            for code_id, value in cost_coding.spread(
                amount, cost_coding.weights(session, payable)
            )
            for account in ("RETENTION_PAYABLE", "ACCOUNTS_PAYABLE")
        ]
    elif kind == "OPENING_BALANCE":
        entries = result["entries"]
    post(
        session,
        project,
        f"control:{record.id}",
        entries,
        {"snapshot_hash": record.snapshot_hash, "kind": kind},
        getattr(
            values,
            "recognition_date",
            getattr(values, "received_date", finance.business_date()),
        ),
        record.id,
    )
    session.flush()
    from . import obligations

    if kind == "CUSTOMER_CERTIFICATE":
        ar = session.scalar(
            select(c.Receivable).where(c.Receivable.certificate_id == record.id)
        )
        obligations.sync(
            session,
            project,
            "RECEIVABLE",
            ar.id,
            "INFLOW",
            "RECEIVABLE",
            ar.amount_minor,
            ar.due_date,
        )
    elif kind == "CUSTOMER_RECEIPT":
        ar = session.get(c.Receivable, values.receivable_id)
        obligations.sync(
            session,
            project,
            "RECEIVABLE",
            ar.id,
            "INFLOW",
            "RECEIVABLE",
            ar.amount_minor - ar.received_minor - ar.credit_minor,
            ar.due_date,
        )
    if kind in ("INVOICE_RECONCILIATION", "RETENTION_RELEASE", "CREDIT_NOTE"):
        payable = (
            session.scalar(
                select(c.Payable).where(c.Payable.invoice_id == values.invoice_id)
            )
            if kind == "INVOICE_RECONCILIATION"
            else session.get(c.Payable, values.payable_id)
        )
        if kind in ("CREDIT_NOTE", "RETENTION_RELEASE"):
            from .payments import release

            for proposal in session.scalars(
                select(m.Proposal).where(
                    m.Proposal.project_id == project.id,
                    (m.Proposal.invoice_id == payable.invoice_id)
                    if payable.invoice_id
                    else (m.Proposal.payable_id == payable.id),
                    m.Proposal.status.in_(("PENDING_APPROVAL", "APPROVED")),
                )
            ):
                proposal.status = "BLOCKED"
                release(session, proposal)
        remaining = payable.amount_minor - payable.paid_minor - payable.credit_minor
        schedules = (
            list(
                session.scalars(
                    select(m.CashMovement).where(
                        m.CashMovement.invoice_id == payable.invoice_id
                    )
                )
            )
            if payable.invoice_id
            else []
        )
        if len(schedules) > 1:
            raise ValueError(
                "Resolve duplicate invoice schedules before publishing accounting"
            )
        obligations.sync(
            session,
            project,
            "PAYABLE",
            payable.id,
            "OUTFLOW",
            "PROCUREMENT",
            remaining,
            payable.due_date,
            invoice_id=payable.invoice_id,
        )


def payment_posted(session, project, invoice, payment):
    payable = (
        session.get(c.Payable, payment.payable_id)
        if payment.payable_id
        else session.scalar(select(c.Payable).where(c.Payable.invoice_id == invoice.id))
    )
    if not payable:
        return
    if (
        payment.amount_minor
        > payable.amount_minor - payable.paid_minor - payable.credit_minor
    ):
        raise DomainError(
            409, "OVERPAYMENT", "Settlement exceeds the authoritative payable balance."
        )
    payable.paid_minor += payment.amount_minor
    payable.version += 1
    from . import obligations

    obligations.sync(
        session,
        project,
        "PAYABLE",
        payable.id,
        "OUTFLOW",
        "PROCUREMENT",
        payable.amount_minor - payable.paid_minor - payable.credit_minor,
        payable.due_date,
        invoice_id=invoice.id if invoice else None,
    )
    post(
        session,
        project,
        f"payment:{payment.id}",
        [
            (
                account,
                value if account == "ACCOUNTS_PAYABLE" else 0,
                value if account == "CASH" else 0,
                code_id,
            )
            for code_id, value in cost_coding.spread(
                payment.amount_minor, cost_coding.weights(session, payable)
            )
            for account in ("ACCOUNTS_PAYABLE", "CASH")
        ],
        {
            "payment_id": payment.id,
            "invoice_id": invoice.id if invoice else None,
            **({"payable_id": payable.id} if not invoice else {}),
        },
        finance.business_date(),
    )


def summary(session, project):
    balances = {}
    for account, debit, credit in session.execute(
        select(
            c.JournalLine.account,
            func.sum(c.JournalLine.debit_minor),
            func.sum(c.JournalLine.credit_minor),
        )
        .join(c.Journal)
        .where(c.Journal.project_id == project.id)
        .group_by(c.JournalLine.account)
    ):
        balances[account] = debit - credit
    return {
        "project_id": project.id,
        "currency": project.currency,
        "recorded_cash": money(project.balance_minor),
        "account_balances": {k: money(v) for k, v in balances.items()},
        "incurred_cost": money(balances["PROJECT_COST"])
        if "PROJECT_COST" in balances
        else None,
        "recognized_revenue": money(-balances["REVENUE"])
        if "REVENUE" in balances
        else None,
        "accrued_liability": money(-balances.get("ACCRUED_LIABILITY", 0))
        if balances
        else None,
        "accounts_payable": money(-balances.get("ACCOUNTS_PAYABLE", 0))
        if balances
        else None,
        "accounts_receivable": money(balances.get("ACCOUNTS_RECEIVABLE", 0))
        if balances
        else None,
        "notice": "Only explicitly recognized, reviewed journals are included. Historical records without opening recognition remain insufficient data.",
    }
