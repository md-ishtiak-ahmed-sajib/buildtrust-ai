"""Shared estimate cash overlay. Approval and the payment liquidity gate stay separate."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from . import (
    coverage,
    finance,
    forecast_links,
    control_models as c,
    models as m,
    procurement,
    commercial_models as cm,
)
from .advanced_math import unit_factor
from .advanced_schemas import EstimateFields
from .commercial_schemas import ContractEstimateLink
from .money import decimal, digest, minor, money
from .security import DomainError


def allowance(fields, base):
    for name in ("site_overhead_percent", "general_overhead_percent"):
        base *= 1 + decimal(getattr(fields, name)) / 100
    return base


def estimated_cost(fields, direct):
    cost = allowance(fields, direct)
    tax = cost * decimal(fields.tax_percent) / 100
    if fields.tax_treatment == "NONRECOVERABLE_COST":
        cost += tax
    cost *= 1 + decimal(fields.contingency_percent) / 100
    cash = cost + (tax if fields.tax_treatment == "RECOVERABLE" else 0)
    return minor(cost), minor(cash), minor(tax)


def overlay(
    session,
    project,
    estimate,
    result,
    *,
    use_contract_links=True,
    scenario="BASE",
    material_percent="10",
    delay_days=15,
):
    fields = EstimateFields.model_validate_json(estimate.fields_json)
    warnings, entries, seen = [], [], set()
    mapped = {}
    if use_contract_links:
        for record, payload, saved in forecast_links.current(
            session, project.id, estimate.id
        ):
            try:
                current = forecast_links.build(
                    session, project, ContractEstimateLink.model_validate(payload)
                )
                if digest(current) != digest(saved):
                    raise ValueError(
                        "Sources changed; independently review a fresh mapping"
                    )
                mapped.setdefault(payload["estimate_line_id"], []).append(
                    (record.id, current)
                )
                warnings.extend(current.get("warnings", []))
            except (ValueError, DomainError) as exc:
                warnings.append(
                    f"Contract mapping #{record.id} unavailable: {exc}. Estimate cost retained."
                )
    escalation = (
        decimal(material_percent)
        if scenario in ("MATERIAL_ESCALATION", "COMBINED")
        else Decimal(0)
    )
    if not -100 <= escalation <= 100:
        raise ValueError("Material scenario percentage must be between -100 and 100")

    def append(line, amount, cost, tax, due, quantity, **extra):
        if not amount and not cost:
            return
        if due and scenario in ("PROJECT_DELAY", "COMBINED"):
            due = str(date.fromisoformat(str(due)) + timedelta(days=delay_days))
        entries.append(
            {
                "line_id": line.id,
                "amount": money(amount),
                "cost_amount": money(cost),
                "tax": money(tax),
                "retention": "0.00",
                "advance_recovery": "0.00",
                "due_date": str(due) if due else None,
                "uncommitted_quantity": str(quantity),
                **extra,
            }
        )

    for line in fields.lines:
        if line.legacy_boq_item_id and line.legacy_boq_item_id in seen:
            raise ValueError(
                "One approved BOQ item cannot cover multiple forecast lines"
            )
        if line.legacy_boq_item_id:
            seen.add(line.legacy_boq_item_id)
        covered, unresolved = coverage.quantity(session, project.id, line)
        warnings.extend(unresolved)
        remaining = max(Decimal(0), decimal(line.quantity) - covered)
        links = mapped.get(line.id, [])
        whole = [v for v in links if v[1]["component_id"] is None]
        whole_quantity = sum(
            (decimal(v["target_quantity"]) for _, v in whole), Decimal(0)
        )
        direct = Decimal(0)
        for comp in line.components:
            quantity = (
                (remaining - whole_quantity)
                * decimal(comp.consumption)
                * (1 + decimal(comp.wastage_percent) / 100)
            )
            quantity -= sum(
                (
                    decimal(v["target_quantity"])
                    for _, v in links
                    if v["component_id"] == comp.id
                ),
                Decimal(0),
            )
            if quantity < 0:
                raise ValueError(
                    "Approved forecast quantities exceed remaining component scope"
                )
            price = decimal(comp.unit_price)
            if comp.category == "MATERIAL":
                price *= 1 + escalation / 100
            direct += quantity * price
        if decimal(fields.tax_percent) and fields.tax_treatment == "UNKNOWN":
            warnings.append(
                f"{line.code}: record tax treatment before calculating unmapped costs"
            )
            # Retain a visible amount; never turn an unresolved tax basis into zero.
        cost, cash, tax = estimated_cost(fields, direct)
        append(
            line,
            cash,
            cost,
            tax,
            line.due_date,
            remaining - whole_quantity,
            scope="ESTIMATE",
        )
        for identity, link in links:
            warnings.extend(
                [
                    f"{line.code}: approved contract rate retained during material escalation"
                ]
                if escalation
                else []
            )
            totals = {
                "base": link["base_minor"],
                "tax": link["tax_minor"],
                "retention": link["retention_minor"],
                "advance": link["advance_minor"],
            }
            used = dict.fromkeys(totals, 0)
            rows = link["schedule"]
            for index, part in enumerate(rows):
                # Allocate rounded terms cumulatively; the last row absorbs only rounding residuals.
                allocation = {}
                for name, total in totals.items():
                    value = (
                        (total - used[name])
                        if index == len(rows) - 1
                        else minor(
                            Decimal(total)
                            / 100
                            * Decimal(part["base_minor"])
                            / Decimal(link["base_minor"])
                        )
                        if link["base_minor"]
                        else 0
                    )
                    used[name] += value
                    allocation[name] = value
                base = Decimal(allocation["base"]) / 100
                overhead = (
                    allowance(fields, base) - base
                    if link["component_id"]
                    else Decimal(0)
                )
                cost_base = (
                    base
                    + overhead
                    + (
                        Decimal(allocation["tax"]) / 100
                        if link["tax_treatment"] == "NONRECOVERABLE"
                        else 0
                    )
                )
                contingency = (
                    cost_base * decimal(fields.contingency_percent) / 100
                    if link["component_id"]
                    else Decimal(0)
                )
                cost = minor(cost_base + contingency)
                cash = (
                    allocation["base"]
                    + allocation["tax"]
                    - allocation["retention"]
                    - allocation["advance"]
                    + minor(overhead + contingency)
                )
                append(
                    line,
                    cash,
                    cost,
                    allocation["tax"],
                    part["due_date"],
                    part["quantity"],
                    contract_link_id=identity,
                    contract_id=link["contract_id"],
                    component_id=link["component_id"],
                    scope="CONTRACT",
                    retention=money(allocation["retention"]),
                    advance_recovery=money(allocation["advance"]),
                )
            if link["retention_minor"]:
                append(
                    line,
                    link["retention_minor"],
                    0,
                    0,
                    link["retention_release_date"],
                    "0",
                    contract_link_id=identity,
                    contract_id=link["contract_id"],
                    component_id=link["component_id"],
                    scope="RETENTION_RELEASE",
                )
    result["estimated_overlay"] = entries
    result.setdefault("unscheduled_obligations", [])
    for item in entries:
        if not item["due_date"]:
            result["unscheduled_obligations"].append(
                {
                    "source_type": "ESTIMATE",
                    "source_id": item["line_id"],
                    "amount": item["amount"],
                    "direction": "OUTFLOW",
                    "category": item.get("scope", "PROCUREMENT"),
                }
            )
    for case in result["scenarios"]:
        cumulative = 0
        for day in case["days"]:
            additions = [
                v
                for v in entries
                if v["due_date"] and max(v["due_date"], result["as_of"]) == day["date"]
            ]
            amount = sum(minor(v["amount"]) for v in additions)
            day["opening"] = money(minor(day["opening"]) - cumulative)
            cumulative += amount
            day["outflows"] = money(minor(day["outflows"]) + amount)
            day["closing"] = money(minor(day["closing"]) - cumulative)
            day.setdefault("obligations", []).extend(
                {
                    "source_type": "ESTIMATE",
                    "source_id": v["line_id"],
                    "amount": v["amount"],
                }
                for v in additions
            )
        low = min(case["days"], key=lambda d: minor(d["closing"]))
        initial = minor(case["days"][0]["opening"])
        minimum = min(initial, minor(low["closing"]))
        case.update(
            lowest_balance=money(minimum),
            pressure_date=result["as_of"]
            if initial < minor(low["closing"])
            else low["date"],
            reserve_maintained=minimum >= project.reserve_minor,
        )
        case["shortfall_obligations"] = [
            o
            for day in case["days"]
            if day["date"] <= case["pressure_date"]
            for o in day["obligations"]
        ]
    result["warnings"] = list(dict.fromkeys(warnings))
    if any(not case["reserve_maintained"] for case in result["scenarios"][:2]):
        result["warnings"].append(
            "Estimated cash requirements breach the reserve; review timing or funding. This overlay cannot authorize payment."
        )
    if any(
        v["due_date"] and v["due_date"] > result["scenarios"][0]["days"][-1]["date"]
        for v in entries
    ):
        result["warnings"].append(
            "Some scheduled estimated costs are outside this preview horizon."
        )
    result["overlay_cost"] = money(sum(minor(v["cost_amount"]) for v in entries))
    result["overlay_cash"] = money(sum(minor(v["amount"]) for v in entries))
    result["overlay_policy"] = (
        "forecast-v2: contract terms on mapped scope; estimate overhead/contingency once on component scope; profit and output tax excluded; retention releases require dates"
    )
    return result


def commitments(session, project):
    """Undated outstanding orders and held retention, excluding recognized source quantities.

    This is exposure, not a fabricated payment schedule. Payable obligations already
    carry recognized installments; historical cash payments are never forecast again.
    """
    import json

    quantities = {}
    # Authoritative invoice entitlement is allocated once, irrespective of installments.
    for claim, line, invoice in session.execute(
        select(c.InvoiceEntitlement, m.InvoiceLine, m.Invoice)
        .join(m.InvoiceLine, c.InvoiceEntitlement.invoice_line_id == m.InvoiceLine.id)
        .join(m.Invoice, m.Invoice.id == c.InvoiceEntitlement.invoice_id)
        .where(m.Invoice.project_id == project.id)
    ):
        key = (invoice.po_id, line.item_code)
        # canonical quantities are kilograms, bag/each or SI units (finance.normalize).
        quantities[key] = quantities.get(key, Decimal(0)) + decimal(
            claim.canonical_quantity
        )
    for allocation, line, invoice, _ in finance.used_allocations(session, project.id):
        if invoice.id < 0:  # Certificate delivery coverage is handled explicitly below.
            continue
        if session.scalar(
            select(c.InvoiceEntitlement.id).where(
                c.InvoiceEntitlement.invoice_line_id == line.id
            )
        ):
            continue
        key = (invoice.po_id, line.item_code)
        quantities[key] = quantities.get(key, Decimal(0)) + decimal(
            allocation.canonical_quantity
        )
    # A certificate's accepted delivery is distinct from invoice entitlement.
    for allocation, record in session.execute(
        select(cm.CertificateAllocation, c.ControlRecord)
        .join(
            c.ControlRecord,
            c.ControlRecord.id == cm.CertificateAllocation.acceptance_id,
        )
        .where(c.ControlRecord.project_id == project.id)
    ):
        payload = json.loads(record.payload_json)
        if record.kind != "ACCEPTANCE":
            continue
        line = session.get(m.ReceiptLine, payload["receipt_line_id"])
        receipt = session.get(m.GoodsReceipt, line.receipt_id)
        key = (receipt.po_id, line.item_code)
        quantities[key] = (
            quantities.get(key, Decimal(0))
            + finance.normalize(line.quantity, line.unit)[0]
        )
    rows = []
    for po in session.scalars(
        select(m.PurchaseOrder).where(
            m.PurchaseOrder.project_id == project.id, m.PurchaseOrder.approved.is_(True)
        )
    ):
        base = 0
        for line in session.scalars(select(m.POLine).where(m.POLine.po_id == po.id)):
            ordered, _, rate = finance.normalize(
                procurement.quantity(session, line), line.unit, line.rate
            )
            base += minor(
                max(
                    Decimal(0),
                    ordered - quantities.get((po.id, line.item_code), Decimal(0)),
                )
                * rate
            )
        if base:
            tax = minor(Decimal(base) / 100 * decimal(po.tax_percent) / 100)
            # Retention is part of total eventual cash, with no invented release date.
            amount = max(0, base + tax - po.discount_minor)
            rows.append(
                {
                    "source_type": "PO_UNRECOGNIZED",
                    "source_id": po.id,
                    "amount": money(amount),
                    "direction": "OUTFLOW",
                    "category": "PROCUREMENT",
                }
            )
    for payable in session.scalars(
        select(c.Payable).where(c.Payable.project_id == project.id)
    ):
        amount = payable.retention_minor - payable.retention_released_minor
        if amount:
            rows.append(
                {
                    "source_type": "PAYABLE_RETENTION",
                    "source_id": payable.id,
                    "amount": money(amount),
                    "direction": "OUTFLOW",
                    "category": "RETENTION",
                }
            )
    return rows


def preview(session, record, settings):
    from .models import Project

    project = session.get(Project, record.project_id)
    base = finance.forecast(session, project, settings)
    result = overlay(session, project, record, deepcopy(base))
    return {
        "estimate_id": record.id,
        "estimate_version": record.version,
        "currency": project.currency,
        "recorded_cash": money(project.balance_minor),
        "base": base,
        "scenarios": result["scenarios"],
        "scheduled_costs": [
            {**v, "amount_minor": minor(v["amount"])}
            for v in result["estimated_overlay"]
            if v["due_date"]
        ],
        "unscheduled_estimated_cost": money(
            sum(
                minor(v["amount"])
                for v in result["estimated_overlay"]
                if not v["due_date"]
            )
        ),
        "warnings": result["warnings"],
        "overlay_cost": result["overlay_cost"],
        "overlay_cash": result["overlay_cash"],
        "unscheduled_commitments": commitments(session, project),
        "estimated_overlay": result["estimated_overlay"],
        "overlay_policy": result["overlay_policy"],
        "notice": "Shared estimate what-if overlay only. Recorded cash and payment eligibility are unchanged.",
    }
