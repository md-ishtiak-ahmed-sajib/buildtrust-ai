from .source_schemas import (
    MaterialView,
    QuotationView,
    ProviderView,
    ExchangeRateView,
    RecordedExchangeRateView,
    HistoricalSelectionView,
)
import hashlib
import json
from pathlib import Path
import httpx
import uuid
from fastapi import APIRouter, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse
from .private_storage import private_path
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import object_session
from . import (
    advanced_models as a,
    models as m,
    audit,
    pricing,
    estimating,
    finance,
    authorship,
    evidence as evidence_store,
)
from .advanced_schemas import (
    MaterialInput,
    SearchInput,
    QuotationInput,
    VersionAction,
    EquivalentInput,
    FXInput,
    FXFetchInput,
    SearchResponse,
    PriceComparison,
)
from .advanced_math import UNITS, nonnegative, unit_factor
from .advanced_imports import quotation_rows, pdf_suggestions
from .money import canonical
from .security import DomainError, project_access, require_role
from .price_providers import safe_url, api_json


from .upgrade_access import load, author


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Materials, prices and quotations"])

    def record_quote(session, actor, material, fields, extraction=None, **attachment):
        if fields.source_url:
            safe_url(fields.source_url)
        for key in (
            "price",
            "quoted_quantity",
            "minimum_quantity",
            "freight",
            "tax",
            "handling",
            "other_cost",
            "package_weight_kg",
            "density_kg_m3",
        ):
            value = getattr(fields, key)
            if value is not None:
                nonnegative(
                    value,
                    key,
                    key
                    in (
                        "price",
                        "quoted_quantity",
                        "package_weight_kg",
                        "density_kg_m3",
                    ),
                )
        record = a.Quotation(
            project_id=material.project_id,
            material_id=material.id,
            fields_json=canonical(
                fields.model_dump(mode="json", exclude={"expected_version"})
            ),
            prepared_by=actor.id,
            **attachment,
        )
        session.add(record)
        session.flush()
        authorship.contribute(session, "quotation", record, actor, "creation")
        evidence_store.append(
            session,
            actor,
            record,
            {
                "extraction": extraction or {"method": "MANUAL"},
                "fields": json.loads(record.fields_json),
            },
        )
        session.flush()
        audit.append(
            session,
            actor,
            "QUOTATION_DRAFTED",
            "quotation",
            record.id,
            {"attachment_hash": record.attachment_hash},
            record.project_id,
        )
        return record

    def quote_view(record):
        return {
            "id": record.id,
            "project_id": record.project_id,
            "material_id": record.material_id,
            "fields": json.loads(record.fields_json),
            "version": record.version,
            "status": record.status,
            "prepared_by": record.prepared_by,
            "contributors": authorship.contributors(
                object_session(record), "quotation", record.id
            ),
            "verified_by": record.verified_by,
            "filename": record.original_filename,
            "attachment_hash": record.attachment_hash,
            "created_at": record.created_at,
            "evidence_revisions": evidence_store.history(
                object_session(record), record
            ),
        }

    @router.get(
        "/materials",
        response_model=list[MaterialView],
        response_model_exclude_unset=True,
    )
    def materials(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                pricing.material_view(r)
                for r in session.scalars(
                    select(a.Material)
                    .where(
                        a.Material.project_id == project_id, a.Material.active.is_(True)
                    )
                    .order_by(a.Material.name)
                )
            ]

    @router.post(
        "/materials",
        status_code=201,
        response_model=MaterialView,
        response_model_exclude_unset=True,
    )
    def material_create(data: MaterialInput, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            project_access(session, actor, data.project_id, write=True)
            if data.unit not in UNITS:
                raise ValueError("Unsupported material unit")
            record = a.Material(
                project_id=data.project_id,
                name=data.name,
                category=data.category,
                unit=data.unit,
                specification_json=canonical(data.specification),
                created_by=actor.id,
            )
            session.add(record)
            session.flush()
            pricing.add_history(session, record)
            audit.append(
                session,
                actor,
                "MATERIAL_CREATED",
                "material",
                record.id,
                pricing.material_view(record),
                record.project_id,
            )
            return pricing.material_view(record)

    @router.get(
        "/materials/{identity}",
        response_model=MaterialView,
        response_model_exclude_unset=True,
    )
    def material_get(identity: int, request: Request):
        with context(request) as (session, actor):
            return pricing.material_view(load(session, actor, a.Material, identity))

    @router.patch(
        "/materials/{identity}",
        response_model=MaterialView,
        response_model_exclude_unset=True,
    )
    def material_update(identity: int, data: MaterialInput, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            record = load(session, actor, a.Material, identity, True)
            estimating.version_check(record, data.expected_version)
            if data.project_id != record.project_id or data.unit != record.unit:
                raise ValueError(
                    "Project and canonical unit cannot change; create a new material"
                )
            before = pricing.material_view(record)
            record.name, record.category, record.specification_json = (
                data.name,
                data.category,
                canonical(data.specification),
            )
            record.version += 1
            audit.append(
                session,
                actor,
                "MATERIAL_UPDATED",
                "material",
                record.id,
                {"before": before, "after": pricing.material_view(record)},
                record.project_id,
            )
            return pricing.material_view(record)

    @router.delete("/materials/{identity}")
    def material_archive(identity: int, request: Request, expected_version: int):
        with context(request, True) as (session, actor):
            require_role(actor, "ADMIN")
            record = load(session, actor, a.Material, identity, True)
            estimating.version_check(record, expected_version)
            record.active = False
            record.version += 1
            audit.append(
                session,
                actor,
                "MATERIAL_ARCHIVED",
                "material",
                identity,
                project_id=record.project_id,
            )
            return {"archived": True}

    @router.get(
        "/prices/providers",
        response_model=list[ProviderView],
        response_model_exclude_unset=True,
    )
    def providers(request: Request):
        with context(request):
            return pricing.provider_status(request.app.state.settings)

    @router.post(
        "/materials/{identity}/prices/refresh",
        status_code=202,
        response_model=SearchResponse,
    )
    def refresh(
        identity: int, data: SearchInput, request: Request, background: BackgroundTasks
    ):
        with context(request, True) as (session, actor):
            author(actor)
            material = load(session, actor, a.Material, identity, True)
            if not material.active:
                raise ValueError("Material is archived")
            project = session.get(m.Project, material.project_id)
            if data.currency != project.currency:
                raise ValueError(
                    "Comparison currency must match the project; source currencies use recorded FX"
                )
            record, cached = pricing.start_search(
                session, material, actor, data, request.app.state.settings
            )
            result = pricing.search_view(record, cached)
        if not cached:
            background.add_task(
                pricing.run_search,
                request.app.state.engine,
                request.app.state.settings,
                result["id"],
            )
        return result

    @router.get("/prices/searches/{identity}", response_model=SearchResponse)
    def search_get(identity: int, request: Request):
        with context(request) as (session, actor):
            return pricing.search_view(load(session, actor, a.PriceSearch, identity))

    @router.post(
        "/prices/searches/{identity}/retry",
        status_code=202,
        response_model=SearchResponse,
    )
    def search_retry(identity: int, request: Request, background: BackgroundTasks):
        with context(request, True) as (session, actor):
            author(actor)
            record = load(session, actor, a.PriceSearch, identity, True)
            from . import jobs

            jobs.ensure_retry(session, "price_search", identity)
            if record.status not in ("WAITING", "INTERRUPTED", "FAILED"):
                raise DomainError(
                    409,
                    "SEARCH_NOT_RETRYABLE",
                    "Only interrupted, waiting or failed searches can resume.",
                )
            states = json.loads(record.states_json)
            for state in states.values():
                if state["status"] == "SUBMITTING":
                    state["status"] = "UNKNOWN_SUBMISSION"
            if any(s["status"] == "UNKNOWN_SUBMISSION" for s in states.values()):
                raise DomainError(
                    409,
                    "UNKNOWN_SUBMISSION",
                    "Check the provider dashboard before creating a new paid task.",
                )
            record.status, record.states_json = "QUEUED", canonical(states)
            result = pricing.search_view(record)
        background.add_task(
            pricing.run_search,
            request.app.state.engine,
            request.app.state.settings,
            identity,
        )
        return result

    @router.get("/materials/{identity}/prices", response_model=PriceComparison)
    def prices(
        identity: int,
        request: Request,
        search_id: int | None = None,
        mode: str = "LIVE",
        quantity: str = "1",
        city: str = "Dhaka",
        country: str = "BD",
    ):
        with context(request) as (session, actor):
            material = load(session, actor, a.Material, identity)
            if search_id:
                search = load(session, actor, a.PriceSearch, search_id)
                if search.material_id != identity:
                    raise ValueError("Search belongs to a different material")
                values = json.loads(search.request_json)
                values.pop("query", None)
                data = SearchInput.model_validate(values)
            else:
                data = SearchInput(
                    mode=mode,
                    quantity=quantity,
                    city=city,
                    country=country,
                    unit=material.unit,
                    currency=session.get(m.Project, material.project_id).currency,
                )
            return pricing.compare(session, material, data, search_id)

    @router.get(
        "/prices/history",
        response_model=list[HistoricalSelectionView],
        response_model_exclude_unset=True,
    )
    def history(request: Request, project_id: int, material_id: int | None = None):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            rows = session.scalars(
                select(a.PriceSelection)
                .where(a.PriceSelection.project_id == project_id)
                .order_by(a.PriceSelection.id.desc())
                .limit(200)
            )
            return [
                {
                    "id": r.id,
                    "estimate_id": r.estimate_id,
                    "created_at": r.created_at,
                    "actor_id": r.actor_id,
                    "reason": r.reason,
                    "snapshot_hash": r.snapshot_hash,
                    "snapshot": json.loads(r.snapshot_json),
                }
                for r in rows
                if not material_id
                or json.loads(r.snapshot_json)["material"]["id"] == material_id
            ]

    @router.post("/materials/{identity}/history/refresh")
    def refresh_history(identity: int, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            material = load(session, actor, a.Material, identity, True)
            if not material.active:
                raise ValueError("Material is archived")
            count = pricing.add_history(session, material)
            audit.append(
                session,
                actor,
                "HISTORICAL_PRICES_REFRESHED",
                "material",
                identity,
                {"snapshots": count},
                material.project_id,
            )
            return {
                "snapshots": count,
                "notice": "Append-only approved purchase history; unknown specifications and charges remain unknown.",
            }

    @router.post("/materials/{identity}/equivalents", status_code=201)
    def equivalent(identity: int, data: EquivalentInput, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "FINANCE_MANAGER", "ADMIN")
            material = load(session, actor, a.Material, identity, True)
            observed = load(session, actor, a.PriceObservation, data.observation_id)
            if observed.material_id != identity:
                raise ValueError("Observation belongs to another material")
            creator = (
                session.get(a.Quotation, observed.quotation_id).prepared_by
                if observed.quotation_id
                else material.created_by
            )
            retained = (
                authorship.contributors(session, "quotation", observed.quotation_id)
                if observed.quotation_id
                else []
            )
            if creator == actor.id or actor.id in retained:
                raise DomainError(
                    403,
                    "SELF_CHECK",
                    "An independent person must approve engineering equivalence.",
                )
            record = a.MaterialEquivalent(
                project_id=material.project_id,
                material_id=identity,
                observation_id=observed.id,
                approved_by=actor.id,
                reason=data.reason,
                material_version=material.version,
            )
            session.add(record)
            session.flush()
            audit.append(
                session,
                actor,
                "MATERIAL_EQUIVALENT_APPROVED",
                "material",
                identity,
                data.model_dump(),
                material.project_id,
            )
            return {
                "id": record.id,
                "status": "APPROVED",
                "material_version": material.version,
            }

    @router.get(
        "/quotations",
        response_model=list[QuotationView],
        response_model_exclude_unset=True,
    )
    def quotations(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                quote_view(q)
                for q in session.scalars(
                    select(a.Quotation)
                    .where(a.Quotation.project_id == project_id)
                    .order_by(a.Quotation.id.desc())
                )
            ]

    @router.post(
        "/quotations",
        status_code=201,
        response_model=QuotationView,
        response_model_exclude_unset=True,
    )
    def quotation_create(data: QuotationInput, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            material = load(session, actor, a.Material, data.material_id, True)
            return quote_view(record_quote(session, actor, material, data))

    @router.post(
        "/prices/observations/{identity}/quotation-draft",
        status_code=201,
        response_model=QuotationView,
        response_model_exclude_unset=True,
    )
    def listing_quotation(identity: int, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            observed = load(session, actor, a.PriceObservation, identity, True)
            payload = json.loads(observed.payload_json)
            material = load(session, actor, a.Material, observed.material_id, True)
            allowed = set(QuotationInput.model_fields) - {
                "expected_version",
                "source_type",
                "material_id",
            }
            values = {
                k: v for k, v in payload.items() if k in allowed and v is not None
            }
            # Listing text remains indicative; conversion to a draft grants no
            # supplier authority and fills no unknown charge with zero.
            values.update(
                material_id=material.id,
                supplier=values.get("supplier") or "Needs review",
                title=values.get("title") or material.name,
                source_type="SUPPLIER_QUOTE",
            )
            values.setdefault("freight_basis", "UNKNOWN")
            values.setdefault("tax_basis", "UNKNOWN")
            return quote_view(
                record_quote(
                    session,
                    actor,
                    material,
                    QuotationInput.model_validate(values),
                    extraction={
                        "method": "LISTING_TO_DRAFT",
                        "observation_id": observed.id,
                        "source_evidence_hash": observed.evidence_hash,
                        "original": payload,
                        "review_required": True,
                    },
                )
            )

    @router.patch(
        "/quotations/{identity}",
        response_model=QuotationView,
        response_model_exclude_unset=True,
    )
    def quotation_update(identity: int, data: QuotationInput, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            record = load(session, actor, a.Quotation, identity, True)
            estimating.version_check(record, data.expected_version)
            if record.status != "DRAFT" or data.material_id != record.material_id:
                raise DomainError(
                    409,
                    "QUOTATION_LOCKED",
                    "Verified quotations are immutable; create a new quotation.",
                )
            if data.source_url:
                safe_url(data.source_url)
            before = json.loads(record.fields_json)
            record.fields_json = canonical(
                data.model_dump(mode="json", exclude={"expected_version"})
            )
            authorship.contribute(session, "quotation", record, actor)
            record.prepared_by = actor.id
            record.version += 1
            evidence_store.append(
                session,
                actor,
                record,
                {
                    "method": "REVIEWED_CORRECTION",
                    "before": before,
                    "after": json.loads(record.fields_json),
                },
            )
            audit.append(
                session,
                actor,
                "QUOTATION_CORRECTED",
                "quotation",
                identity,
                {"before": before, "after": json.loads(record.fields_json)},
                record.project_id,
            )
            return quote_view(record)

    @router.post(
        "/quotations/{identity}/verify",
        response_model=QuotationView,
        response_model_exclude_unset=True,
    )
    def quotation_verify(identity: int, data: VersionAction, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "FINANCE_MANAGER", "ADMIN")
            record = load(session, actor, a.Quotation, identity, True)
            estimating.version_check(record, data.expected_version)
            if actor.id == record.prepared_by or actor.id in authorship.contributors(
                session, "quotation", record.id
            ):
                raise DomainError(
                    403, "SELF_CHECK", "A different person must verify this quotation."
                )
            if record.status != "DRAFT":
                raise DomainError(
                    409, "QUOTATION_LOCKED", "Quotation is already verified."
                )
            fields = QuotationInput.model_validate_json(record.fields_json)
            if (
                fields.price is None
                or not fields.unit
                or fields.supplier.strip().lower() == "needs review"
            ):
                raise ValueError("Price and unit require human entry or confirmation")
            nonnegative(fields.price, "Price", True)
            unit_factor(
                fields.unit,
                session.get(a.Material, record.material_id).unit,
                fields.package_weight_kg,
                fields.density_kg_m3,
                fields.density_assumption,
            )
            if fields.valid_until and fields.valid_until < finance.business_date():
                raise ValueError(
                    "An expired quotation cannot be verified for selection"
                )
            if fields.source_type == "OFFICIAL_REFERENCE" and not (
                fields.edition and fields.effective_date and fields.source_url
            ):
                raise ValueError(
                    "Official references require edition, effective date and source URL"
                )
            record.status, record.verified_by = "VERIFIED", actor.id
            record.version += 1
            payload = fields.model_dump(
                mode="json", exclude={"expected_version", "material_id"}
            )
            payload.update(
                verification="HUMAN_VERIFIED",
                verified_by=actor.id,
                attachment_hash=record.attachment_hash,
            )
            observed = pricing.observation(
                session,
                session.get(a.Material, record.material_id),
                payload,
                "supplier" if fields.source_type == "SUPPLIER_QUOTE" else "reference",
                fields.source_type,
                quotation_id=record.id,
            )
            audit.append(
                session,
                actor,
                "QUOTATION_VERIFIED",
                "quotation",
                identity,
                {
                    "observation_id": observed.id,
                    "evidence_hash": observed.evidence_hash,
                },
                record.project_id,
            )
            return quote_view(record)

    @router.post("/quotations/import", status_code=201)
    async def quotation_import(
        request: Request,
        material_id: int = Form(...),
        metadata: str = Form("{}"),
        file: UploadFile = File(...),
    ):
        from fastapi.concurrency import run_in_threadpool

        settings = request.app.state.settings
        contents = await file.read(settings.max_upload_bytes + 1)
        if len(contents) > settings.max_upload_bytes:
            raise DomainError(413, "UPLOAD_TOO_LARGE", "Maximum upload is 10 MB.")
        extension = Path(file.filename or "").suffix.lower()
        values = json.loads(metadata)
        if not isinstance(values, dict):
            raise ValueError("Quotation metadata must be a JSON object")
        with context(request) as (session, actor):
            author(actor)
            material = load(session, actor, a.Material, material_id, True)
            material_name, material_version = material.name, material.version
        if extension not in (".csv", ".xlsx", ".pdf"):
            raise ValueError("Supported formats are CSV, XLSX and PDF")
        if extension == ".pdf" and not contents.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF content")
        storage = uuid.uuid4().hex + extension
        from .private_storage import private_path, protect_file
        path = private_path(settings.data_dir, "uploads", storage)
        path.write_bytes(contents)
        protect_file(path)
        try:
            if extension == ".pdf":
                suggestions, evidence = await run_in_threadpool(
                    pdf_suggestions, path, settings
                )
                base = {
                    "supplier": "Needs review",
                    "title": material_name,
                    "material_id": material_id,
                }
                for key, value in suggestions.items():
                    try:
                        QuotationInput.model_validate({**base, key: value})
                        base[key] = value
                    except ValidationError:
                        evidence["fields"][key]["rejected_suggestion"] = True
                records = [
                    QuotationInput.model_validate(
                        {**base, **values, "material_id": material_id}
                    )
                ]
            else:
                records = await run_in_threadpool(
                    quotation_rows, contents, extension, material_id, values
                )
                evidence = {
                    "method": "CSV_SCHEMA" if extension == ".csv" else "XLSX_SCHEMA",
                    "rows": len(records),
                    "review_required": True,
                }
            with context(request, True) as (session, actor):
                author(actor)
                material = load(session, actor, a.Material, material_id, True)
                estimating.version_check(material, material_version)
                result = [
                    quote_view(
                        record_quote(
                            session,
                            actor,
                            material,
                            fields,
                            storage_name=storage,
                            original_filename=Path(file.filename or "upload").name,
                            attachment_hash=hashlib.sha256(contents).hexdigest(),
                            extraction=evidence,
                        )
                    )
                    for fields in records
                ]
                return {"quotations": result, "extraction": evidence}
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @router.get("/quotations/{identity}/attachment")
    def attachment(identity: int, request: Request):
        with context(request) as (session, actor):
            record = load(session, actor, a.Quotation, identity)
            if not record.storage_name:
                raise DomainError(404, "NOT_FOUND", "No attachment is stored.")
            return FileResponse(
                private_path(request.app.state.settings.data_dir, "uploads", record.storage_name),
                filename=record.original_filename,
                media_type="application/octet-stream",
            )

    @router.post(
        "/prices/exchange-rates",
        status_code=201,
        response_model=RecordedExchangeRateView,
        response_model_exclude_unset=True,
    )
    def exchange_create(data: FXInput, request: Request):
        with context(request, True) as (session, actor):
            require_role(actor, "FINANCE_MANAGER", "ADMIN")
            project_access(session, actor, data.project_id, write=True)
            nonnegative(data.factor, "Exchange factor", True)
            if data.observed_date > finance.business_date() or data.base == data.quote:
                raise ValueError(
                    "Use a recorded non-future date and different currencies"
                )
            record = a.ExchangeRate(
                project_id=data.project_id,
                base=data.base,
                quote=data.quote,
                factor=data.factor,
                source=data.source,
                observed_date=data.observed_date.isoformat(),
                actor_id=actor.id,
            )
            session.add(record)
            session.flush()
            audit.append(
                session,
                actor,
                "EXCHANGE_RATE_RECORDED",
                "exchange_rate",
                record.id,
                data.model_dump(mode="json"),
                data.project_id,
            )
            return {"id": record.id, **data.model_dump(mode="json")}

    @router.post(
        "/prices/exchange-rates/fetch",
        status_code=201,
        response_model=RecordedExchangeRateView,
        response_model_exclude_unset=True,
    )
    async def exchange_fetch(data: FXFetchInput, request: Request):
        with context(request) as (session, actor):
            require_role(actor, "FINANCE_MANAGER", "ADMIN")
            project_access(session, actor, data.project_id, write=True)
        try:
            result = await api_json(
                "GET",
                f"https://api.frankfurter.dev/v2/rate/{data.base.lower()}/{data.quote.lower()}",
                request.app.state.settings,
                params={"expand": "providers"},
            )
        except (httpx.HTTPError, ValueError):
            raise DomainError(
                502,
                "EXCHANGE_RATE_UNAVAILABLE",
                "Rate provider or currency pair unavailable. Enter an explicitly sourced manual rate or retry later.",
            )
        if not result.get("rate") or not result.get("date"):
            raise ValueError(
                "Pair unavailable; provide an explicitly sourced manual exchange rate"
            )
        # Pair responses expand providers into objects; store compact identifiers
        # and their observation dates rather than Python object representations.
        providers = result.get("providers", [])
        if not isinstance(providers, list) or len(providers) > 104:
            raise ValueError(
                "Unexpected FX attribution response; enter a sourced manual observation"
            )
        attribution = (
            ",".join(
                (str(item.get("key", "")) + "@" + str(item.get("date", result["date"])))
                if isinstance(item, dict)
                else str(item)
                for item in providers
            )
            or "peg or blended feed; see provider documentation"
        )
        return exchange_create(
            FXInput(
                **data.model_dump(),
                factor=str(result["rate"]),
                observed_date=result["date"],
                source="https://api.frankfurter.dev/v2/rate/"
                + data.base.lower()
                + "/"
                + data.quote.lower()
                + "; providers="
                + attribution,
            ),
            request,
        )

    @router.get(
        "/prices/exchange-rates",
        response_model=list[ExchangeRateView],
        response_model_exclude_unset=True,
    )
    def exchange_list(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                {
                    "id": r.id,
                    "base": r.base,
                    "quote": r.quote,
                    "factor": r.factor,
                    "source": r.source,
                    "date": r.observed_date,
                }
                for r in session.scalars(
                    select(a.ExchangeRate)
                    .where(a.ExchangeRate.project_id == project_id)
                    .order_by(a.ExchangeRate.id.desc())
                    .limit(100)
                )
            ]

    return router
