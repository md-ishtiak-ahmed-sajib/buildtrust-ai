from .source_schemas import AccountingSources, CostCodeView, SupplierView
from .calculation_schemas import CostCodePosition

"""Independent preparation, checking and approval for accounting controls."""

import json

from fastapi import APIRouter, Request
from pydantic import TypeAdapter
from sqlalchemy import select

from . import accounting, audit, control_services
from . import control_models as c
from . import models as m
from .advanced_schemas import VersionAction
from .control_schemas import (
    ControlInput,
    ControlPayload,
    ControlResponse,
    CostCodeInput,
    InstallmentInput,
)
from .money import canonical, digest, money, decimal, published
from decimal import Decimal
from .security import DomainError, project_access, require_role
from .report_schemas import AccountingSummary, BalanceRegister, JournalResponse

payload_adapter = TypeAdapter(ControlPayload)


def view(record):
    return {
        "id": record.id,
        "project_id": record.project_id,
        "kind": record.kind,
        "name": record.name,
        "status": record.status,
        "version": record.version,
        "prepared_by": record.prepared_by,
        "checked_by": record.checked_by,
        "approved_by": record.approved_by,
        "contributors": json.loads(record.contributors_json),
        "payload": json.loads(record.payload_json),
        "calculated": json.loads(record.calculated_json),
        "snapshot_hash": record.snapshot_hash,
        "created_at": record.created_at,
    }


def snapshot(record, calculated):
    return {
        "project_id": record.project_id,
        "kind": record.kind,
        "name": record.name,
        "payload": json.loads(record.payload_json),
        "calculated": calculated,
        "contributors": json.loads(record.contributors_json),
        "policy": "independent-controls-v1",
    }


def load(session, actor, identity, write=False):
    record = session.get(c.ControlRecord, identity)
    if not record:
        raise DomainError(404, "NOT_FOUND", "Control is unavailable.")
    project_access(session, actor, record.project_id, write=write)
    return record


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Accounting and controlled records"])

    @router.get("/accounting/cost-codes", response_model=list[CostCodeView])
    def codes(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                {
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "active": r.active,
                    "version": r.version,
                }
                for r in session.scalars(
                    select(c.CostCode).where(c.CostCode.project_id == project_id)
                )
            ]

    @router.get("/accounting/cost-code-position", response_model=CostCodePosition)
    def cost_code_position(request: Request, project_id: int):
        from .cost_coding import position

        with context(request) as (session, actor):
            return position(session, project_access(session, actor, project_id))

    @router.get("/suppliers", response_model=list[SupplierView])
    def supplier_masters(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                {
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "version": r.version,
                    "approved": r.approved,
                    "beneficiary_fingerprint": r.beneficiary_fingerprint,
                }
                for r in session.scalars(
                    select(m.Supplier).where(m.Supplier.project_id == project_id)
                )
            ]

    @router.post("/accounting/cost-codes", status_code=201)
    def create_code(data: CostCodeInput, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            project_access(session, actor, data.project_id, write=True)
            row = c.CostCode(**data.model_dump())
            session.add(row)
            session.flush()
            audit.append(
                session,
                actor,
                "COST_CODE_CREATED",
                "cost_code",
                row.id,
                data.model_dump(),
                data.project_id,
            )
            return {"id": row.id, "version": row.version, **data.model_dump()}

    @router.get("/controls", response_model=list[ControlResponse])
    def controls(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                view(r)
                for r in session.scalars(
                    select(c.ControlRecord)
                    .where(c.ControlRecord.project_id == project_id)
                    .order_by(c.ControlRecord.id.desc())
                    .limit(500)
                )
            ]

    @router.post("/controls", status_code=201, response_model=ControlResponse)
    def create_control(data: ControlInput, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            project = project_access(session, actor, data.project_id, write=True)
            calculated = control_services.build(session, project, data.payload)
            row = c.ControlRecord(
                project_id=project.id,
                kind=data.payload.kind,
                name=data.name,
                payload_json=canonical(data.payload.model_dump(mode="json")),
                calculated_json=canonical(calculated),
                contributors_json=canonical([actor.id]),
                prepared_by=actor.id,
            )
            session.add(row)
            session.flush()
            audit.append(
                session,
                actor,
                "CONTROL_CREATED",
                "control",
                row.id,
                {
                    "kind": row.kind,
                    "payload_hash": digest(data.payload.model_dump(mode="json")),
                },
                project.id,
            )
            return view(row)

    @router.patch("/controls/{identity}", response_model=ControlResponse)
    def edit_control(identity: int, data: ControlInput, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            row = load(session, actor, identity, True)
            if row.status != "DRAFT" or row.version != data.expected_version:
                raise DomainError(
                    409,
                    "VERSION_CONFLICT",
                    "Reload the draft; submitted records are locked.",
                )
            if data.project_id != row.project_id or data.payload.kind != row.kind:
                raise ValueError("Project and control kind cannot change")
            row.calculated_json = canonical(
                control_services.build(
                    session, session.get(m.Project, row.project_id), data.payload
                )
            )
            row.payload_json = canonical(data.payload.model_dump(mode="json"))
            row.name = data.name
            row.contributors_json = canonical(
                sorted(set(json.loads(row.contributors_json) + [actor.id]))
            )
            row.version += 1
            audit.append(
                session,
                actor,
                "CONTROL_UPDATED",
                "control",
                row.id,
                {
                    "version": row.version,
                    "contributors": json.loads(row.contributors_json),
                },
                row.project_id,
            )
            return view(row)

    @router.post("/controls/{identity}/{action}", response_model=ControlResponse)
    def transition(identity: int, action: str, data: VersionAction, request: Request):
        with context(request, True) as (session, actor):
            row = load(session, actor, identity, True)
            project = session.get(m.Project, row.project_id)
            if row.version != data.expected_version:
                raise DomainError(
                    409,
                    "VERSION_CONFLICT",
                    "Control changed; reload before continuing.",
                )
            contributors = json.loads(row.contributors_json)
            if action == "revise":
                require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
                if row.status == "APPROVED" and row.kind != "ACCOUNTING_POLICY":
                    raise DomainError(
                        409,
                        "POSTING_IMMUTABLE",
                        "Approved postings require a separately supported correcting event.",
                    )
                if row.status != "APPROVED":
                    row.status = "SUPERSEDED"
                    row.version += 1
                clone = c.ControlRecord(
                    project_id=row.project_id,
                    kind=row.kind,
                    name=row.name,
                    parent_id=row.id,
                    payload_json=row.payload_json,
                    calculated_json=row.calculated_json,
                    prepared_by=actor.id,
                    contributors_json=canonical(sorted(set(contributors + [actor.id]))),
                )
                session.add(clone)
                session.flush()
                audit.append(
                    session,
                    actor,
                    "CONTROL_REVISED",
                    "control",
                    clone.id,
                    {"parent_id": row.id},
                    row.project_id,
                )
                return view(clone)
            if action == "reject":
                require_role(actor, "FINANCE_MANAGER", "ADMIN")
                if row.status not in ("SUBMITTED", "CHECKED"):
                    raise DomainError(
                        409,
                        "INVALID_TRANSITION",
                        "Only submitted controls can be rejected.",
                    )
                if actor.id in contributors:
                    raise DomainError(
                        403, "SEPARATION_OF_DUTIES", "Independent review is required."
                    )
                row.status = "REJECTED"
            else:
                values = payload_adapter.validate_json(row.payload_json)
                calculated = control_services.build(session, project, values)
                bound = snapshot(row, calculated)
                if action == "submit":
                    require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
                    if row.status != "DRAFT":
                        raise DomainError(
                            409, "VERSION_LOCKED", "Only drafts may be submitted."
                        )
                    row.snapshot_json = canonical(bound)
                    row.snapshot_hash = digest(bound)
                    row.calculated_json = canonical(calculated)
                    row.status = "SUBMITTED"
                elif action in ("check", "approve"):
                    require_role(
                        actor,
                        *(
                            ("ADMIN",)
                            if action == "approve"
                            else ("FINANCE_MANAGER", "ADMIN")
                        ),
                    )
                    if actor.id in contributors or (
                        action == "approve" and actor.id == row.checked_by
                    ):
                        raise DomainError(
                            403,
                            "SEPARATION_OF_DUTIES",
                            "Retained contributors and checker cannot approve their own work.",
                        )
                    if row.snapshot_hash != digest(bound):
                        raise DomainError(
                            409,
                            "SOURCE_CHANGED",
                            "Sources changed. Create a fresh revision.",
                        )
                    if action == "check":
                        if row.status != "SUBMITTED":
                            raise DomainError(
                                409,
                                "INVALID_TRANSITION",
                                "Submit before independent checking.",
                            )
                        row.checked_by = actor.id
                        row.status = "CHECKED"
                    else:
                        if row.status != "CHECKED":
                            raise DomainError(
                                409,
                                "INVALID_TRANSITION",
                                "Independent checking is required.",
                            )
                        checker = session.get(m.User, row.checked_by)
                        if (
                            not checker
                            or not checker.active
                            or checker.role not in ("ADMIN", "FINANCE_MANAGER")
                            or not session.get(m.Membership, (checker.id, project.id))
                        ):
                            raise DomainError(
                                409,
                                "CHECKER_AUTHORITY_CHANGED",
                                "Checking authority changed; revise for fresh checking.",
                            )
                        control_services.apply(
                            session, actor, project, row, values, calculated
                        )
                        row.approved_by = actor.id
                        row.status = "APPROVED"
                else:
                    raise DomainError(404, "NOT_FOUND", "Unknown control action.")
            row.version += 1
            audit.append(
                session,
                actor,
                "CONTROL_" + action.upper(),
                "control",
                row.id,
                {
                    "kind": row.kind,
                    "version": row.version,
                    "snapshot_hash": row.snapshot_hash,
                },
                row.project_id,
            )
            return view(row)

    @router.get("/accounting/summary", response_model=AccountingSummary)
    def summary(request: Request, project_id: int):
        with context(request) as (session, actor):
            return accounting.summary(
                session, project_access(session, actor, project_id)
            )

    @router.get("/accounting/sources", response_model=AccountingSources)
    def sources(request: Request, project_id: int):
        from . import cost_coding

        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return {
                "cost_sources": [
                    {
                        "id": line.id,
                        "type": kind,
                        "label": f"{kind} #{line.id} · {getattr(line, 'item_code', '')}",
                        "version": cost_coding.source(
                            session, project_id, kind, line.id
                        )[1],
                        "link_version": mapped.version
                        if (
                            mapped := cost_coding.link(
                                session, project_id, kind, line.id
                            )
                        )
                        else None,
                        "cost_code_id": mapped.cost_code_id if mapped else None,
                    }
                    for cls, kind, query in (
                        (
                            m.BOQItem,
                            "BOQ_ITEM",
                            select(m.BOQItem).where(m.BOQItem.project_id == project_id),
                        ),
                        (
                            m.POLine,
                            "PO_LINE",
                            select(m.POLine)
                            .join(m.PurchaseOrder)
                            .where(m.PurchaseOrder.project_id == project_id),
                        ),
                        (
                            m.ReceiptLine,
                            "RECEIPT_LINE",
                            select(m.ReceiptLine)
                            .join(m.GoodsReceipt)
                            .join(m.PurchaseOrder)
                            .where(m.PurchaseOrder.project_id == project_id),
                        ),
                        (
                            m.InvoiceLine,
                            "INVOICE_LINE",
                            select(m.InvoiceLine)
                            .join(m.Invoice)
                            .where(
                                m.Invoice.project_id == project_id,
                                m.InvoiceLine.active.is_(True),
                            ),
                        ),
                    )
                    for line in session.scalars(query.limit(500))
                ],
                "receipt_lines": [
                    {
                        "id": line.id,
                        "receipt": receipt.number,
                        "po": po.number,
                        "item_code": line.item_code,
                        "quantity": line.quantity,
                        "unit": line.unit,
                        "po_rate": pol.rate,
                        "recognized": session.scalar(
                            select(c.Recognition.id).where(
                                c.Recognition.receipt_line_id == line.id
                            )
                        ),
                    }
                    for line, receipt, po, pol in session.execute(
                        select(m.ReceiptLine, m.GoodsReceipt, m.PurchaseOrder, m.POLine)
                        .join(
                            m.GoodsReceipt,
                            m.ReceiptLine.receipt_id == m.GoodsReceipt.id,
                        )
                        .join(
                            m.PurchaseOrder, m.GoodsReceipt.po_id == m.PurchaseOrder.id
                        )
                        .join(
                            m.POLine,
                            (m.POLine.po_id == m.PurchaseOrder.id)
                            & (m.POLine.item_code == m.ReceiptLine.item_code),
                        )
                        .where(m.PurchaseOrder.project_id == project_id)
                    )
                ],
                "recognitions": [
                    {
                        "id": r.id,
                        "receipt_line_id": r.receipt_line_id,
                        "invoice_id": r.invoice_id,
                        "amount": money(r.amount_minor),
                        "remaining_quantity": published(
                            decimal(r.quantity)
                            - sum(
                                (
                                    decimal(allocation.quantity)
                                    for allocation in session.scalars(
                                        select(c.RecognitionAllocation).where(
                                            c.RecognitionAllocation.recognition_id
                                            == r.id
                                        )
                                    )
                                ),
                                Decimal(0),
                            )
                        ),
                    }
                    for r in session.scalars(
                        select(c.Recognition).where(
                            c.Recognition.project_id == project_id
                        )
                    )
                ],
                "invoices": [
                    {
                        "id": r.id,
                        "number": r.number,
                        "amount": money(r.total_minor),
                        "status": r.status,
                        "version": r.version,
                    }
                    for r in session.scalars(
                        select(m.Invoice).where(m.Invoice.project_id == project_id)
                    )
                ],
            }

    @router.get("/accounting/journals", response_model=list[JournalResponse])
    def journals(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                {
                    "id": r.id,
                    "source_key": r.source_key,
                    "business_date": r.business_date,
                    "currency": r.currency,
                    "snapshot_hash": r.snapshot_hash,
                    "entries": [
                        {
                            "account": line.account,
                            "debit": money(line.debit_minor),
                            "credit": money(line.credit_minor),
                            "cost_code_id": line.cost_code_id,
                        }
                        for line in session.scalars(
                            select(c.JournalLine).where(
                                c.JournalLine.journal_id == r.id
                            )
                        )
                    ],
                }
                for r in session.scalars(
                    select(c.Journal)
                    .where(c.Journal.project_id == project_id)
                    .order_by(c.Journal.id.desc())
                    .limit(500)
                )
            ]

    @router.get("/accounting/balances", response_model=BalanceRegister)
    def balances(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return {
                "payables": [
                    {
                        "id": p.id,
                        "invoice_id": p.invoice_id,
                        "certificate_id": p.record_id if not p.invoice_id else None,
                        "version": p.version,
                        "amount": money(p.amount_minor),
                        "paid": money(p.paid_minor),
                        "credit": money(p.credit_minor),
                        "remaining": money(
                            p.amount_minor - p.paid_minor - p.credit_minor
                        ),
                        "retention": money(
                            p.retention_minor - p.retention_released_minor
                        ),
                        "supplier_credit": money(p.supplier_credit_minor),
                        "currency": p.currency,
                        "due_date": p.due_date,
                    }
                    for p in session.scalars(
                        select(c.Payable).where(c.Payable.project_id == project_id)
                    )
                ],
                "receivables": [
                    {
                        "id": p.id,
                        "certificate_id": p.certificate_id,
                        "version": p.version,
                        "amount": money(p.amount_minor),
                        "received": money(p.received_minor),
                        "remaining": money(
                            p.amount_minor - p.received_minor - p.credit_minor
                        ),
                        "credit": money(p.credit_minor),
                        "customer_credit": money(p.customer_credit_minor),
                        "retention": money(p.retention_minor),
                        "currency": p.currency,
                        "due_date": p.due_date,
                    }
                    for p in session.scalars(
                        select(c.Receivable).where(
                            c.Receivable.project_id == project_id
                        )
                    )
                ],
            }

    @router.post("/payables/{identity}/installments", status_code=201)
    def installment(identity: int, data: InstallmentInput, request: Request):
        from . import payments

        with context(request, True) as (session, actor):
            require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            payable = session.get(c.Payable, identity)
            if not payable:
                raise DomainError(404, "NOT_FOUND", "Payable is unavailable.")
            project_access(session, actor, payable.project_id, write=True)
            if data.expected_version != payable.version:
                raise DomainError(
                    409, "VERSION_CONFLICT", "Payable changed; reload the balance."
                )
            if not payable.invoice_id:
                from .certified_payables import prepare

                return payments.proposal_view(
                    session,
                    prepare(
                        session,
                        payable,
                        request.app.state.settings,
                        actor,
                        accounting.positive(data.amount),
                    ),
                )
            proposal = payments.create_proposal(
                session,
                session.get(m.Invoice, payable.invoice_id),
                request.app.state.settings,
                actor,
                amount_minor=accounting.positive(data.amount),
            )
            return payments.proposal_view(session, proposal)

    return router
