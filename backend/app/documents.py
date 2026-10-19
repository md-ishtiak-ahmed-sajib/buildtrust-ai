import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
from pydantic import ValidationError
from sqlalchemy import select

from . import audit
from .diagnostics import timed
from .bounded_json import loads as bounded_loads
from .models import (
    Document,
    ExtractionRevision,
    BOQItem,
    Variation,
    Supplier,
    PurchaseOrder,
    POLine,
    GoodsReceipt,
    ReceiptLine,
    Invoice,
    InvoiceLine,
    Proposal,
    Reservation,
    ReceiptAllocation,
)
from .schemas import DocumentInput
from .security import DomainError, require_role, project_access
from .money import canonical, minor, decimal


def parse_file(path, extension, settings=None):
    if extension == ".json":
        text = path.read_text(encoding="utf-8-sig")
        data = bounded_loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON must contain one document object")
        return data, text, "JSON_SCHEMA", False, {}
    if extension == ".csv":
        text = path.read_text(encoding="utf-8-sig")
        from .advanced_imports import table_rows
        rows = table_rows(path.read_bytes(), ".csv")
        if not rows or len(rows) > 500:
            raise ValueError("CSV requires 1–500 data rows")
        item_keys = {
            "item_code",
            "description",
            "quantity",
            "unit",
            "unit_rate",
            "amount",
        }
        data = {k: v for k, v in rows[0].items() if k and k not in item_keys and v}
        data["items"] = [
            {k: v for k, v in row.items() if k in item_keys and v} for row in rows
        ]
        for row in rows[1:]:
            if any(row.get(k) and row[k] != v for k, v in data.items() if k != "items"):
                raise ValueError("CSV document metadata must agree on every row")
        return data, text, "CSV_SCHEMA", False, {}
    if extension == ".pdf":
        from .ocr import worker_args
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("pdf_worker.py")), str(path), *worker_args(settings)],
            capture_output=True,
            timeout=45 if settings and settings.ocr_enabled else 15,
            check=True,
            text=True,
            encoding="utf-8",
        )
        extracted = json.loads(result.stdout)
        text = "\f".join(extracted["pages"])
        data, items = {}, []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("ITEM|"):
                cells = line.split("|")[1:]
                if len(cells) == 6:
                    items.append(
                        dict(
                            zip(
                                [
                                    "item_code",
                                    "description",
                                    "quantity",
                                    "unit",
                                    "unit_rate",
                                    "amount",
                                ],
                                cells,
                            )
                        )
                    )
            elif ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                if key in DocumentInput.model_fields and key != "items":
                    data[key] = value.strip()
        data["items"] = items
        return (
            data,
            text,
            "PDF_TEXT_TABLE",
            True,
            {"pages": len(extracted["pages"]), "tables": extracted["tables"],
             "page_evidence":extracted.get("page_evidence",[]),"ocr":extracted.get("ocr",{})},
        )
    raise ValueError("Unsupported file type")


def fields(data, document, method, actor_id=None):
    result = []

    def visit(value, prefix="", row=None):
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{prefix}.{key}" if prefix else key, row)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(
                    item,
                    f"{prefix}.{index}",
                    index + 2 if method == "CSV_SCHEMA" else None,
                )
        else:
            page_matches = (
                [
                    i + 1
                    for i, page_text in enumerate(document.text.split("\f"))
                    if str(value) and str(value) in page_text
                ]
                if method == "PDF_TEXT_TABLE"
                else []
            )
            result.append(
                {
                    "path": prefix,
                    "value": str(value),
                    "source_document_id": document.id,
                    "page": page_matches[0] if len(page_matches) == 1 else None,
                    "row": row,
                    "extraction_method": method,
                    "confidence": None,
                    "human_reviewed": actor_id is not None,
                    "reviewed_by": actor_id,
                }
            )

    visit(data, row=2 if method == "CSV_SCHEMA" else None)
    return result


def revision(session, document, data, method, actor=None):
    session.add(
        ExtractionRevision(
            document_id=document.id,
            version=document.version,
            fields_json=canonical(
                fields(data, document, method, actor.id if actor else None)
            ),
            actor_id=actor.id if actor else None,
        )
    )


def release_proposals(session, invoice_id):
    for proposal in session.scalars(
        select(Proposal).where(
            Proposal.invoice_id == invoice_id,
            Proposal.status.in_(["PENDING_APPROVAL", "APPROVED"]),
        )
    ):
        proposal.status = "EXPIRED"
        for r in session.scalars(
            select(Reservation).where(Reservation.proposal_id == proposal.id)
        ):
            r.state = "RELEASED"
        for a in session.scalars(
            select(ReceiptAllocation).where(
                ReceiptAllocation.proposal_id == proposal.id
            )
        ):
            a.state = "RELEASED"


def publish_invoice(session, document, data, actor):
    duplicate = session.scalar(
        select(Invoice).where(
            Invoice.project_id == document.project_id,
            Invoice.supplier_code == data.supplier_code,
            Invoice.number == data.invoice_number,
            Invoice.document_id != document.id,
        )
    )
    if duplicate:
        document.extraction_status = "DUPLICATE"
        audit.append(
            session,
            actor,
            "DUPLICATE_INVOICE",
            "document",
            document.id,
            {"existing_invoice_id": duplicate.id},
            document.project_id,
        )
        return None
    supplier = session.scalar(
        select(Supplier).where(
            Supplier.project_id == document.project_id,
            Supplier.code == data.supplier_code,
        )
    )
    po = session.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.project_id == document.project_id,
            PurchaseOrder.number == data.po_number,
        )
    )
    invoice = session.scalar(select(Invoice).where(Invoice.document_id == document.id))
    if invoice and invoice.status == "SETTLED":
        raise DomainError(409, "ALREADY_PAID", "A settled invoice is immutable.")
    if invoice:
        release_proposals(session, invoice.id)
        for old in session.scalars(
            select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
        ):
            old.active = False
        invoice.version += 1
    else:
        invoice = Invoice(project_id=document.project_id, document_id=document.id)
        session.add(invoice)
    for key, value in {
        "supplier_id": supplier.id if supplier else None,
        "supplier_code": data.supplier_code,
        "po_id": po.id if po else None,
        "number": data.invoice_number,
        "invoice_date": data.invoice_date.isoformat(),
        "currency": data.currency,
        "subtotal_minor": minor(data.subtotal),
        "tax_minor": minor(data.tax),
        "retention_minor": minor(data.retention),
        "discount_minor": minor(data.discount),
        "total_minor": minor(data.grand_total),
        "beneficiary_fingerprint": data.beneficiary_fingerprint,
        "status": "PENDING_REVIEW",
    }.items():
        setattr(invoice, key, value)
    session.flush()
    for item in data.items:
        session.add(
            InvoiceLine(
                invoice_id=invoice.id,
                item_code=item.item_code,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                rate=item.unit_rate,
                amount_minor=minor(item.amount)
                if item.amount is not None
                else minor(decimal(item.quantity) * decimal(item.unit_rate)),
            )
        )
    document.extraction_status = "EXTRACTED"
    return invoice


def confirm(session, document, actor):
    project_access(session, actor, document.project_id, write=True)
    try:
        data = DocumentInput.model_validate_json(document.extracted_json)
    except ValidationError:
        raise DomainError(
            422,
            "DOCUMENT_REVIEW_REQUIRED",
            "Review and save a complete valid extraction before confirming.",
        )
    if document.document_type == "INVOICE":
        require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
        if document.extraction_status == "NEEDS_REVIEW" and not document.reviewed_by:
            raise DomainError(
                409,
                "DOCUMENT_REVIEW_REQUIRED",
                "Review and save the extracted fields first.",
            )
        publish_invoice(session, document, data, actor)
    else:
        require_role(
            actor,
            *(
                ["ADMIN"]
                if document.document_type in ("BOQ", "VARIATION")
                else ["FINANCE_MANAGER", "ADMIN"]
            ),
        )
        if document.confirmed_by:
            raise DomainError(
                409, "ALREADY_CONFIRMED", "Procurement evidence is already confirmed."
            )
        if data.document_type == "BOQ":
            for item in data.items:
                if session.scalar(
                    select(BOQItem).where(
                        BOQItem.project_id == document.project_id,
                        BOQItem.item_code == item.item_code,
                    )
                ):
                    raise DomainError(
                        409,
                        "USE_VARIATION",
                        "Existing BOQ scope requires a separately approved variation.",
                    )
                session.add(
                    BOQItem(
                        project_id=document.project_id,
                        document_id=document.id,
                        item_code=item.item_code,
                        description=item.description,
                        unit=item.unit,
                        quantity=item.quantity,
                        rate=item.unit_rate,
                    )
                )
        elif data.document_type == "VARIATION":
            for item in data.items:
                boq = session.scalar(
                    select(BOQItem).where(
                        BOQItem.project_id == document.project_id,
                        BOQItem.item_code == item.item_code,
                    )
                )
                if not boq:
                    raise DomainError(
                        422, "UNKNOWN_ITEM", "Variation requires an existing BOQ item."
                    )
                session.add(
                    Variation(
                        boq_item_id=boq.id,
                        document_id=document.id,
                        quantity=item.quantity,
                        unit=item.unit,
                        approved_by=actor.id,
                    )
                )
                boq.version += 1
        elif data.document_type == "PO":
            supplier = session.scalar(
                select(Supplier).where(
                    Supplier.project_id == document.project_id,
                    Supplier.code == data.supplier_code,
                    Supplier.approved.is_(True),
                )
            )
            if not supplier:
                raise DomainError(
                    422, "UNKNOWN_SUPPLIER", "PO requires an approved supplier master."
                )
            po = PurchaseOrder(
                project_id=document.project_id,
                document_id=document.id,
                supplier_id=supplier.id,
                number=data.po_number,
                currency=data.currency,
                tax_percent=data.tax_percent,
                retention_percent=data.retention_percent,
                discount_minor=minor(data.discount),
            )
            session.add(po)
            session.flush()
            for item in data.items:
                session.add(
                    POLine(
                        po_id=po.id,
                        item_code=item.item_code,
                        description=item.description,
                        quantity=item.quantity,
                        unit=item.unit,
                        rate=item.unit_rate,
                    )
                )
        elif data.document_type == "GRN":
            po = session.scalar(
                select(PurchaseOrder).where(
                    PurchaseOrder.project_id == document.project_id,
                    PurchaseOrder.number == data.po_number,
                )
            )
            if not po:
                raise DomainError(
                    422,
                    "MISSING_PO",
                    "Receipt requires an approved PO in this project.",
                )
            receipt = GoodsReceipt(
                po_id=po.id,
                document_id=document.id,
                number=data.receipt_number,
                approved_by=actor.id,
            )
            session.add(receipt)
            session.flush()
            for item in data.items:
                session.add(
                    ReceiptLine(
                        receipt_id=receipt.id,
                        item_code=item.item_code,
                        quantity=item.quantity,
                        unit=item.unit,
                    )
                )
        document.confirmed_by = actor.id
        document.extraction_status = "CONFIRMED"
    audit.append(
        session,
        actor,
        "DOCUMENT_CONFIRMED",
        "document",
        document.id,
        {"type": document.document_type},
        document.project_id,
    )


@timed("document_parser")
def prepare_upload(settings, filename, content):
    """File I/O and bounded parsing run before acquiring the financial writer."""
    extension = Path(filename.replace("\\", "/")).suffix.lower()
    if extension not in (".json", ".csv", ".pdf"):
        raise DomainError(415, "UNSUPPORTED_FILE", "Upload PDF, CSV, or JSON.")
    if not content or len(content) > settings.max_upload_bytes:
        raise DomainError(
            413, "UPLOAD_LIMIT", "File must be nonempty and at most 10 MB."
        )
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise DomainError(415, "INVALID_SIGNATURE", "The content is not a PDF.")
    storage_name = uuid.uuid4().hex + extension
    path = settings.data_dir / "uploads" / storage_name
    path.write_bytes(content)
    try:
        extracted = parse_file(path, extension, settings)
    except (ValueError, UnicodeError, subprocess.SubprocessError, KeyError, AttributeError) as exc:
        path.unlink(missing_ok=True)
        raise DomainError(422, "EXTRACTION_FAILED", "File could not be parsed safely. Use the documented schema or reviewable PDF.") from exc
    return storage_name, extracted


def upload(session, settings, actor, project_id, filename, content, prepared=None):
    project_access(session, actor, project_id, write=True)
    require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
    storage_name, extracted = prepared or prepare_upload(settings, filename, content)
    path = settings.data_dir / "uploads" / storage_name
    sha = hashlib.sha256(content).hexdigest()
    duplicate = session.scalar(
        select(Document).where(
            Document.project_id == project_id, Document.sha256 == sha
        )
    )
    try:
        data, text, method, needs_review, extra = extracted
        validation = None
        try:
            parsed = DocumentInput.model_validate(data)
            data = parsed.model_dump(mode="json")
        except ValidationError as exc:
            validation = [
                {"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()
            ]
            needs_review = True
        doc_type = (
            data.get("document_type", "UNKNOWN")
            if isinstance(data, dict)
            else "UNKNOWN"
        )
        document = Document(
            project_id=project_id,
            document_type=doc_type,
            original_filename=Path(filename.replace("\\", "/")).name[:240],
            storage_name=storage_name,
            sha256=sha,
            extraction_status="NEEDS_REVIEW" if needs_review else "EXTRACTED",
            extracted_json=canonical(data),
            text=text[:250000],
        )
        session.add(document)
        session.flush()
        revision(session, document, data, method)
        audit.append(
            session,
            actor,
            "DOCUMENT_UPLOADED",
            "document",
            document.id,
            {"sha256": sha, "filename": document.original_filename},
            project_id,
        )
        if duplicate:
            document.extraction_status = "DUPLICATE"
            audit.append(
                session,
                actor,
                "DUPLICATE_INVOICE",
                "document",
                document.id,
                {"duplicate_document_id": duplicate.id},
                project_id,
            )
        elif not needs_review and doc_type == "INVOICE":
            publish_invoice(session, document, parsed, actor)
        audit.append(
            session,
            actor,
            "DOCUMENT_EXTRACTED",
            "document",
            document.id,
            {
                "method": method,
                "status": document.extraction_status,
                "validation_errors": validation,
                **extra,
            },
            project_id,
        )
        return document, validation
    except (
        ValueError,
        UnicodeError,
        subprocess.SubprocessError,
        KeyError,
        AttributeError,
    ) as exc:
        path.unlink(missing_ok=True)
        raise DomainError(
            422,
            "EXTRACTION_FAILED",
            "File could not be parsed safely. Use the documented CSV/JSON schema or a readable PDF.",
        ) from exc
