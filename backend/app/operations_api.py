"""Project-scoped work queues and additive paginated registers."""

import json
from datetime import datetime

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from . import advanced_models as a
from . import authorship
from . import control_models as c
from . import models as m
from .money import money, utcnow
from .operations_models import JobAttempt
from .security import DomainError, project_access
from .interface_schemas import RegisterPage, AttemptResponse


class WorkItem(BaseModel):
    kind: str
    id: int
    title: str
    status: str
    actionable: bool
    explanation: str
    url: str
    expires_at: str | None = None
    expiry_state: str | None = None


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Work queues and registers"])

    @router.get("/work-items", response_model=list[WorkItem])
    def work_items(request: Request, project_id: int):
        with context(request) as (session, actor):
            project = project_access(session, actor, project_id)
            rows = []
            specs = [
                (a.Quotation, "quotation", "/materials", ("DRAFT",)),
                (a.TakeoffSheet, "measurement", "/takeoff", ("DRAFT",)),
                (a.Estimate, "estimate", "/estimates", ("SUBMITTED", "CHECKED")),
                (m.Proposal, "payment", "/payments", ("PENDING_APPROVAL", "APPROVED")),
                (c.ControlRecord, "control", "/controls", ("SUBMITTED", "CHECKED")),
            ]
            for cls, kind, url, states in specs:
                for record in session.scalars(
                    select(cls).where(
                        cls.project_id == project_id, cls.status.in_(states)
                    )
                ):
                    creator = getattr(
                        record, "prepared_by", getattr(record, "requested_by", None)
                    )
                    own = actor.id == creator or actor.id in authorship.contributors(
                        session, kind, record.id
                    )
                    if kind == "control":
                        own = actor.id in json.loads(record.contributors_json)
                        from .commercial import KINDS
                        from .procurement import KINDS as PROCUREMENT
                        from .corrections import KINDS as CORRECTIONS

                        if record.kind in KINDS | PROCUREMENT | CORRECTIONS:
                            url = "/commercial"
                        else:
                            url = "/controls"
                    expired = getattr(record, "expires_at", None)
                    can = (
                        project.active
                        and not own
                        and actor.role in ("ADMIN", "FINANCE_MANAGER")
                    )
                    if kind in ("estimate", "control") and record.status == "CHECKED":
                        can = (
                            can
                            and actor.role == "ADMIN"
                            and actor.id != record.checked_by
                        )
                    if expired and expired <= utcnow():
                        can = False
                    expiry_state = None
                    if expired:
                        remaining = (
                            datetime.fromisoformat(expired)
                            - datetime.fromisoformat(utcnow())
                        ).total_seconds()
                        expiry_state = (
                            "EXPIRED"
                            if remaining <= 0
                            else "EXPIRING"
                            if remaining <= 300
                            else "VALID"
                        )
                    reason = (
                        "Ready for independent review"
                        if can
                        else "Independent authorized reviewer required"
                    )
                    if not project.active:
                        reason = "Archived run: read only"
                    if expired and expired <= utcnow():
                        reason = "Approval expired; prepare fresh validation"
                    elif expiry_state == "EXPIRING":
                        reason += "; approval expires within five minutes"
                    rows.append(
                        WorkItem(
                            kind=kind,
                            id=record.id,
                            title=getattr(record, "name", None)
                            or f"{kind.title()} #{record.id}",
                            status=record.status,
                            actionable=can,
                            explanation=reason,
                            url=url,
                            expires_at=expired,
                            expiry_state=expiry_state,
                        )
                    )
            return rows

    @router.get("/projects/archived")
    def archives(request: Request):
        with context(request) as (session, actor):
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "code": p.code,
                    "run_id": p.run_id,
                    "active": False,
                    "currency": p.currency,
                    "budget": money(p.budget_minor),
                    "balance": money(p.balance_minor),
                    "minimum_reserve": money(p.reserve_minor),
                }
                for p in session.scalars(
                    select(m.Project)
                    .join(m.Membership)
                    .where(
                        m.Membership.user_id == actor.id, m.Project.active.is_(False)
                    )
                    .order_by(m.Project.id.desc())
                )
            ]

    registers = {
        "documents": (m.Document, "original_filename"),
        "quotations": (a.Quotation, "fields_json"),
        "estimates": (a.Estimate, "name"),
        "payments": (m.Proposal, "status"),
        "audit": (m.AuditEvent, "event_type"),
        "controls": (c.ControlRecord, "name"),
        "contracts": (c.ControlRecord, "name"),
        "certificates": (c.ControlRecord, "name"),
        "amendments": (c.ControlRecord, "name"),
        "corrections": (c.ControlRecord, "name"),
        "measurements": (a.TakeoffSheet, "fields_json"),
        "materials": (a.Material, "name"),
        "prices": (a.PriceObservation, "payload_json"),
        "invoices": (m.Invoice, "number"),
        "purchase-orders": (m.PurchaseOrder, "number"),
        "receipts": (m.GoodsReceipt, "number"),
        "journals": (c.Journal, "source_key"),
        "cost-codes": (c.CostCode, "code"),
    }

    @router.get("/registers/{kind}", response_model=RegisterPage)
    def register(
        kind: str,
        request: Request,
        project_id: int,
        q: str = Query("", max_length=120),
        status: str = Query("", max_length=40),
        order: str = Query("desc", pattern="^(asc|desc)$"),
        offset: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=100),
    ):
        if kind not in registers:
            raise DomainError(404, "NOT_FOUND", "Unknown register.")
        cls, label = registers[kind]
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            conditions = (
                [
                    cls.po_id.in_(
                        select(m.PurchaseOrder.id).where(
                            m.PurchaseOrder.project_id == project_id
                        )
                    )
                ]
                if cls is m.GoodsReceipt
                else [cls.project_id == project_id]
            )
            categories = {
                "contracts": ("COMMERCIAL_CONTRACT",),
                "certificates": ("INTERIM_CERTIFICATE", "CUSTOMER_CERTIFICATE"),
                "amendments": ("PROCUREMENT_AMENDMENT",),
                "corrections": (
                    "CERTIFICATE_CORRECTION",
                    "ACCEPTED_COST_CORRECTION",
                    "CREDIT_NOTE",
                ),
            }
            if kind in categories:
                conditions.append(c.ControlRecord.kind.in_(categories[kind]))
            if q:
                conditions.append(getattr(cls, label).icontains(q, autoescape=True))
            status_column = getattr(
                cls, "status", getattr(cls, "extraction_status", None)
            )
            if status and status_column is not None:
                conditions.append(status_column == status)
            total = session.scalar(
                select(func.count()).select_from(cls).where(*conditions)
            )
            records = session.scalars(
                select(cls)
                .where(*conditions)
                .order_by(cls.id.desc() if order == "desc" else cls.id.asc())
                .offset(offset)
                .limit(limit)
            )
            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "items": [
                    {
                        "id": r.id,
                        "label": getattr(r, label),
                        "status": getattr(
                            r, "status", getattr(r, "extraction_status", "RECORDED")
                        ),
                        "created_at": getattr(
                            r,
                            "created_at",
                            getattr(r, "retrieved_at", getattr(r, "business_date", "")),
                        ),
                    }
                    for r in records
                ],
            }

    @router.get("/operations/attempts", response_model=list[AttemptResponse])
    def attempts(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            searches = set(
                session.scalars(
                    select(a.PriceSearch.id).where(
                        a.PriceSearch.project_id == project_id
                    )
                )
            )
            workflows = set(
                session.scalars(
                    select(m.Workflow.id)
                    .join(m.Invoice)
                    .where(m.Invoice.project_id == project_id)
                )
            )
            return [
                {
                    "id": r.id,
                    "kind": r.kind,
                    "entity_id": r.entity_id,
                    "attempt": r.attempt,
                    "status": r.status,
                    "started_at": r.started_at,
                    "heartbeat_at": r.heartbeat_at,
                    "lease_until": r.lease_until,
                    "next_attempt_at": r.next_attempt_at,
                    "finished_at": r.finished_at,
                }
                for r in session.scalars(
                    select(JobAttempt)
                    .where(
                        or_(
                            (JobAttempt.kind == "price_search")
                            & JobAttempt.entity_id.in_(searches),
                            (JobAttempt.kind == "workflow")
                            & JobAttempt.entity_id.in_(workflows),
                        )
                    )
                    .order_by(JobAttempt.id.desc())
                    .limit(100)
                )
            ]

    return router
