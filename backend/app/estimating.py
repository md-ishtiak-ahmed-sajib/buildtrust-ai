from . import procurement
from copy import deepcopy
from decimal import Decimal
import json
import uuid
from sqlalchemy import select, func
from sqlalchemy.orm import object_session
from . import advanced_models as a, audit, finance, authorship, coverage
from .models import (
    Project,
    BOQItem,
    POLine,
    PurchaseOrder,
    Payment,
    Proposal,
    User,
    Membership,
)
from .money import canonical, digest, money, minor, decimal
from .advanced_math import rate_analysis, unit_factor
from .advanced_schemas import EstimateFields, EstimateLine, RateComponent
from .security import DomainError, project_access, require_role


def version_check(record, expected):
    if record.version != expected:
        raise DomainError(
            409,
            "VERSION_CONFLICT",
            "This record changed. Reload before saving.",
            record.project_id,
        )


def writable(record):
    if record.status != "DRAFT":
        raise DomainError(
            409,
            "VERSION_LOCKED",
            "Create a revision to change a submitted or approved estimate.",
            record.project_id,
        )


def validate_links(session, project_id, fields):
    used_boq = set()
    for line in fields.lines:
        if line.cost_code:
            from .control_models import CostCode

            if not session.scalar(
                select(CostCode.id).where(
                    CostCode.project_id == project_id,
                    CostCode.code == line.cost_code,
                    CostCode.active.is_(True),
                )
            ):
                raise ValueError(
                    f"Create active project cost code {line.cost_code} before linking it to this estimate"
                )
        if line.legacy_boq_item_id:
            if line.legacy_boq_item_id in used_boq:
                raise ValueError(
                    "An approved BOQ item may link to only one estimate line"
                )
            used_boq.add(line.legacy_boq_item_id)
            boq = session.get(BOQItem, line.legacy_boq_item_id)
            if not boq or boq.project_id != project_id:
                raise ValueError("Approved BOQ link does not belong to this project")
            unit_factor(boq.unit, line.unit)
        if line.takeoff_sheet_id:
            sheet = session.get(a.TakeoffSheet, line.takeoff_sheet_id)
            if not sheet or sheet.project_id != project_id:
                raise ValueError("Takeoff sheet does not belong to this project")
            result = json.loads(sheet.result_json)
            factor = unit_factor(result["unit"], line.unit)
            if decimal(line.quantity) != decimal(result["quantity"]) * factor:
                raise ValueError(
                    "BOQ quantity must agree with the linked takeoff sheet"
                )
        for comp in line.components:
            if comp.material_id:
                material = session.get(a.Material, comp.material_id)
                if (
                    not material
                    or material.project_id != project_id
                    or not material.active
                ):
                    raise ValueError(
                        "Component material is unavailable in this project"
                    )
                unit_factor(comp.unit, material.unit)
            if comp.selection_id:
                chosen = session.get(a.PriceSelection, comp.selection_id)
                if not chosen or chosen.project_id != project_id:
                    raise ValueError("Selection does not belong to this project")
                snapshot = json.loads(chosen.snapshot_json)
                if (
                    snapshot["material"]["id"] != comp.material_id
                    or comp.unit != snapshot["material"]["unit"]
                    or chosen.line_id != line.id
                    or chosen.component_id != comp.id
                ):
                    raise ValueError(
                        "Selection is bound to a different material, line or component"
                    )
                if decimal(snapshot["landed_unit_cost"]) != decimal(comp.unit_price):
                    raise ValueError(
                        "Selected evidence price cannot be edited; clear the selection for a manual rate"
                    )
                if (
                    snapshot["material"]["version"]
                    != session.get(a.Material, comp.material_id).version
                ):
                    raise ValueError(
                        "Material requirements changed; select fresh compatible evidence"
                    )


def calculate(session, record, fields):
    validate_links(session, record.project_id, fields)
    coverage.sync(session, record.project_id, fields)
    result = rate_analysis(fields)
    record.fields_json = canonical(fields.model_dump(mode="json"))
    record.calculated_json = canonical(result)
    record.total_minor = minor(result["total"])
    return result


def estimate_view(record):
    return {
        "id": record.id,
        "project_id": record.project_id,
        "estimate_key": record.estimate_key,
        "revision": record.revision,
        "version": record.version,
        "name": record.name,
        "status": record.status,
        "prepared_by": record.prepared_by,
        "contributors": authorship.contributors(
            object_session(record), "estimate", record.id
        ),
        "checked_by": record.checked_by,
        "approved_by": record.approved_by,
        "snapshot_hash": record.snapshot_hash,
        "total": money(record.total_minor),
        "cost_total": json.loads(record.calculated_json).get("cost_total"),
        "tender_total": json.loads(record.calculated_json).get("tender_total"),
        "fields": json.loads(record.fields_json),
        "calculated": json.loads(record.calculated_json),
        "created_at": record.created_at,
    }


def create_estimate(session, actor, project, name, import_boq=True):
    fields = EstimateFields()
    if import_boq:
        for item in session.scalars(
            select(BOQItem).where(BOQItem.project_id == project.id)
        ):
            unit = {"tonnes": "tonne", "t": "tonne", "bags": "bag"}.get(
                item.unit, item.unit
            )
            fields.lines.append(
                EstimateLine(
                    id=uuid.uuid4().hex,
                    code=item.item_code,
                    description=item.description,
                    unit=unit,
                    quantity=item.quantity,
                    legacy_boq_item_id=item.id,
                    components=[
                        RateComponent(
                            id=uuid.uuid4().hex,
                            description=item.description,
                            unit=unit,
                            unit_price=item.rate,
                            source_note=f"Approved BOQ document {item.document_id}; catalogue specification needs review",
                        )
                    ],
                )
            )
    record = a.Estimate(
        project_id=project.id,
        estimate_key=uuid.uuid4().hex,
        name=name,
        prepared_by=actor.id,
        fields_json="{}",
        calculated_json="{}",
    )
    session.add(record)
    calculate(session, record, fields)
    session.flush()
    authorship.contribute(session, "estimate", record, actor, "creation/import")
    audit.append(
        session,
        actor,
        "ESTIMATE_CREATED",
        "estimate",
        record.id,
        {"imported_boq": import_boq},
        project.id,
    )
    return record


def fingerprint_payload(session, record):
    fields = EstimateFields.model_validate_json(record.fields_json)
    selections, sheets, materials = {}, {}, {}
    for line in fields.lines:
        if line.takeoff_sheet_id:
            sheet = session.get(a.TakeoffSheet, line.takeoff_sheet_id)
            sheets[str(sheet.id)] = {
                "fields": json.loads(sheet.fields_json),
                "result": json.loads(sheet.result_json),
                "profile_id": sheet.profile_id,
                "checked_by": sheet.checked_by,
                "status": sheet.status,
            }
        for comp in line.components:
            if comp.selection_id:
                selection = session.get(a.PriceSelection, comp.selection_id)
                selections[str(selection.id)] = {
                    "snapshot": json.loads(selection.snapshot_json),
                    "hash": selection.snapshot_hash,
                }
            if comp.material_id:
                material = session.get(a.Material, comp.material_id)
                materials[str(material.id)] = {
                    "version": material.version,
                    "specification": json.loads(material.specification_json),
                    "unit": material.unit,
                    "active": material.active,
                }
    return {
        "project_id": record.project_id,
        "name": record.name,
        "revision": record.revision,
        "fields": fields.model_dump(mode="json"),
        "calculated": json.loads(record.calculated_json),
        "selections": selections,
        "takeoffs": sheets,
        "materials": materials,
        "policy": "estimate-v1",
        "contributors": authorship.contributors(session, "estimate", record.id),
    }


def fingerprint(session, record):
    return digest(fingerprint_payload(session, record))


def transition(session, actor, record, action, expected):
    project_access(session, actor, record.project_id, write=True)
    version_check(record, expected)
    if action == "submit":
        require_role(actor, "OPERATOR", "FINANCE_MANAGER", "ADMIN")
        writable(record)
        fields = EstimateFields.model_validate_json(record.fields_json)
        calculate(session, record, fields)
        if json.loads(record.calculated_json).get("cost_total") is None:
            raise DomainError(
                422,
                "UNKNOWN_TAX_TREATMENT",
                "Record tax treatment before approving a cost budget.",
            )
        if not fields.lines or record.total_minor <= 0 or not fields.basis.strip():
            raise DomainError(
                422,
                "INCOMPLETE_ESTIMATE",
                "Add priced items and a Basis of Estimate before submission.",
            )
        for line in fields.lines:
            if (
                line.takeoff_sheet_id
                and session.get(a.TakeoffSheet, line.takeoff_sheet_id).status
                != "CHECKED"
            ):
                raise DomainError(
                    422,
                    "UNCHECKED_MEASUREMENT",
                    "Linked takeoff sheets need independent checking.",
                )
            for comp in line.components:
                if not comp.selection_id and not comp.source_note.strip():
                    raise DomainError(
                        422,
                        "MISSING_RATE_SOURCE",
                        "Manual component rates require a source and assumptions.",
                    )
        payload = fingerprint_payload(session, record)
        record.snapshot_hash, record.approval_snapshot_json = (
            digest(payload),
            canonical(payload),
        )
        record.status = "SUBMITTED"
    elif action == "check":
        require_role(actor, "FINANCE_MANAGER", "ADMIN")
        if actor.id in authorship.contributors(session, "estimate", record.id):
            raise DomainError(
                403,
                "SELF_CHECK",
                "The preparer cannot independently check this estimate.",
            )
        if record.status != "SUBMITTED":
            raise DomainError(
                409, "INVALID_TRANSITION", "A submitted estimate is required."
            )
        if record.snapshot_hash != fingerprint(session, record):
            raise DomainError(
                409,
                "SOURCE_CHANGED",
                "Supporting records changed. Create and submit a revision.",
            )
        record.checked_by, record.status = actor.id, "CHECKED"
    elif action == "approve":
        require_role(actor, "ADMIN")
        if actor.id == record.checked_by or actor.id in authorship.contributors(
            session, "estimate", record.id
        ):
            raise DomainError(
                403,
                "SEPARATION_OF_DUTIES",
                "An independent Admin must approve after a different person checks.",
            )
        if record.status != "CHECKED":
            raise DomainError(
                409,
                "INVALID_TRANSITION",
                "Independent checking is required before approval.",
            )
        checker = session.get(User, record.checked_by)
        if (
            not checker
            or not checker.active
            or checker.role not in ("FINANCE_MANAGER", "ADMIN")
            or not session.get(Membership, (checker.id, record.project_id))
        ):
            raise DomainError(
                409,
                "CHECKER_AUTHORITY_CHANGED",
                "The checking authority is no longer valid; create a revision for fresh checking.",
            )
        if record.snapshot_hash != fingerprint(session, record):
            raise DomainError(
                409,
                "SOURCE_CHANGED",
                "Supporting records changed. Create and submit a revision.",
            )
        record.approved_by, record.status = actor.id, "APPROVED"
        session.add(
            a.BudgetBaseline(
                project_id=record.project_id,
                estimate_id=record.id,
                amount_minor=minor(json.loads(record.calculated_json)["cost_total"]),
                snapshot_hash=record.snapshot_hash,
                approved_by=actor.id,
            )
        )
    record.version += 1
    audit.append(
        session,
        actor,
        "ESTIMATE_" + action.upper(),
        "estimate",
        record.id,
        {
            "version": record.version,
            "snapshot_hash": record.snapshot_hash,
            "total": money(record.total_minor),
        },
        record.project_id,
    )


def revise(session, actor, record, expected):
    version_check(record, expected)
    maximum = session.scalar(
        select(func.max(a.Estimate.revision)).where(
            a.Estimate.estimate_key == record.estimate_key,
            a.Estimate.project_id == record.project_id,
        )
    )
    if record.status in ("SUBMITTED", "CHECKED"):
        record.status = "SUPERSEDED"
        record.version += 1
    revision = a.Estimate(
        project_id=record.project_id,
        estimate_key=record.estimate_key,
        revision=maximum + 1,
        parent_id=record.id,
        name=record.name,
        prepared_by=actor.id,
        fields_json=record.fields_json,
        calculated_json=record.calculated_json,
        total_minor=record.total_minor,
    )
    session.add(revision)
    session.flush()
    authorship.inherit(session, record, revision, actor)
    audit.append(
        session,
        actor,
        "ESTIMATE_REVISED",
        "estimate",
        revision.id,
        {"parent_id": record.id},
        record.project_id,
    )
    return revision


def committed_quantity(session, project_id, line):
    return coverage.quantity(session, project_id, line)[0]


def preview_forecast(session, record, settings):
    from .forecasting import preview

    return preview(session, record, settings)


def cost_control(session, project):
    baseline = session.scalar(
        select(a.BudgetBaseline)
        .where(a.BudgetBaseline.project_id == project.id)
        .order_by(a.BudgetBaseline.id.desc())
    )
    latest = session.scalar(
        select(a.Estimate)
        .where(a.Estimate.project_id == project.id, a.Estimate.status != "SUPERSEDED")
        .order_by(a.Estimate.id.desc())
    )
    committed = sum(
        minor(procurement.quantity(session, pol) * decimal(pol.rate))
        for pol in session.scalars(
            select(POLine)
            .join(PurchaseOrder)
            .where(
                PurchaseOrder.project_id == project.id, PurchaseOrder.approved.is_(True)
            )
        )
    )
    paid = sum(
        p.amount_minor
        for p in session.scalars(
            select(Payment)
            .join(Proposal, Payment.proposal_id == Proposal.id)
            .where(Proposal.project_id == project.id)
        )
    )
    budget = baseline.amount_minor if baseline else project.budget_minor
    from .accounting import summary

    actual = summary(session, project)
    latest_cost = (
        json.loads(latest.calculated_json).get("cost_total") if latest else None
    )
    return {
        "project_id": project.id,
        "currency": project.currency,
        "original_budget": money(project.budget_minor),
        "approved_estimate_budget": money(baseline.amount_minor) if baseline else None,
        "current_estimate": money(latest.total_minor) if latest else None,
        "estimate_id": latest.id if latest else None,
        "estimate_status": latest.status if latest else None,
        "forecast_vs_budget": money(minor(latest_cost) - budget)
        if latest_cost is not None
        else None,
        "budget_overrun": bool(latest_cost is not None and minor(latest_cost) > budget),
        "tender_vs_budget": money(latest.total_minor - budget) if latest else None,
        "po_line_commitment": money(committed),
        "commitment_basis": "Approved PO line values before tax, retention and per-invoice discount; not incurred cost",
        "paid_cash": money(paid),
        "current_cost_estimate": latest_cost,
        "current_tender_estimate": money(latest.total_minor) if latest else None,
        "actual_incurred_cost": actual["incurred_cost"],
        "accrued_liabilities": actual["accrued_liability"],
        "notice": "Costs, contractual commitments and cash payments are distinct. Explicit reviewed accounting journals cover recognized costs; historical gaps remain insufficient data.",
    }


def seed_profiles(session):
    sources = [
        (
            "NRM2",
            "RICS NRM 2",
            "2021 / reissued 2022",
            "https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm",
        ),
        (
            "NRM1",
            "RICS NRM 1",
            "2021",
            "https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm",
        ),
        (
            "NRM3",
            "RICS NRM 3",
            "2021",
            "https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm",
        ),
        (
            "CESMM4",
            "CESMM4",
            "2012",
            "https://ice.org.uk/areas-of-interest/infrastructure-delivery/civil-engineering-standard-measurement",
        ),
        (
            "ICMS3",
            "ICMS 3 reporting classification",
            "2021",
            "https://icms-coalition.org/the-standard/",
        ),
        (
            "PWD",
            "Bangladesh PWD",
            "User-supplied edition required",
            "https://ss.pwd.gov.bd/sor",
        ),
        (
            "LGED",
            "Bangladesh LGED",
            "User-supplied edition required",
            "https://lged.gov.bd",
        ),
        (
            "PROJECT",
            "Project-specific geometry",
            "1.0",
            "",
        ),
    ]
    for code, name, edition, url in sources:
        existing = session.scalar(
            select(a.MeasurementProfile).where(a.MeasurementProfile.code == code)
        )
        if (
            code == "PROJECT"
            and existing
            and existing.source_url == "https://example.com/project-rules"
        ):
            existing.source_url = ""
        if not session.scalar(
            select(a.MeasurementProfile).where(a.MeasurementProfile.code == code)
        ):
            session.add(
                a.MeasurementProfile(
                    code=code,
                    name=name,
                    edition=edition,
                    source_url=url,
                    rules_json=canonical(
                        {
                            "rule_id": "geometry-v1",
                            "deduction": "Explicit user deduction in output units, with reason; no standard threshold inferred",
                            "assumptions": "Geometry only; engineering design and licensed measurement clauses require review",
                            "effective_date": "2026-10-18",
                        }
                    ),
                )
            )
