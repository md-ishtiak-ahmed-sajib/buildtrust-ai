"""Explicit, nonoverlapping forecast allocations. These never reserve procurement or cash."""

import json
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from . import (
    accounting,
    advanced_models as a,
    control_models as c,
    models as m,
    coverage,
    procurement,
)
from .advanced_math import unit_factor, rate_analysis
from .advanced_schemas import EstimateFields
from .money import decimal, digest, minor, money, published


def key(payload):
    return (
        payload["estimate_id"],
        payload["estimate_line_id"],
        payload.get("component_id"),
        payload["contract_id"],
        payload["item_code"],
    )


def current(session, project_id, estimate_id):
    rows = [
        (row, json.loads(row.payload_json), json.loads(row.calculated_json))
        for row in session.scalars(
            select(c.ControlRecord)
            .where(
                c.ControlRecord.project_id == project_id,
                c.ControlRecord.kind == "CONTRACT_ESTIMATE_LINK",
                c.ControlRecord.status == "APPROVED",
            )
            .order_by(c.ControlRecord.id)
        )
    ]
    superseded = {p.get("supersedes_id") for _, p, _ in rows}
    newest = {
        key(p): (row, p, r)
        for row, p, r in rows
        if row.id not in superseded and p["estimate_id"] == estimate_id
    }
    return list(newest.values())


def free_start(intervals, lower, upper, size, requested):
    intervals = sorted(intervals)
    start = decimal(requested) if requested is not None else lower
    if requested is None:
        for first, last in intervals:
            if start + size <= first:
                break
            if last > start:
                start = last
    if (
        start < lower
        or start + size > upper
        or any(start < last and start + size > first for first, last in intervals)
    ):
        raise ValueError(
            "Forecast allocation overlaps another approved scope or exceeds the remaining quantity"
        )
    return start


def build(session, project, values):
    from .commercial import contract_scope, valuation, records, approved

    record, contract, lines, variations = contract_scope(
        session, project.id, values.contract_id
    )
    line = lines.get(values.item_code)
    estimate = accounting.scoped(session, a.Estimate, values.estimate_id, project.id)
    fields = EstimateFields.model_validate_json(estimate.fields_json)
    target = next(
        (row for row in fields.lines if row.id == values.estimate_line_id), None
    )
    if (
        not target
        or not line
        or contract["direction"] != "SUPPLIER"
        or not values.complete_cost_scope_confirmed
    ):
        raise ValueError(
            "Confirm the complete supported supplier/estimate forecast scope"
        )
    normalize = lambda text: " ".join(text.casefold().split())
    component = (
        next(
            (comp for comp in target.components if comp.id == values.component_id), None
        )
        if values.component_id
        else None
    )
    if values.component_id and component is None:
        raise ValueError("Selected rate component is absent from this estimate version")
    description = component.description if component else target.description
    target_unit = component.unit if component else target.unit
    if normalize(description) != normalize(line["description"]):
        raise ValueError(
            "Contract and selected component specifications must match explicitly"
        )
    if not component and target.legacy_boq_item_id != line.get("boq_item_id"):
        raise ValueError("Whole-item procurement scope must match the BOQ link")
    factor = unit_factor(line["unit"], target_unit)
    covered, warnings = coverage.quantity(session, project.id, target)
    if warnings:
        raise ValueError(
            "Resolve procurement coverage before approving the forecast allocation"
        )
    remaining = max(Decimal(0), decimal(target.quantity) - covered)
    demand = remaining * (
        decimal(component.consumption) * (1 + decimal(component.wastage_percent) / 100)
        if component
        else 1
    )
    pos = []
    ordered = Decimal(0)
    if line.get("boq_item_id"):
        boq = accounting.scoped(session, m.BOQItem, line["boq_item_id"], project.id)
        for pol, po in session.execute(
            select(m.POLine, m.PurchaseOrder)
            .join(m.PurchaseOrder)
            .where(
                m.PurchaseOrder.project_id == project.id,
                m.PurchaseOrder.supplier_id == contract["supplier_id"],
                m.PurchaseOrder.approved.is_(True),
                m.POLine.item_code == boq.item_code,
            )
        ):
            if (
                pol.description.strip().casefold()
                != line["description"].strip().casefold()
                or po.currency != project.currency
            ):
                raise ValueError(
                    "Resolve incompatible commitment sources before mapping this contract"
                )
            qty = procurement.quantity(session, pol) * unit_factor(
                pol.unit, line["unit"]
            )
            ordered += qty
            pos.append([po.id, po.version, pol.id, str(qty), pol.rate])
    accepted = sum(
        (
            decimal(p["quantity"])
            for _, p, _ in records(
                session,
                project.id,
                "WORK_ACCEPTANCE",
                contract_id=values.contract_id,
                item_code=values.item_code,
            )
        ),
        Decimal(0),
    )
    certified = max(
        (
            decimal(r.get("cumulative_quantities", {}).get(values.item_code, "0"))
            for _, _, r in records(
                session,
                project.id,
                "INTERIM_CERTIFICATE",
                contract_id=values.contract_id,
            )
        ),
        default=Decimal(0),
    )
    protected = max(ordered, accepted, certified)
    if component and covered and protected:
        raise ValueError(
            "Whole-work and component commitments need disjoint source scopes; automatic overlapping coverage is not permitted"
        )
    capacity = decimal(line["quantity"]) - protected
    if capacity < 0:
        raise ValueError("Protected quantity exceeds the authorized contract scope")
    active = [
        (r, p, result)
        for r, p, result in current(session, project.id, estimate.id)
        if key(p) != key(values.model_dump()) and r.id != values.supersedes_id
    ]
    if values.supersedes_id:
        old, old_payload, _ = approved(
            session, values.supersedes_id, "CONTRACT_ESTIMATE_LINK", project.id
        )
        if (
            old_payload["estimate_id"] != estimate.id
            or old_payload["estimate_line_id"] != target.id
        ):
            raise ValueError("Superseded mapping must belong to the same estimate item")
    same_target = [
        (r, p, result) for r, p, result in active if p["estimate_line_id"] == target.id
    ]
    if any(
        bool(p.get("component_id")) != bool(values.component_id)
        for _, p, _ in same_target
    ):
        raise ValueError(
            "Whole-item and component mappings cannot overlap; explicitly supersede the prior mapping"
        )
    source_intervals = []
    target_intervals = []
    for _, p, result in active:
        if "source_offset" not in result or "target_offset" not in result:
            if p["estimate_line_id"] == target.id:
                raise ValueError(
                    "Review the legacy mapping before combining forecast allocations"
                )
            continue
        if (
            p["contract_id"] == values.contract_id
            and p["item_code"] == values.item_code
        ):
            first = decimal(result["source_offset"])
            source_intervals.append(
                (first, first + decimal(result["allocation_quantity"]))
            )
        if (
            p["estimate_line_id"] == target.id
            and p.get("component_id") == values.component_id
        ):
            first = decimal(result["target_offset"])
            target_intervals.append((first, first + decimal(result["target_quantity"])))
    quantity = (
        decimal(values.allocation_quantity)
        if values.allocation_quantity is not None
        else min(capacity, demand / factor)
    )
    if quantity <= 0:
        raise ValueError("Forecast allocation requires positive uncommitted quantity")
    source_start = free_start(
        source_intervals,
        protected,
        decimal(line["quantity"]),
        quantity,
        values.source_offset,
    )
    target_start = free_start(
        target_intervals, Decimal(0), demand, quantity * factor, values.target_offset
    )
    # Persist automatically chosen intervals in the submitted payload. Later source
    # changes require review rather than moving an approved allocation silently.
    values.allocation_quantity = str(quantity)
    values.source_offset = str(source_start)
    values.target_offset = str(target_start)
    base = valuation(line, source_start + quantity) - valuation(line, source_start)
    tax = minor(Decimal(base) / 100 * decimal(contract["tax_percent"]) / 100)
    retention = minor(
        Decimal(base) / 100 * decimal(contract["retention_percent"]) / 100
    )
    recovery = 0
    advance_hash = None
    notes = []
    if decimal(contract["advance_recovery_percent"]):
        if values.advance_assignment_id:
            assignment, ap, ar = approved(
                session, values.advance_assignment_id, "ADVANCE_ASSIGNMENT", project.id
            )
            if ap["contract_id"] != record.id:
                raise ValueError("Advance assignment belongs to another contract")
            certs = {
                r.id: cr
                for r, p, cr in records(session, project.id, "INTERIM_CERTIFICATE")
                if p.get("advance_assignment_id") == assignment.id
            }
            used = sum(cr.get("advance_minor", 0) for cr in certs.values())
            used -= sum(
                cr["advance_minor"]
                for _, p, cr in records(session, project.id, "CERTIFICATE_CORRECTION")
                if p["certificate_id"] in certs
            )
            planned = sum(
                r.get("advance_minor", 0)
                for _, p, r in active
                if p.get("advance_assignment_id") == assignment.id
            )
            available = max(0, ar["amount_minor"] - used - planned)
            expected = minor(
                Decimal(base)
                / 100
                * decimal(contract["advance_recovery_percent"])
                / 100
            )
            recovery = min(expected, available)
            advance_hash = assignment.snapshot_hash
            if recovery < expected:
                notes.append(
                    "Forecast recovery is capped at the sourced unrecouped advance balance"
                )
        else:
            notes.append(
                "No approved advance assignment; forecast cash is not reduced by an assumed recovery"
            )
    if base + tax - retention - recovery < 0:
        raise ValueError(
            "Contract terms produce a negative prospective cash requirement"
        )
    policy, terms = accounting.policy(
        session,
        contract["policy_id"],
        project,
        date.fromisoformat(contract["effective_date"]),
    )
    schedule = values.schedule
    if schedule and (
        any(decimal(v.quantity) <= 0 for v in schedule)
        or sum((decimal(v.quantity) for v in schedule), Decimal(0)) != quantity
    ):
        raise ValueError(
            "Scheduled quantities must be positive and sum exactly to the allocated quantity"
        )
    rows = []
    offset = source_start
    if schedule:
        for item in schedule:
            end = offset + decimal(item.quantity)
            rows.append(
                {
                    "quantity": item.quantity,
                    "base_minor": valuation(line, end) - valuation(line, offset),
                    "due_date": str(item.due_date) if item.due_date else None,
                }
            )
            offset = end
    else:
        rows = [
            {
                "quantity": str(quantity),
                "base_minor": base,
                "due_date": str(values.due_date or target.due_date)
                if (values.due_date or target.due_date)
                else None,
            }
        ]
    return {
        "policy": "forecast-allocation-v2",
        "currency": project.currency,
        "estimate_id": estimate.id,
        "estimate_line_id": target.id,
        "component_id": values.component_id,
        "estimate_version": estimate.version,
        "estimate_hash": digest(json.loads(estimate.fields_json)),
        "contract_id": record.id,
        "source": {
            "contract": record.snapshot_hash,
            "variations": variations,
            "procurement": pos,
            "policy": policy.snapshot_hash,
            "advance": advance_hash,
        },
        "source_quantity": str(decimal(line["quantity"])),
        "protected_quantity": str(protected),
        "allocation_quantity": str(quantity),
        "source_offset": str(source_start),
        "target_offset": str(target_start),
        "target_quantity": str(quantity * factor),
        "conversion_factor": str(factor),
        "uncommitted_quantity": str(quantity),
        "base_minor": base,
        "tax_minor": tax,
        "retention_minor": retention,
        "advance_minor": recovery,
        "amount": money(base + tax - retention - recovery),
        "cost_amount": money(
            base + (tax if terms["tax_treatment"] == "NONRECOVERABLE" else 0)
        ),
        "tax_treatment": terms["tax_treatment"],
        "due_date": rows[0]["due_date"] if len(rows) == 1 else None,
        "schedule": rows,
        "retention_release_date": str(values.retention_release_date)
        if values.retention_release_date
        else None,
        "warnings": notes,
        "notice": "Approved forecast allocation only; procurement, accounting, budgets and payment authority remain separate.",
    }
