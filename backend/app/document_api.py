import json
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Request,
    UploadFile,
    File,
    Form,
    Query,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy import select

from . import models as m, documents, audit
from .security import (
    DomainError,
    project_access,
    require_role,
)
from .schemas import (
    CorrectionRequest,
)
from .money import canonical
from .schemas import (
    DocumentResponse,
)
from .interface_schemas import DocumentDetail, DocumentExtraction


from .api_support import context, entity, selected_project, document_view


def create_router(settings, engine, app):
    router = APIRouter(tags=["Document intake"])

    @router.post("/api/v1/documents/upload", status_code=201)
    async def upload_document(
        request: Request,
        project_id: Annotated[int, Form()],
        file: Annotated[UploadFile, File()],
    ):
        content = await file.read(settings.max_upload_bytes + 1)
        with context(request) as (session, user):
            project_access(session, user, project_id, write=True)
            require_role(user, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
        prepared = await run_in_threadpool(
            documents.prepare_upload, settings, file.filename or "document", content
        )
        try:
            with context(request, True) as (session, user):
                project_access(session, user, project_id, write=True)
                document, errors = documents.upload(
                    session,
                    settings,
                    user,
                    project_id,
                    file.filename or "document",
                    content,
                    prepared=prepared,
                )
                return {**document_view(document), "validation_errors": errors}
        except Exception:
            # Only the fresh generated storage name is removed after rollback.
            (settings.data_dir / "uploads" / prepared[0]).unlink(missing_ok=True)
            raise

    @router.get("/api/v1/documents", response_model=list[DocumentResponse])
    def list_documents(request: Request, project_id: int | None = None):
        with context(request) as (session, user):
            project = selected_project(session, user, project_id)
            return [
                document_view(d)
                for d in session.scalars(
                    select(m.Document)
                    .where(m.Document.project_id == project.id)
                    .order_by(m.Document.id.desc())
                )
            ]

    @router.get("/api/v1/documents/{document_id}", response_model=DocumentDetail)
    def document_detail(document_id: int, request: Request):
        with context(request) as (session, user):
            document = entity(session, user, m.Document, document_id)
            return {
                **document_view(document),
                "data": json.loads(document.extracted_json),
                "text": document.text,
            }

    @router.get(
        "/api/v1/documents/{document_id}/extraction", response_model=DocumentExtraction
    )
    def extraction(document_id: int, request: Request):
        with context(request) as (session, user):
            document = entity(session, user, m.Document, document_id)
            revisions = session.scalars(
                select(m.ExtractionRevision)
                .where(m.ExtractionRevision.document_id == document_id)
                .order_by(m.ExtractionRevision.version)
            )
            return {
                "document": document_view(document),
                "data": json.loads(document.extracted_json),
                "revisions": [
                    {
                        "version": r.version,
                        "fields": json.loads(r.fields_json),
                        "created_at": r.created_at,
                    }
                    for r in revisions
                ],
            }

    @router.patch("/api/v1/documents/{document_id}/extraction")
    def correct(document_id: int, body: CorrectionRequest, request: Request):
        with context(request, True) as (session, user):
            require_role(user, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
            document = entity(session, user, m.Document, document_id)
            project_access(session, user, document.project_id, write=True)
            if document.version != body.version:
                raise DomainError(
                    409, "STALE_VERSION", "Reload the latest extraction before saving."
                )
            if document.confirmed_by:
                raise DomainError(
                    409,
                    "CONFIRMED_EVIDENCE",
                    "Confirmed procurement evidence is immutable. Use a separately authorized variation or new source record.",
                )
            if (
                document.document_type != "UNKNOWN"
                and document.document_type != body.data.document_type
            ):
                raise DomainError(
                    422,
                    "TYPE_MISMATCH",
                    "Document classification cannot change after publication.",
                )
            document.document_type = body.data.document_type
            document.extracted_json = canonical(body.data.model_dump(mode="json"))
            document.reviewed_by = user.id
            document.version += 1
            document.extraction_status = "EXTRACTED"
            documents.revision(
                session,
                document,
                body.data.model_dump(mode="json"),
                "HUMAN_REVIEW",
                user,
            )
            if document.document_type == "INVOICE":
                documents.publish_invoice(session, document, body.data, user)
            audit.append(
                session,
                user,
                "HUMAN_CORRECTION",
                "document",
                document.id,
                {"version": document.version},
                document.project_id,
            )
            return document_view(document)

    @router.post("/api/v1/documents/{document_id}/confirm")
    def confirm_document(document_id: int, request: Request):
        with context(request, True) as (session, user):
            document = entity(session, user, m.Document, document_id)
            documents.confirm(session, document, user)
            return document_view(document)

    @router.get("/api/v1/documents/{document_id}/preview")
    def preview(
        document_id: int, request: Request, page: int = Query(default=1, ge=1, le=50)
    ):
        with context(request) as (session, user):
            document = entity(session, user, m.Document, document_id)
            from .private_storage import private_path
            path = private_path(settings.data_dir, "uploads", document.storage_name)
            if path.suffix == ".pdf":
                import subprocess, sys, base64

                try:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(Path(__file__).with_name("pdf_worker.py")),
                            str(path),
                            "--preview",
                            str(page),
                        ],
                        capture_output=True,
                        timeout=15,
                        check=True,
                        text=True,
                        encoding="utf-8",
                    )
                    return Response(
                        base64.b64decode(json.loads(result.stdout)["png"]),
                        media_type="image/png",
                    )
                except (subprocess.SubprocessError, ValueError, KeyError):
                    raise DomainError(
                        422, "PREVIEW_UNAVAILABLE", "Page could not be rendered safely."
                    )
            return Response(
                document.text,
                media_type="text/plain",
                headers={"Content-Disposition": "inline"},
            )

    return router
