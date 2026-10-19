import json

from fastapi import (
    APIRouter,
    Request,
    Query,
)
from sqlalchemy import select

from . import models as m, finance, workflow
from .security import (
    DomainError,
    require_role,
)
from .money import money
from .schemas import (
    ForecastResponse,
    VerificationResponse,
    WorkflowResponse,
)


from .api_support import context, entity, selected_project, invoice_view


def create_router(settings, engine, app):
    router = APIRouter(tags=["Invoice intelligence"])

    @router.get("/api/v1/invoices")
    def invoices(request: Request, project_id: int | None = None):
        with context(request) as (session, user):
            project = selected_project(session, user, project_id)
            return [
                invoice_view(session, i)
                for i in session.scalars(
                    select(m.Invoice)
                    .where(m.Invoice.project_id == project.id)
                    .order_by(m.Invoice.id)
                )
            ]

    @router.get("/api/v1/invoices/{invoice_id}")
    def invoice_detail(invoice_id: int, request: Request):
        with context(request) as (session, user):
            invoice = entity(session, user, m.Invoice, invoice_id)
            return {
                **invoice_view(session, invoice),
                "lines": [
                    {
                        "id": l.id,
                        "item_code": l.item_code,
                        "description": l.description,
                        "quantity": l.quantity,
                        "unit": l.unit,
                        "rate": l.rate,
                        "amount": money(l.amount_minor),
                    }
                    for l in session.scalars(
                        select(m.InvoiceLine).where(
                            m.InvoiceLine.invoice_id == invoice_id,
                            m.InvoiceLine.active.is_(True),
                        )
                    )
                ],
            }

    @router.post(
        "/api/v1/invoices/{invoice_id}/analyze", response_model=VerificationResponse
    )
    def analyze_invoice(invoice_id: int, request: Request):
        with context(request, True) as (session, user):
            require_role(user, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            return finance.analyze(
                session, entity(session, user, m.Invoice, invoice_id), settings, user
            )

    @router.get(
        "/api/v1/invoices/{invoice_id}/workflows", response_model=list[WorkflowResponse]
    )
    def invoice_workflows(invoice_id: int, request: Request):
        with context(request) as (session, user):
            entity(session, user, m.Invoice, invoice_id)
            runs = session.scalars(
                select(m.Workflow)
                .where(m.Workflow.invoice_id == invoice_id)
                .order_by(m.Workflow.id.desc())
                .limit(10)
            )
            return [workflow.workflow_view(session, run) for run in runs]

    @router.get(
        "/api/v1/invoices/{invoice_id}/verification",
        response_model=VerificationResponse,
    )
    def verification(invoice_id: int, request: Request):
        with context(request) as (session, user):
            entity(session, user, m.Invoice, invoice_id)
            result = session.scalar(
                select(m.Verification)
                .where(m.Verification.invoice_id == invoice_id)
                .order_by(m.Verification.id.desc())
            )
            if not result:
                raise DomainError(
                    404, "ANALYSIS_REQUIRED", "Analyze this invoice first."
                )
            return {**json.loads(result.report_json), "analyzed_at": result.analyzed_at}

    @router.get("/api/v1/cashflow/forecast", response_model=ForecastResponse)
    def cashflow(
        request: Request,
        project_id: int | None = None,
        delay_days: int = Query(default=15, ge=0, le=90),
        cost_pressure_percent: str = "10",
    ):
        from .money import decimal

        try:
            pressure = decimal(cost_pressure_percent)
            if pressure < 0 or pressure > 100:
                raise ValueError()
        except ValueError:
            raise DomainError(
                422,
                "INVALID_SCENARIO",
                "Cost pressure must be between 0 and 100 percent.",
            )
        with context(request) as (session, user):
            return finance.forecast(
                session,
                selected_project(session, user, project_id),
                settings,
                delay=delay_days,
                pressure=pressure,
            )

    return router
