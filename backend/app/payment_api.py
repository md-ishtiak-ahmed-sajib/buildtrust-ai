import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Request,
    Header,
)
from sqlalchemy import select

from .database import transaction
from . import models as m, payments, audit
from .security import (
    DomainError,
)
from .schemas import (
    ProposalRequest,
    ReceiptResponse,
)
from .money import canonical, digest
from .schemas import (
    ProposalResponse,
)


from .api_support import context, entity, selected_project


def create_router(settings, engine, app):
    router = APIRouter(tags=["Sandbox settlement"])

    @router.get("/api/v1/payments", response_model=list[ProposalResponse])
    def list_payments(request: Request, project_id: int | None = None):
        with context(request) as (session, user):
            project = selected_project(session, user, project_id)
            return [
                payments.proposal_view(session, p)
                for p in session.scalars(
                    select(m.Proposal)
                    .where(m.Proposal.project_id == project.id)
                    .order_by(m.Proposal.id.desc())
                )
            ]

    @router.post(
        "/api/v1/payments/proposals", status_code=201, response_model=ProposalResponse
    )
    def prepare(body: ProposalRequest, request: Request):
        with context(request, True) as (session, user):
            invoice = entity(session, user, m.Invoice, body.invoice_id)
            return payments.proposal_view(
                session, payments.create_proposal(session, invoice, settings, user)
            )

    @router.post(
        "/api/v1/payments/{proposal_id}/approve", response_model=ProposalResponse
    )
    def approve_payment(proposal_id: int, request: Request):
        with context(request, True) as (session, user):
            proposal = entity(session, user, m.Proposal, proposal_id)
            payments.approve(session, proposal, settings, user)
            return payments.proposal_view(session, proposal)

    @router.post(
        "/api/v1/payments/{proposal_id}/reject", response_model=ProposalResponse
    )
    def reject_payment(proposal_id: int, request: Request):
        with context(request, True) as (session, user):
            proposal = entity(session, user, m.Proposal, proposal_id)
            payments.reject(session, proposal, settings, user)
            return payments.proposal_view(session, proposal)

    @router.post(
        "/api/v1/payments/{proposal_id}/execute",
        response_model=ReceiptResponse,
        response_model_exclude_unset=True,
    )
    def execute_payment(
        proposal_id: int,
        request: Request,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ):
        try:
            with context(request, True) as (session, user):
                return payments.execute(
                    session,
                    entity(session, user, m.Proposal, proposal_id),
                    settings,
                    user,
                    idempotency_key,
                    app.state.execution_failure_hook,
                )
        except RuntimeError:
            with transaction(engine, write=True) as session:
                proposal = session.get(m.Proposal, proposal_id)
                if proposal and proposal.status == "APPROVED":
                    proposal.status = "FAILED"
                    payments.release(session, proposal)
                    audit.append(
                        session,
                        session.get(m.User, request.state.actor_id),
                        "PAYMENT_FAILED",
                        "proposal",
                        proposal_id,
                        {"balance_deducted": False},
                        proposal.project_id,
                    )
                    if not session.scalar(
                        select(m.ExecutionAttempt).where(
                            m.ExecutionAttempt.idempotency_key == idempotency_key
                        )
                    ):
                        session.add(
                            m.ExecutionAttempt(
                                proposal_id=proposal.id,
                                actor_id=request.state.actor_id,
                                idempotency_key=idempotency_key,
                                request_hash=digest(
                                    {
                                        "proposal_id": proposal.id,
                                        "version": proposal.version,
                                        "operation": "execute",
                                    }
                                ),
                                status_code=503,
                                response_json=canonical(
                                    {
                                        "error": {
                                            "code": "SANDBOX_FAILURE",
                                            "message": "Simulated settlement failed; no funds were deducted.",
                                        }
                                    }
                                ),
                            )
                        )
            raise DomainError(
                503,
                "SANDBOX_FAILURE",
                "Simulated settlement failed; no funds were deducted.",
            )

    @router.get(
        "/api/v1/payments/{proposal_id}/receipt",
        response_model=ReceiptResponse,
        response_model_exclude_unset=True,
    )
    def receipt(proposal_id: int, request: Request):
        with context(request) as (session, user):
            entity(session, user, m.Proposal, proposal_id)
            attempt = session.scalar(
                select(m.ExecutionAttempt).where(
                    m.ExecutionAttempt.proposal_id == proposal_id,
                    m.ExecutionAttempt.status_code == 200,
                )
            )
            if not attempt:
                raise DomainError(
                    404, "NO_RECEIPT", "Only a settled payment has a receipt."
                )
            return json.loads(attempt.response_json)

    return router
