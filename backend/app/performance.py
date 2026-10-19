"""Sourced cost performance and immutable estimating scenarios."""

import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from . import (
    accounting,
    finance,
    obligations,
)
from . import (
    advanced_models as a,
)
from . import (
    control_models as c,
)
from .advanced_math import rate_analysis
from .advanced_schemas import EstimateFields
from .money import decimal, digest, minor, money, published

KINDS = {
    "PERFORMANCE_BASELINE",
    "PROGRESS",
    "SENSITIVITY",
    "ESTIMATE_MATURITY",
    "OBLIGATION",
    "OBLIGATION_SCHEDULE_CHANGE",
    "PROJECT_SCHEDULE",
    "FINANCIAL_FORECAST",
}


def build(session, project, values):
    kind = values.kind
    if kind == "OBLIGATION_SCHEDULE_CHANGE":
        row = accounting.scoped(session, c.Obligation, values.obligation_id, project.id)
        if row.version != values.expected_obligation_version:
            raise accounting.DomainError(
                409,
                "SOURCE_CHANGED",
                "Obligation changed; refresh the schedule review.",
            )
        return {
            "obligation_id": row.id,
            "source_version": row.version,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "amount": money(row.amount_minor),
            "currency": row.currency,
            "old_due_date": row.due_date,
            "due_date": str(values.due_date) if values.due_date else None,
            "cash_movement_id": row.cash_movement_id,
        }
    if kind == "PROJECT_SCHEDULE":
        if not 0 <= (values.completion_date - values.start_date).days < 1095:
            raise ValueError(
                "Project schedule requires ascending dates within 1095 calendar days"
            )
        return {
            "start_date": str(values.start_date),
            "completion_date": str(values.completion_date),
            "calendar": "Explicit calendar dates; no contractual holiday rules inferred",
        }
    if kind == "FINANCIAL_FORECAST":
        from .commercial import contract_scope, valuation

        if (
            not values.complete_scope_confirmed
            or values.as_of > finance.business_date()
        ):
            raise ValueError(
                "Confirm the complete recorded forecast scope at a nonfuture observation date"
            )
        if len(set(values.customer_contract_ids)) != len(values.customer_contract_ids):
            raise ValueError(
                "Duplicate revenue contracts would double count forecast revenue"
            )
        revenue, sources = 0, []
        for identity in values.customer_contract_ids:
            record, payload, lines, variations = contract_scope(
                session, project.id, identity
            )
            if payload["direction"] != "CUSTOMER":
                raise ValueError(
                    "Forecast revenue requires approved customer contracts"
                )
            revenue += sum(valuation(line, line["quantity"]) for line in lines.values())
            sources.append(
                {
                    "contract_id": record.id,
                    "hash": record.snapshot_hash,
                    "variations": variations,
                }
            )
        if values.cost_method == "APPROVED_ESTIMATE":
            estimate = accounting.scoped(
                session, a.Estimate, values.estimate_id, project.id
            )
            cost = json.loads(estimate.calculated_json).get("cost_total")
            if estimate.status != "APPROVED" or cost is None:
                raise ValueError("An approved explicit cost estimate is required")
            cost_source = {
                "estimate_id": estimate.id,
                "snapshot_hash": estimate.snapshot_hash,
            }
        else:
            report = evm(session, project, values.as_of)
            cost = report.get("EAC", {}).get(values.cost_method)
            if cost is None:
                raise ValueError(
                    "The selected EAC method is unavailable without sourced progress, costs and denominators"
                )
            cost_source = report
        total_cost = minor(cost)
        return {
            "as_of": str(values.as_of),
            "currency": project.currency,
            "forecast_revenue": money(revenue),
            "forecast_cost": money(total_cost),
            "forecast_profit": money(revenue - total_cost),
            "forecast_margin_percent": published(
                Decimal(revenue - total_cost) / Decimal(revenue) * 100
            )
            if revenue > 0
            else None,
            "revenue_sources": sources,
            "cost_source": cost_source,
            "notice": "Independently reviewed scope snapshot. Forecast revenue is separate from certified revenue, receivables and cash.",
        }
    if kind == "PERFORMANCE_BASELINE":
        bac = accounting.positive(values.bac)
        previous, last = -1, None
        for point in values.planned_values:
            value = minor(point.value)
            if (
                value < previous
                or value > bac
                or value < 0
                or (last and point.date <= last)
            ):
                raise ValueError(
                    "Planned values require ascending dates and nondecreasing cost values within BAC"
                )
            previous, last = value, point.date
        source = None
        if values.approved_estimate_id:
            estimate = accounting.scoped(
                session, a.Estimate, values.approved_estimate_id, project.id
            )
            cost = json.loads(estimate.calculated_json).get("cost_total")
            if estimate.status != "APPROVED" or cost is None or minor(cost) != bac:
                raise ValueError("BAC must equal the approved estimate cost basis")
            source = estimate.snapshot_hash
        return {
            "bac": money(bac),
            "basis": "COST",
            "estimate_snapshot": source,
            "planned_values": [
                p.model_dump(mode="json") for p in values.planned_values
            ],
        }
    if kind == "PROGRESS":
        baseline = accounting.scoped(
            session, c.ControlRecord, values.baseline_id, project.id
        )
        if baseline.kind != "PERFORMANCE_BASELINE" or baseline.status != "APPROVED":
            raise ValueError("Approved cost-performance baseline is required")
        bac = minor(json.loads(baseline.calculated_json)["bac"])
        ev = minor(values.earned_value)
        if ev < 0 or ev > bac or values.as_of > finance.business_date():
            raise ValueError("Earned value must be within BAC at an observed date")
        if values.bottom_up_remaining is not None and (
            decimal(values.bottom_up_remaining) < 0
            or len(values.bottom_up_source.strip()) < 10
        ):
            raise ValueError(
                "Bottom-up remaining cost needs a nonnegative amount and source"
            )
        return {
            "earned_value": money(ev),
            "baseline_hash": baseline.snapshot_hash,
            "as_of": str(values.as_of),
            "basis": "Independently checked physical progress valued at baseline cost",
        }
    if kind == "SENSITIVITY":
        estimate = accounting.scoped(
            session, a.Estimate, values.estimate_id, project.id
        )
        fields = EstimateFields.model_validate_json(estimate.fields_json)
        original = rate_analysis(fields)
        adjustments = {
            "MATERIAL": values.material_percent,
            "LABOUR": values.labour_percent,
            "EQUIPMENT": values.equipment_percent,
            "TRANSPORT": values.transport_percent,
        }
        warnings = []
        for number in [*adjustments.values(), values.fx_percent, values.waste_points]:
            if not Decimal(-100) <= decimal(number) <= Decimal(100):
                raise ValueError(
                    "Sensitivity changes are bounded to -100 through 100 percent/points"
                )
        for line in fields.lines:
            if line.due_date:
                line.due_date += timedelta(days=values.delay_days)
            for comp in line.components:
                price = decimal(comp.unit_price) * (
                    1 + decimal(adjustments.get(comp.category, "0")) / 100
                )
                if comp.category == "MATERIAL":
                    waste = decimal(comp.wastage_percent) + decimal(values.waste_points)
                    if not 0 <= waste <= 100:
                        raise ValueError(
                            "Resulting waste must remain between zero and 100 percent"
                        )
                    comp.wastage_percent = str(waste)
                if decimal(values.fx_percent) and comp.selection_id:
                    selection = session.get(a.PriceSelection, comp.selection_id)
                    snapshot = json.loads(selection.snapshot_json)
                    if snapshot["payload"].get("currency") != project.currency:
                        price *= 1 + decimal(values.fx_percent) / 100
                elif decimal(values.fx_percent):
                    warnings.append(
                        f"{line.code}: no foreign-currency selection; FX sensitivity was not applied"
                    )
                comp.unit_price = str(price)
        changed = rate_analysis(fields)
        return {
            "original": original,
            "scenario": changed,
            "cost_difference": money(
                minor(changed["cost_total"]) - minor(original["cost_total"])
            )
            if original["cost_total"] and changed["cost_total"]
            else None,
            "tender_difference": money(
                minor(changed["total"]) - minor(original["total"])
            ),
            "source_estimate_version": estimate.version,
            "source_estimate_hash": digest(json.loads(estimate.fields_json)),
            "warnings": warnings,
            "notice": "Immutable estimate sensitivity. Contractual commitments and recorded cash are unchanged.",
        }
    if kind == "ESTIMATE_MATURITY":
        estimate = accounting.scoped(
            session, a.Estimate, values.estimate_id, project.id
        )
        if (
            values.claimed_classification
            and len(values.classification_source.strip()) < 10
        ):
            raise ValueError(
                "A maturity classification needs explicit source evidence; project labels cannot establish a class"
            )
        if len(set(values.historical_estimate_ids)) != len(
            values.historical_estimate_ids
        ):
            raise ValueError("Historical estimate comparisons must not repeat a source")
        current_fields = EstimateFields.model_validate_json(estimate.fields_json)
        current_result = rate_analysis(current_fields)
        current_costs = {line["id"]: line for line in current_result["lines"]}
        comparisons = []
        for identity in values.historical_estimate_ids:
            previous = accounting.scoped(session, a.Estimate, identity, project.id)
            if previous.id == estimate.id or previous.status != "APPROVED":
                raise ValueError(
                    "Historical comparison requires a different approved project estimate"
                )
            old_fields = EstimateFields.model_validate_json(previous.fields_json)
            old_result = json.loads(previous.calculated_json)
            old_lines = {line.code: line for line in old_fields.lines}
            old_costs = {line["id"]: line for line in old_result["lines"]}
            lines = []
            for line in current_fields.lines:
                prior = old_lines.get(line.code)
                old_cost = (
                    old_costs.get(prior.id, {}).get("cost_unit_rate") if prior else None
                )
                new_cost = current_costs[line.id].get("cost_unit_rate")
                compatible = bool(
                    prior
                    and prior.description == line.description
                    and prior.unit == line.unit
                )
                difference = (
                    (decimal(new_cost) - decimal(old_cost))
                    if compatible and new_cost is not None and old_cost is not None
                    else None
                )
                lines.append(
                    {
                        "code": line.code,
                        "unit": line.unit,
                        "comparison": "EXACT_DESCRIPTION_UNIT"
                        if compatible
                        else "REQUIRES_REVIEW",
                        "historical_quantity": prior.quantity if prior else None,
                        "current_quantity": line.quantity,
                        "historical_cost_rate": old_cost,
                        "current_cost_rate": new_cost,
                        "rate_difference": published(difference)
                        if difference is not None
                        else None,
                        "rate_change_percent": published(
                            difference / decimal(old_cost) * 100
                        )
                        if difference is not None and decimal(old_cost)
                        else None,
                    }
                )
            comparisons.append(
                {
                    "estimate_id": previous.id,
                    "name": previous.name,
                    "revision": previous.revision,
                    "snapshot_hash": previous.snapshot_hash,
                    "approved_cost_total": old_result.get("cost_total"),
                    "current_cost_total": current_result.get("cost_total"),
                    "lines": lines,
                }
            )
        return {
            "estimate_version": estimate.version,
            "estimate_hash": digest(json.loads(estimate.fields_json)),
            "claimed_classification": values.claimed_classification or None,
            "professional_acceptance": "REQUIRES_EXTERNAL_ACCEPTANCE",
            "historical_comparisons": comparisons,
            "notice": "Evidence-based maturity description; no automatic AACE classification or certification.",
        }
    if values.currency != project.currency:
        raise ValueError(
            "Obligation currency must match the project; reporting FX cannot authorize transactions"
        )
    return {
        "amount": money(accounting.positive(values.amount)),
        "due_date": str(values.due_date) if values.due_date else None,
        "scheduled": values.due_date is not None,
        "direction": values.direction,
        "category": values.category,
    }


def apply(session, actor, project, record, values, result):
    if values.kind == "OBLIGATION_SCHEDULE_CHANGE":
        row = accounting.scoped(session, c.Obligation, values.obligation_id, project.id)
        linked = (
            session.get(
                __import__("app.models", fromlist=["CashMovement"]).CashMovement,
                row.cash_movement_id,
            )
            if row.cash_movement_id
            else None
        )
        obligations.sync(
            session,
            project,
            row.source_type,
            row.source_id,
            row.direction,
            row.category,
            row.amount_minor,
            values.due_date,
            invoice_id=linked.invoice_id if linked else None,
            clear_due_date=values.due_date is None,
        )
        if row.source_type in ("PAYABLE", "RECEIVABLE"):
            balance = session.get(
                c.Payable if row.source_type == "PAYABLE" else c.Receivable,
                row.source_id,
            )
            if balance:
                balance.due_date = str(values.due_date) if values.due_date else None
                balance.version += 1
        return
    if values.kind == "OBLIGATION":
        obligations.sync(
            session,
            project,
            "CONTROL",
            record.id,
            values.direction,
            values.category,
            minor(values.amount),
            str(values.due_date) if values.due_date else None,
        )


def evm(session, project, as_of=None):
    as_of = as_of or finance.business_date()
    baseline = session.scalar(
        select(c.ControlRecord)
        .where(
            c.ControlRecord.project_id == project.id,
            c.ControlRecord.kind == "PERFORMANCE_BASELINE",
            c.ControlRecord.status == "APPROVED",
        )
        .order_by(c.ControlRecord.id.desc())
    )
    if not baseline:
        return {
            "available": False,
            "reason": "Approved cost-performance baseline is missing",
        }
    payload = json.loads(baseline.payload_json)
    bac = decimal(payload["bac"])
    points = [p for p in payload["planned_values"] if p["date"] <= str(as_of)]
    pv = decimal(points[-1]["value"]) if points else Decimal(0)
    progress = session.scalar(
        select(c.ControlRecord)
        .where(
            c.ControlRecord.project_id == project.id,
            c.ControlRecord.kind == "PROGRESS",
            c.ControlRecord.status == "APPROVED",
            func.json_extract(c.ControlRecord.payload_json, "$.baseline_id")
            == baseline.id,
            func.json_extract(c.ControlRecord.payload_json, "$.as_of") <= str(as_of),
        )
        .order_by(
            func.json_extract(c.ControlRecord.payload_json, "$.as_of").desc(),
            c.ControlRecord.id.desc(),
        )
    )
    count = session.scalar(
        select(func.count(c.JournalLine.id))
        .join(c.Journal)
        .where(
            c.Journal.project_id == project.id,
            c.Journal.business_date <= str(as_of),
            c.JournalLine.account == "PROJECT_COST",
        )
    )
    actual = session.scalar(
        select(func.sum(c.JournalLine.debit_minor - c.JournalLine.credit_minor))
        .join(c.Journal)
        .where(
            c.Journal.project_id == project.id,
            c.Journal.business_date <= str(as_of),
            c.JournalLine.account == "PROJECT_COST",
        )
    )
    ac = Decimal(actual or 0) / 100 if count else None
    ev = (
        decimal(json.loads(progress.payload_json)["earned_value"]) if progress else None
    )
    cpi = ev / ac if ev is not None and ac is not None and ac > 0 else None
    spi = ev / pv if ev is not None and pv > 0 else None
    bottom = (
        json.loads(progress.payload_json).get("bottom_up_remaining")
        if progress
        else None
    )
    fmt = lambda value: (
        format(value.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP"), "f")
        if value is not None
        else None
    )
    estimates = {
        "remaining_at_budget": ac + bac - ev
        if ac is not None and ev is not None
        else None,
        "cpi_based": bac / cpi if cpi and cpi > 0 else None,
        "combined_cpi_spi": ac + (bac - ev) / (cpi * spi)
        if cpi and spi and cpi > 0 and spi > 0
        else None,
        "bottom_up": ac + decimal(bottom)
        if bottom is not None and ac is not None
        else None,
    }
    return {
        "available": ev is not None and ac is not None,
        "as_of": str(as_of),
        "basis": "COST",
        "baseline_id": baseline.id,
        "progress_id": progress.id if progress else None,
        "BAC": fmt(bac),
        "PV": fmt(pv),
        "EV": fmt(ev),
        "AC": fmt(ac),
        "CV": fmt(ev - ac) if ev is not None and ac is not None else None,
        "SV": fmt(ev - pv) if ev is not None else None,
        "CPI": published(cpi) if cpi is not None else None,
        "SPI": published(spi) if spi is not None else None,
        "EAC": {key: fmt(value) for key, value in estimates.items()},
        "ETC": {
            key: fmt(value - ac) if value is not None and ac is not None else None
            for key, value in estimates.items()
        },
        "VAC": {
            key: fmt(bac - value) if value is not None else None
            for key, value in estimates.items()
        },
        "TCPI": published((bac - ev) / (bac - ac))
        if ac is not None and ev is not None and bac > ac
        else None,
        "notice": "Missing progress, costs or zero denominators remain unavailable. AC is recognized project cost, not cash paid.",
    }
