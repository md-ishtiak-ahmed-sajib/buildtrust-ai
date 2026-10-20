from contextlib import contextmanager
from sqlalchemy import select
from . import models as m, payments
from .database import transaction
from .money import money, minor
from .security import DomainError, authenticate, project_access


def user_view(user, settings):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "approval_limit": money(
            minor(settings.admin_ceiling)
            if user.role == "ADMIN"
            else 10000000
            if user.role == "FINANCE_MANAGER"
            else 0
        ),
    }


def project_view(project):
    return {
        "id": project.id,
        "code": project.code,
        "name": project.name,
        "client": project.client,
        "currency": project.currency,
        "budget": money(project.budget_minor),
        "balance": money(project.balance_minor),
        "minimum_reserve": money(project.reserve_minor),
        "run_id": project.run_id,
        "active": project.active,
    }


def document_view(doc):
    return {
        "id": doc.id,
        "project_id": doc.project_id,
        "document_type": doc.document_type,
        "original_filename": doc.original_filename,
        "sha256": doc.sha256,
        "extraction_status": doc.extraction_status,
        "version": doc.version,
        "reviewed_by": doc.reviewed_by,
        "confirmed_by": doc.confirmed_by,
        "created_at": doc.created_at,
    }


def invoice_view(session, invoice):
    supplier = (
        session.get(m.Supplier, invoice.supplier_id) if invoice.supplier_id else None
    )
    return {
        "id": invoice.id,
        "project_id": invoice.project_id,
        "document_id": invoice.document_id,
        "invoice_number": invoice.number,
        "supplier": supplier.name if supplier else invoice.supplier_code,
        "supplier_code": invoice.supplier_code,
        "currency": invoice.currency,
        "subtotal": money(invoice.subtotal_minor),
        "tax": money(invoice.tax_minor),
        "retention": money(invoice.retention_minor),
        "discount": money(invoice.discount_minor),
        "grand_total": money(invoice.total_minor),
        "status": invoice.status,
        "invoice_date": invoice.invoice_date,
        "version": invoice.version,
    }


@contextmanager
def context(request, write=False):
    # Admission commits before opening the business transaction. Never nest a
    # quota writer inside an existing financial writer lock.
    if not getattr(request.state, "admission_checked", False):
        request.state.admission_checked = True
        path, method = request.url.path, request.method
        group, limit = None, 10
        if path.endswith("/preview"):
            group, limit = "preview", 30
        elif method == "POST" and path.endswith("/prices/refresh"):
            group, limit = "price", 5
        elif method == "POST" and path == "/api/v1/administration/users":
            group, limit = "account-create", 5
        elif (method == "POST" and any(p in path for p in ("/documents", "/import", "/agent/analyze", "/retry", "/agent/ask", "/copilot"))) or any(p in path for p in ("/export", "/attachment")):
            group = "expensive"
        if group:
            header = request.headers.get("authorization", "")
            with transaction(request.app.state.engine) as pre:
                actor = authenticate(pre, header[7:] if header.startswith("Bearer ") else "", request.app.state.secret)
                actor_id = actor.id
            from .admission import consume
            consume(request.app.state.engine, [(f"{group}:{actor_id}", limit, 60)])
    with transaction(request.app.state.engine, write) as session:
        session.info["api_write"] = write
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            raise DomainError(401, "UNAUTHENTICATED", "Sign in to continue.")
        user = authenticate(session, header[7:], request.app.state.secret)
        request.state.actor_id = user.id
        if write:
            payments.expire(session)
        yield session, user


def entity(session, user, model, identity):
    value = session.get(model, identity)
    if not value:
        raise DomainError(404, "NOT_FOUND", "Resource is unavailable.")
    project_id = (
        value.project_id
        if hasattr(value, "project_id")
        else session.get(m.Invoice, value.invoice_id).project_id
    )
    project_access(session, user, project_id)
    return value


def allowed_projects(session, user):
    return list(
        session.scalars(
            select(m.Project)
            .join(m.Membership)
            .where(m.Membership.user_id == user.id, m.Project.active.is_(True))
            .order_by(m.Project.id)
        )
    )


def selected_project(session, user, project_id=None):
    if project_id:
        return project_access(session, user, project_id)
    projects = allowed_projects(session, user)
    if not projects:
        raise DomainError(404, "NOT_FOUND", "No assigned project is available.")
    return projects[0]
