from .calculation_schemas import (
    EstimateForecast,
    EstimateDifference,
    CostControl,
    PriceSelectionPreview,
)
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy import select
from . import (
    advanced_models as a,
    models as m,
    audit,
    pricing,
    estimating,
    authorship,
)
from .advanced_schemas import (
    SearchInput,
    VersionAction,
    EstimateCreate,
    EstimateUpdate,
    SelectPriceInput,
    EstimateFields,
    EstimateResponse,
)
from .advanced_imports import export_table, boq_import
from .money import canonical, digest, decimal, utcnow
from .security import DomainError, project_access


from .upgrade_access import load, author


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["BOQs and estimates"])

    @router.get("/estimates", response_model=list[EstimateResponse])
    def estimates_list(request: Request, project_id: int):
        with context(request) as (session, actor):
            project_access(session, actor, project_id)
            return [
                estimating.estimate_view(r)
                for r in session.scalars(
                    select(a.Estimate)
                    .where(a.Estimate.project_id == project_id)
                    .order_by(a.Estimate.id.desc())
                )
            ]

    @router.post("/estimates", status_code=201, response_model=EstimateResponse)
    def estimate_create(data: EstimateCreate, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            project = project_access(session, actor, data.project_id, write=True)
            return estimating.estimate_view(
                estimating.create_estimate(
                    session, actor, project, data.name, data.import_boq
                )
            )

    @router.get("/estimates/{identity}", response_model=EstimateResponse)
    def estimate_get(identity: int, request: Request):
        with context(request) as (session, actor):
            return estimating.estimate_view(load(session, actor, a.Estimate, identity))

    @router.patch("/estimates/{identity}", response_model=EstimateResponse)
    def estimate_update(identity: int, data: EstimateUpdate, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            record = load(session, actor, a.Estimate, identity, True)
            estimating.version_check(record, data.expected_version)
            estimating.writable(record)
            before = digest(record.fields_json)
            record.name = data.name
            estimating.calculate(session, record, data.fields)
            authorship.contribute(session, "estimate", record, actor)
            record.prepared_by = actor.id
            record.version += 1
            audit.append(
                session,
                actor,
                "ESTIMATE_UPDATED",
                "estimate",
                identity,
                {
                    "before_hash": before,
                    "after": json.loads(record.fields_json),
                    "version": record.version,
                },
                record.project_id,
            )
            return estimating.estimate_view(record)

    def estimate_action(
        identity: int, action: str, data: VersionAction, request: Request
    ):
        if action not in ("submit", "check", "approve", "revise", "recalculate"):
            raise DomainError(404, "NOT_FOUND", "Unknown estimate action.")
        with context(request, True) as (session, actor):
            record = load(session, actor, a.Estimate, identity, True)
            if action == "revise":
                author(actor)
                record = estimating.revise(
                    session, actor, record, data.expected_version
                )
            elif action == "recalculate":
                author(actor)
                estimating.writable(record)
                estimating.version_check(record, data.expected_version)
                estimating.calculate(
                    session,
                    record,
                    EstimateFields.model_validate_json(record.fields_json),
                )
                record.version += 1
            else:
                estimating.transition(
                    session, actor, record, action, data.expected_version
                )
            return estimating.estimate_view(record)

    def action_endpoint(action):
        def endpoint(identity: int, data: VersionAction, request: Request):
            return estimate_action(identity, action, data, request)

        return endpoint

    for action_name in ("submit", "check", "approve", "revise", "recalculate"):
        router.add_api_route(
            "/estimates/{identity}/" + action_name,
            action_endpoint(action_name),
            methods=["POST"],
            response_model=EstimateResponse,
            name="estimate_" + action_name,
        )

    @router.post("/materials/{identity}/prices/select", response_model=EstimateResponse)
    def select_price(identity: int, data: SelectPriceInput, request: Request):
        with context(request, True) as (session, actor):
            author(actor)
            material = load(session, actor, a.Material, identity, True)
            record = load(session, actor, a.Estimate, data.estimate_id, True)
            observed = load(session, actor, a.PriceObservation, data.observation_id)
            if (
                record.project_id != material.project_id
                or observed.material_id != material.id
            ):
                raise ValueError(
                    "Estimate, material and observation must belong to the same project"
                )
            estimating.version_check(record, data.expected_version)
            estimating.writable(record)
            fields = EstimateFields.model_validate_json(record.fields_json)
            line = next((r for r in fields.lines if r.id == data.line_id), None)
            comp = (
                next((r for r in line.components if r.id == data.component_id), None)
                if line
                else None
            )
            if (
                not comp
                or comp.material_id != material.id
                or comp.unit != material.unit
            ):
                raise ValueError(
                    "Link this material and its canonical unit to the component first"
                )
            values = SearchInput(
                quantity=str(
                    decimal(line.quantity)
                    * decimal(comp.consumption)
                    * (1 + decimal(comp.wastage_percent) / 100)
                ),
                unit=material.unit,
                currency=session.get(m.Project, material.project_id).currency,
                mode="DEMO" if observed.source_type == "DEMO" else "LIVE",
            )
            if data.search_id:
                search = load(session, actor, a.PriceSearch, data.search_id)
                if search.material_id != material.id:
                    raise ValueError("Search belongs to a different material")
                saved = json.loads(search.request_json)
                values.country, values.city, values.delivery_location = (
                    saved["country"],
                    saved["city"],
                    saved["delivery_location"],
                )
            comparison = pricing.compare(session, material, values, data.search_id)
            row = next(
                (r for r in comparison["offers"] if r["observation_id"] == observed.id),
                None,
            )
            if not row or not row["eligible"]:
                raise DomainError(
                    422,
                    "INELIGIBLE_PRICE",
                    "Price requires compatible specifications, known costs, suitable delivery, units and current evidence.",
                )
            if not row["recommended"] and len(data.reason.strip()) < 10:
                raise ValueError(
                    "Choosing another eligible price requires a documented reason"
                )
            snapshot = {
                **row,
                "material": pricing.material_view(material),
                "request": values.model_dump(mode="json"),
                "selection_policy": comparison["policy"],
                "selected_by": actor.id,
                "selected_at": utcnow(),
            }
            chosen = a.PriceSelection(
                project_id=record.project_id,
                estimate_id=record.id,
                observation_id=observed.id,
                line_id=line.id,
                component_id=comp.id,
                snapshot_json=canonical(snapshot),
                snapshot_hash=digest(snapshot),
                reason=data.reason or "Selected recommended eligible price",
                actor_id=actor.id,
            )
            session.add(chosen)
            session.flush()
            old = comp.unit_price
            comp.selection_id, comp.unit_price = chosen.id, row["landed_unit_cost"]
            estimating.calculate(session, record, fields)
            authorship.contribute(session, "estimate", record, actor, "price selection")
            record.prepared_by = actor.id
            record.version += 1
            audit.append(
                session,
                actor,
                "PRICE_SELECTED",
                "estimate",
                record.id,
                {
                    "selection_id": chosen.id,
                    "snapshot_hash": chosen.snapshot_hash,
                    "old_rate": old,
                    "new_rate": comp.unit_price,
                    "total": str(record.total_minor),
                    "reason": chosen.reason,
                },
                record.project_id,
            )
            return estimating.estimate_view(record)

    @router.post(
        "/materials/{identity}/prices/preview", response_model=PriceSelectionPreview
    )
    def price_preview(identity: int, data: SelectPriceInput, request: Request):
        with context(request) as (session, actor):
            author(actor)
            material = load(session, actor, a.Material, identity)
            record = load(session, actor, a.Estimate, data.estimate_id)
            observed = load(session, actor, a.PriceObservation, data.observation_id)
            estimating.version_check(record, data.expected_version)
            estimating.writable(record)
            if (
                record.project_id != material.project_id
                or observed.material_id != material.id
            ):
                raise ValueError(
                    "Estimate, material and observation must belong to the same project"
                )
            fields = EstimateFields.model_validate_json(record.fields_json)
            line = next((v for v in fields.lines if v.id == data.line_id), None)
            component = (
                next((v for v in line.components if v.id == data.component_id), None)
                if line
                else None
            )
            if (
                not component
                or component.material_id != identity
                or component.unit != material.unit
            ):
                raise ValueError(
                    "Component must use the chosen material's canonical unit"
                )
            inputs = SearchInput(
                quantity=str(
                    decimal(line.quantity)
                    * decimal(component.consumption)
                    * (1 + decimal(component.wastage_percent) / 100)
                ),
                unit=material.unit,
                currency=session.get(m.Project, record.project_id).currency,
                mode="DEMO" if observed.source_type == "DEMO" else "LIVE",
            )
            if data.search_id:
                task = load(session, actor, a.PriceSearch, data.search_id)
                if task.material_id != identity:
                    raise ValueError("Search belongs to a different material")
                task_request = json.loads(task.request_json)
                inputs.country, inputs.city = (
                    task_request["country"],
                    task_request["city"],
                )
            row = pricing.normalize_offer(
                session,
                material,
                observed,
                inputs,
                session.get(m.Project, record.project_id).currency,
            )
            if not row["eligible"]:
                raise DomainError(
                    422,
                    "INELIGIBLE_PRICE",
                    "This source is not eligible for rate selection.",
                )
            old_price = decimal(component.unit_price)
            component.unit_price, component.selection_id = row["landed_unit_cost"], None
            proposed = a.Estimate(
                id=record.id,
                project_id=record.project_id,
                version=record.version,
                fields_json="{}",
                calculated_json="{}",
            )
            calculated = estimating.calculate(session, proposed, fields)
            forecast = estimating.preview_forecast(
                session, proposed, request.app.state.settings
            )
            current_forecast = estimating.preview_forecast(
                session, record, request.app.state.settings
            )
            return {
                "old_rate": str(old_price),
                "new_rate": component.unit_price,
                "difference_percent": format(
                    (decimal(component.unit_price) / old_price - 1) * 100, ".4f"
                )
                if old_price
                else None,
                "item_amount": next(
                    r["amount"] for r in calculated["lines"] if r["id"] == line.id
                ),
                "estimate_total": calculated["total"],
                "estimate_difference": format(
                    Decimal(proposed.total_minor - record.total_minor) / 100, ".2f"
                ),
                "forecast_minimum": forecast["scenarios"][0]["lowest_balance"],
                "forecast_difference": format(
                    decimal(forecast["scenarios"][0]["lowest_balance"])
                    - decimal(current_forecast["scenarios"][0]["lowest_balance"]),
                    ".2f",
                ),
                "evidence_hash": observed.evidence_hash,
                "notice": "Preview only; no rate or cash has changed.",
            }

    @router.get(
        "/estimates/{identity}/forecast",
        response_model=EstimateForecast,
        response_model_exclude_unset=True,
    )
    def forecast(identity: int, request: Request):
        with context(request) as (session, actor):
            return estimating.preview_forecast(
                session,
                load(session, actor, a.Estimate, identity),
                request.app.state.settings,
            )

    @router.get("/estimates/{identity}/evidence")
    def estimate_evidence(identity: int, request: Request):
        with context(request) as (session, actor):
            record = load(session, actor, a.Estimate, identity)
            snapshot = (
                json.loads(record.approval_snapshot_json)
                if record.approval_snapshot_json
                else None
            )
            return {
                "estimate_id": identity,
                "revision": record.revision,
                "status": record.status,
                "snapshot_hash": record.snapshot_hash,
                "snapshot": snapshot,
                "snapshot_valid": digest(snapshot) == record.snapshot_hash
                if snapshot
                else None,
                "prepared_by": record.prepared_by,
                "checked_by": record.checked_by,
                "approved_by": record.approved_by,
            }

    @router.get(
        "/estimates/{identity}/compare",
        response_model=EstimateDifference,
        response_model_exclude_unset=True,
    )
    def estimate_compare(identity: int, other_id: int, request: Request):
        with context(request) as (session, actor):
            left, right = (
                load(session, actor, a.Estimate, identity),
                load(session, actor, a.Estimate, other_id),
            )
            if left.estimate_key != right.estimate_key:
                raise ValueError("Compare revisions of the same estimate")
            lrows = {r["code"]: r for r in json.loads(left.calculated_json)["lines"]}
            rrows = {r["code"]: r for r in json.loads(right.calculated_json)["lines"]}
            return {
                "left": identity,
                "right": other_id,
                "total_difference": str(
                    (Decimal(left.total_minor) - right.total_minor) / 100
                ),
                "items": [
                    {"code": code, "left": lrows.get(code), "right": rrows.get(code)}
                    for code in sorted(set(lrows) | set(rrows))
                ],
            }

    @router.get("/estimates/{identity}/export")
    def estimate_export(identity: int, request: Request, format: str = "csv"):
        if format not in ("csv", "xlsx"):
            raise ValueError("Choose CSV or XLSX")
        with context(request) as (session, actor):
            record = load(session, actor, a.Estimate, identity)
            fields, result = (
                json.loads(record.fields_json),
                json.loads(record.calculated_json),
            )
            calc = {r["id"]: r for r in result["lines"]}
            headers = [
                "id",
                "section",
                "code",
                "description",
                "unit",
                "quantity",
                "unit_rate",
                "amount",
                "cost_code",
                "due_date",
                "drawing_reference",
                "notes",
                "source_note",
            ]
            rows = [
                [
                    line.get(key)
                    if key not in ("unit_rate", "amount", "source_note")
                    else calc[line["id"]].get(key)
                    if key != "source_note"
                    else "; ".join(
                        str(c.get("selection_id") or c.get("source_note") or "")
                        for c in line["components"]
                    )
                    for key in headers
                ]
                for line in fields["lines"]
            ]
            project = session.get(m.Project, record.project_id)
            context_values = {
                "project_code": project.code,
                "project_name": project.name,
                "estimate_name": record.name,
                "estimate_revision": record.revision,
                "estimate_status": record.status,
                "currency": project.currency,
                "basis": fields.get("basis", ""),
                "calculation_policy": result.get("policy", ""),
                "estimate_cost_total": result.get("cost_total"),
                "estimate_tender_total": result.get("tender_total", result["total"]),
            }
            rows = [row + list(context_values.values()) for row in rows]
            headers += list(context_values)
            allowances = [
                "site_overhead_percent",
                "general_overhead_percent",
                "profit_percent",
                "tax_percent",
                "contingency_percent",
                "tax_treatment",
            ]
            headers += ["buildtrust_export_version", "components_json", *allowances]
            rows = [
                row
                + [
                    "2",
                    canonical(line["components"]),
                    *(fields.get(key) for key in allowances),
                ]
                for row, line in zip(rows, fields["lines"])
            ]
            content, mime = export_table(headers, rows, format)
            return Response(
                content,
                media_type=mime,
                headers={
                    "Content-Disposition": f'attachment; filename="estimate-{identity}-r{record.revision}.{format}"'
                },
            )

    @router.post("/estimates/{identity}/import")
    async def estimate_import(
        identity: int,
        request: Request,
        expected_version: int = Form(...),
        file: UploadFile = File(...),
    ):
        contents = await file.read(request.app.state.settings.max_upload_bytes + 1)
        if len(contents) > request.app.state.settings.max_upload_bytes:
            raise DomainError(413, "UPLOAD_TOO_LARGE", "Maximum upload is 10 MB.")
        from fastapi.concurrency import run_in_threadpool

        with context(request) as (session, actor):
            author(actor)
            load(session, actor, a.Estimate, identity, True)
        imported = await run_in_threadpool(
            boq_import, contents, Path(file.filename or "").suffix.lower()
        )
        with context(request, True) as (session, actor):
            author(actor)
            record = load(session, actor, a.Estimate, identity, True)
            estimating.version_check(record, expected_version)
            estimating.writable(record)
            fields = EstimateFields.model_validate_json(record.fields_json)
            fields.lines = imported.lines
            for key in (
                "site_overhead_percent",
                "general_overhead_percent",
                "profit_percent",
                "tax_percent",
                "contingency_percent",
                "tax_treatment",
            ):
                setattr(fields, key, getattr(imported, key))
            estimating.calculate(session, record, fields)
            authorship.contribute(session, "estimate", record, actor, "BOQ import")
            record.prepared_by = actor.id
            record.version += 1
            audit.append(
                session,
                actor,
                "ESTIMATE_BOQ_IMPORTED",
                "estimate",
                identity,
                {
                    "sha256": hashlib.sha256(contents).hexdigest(),
                    "rows": len(fields.lines),
                },
                record.project_id,
            )
            return estimating.estimate_view(record)

    @router.get(
        "/finance/cost-control",
        response_model=CostControl,
        response_model_exclude_unset=True,
    )
    def cost_control(request: Request, project_id: int):
        with context(request) as (session, actor):
            return estimating.cost_control(
                session, project_access(session, actor, project_id)
            )

    return router
