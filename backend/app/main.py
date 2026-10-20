from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    Request,
    Query,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError, OperationalError

from .config import get_settings, ROOT
from .database import make_engine, transaction
from .migrations import migrate
from . import advanced_models as advanced
from . import estimating
from .login_security import LoginThrottle
from .diagnostics import RequestBoundary
from .interface_schemas import ErrorResponse
from .advanced_api import create_router as advanced_router
from .operations_api import create_router as operations_router
from .control_api import create_router as control_router
from .commercial_api import create_router as commercial_router
from .reporting_api import create_router as reporting_router
from .administration_api import create_router as administration_router
from . import models as m, finance, payments, audit
from .security import (
    DomainError,
    token_for,
    passwords,
    DUMMY_HASH,
    project_access,
    require_role,
)
from .schemas import (
    LoginRequest,
)
from .money import money, utcnow
from .seed import seed
from .schemas import (
    UserResponse,
    LoginResponse,
    ProjectResponse,
)


from .api_support import (
    user_view,
    project_view,
    invoice_view,
    context,
    allowed_projects,
    selected_project,
)
from .document_api import create_router as document_api_router
from .invoice_api import create_router as invoice_api_router
from .payment_api import create_router as payment_api_router
from .workflow_api import create_router as workflow_api_router
from .mfa_api import MfaChallengeResponse


def create_app(settings=None, initialize=True):
    settings = settings or get_settings()
    settings.prepare()
    engine = make_engine(settings.data_dir / "buildtrust.db")
    if initialize:
        migrate(engine)
        with transaction(engine, True) as session:
            estimating.seed_profiles(session)

    @asynccontextmanager
    async def lifespan(app):
        import asyncio
        from . import worker

        with transaction(engine, write=True) as session:
            worker.recover(session)
        stopped = asyncio.Event()
        scheduler = (
            asyncio.create_task(worker.serve(engine, settings, stopped))
            if settings.background_jobs
            else None
        )
        try:
            yield
        finally:
            stopped.set()
            if scheduler:
                try:
                    await asyncio.wait_for(scheduler, timeout=5)
                except TimeoutError:
                    scheduler.cancel()
                    await asyncio.gather(scheduler, return_exceptions=True)

    app = FastAPI(
        title="BuildTrust AI",
        debug=False,
        version="0.2.0",
        lifespan=lifespan,
        responses={
            status: {"model": ErrorResponse}
            for status in (400, 401, 403, 404, 408, 409, 413, 422, 429, 503)
        },
        description="Construction finance copilot. All settlement is simulated; money values are decimal strings.",
    )
    app.state.engine, app.state.settings, app.state.secret = (
        engine,
        settings,
        settings.signing_secret(),
    )
    app.state.execution_failure_hook = None
    from .admission import DurableLoginThrottle
    app.state.login_throttle = DurableLoginThrottle(engine)
    from .request_security import RequestSecurity
    app.add_middleware(RequestSecurity,settings=settings)
    app.add_middleware(RequestBoundary, max_body=settings.max_upload_bytes + 128 * 1024)
    # Static archive routes precede the legacy /projects/{project_id} route.
    app.include_router(operations_router(context))

    @app.exception_handler(ValueError)
    async def invalid_financial_input(request, exc):
        message = str(exc)[:600]
        for secret in (settings.serpapi_key, settings.dataforseo_password, app.state.secret):
            if secret:
                message = message.replace(secret, "[redacted]")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_INPUT",
                    "message": message,
                    "fields": getattr(exc, "fields", []),
                    "request_id": request.scope.get("request_id"),
                }
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        try:
            with transaction(engine, write=True) as session:
                payments.expire(session)
                actor = (
                    session.get(m.User, getattr(request.state, "actor_id", None))
                    if getattr(request.state, "actor_id", None)
                    else None
                )
                if actor and not error.project_id:
                    import re

                    match = re.search(
                        r"/(payments|invoices|documents|agent/workflows|materials|quotations|estimates|takeoff/sheets|prices/searches)/(\d+)",
                        request.url.path,
                    )
                    if match:
                        model = {
                            "payments": m.Proposal,
                            "invoices": m.Invoice,
                            "documents": m.Document,
                            "agent/workflows": m.Workflow,
                            "materials": advanced.Material,
                            "quotations": advanced.Quotation,
                            "estimates": advanced.Estimate,
                            "takeoff/sheets": advanced.TakeoffSheet,
                            "prices/searches": advanced.PriceSearch,
                        }[match[1]]
                        resource = session.get(model, int(match[2]))
                        if resource:
                            pid = (
                                resource.project_id
                                if hasattr(resource, "project_id")
                                else session.get(
                                    m.Invoice, resource.invoice_id
                                ).project_id
                            )
                            if session.get(m.Membership, (actor.id, pid)):
                                error.project_id = pid
                if error.entity_id and error.code in (
                    "APPROVAL_EXPIRED",
                    "APPROVAL_SNAPSHOT_CHANGED",
                    "APPROVAL_INVALID",
                    "PAYMENT_BLOCKED",
                    "RESERVATION_INVALID",
                    "PREPARER_AUTHORITY_CHANGED",
                ):
                    proposal = session.get(m.Proposal, error.entity_id)
                    if proposal and proposal.status in ("PENDING_APPROVAL", "APPROVED"):
                        proposal.status = (
                            "EXPIRED" if error.code != "PAYMENT_BLOCKED" else "BLOCKED"
                        )
                        payments.release(session, proposal)
                audit.append(
                    session,
                    actor,
                    "UNAUTHORIZED_ACTION"
                    if error.status in (401, 403)
                    else "OPERATION_DENIED",
                    "api",
                    error.entity_id or request.url.path,
                    {"code": error.code, "message": error.message},
                    error.project_id,
                )
        except OperationalError:
            pass
        return JSONResponse(
            status_code=error.status,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "fields": error.fields,
                    "retry_after": error.retry_after,
                }
            },
            headers={"Retry-After": str(error.retry_after)}
            if error.retry_after
            else {},
        )

    @app.exception_handler(RequestValidationError)
    async def input_error(request, error):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Check request fields.",
                    "request_id": request.scope.get("request_id"),
                    "fields": [
                        {"location": list(e["loc"]), "message": e["msg"]}
                        for e in error.errors()
                    ],
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def constraint_error(request, error):
        return await domain_error(
            request,
            DomainError(
                409,
                "BUSINESS_CONFLICT",
                "A duplicate business identity or inconsistent financial record was rejected.",
            ),
        )

    @app.exception_handler(OperationalError)
    async def busy_error(request, error):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_BUSY",
                    "message": "Storage is temporarily unavailable; retry safely with the same idempotency key.",
                    "request_id": request.scope.get("request_id"),
                    "retry_after": 1,
                }
            },
            headers={"Retry-After": "1"},
        )

    @app.middleware("http")
    async def security_headers(request, call_next):
        # Only same-origin UI is supported; no wildcard CORS or cookie-based authority.
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/v1/health")
    def health():
        with transaction(engine) as session:
            session.execute(select(1))
        return {
            "status": "ok",
            "simulation": True,
            "demo_mode": settings.demo_mode,
            "llm_provider": settings.llm_provider,
        }

    @app.post("/api/v1/auth/login", response_model=LoginResponse | MfaChallengeResponse)
    def login(body: LoginRequest, request: Request):
        address = request.client.host if request.client else "local"
        identifier = body.email.strip().lower()
        app.state.login_throttle.check(identifier, address)
        # Argon2 runs without a SQLite writer lock. Recheck active identity and
        # the verified hash before recording a successful login.
        with transaction(engine) as session:
            user = session.scalar(select(m.User).where(m.User.email == identifier))
            identity, verified_hash = (
                (user.id, user.password_hash) if user else (None, DUMMY_HASH)
            )
            valid = passwords.verify(body.password, verified_hash)
            if not valid or not user or not user.active:
                app.state.login_throttle.failed(identifier, address)
                raise DomainError(
                    401, "INVALID_LOGIN", "Email or password is incorrect."
                )
        with transaction(engine, write=True) as session:
            user = session.get(m.User, identity)
            if (
                not user
                or not user.active
                or user.password_hash != verified_hash
                or user.email != identifier
            ):
                raise DomainError(
                    401, "INVALID_LOGIN", "Email or password is incorrect."
                )
            request.state.actor_id = user.id
            from . import mfa
            if mfa.needs_second_factor(session,settings,user):
                from .mfa_models import MfaFactor
                return mfa.issue(session,user,'VERIFY' if session.get(MfaFactor,user.id) else 'ENROLL')
            audit.append(session, user, "USER_LOGIN", "user", user.id)
            return {
                "access_token": token_for(user, app.state.secret, session),
                "token_type": "bearer",
                "expires_in": 1800,
                "user": user_view(user, settings),
            }

    @app.get("/api/v1/auth/me", response_model=UserResponse)
    def me(request: Request):
        with context(request) as (session, user):
            return user_view(user, settings)

    @app.get("/api/v1/projects", response_model=list[ProjectResponse])
    def projects(request: Request):
        with context(request) as (session, user):
            return [project_view(p) for p in allowed_projects(session, user)]

    @app.get("/api/v1/projects/{project_id}")
    def project_detail(project_id: int, request: Request):
        with context(request) as (session, user):
            project = project_access(session, user, project_id)
            suppliers = session.scalars(
                select(m.Supplier).where(m.Supplier.project_id == project_id)
            )
            return {
                **project_view(project),
                "suppliers": [
                    {
                        "code": s.code,
                        "name": s.name,
                        "approved": s.approved,
                        "beneficiary_fingerprint": s.beneficiary_fingerprint,
                    }
                    for s in suppliers
                ],
            }

    @app.get("/api/v1/dashboard/summary")
    def dashboard(request: Request, project_id: int | None = None):
        with context(request) as (session, user):
            project = selected_project(session, user, project_id)
            invoices = list(
                session.scalars(
                    select(m.Invoice).where(m.Invoice.project_id == project.id)
                )
            )
            proposals = list(
                session.scalars(
                    select(m.Proposal).where(m.Proposal.project_id == project.id)
                )
            )
            ids = [i.id for i in invoices]
            settled = list(
                session.scalars(
                    select(m.Payment)
                    .join(m.Proposal)
                    .where(m.Proposal.project_id == project.id)
                )
            )
            cash = finance.forecast(session, project, settings)
            events = list(
                session.scalars(
                    select(m.AuditEvent)
                    .where(m.AuditEvent.project_id == project.id)
                    .order_by(m.AuditEvent.id.desc())
                    .limit(8)
                )
            )
            return {
                "project": project_view(project),
                "available_cash": cash["available_cash"],
                "outstanding_obligations": money(
                    sum(i.total_minor for i in invoices if i.status == "VERIFIED")
                ),
                "pending_review": sum(i.status == "PENDING_REVIEW" for i in invoices),
                "blocked_invoices": sum(i.status == "BLOCKED" for i in invoices),
                "awaiting_approval": sum(
                    p.status == "PENDING_APPROVAL" and p.expires_at > utcnow()
                    for p in proposals
                ),
                "approved_payments": sum(
                    p.status == "APPROVED" and p.expires_at > utcnow()
                    for p in proposals
                ),
                "settled_payments": len(settled),
                "total_paid": money(sum(p.amount_minor for p in settled)),
                "cashflow": cash,
                "invoices": [invoice_view(session, i) for i in invoices],
                "activity": [
                    {
                        "id": e.id,
                        "type": e.event_type,
                        "actor": e.actor_name,
                        "created_at": e.created_at,
                    }
                    for e in events
                ],
            }

    app.include_router(document_api_router(settings, engine, app))

    app.include_router(invoice_api_router(settings, engine, app))

    app.include_router(payment_api_router(settings, engine, app))

    app.include_router(workflow_api_router(settings, engine, app))

    @app.get("/api/v1/audit/events")
    def audit_events(
        request: Request,
        project_id: int | None = None,
        limit: int = Query(default=200, ge=1, le=1000),
    ):
        with context(request) as (session, user):
            project = selected_project(session, user, project_id)
            events = session.scalars(
                select(m.AuditEvent)
                .where(
                    or_(
                        m.AuditEvent.project_id == project.id,
                        (
                            m.AuditEvent.project_id.is_(None)
                            & (m.AuditEvent.actor_id == user.id)
                        ),
                    )
                )
                .order_by(m.AuditEvent.id.desc())
                .limit(limit)
            )
            return [{**audit.payload(e), "event_hash": e.event_hash} for e in events]

    @app.get("/api/v1/audit/verify")
    def verify_chain(request: Request):
        with context(request) as (session, user):
            return audit.verify(session)

    @app.post("/api/v1/demo/reset")
    def reset(request: Request):
        if not settings.demo_mode:
            raise DomainError(404, "NOT_FOUND", "This endpoint is unavailable.")
        with context(request, True) as (session, user):
            require_role(user, "ADMIN")
            return seed(session, settings, reset=True)

    app.include_router(control_router(context))
    app.include_router(commercial_router(context))
    app.include_router(reporting_router(context))
    app.include_router(administration_router(context))
    from .auth_api import create_router as auth_router
    app.include_router(auth_router(context))
    from .mfa_api import create_router as mfa_router
    app.include_router(mfa_router(context))
    app.include_router(advanced_router(context))

    static = ROOT / "frontend" / "dist"
    if static.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Unknown API endpoint.",
                        }
                    },
                )
            return FileResponse(static / "index.html")

    return app


def get_app():
    return create_app()
