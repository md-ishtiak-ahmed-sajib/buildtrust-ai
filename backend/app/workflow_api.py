from fastapi import (
    APIRouter,
    Request,
    BackgroundTasks,
)

from . import models as m, audit, workflow
from .security import (
    DomainError,
    project_access,
    require_role,
)
from .schemas import (
    AnalyzeRequest,
    AskRequest,
)
from .schemas import (
    WorkflowResponse,
)


from .api_support import context, entity
from pydantic import BaseModel, JsonValue


class AgentAnswer(BaseModel):
    answer: str
    explanation_source: str
    document_ids: list[int]
    facts: JsonValue
    notice: str
    model_status: str


def create_router(settings, engine, app):
    router = APIRouter(tags=["Persisted analysis"])

    @router.post("/api/v1/agent/analyze", status_code=202)
    def start_workflow(
        body: AnalyzeRequest, request: Request, background_tasks: BackgroundTasks
    ):
        with context(request, True) as (session, user):
            require_role(user, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            invoice = entity(session, user, m.Invoice, body.invoice_id)
            project_access(session, user, invoice.project_id, write=True)
            run = m.Workflow(invoice_id=invoice.id, actor_id=user.id)
            session.add(run)
            session.flush()
            identity = run.id
            audit.append(
                session,
                user,
                "WORKFLOW_STARTED",
                "workflow",
                identity,
                {"invoice_id": invoice.id},
                invoice.project_id,
            )
        background_tasks.add_task(workflow.run_workflow, engine, settings, identity)
        return {"workflow_id": identity, "status": "QUEUED"}

    @router.get(
        "/api/v1/agent/workflows/{workflow_id}", response_model=WorkflowResponse
    )
    def get_workflow(workflow_id: int, request: Request):
        with context(request) as (session, user):
            return workflow.workflow_view(
                session, entity(session, user, m.Workflow, workflow_id)
            )

    @router.post("/api/v1/agent/workflows/{workflow_id}/retry", status_code=202)
    def retry_workflow(
        workflow_id: int, request: Request, background_tasks: BackgroundTasks
    ):
        with context(request, True) as (session, user):
            require_role(user, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            run = entity(session, user, m.Workflow, workflow_id)
            project_access(
                session,
                user,
                session.get(m.Invoice, run.invoice_id).project_id,
                write=True,
            )
            from . import jobs

            jobs.ensure_retry(session, "workflow", workflow_id)
            if run.status not in ("FAILED", "INTERRUPTED", "BLOCKED"):
                raise DomainError(
                    409,
                    "INVALID_STATE",
                    "Only interrupted, failed, or blocked analysis can be retried.",
                )
            run.status, run.error, run.actor_id = "QUEUED", None, user.id
        background_tasks.add_task(workflow.run_workflow, engine, settings, workflow_id)
        return {"workflow_id": workflow_id, "status": "QUEUED"}

    @router.post("/api/v1/agent/ask", response_model=AgentAnswer)
    def ask_agent(body: AskRequest, request: Request):
        llm_allowed = False
        reservation = None
        if settings.llm_provider == "ollama" and settings.ollama_model:
            with context(request) as (session, actor):
                project_access(session, actor, body.project_id)
                actor_id = actor.id
            from .admission import reserve_usage
            import uuid
            try:
                reservation = reserve_usage(engine, settings, "ollama", uuid.uuid4().hex, actor_id, body.project_id)
                llm_allowed = True
            except DomainError as exc:
                if exc.code != "PROVIDER_BUDGET":
                    raise
        with context(request) as (session, user):
            project = project_access(session, user, body.project_id)
            invoice = (
                entity(session, user, m.Invoice, body.invoice_id)
                if body.invoice_id
                else None
            )
            if invoice and invoice.project_id != project.id:
                raise DomainError(
                    422,
                    "PROJECT_MISMATCH",
                    "Invoice must belong to the selected project.",
                )
            result = workflow.ask(session, settings, project, body.question, invoice, llm_allowed=llm_allowed)
        if reservation:
            from .admission import mark_usage
            mark_usage(engine, reservation, "CONSUMED")
        result["model_status"] = "USED" if result["explanation_source"] == "ollama" else "BUDGET_EXHAUSTED" if settings.llm_provider == "ollama" and settings.ollama_model and not llm_allowed else "UNAVAILABLE_OR_DISABLED"
        return result

    return router
