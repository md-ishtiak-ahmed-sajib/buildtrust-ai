from datetime import timedelta
from decimal import Decimal
import json
import uuid
from fastapi import APIRouter, Request
from sqlalchemy import select
from . import (
    advanced_models as a,
    models as m,
    audit,
    pricing,
    estimating,
    finance,
)
from .advanced_schemas import (
    SearchInput,
    EstimateFields,
    EstimateLine,
    RateComponent,
    UpgradeAsk,
)
from .advanced_math import calculate_takeoff
from .money import canonical, decimal, minor
from .security import DomainError, project_access, require_role


from .upgrade_access import load


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Grounded copilot and demo"])

    @router.post("/advanced/ask")
    def copilot(data: UpgradeAsk, request: Request):
        import re

        with context(request, True) as (session, actor):
            project = project_access(session, actor, data.project_id)
            record = (
                load(session, actor, a.Estimate, data.estimate_id)
                if data.estimate_id
                else None
            )
            if record and record.project_id != project.id:
                raise ValueError("Estimate belongs to another project")
            q, sources, tools, facts = data.question.lower(), [], [], {}
            if any(
                word in q
                for word in (
                    "rfq",
                    "contract",
                    "certificate",
                    "purchase award",
                    "commercial",
                    "variation",
                    "amendment",
                    "correction",
                    "reversal",
                    "composite forecast",
                )
            ):
                from .commercial import KINDS
                from .procurement import KINDS as PROCUREMENT
                from .corrections import KINDS as CORRECTIONS

                KINDS = KINDS | PROCUREMENT | CORRECTIONS
                from .control_models import ControlRecord

                rows = session.scalars(
                    select(ControlRecord)
                    .where(
                        ControlRecord.project_id == project.id,
                        ControlRecord.kind.in_(KINDS),
                    )
                    .order_by(ControlRecord.id.desc())
                    .limit(100)
                )
                facts = {
                    "records": [
                        {
                            "id": row.id,
                            "name": row.name,
                            "kind": row.kind,
                            "status": row.status,
                            "calculated": json.loads(row.calculated_json),
                            "snapshot_hash": row.snapshot_hash,
                        }
                        for row in rows
                    ]
                }
                sources = [
                    {
                        "control_id": row["id"],
                        "snapshot_hash": row["snapshot_hash"],
                        "url": "/commercial",
                    }
                    for row in facts["records"]
                ]
                tools.append(
                    {
                        "tool": "commercial_evidence_register",
                        "input": {"project_id": project.id},
                        "output": facts,
                    }
                )
                counts = {
                    kind: sum(
                        row["kind"] == kind and row["status"] == "APPROVED"
                        for row in facts["records"]
                    )
                    for kind in sorted(KINDS)
                }
                answer = f"Approved commercial records: {json.dumps(counts)}. Certificate calculations retain cumulative, previous and current valuation with sourced deductions. Financial reversals do not reverse accepted cost or physical entitlement: a separately approved linked cost correction is required. Neither correction refunds settled cash. PO amendments preserve original rates and publish only eligible unreceived replacement scope. Component forecast mappings preserve unrelated costs; missing payment and retention dates remain unscheduled. Procurement and budget amendments need separate approval. Payment requires an independently approved installment."
            elif any(
                word in q
                for word in (
                    "evm",
                    "earned value",
                    "margin",
                    "accrual",
                    "cost performance",
                    "receivable",
                    "payable",
                    "retention",
                    "credit",
                    "installment",
                )
            ):
                from .reporting_api import reports
                from .control_models import Journal, ControlRecord

                facts = reports(session, project)
                sources = [
                    {
                        "journal_id": r.id,
                        "snapshot_hash": r.snapshot_hash,
                        "url": "/controls",
                    }
                    for r in session.scalars(
                        select(Journal)
                        .where(Journal.project_id == project.id)
                        .order_by(Journal.id.desc())
                        .limit(30)
                    )
                ]
                tools.append(
                    {
                        "tool": "recognized_cost_performance",
                        "input": {"project_id": project.id},
                        "output": facts,
                    }
                )
                answer = f"Recorded cost: {facts['incurred_cost'] or 'insufficient data'} {project.currency}; certified revenue: {facts['recognized_revenue'] or 'insufficient data'}; project margin: {facts['project_margin_percent'] or 'insufficient data'} percent. EVM: {json.dumps(facts['evm'])}. {facts['accounting_completeness']}"
            elif data.measurement:
                if data.measurement.project_id != project.id:
                    raise ValueError("Measurement belongs to another project")
                facts = calculate_takeoff(data.measurement)
                tools.append(
                    {
                        "tool": "calculate_takeoff",
                        "input": data.measurement.model_dump(mode="json"),
                        "output": facts,
                    }
                )
                answer = f"Calculated quantity: {facts['quantity']} {facts['unit']}. Formula: {facts['formula']}. Geometry only; design and measurement rules require review."
            elif (
                any(word in q for word in ("price", "supplier", "quote"))
                and data.material_id
            ):
                material = load(session, actor, a.Material, data.material_id)
                if material.project_id != project.id:
                    raise ValueError("Material belongs to another project")
                result = pricing.compare(
                    session,
                    material,
                    SearchInput(unit=material.unit, currency=project.currency),
                )
                facts = {
                    "recommended_observation_id": result["recommended_observation_id"],
                    "notice": result["notice"],
                    "offers": result["offers"],
                }
                sources = [
                    {
                        "observation_id": offer["observation_id"],
                        "url": offer["payload"].get("source_url"),
                        "source_type": offer["source_type"],
                    }
                    for offer in result["offers"]
                ]
                tools.append(
                    {
                        "tool": "compare_stored_prices",
                        "input": {"material_id": material.id},
                        "output": facts,
                    }
                )
                answer = (
                    result["notice"]
                    or f"Found {len(result['offers'])} stored source observation(s). Review technical compatibility, cost completeness and retrieval dates before selection."
                )
            elif record and re.search(r"\d+(?:\.\d+)?\s*%", q):
                pct = decimal(re.search(r"(\d+(?:\.\d+)?)\s*%", q).group(1))
                if pct > 100:
                    raise ValueError(
                        "Sensitivity is limited to 0–100%; it is an assumption, not a market forecast"
                    )
                fields = EstimateFields.model_validate_json(record.fields_json)
                changed = 0
                for line in fields.lines:
                    for comp in line.components:
                        if comp.category == "MATERIAL" and (
                            "steel" not in q or "steel" in comp.description.lower()
                        ):
                            comp.unit_price = str(
                                decimal(comp.unit_price) * (1 + pct / 100)
                            )
                            comp.selection_id = None
                            changed += 1
                proposed = a.Estimate(
                    id=record.id,
                    project_id=record.project_id,
                    version=record.version,
                    fields_json="{}",
                    calculated_json="{}",
                )
                estimating.calculate(session, proposed, fields)
                facts = {
                    "assumed_increase_percent": str(pct),
                    "affected_components": changed,
                    "original_total": str(Decimal(record.total_minor) / 100),
                    "scenario_total": str(Decimal(proposed.total_minor) / 100),
                    "increase": str(
                        Decimal(proposed.total_minor - record.total_minor) / 100
                    ),
                    "forecast": estimating.preview_forecast(
                        session, proposed, request.app.state.settings
                    ),
                }
                tools.append(
                    {
                        "tool": "estimate_sensitivity",
                        "input": {"estimate_id": record.id, "percent": str(pct)},
                        "output": facts,
                    }
                )
                answer = f"With an assumed {pct}% material rate increase across {changed} component(s), the estimate increases by {project.currency} {facts['increase']} to {facts['scenario_total']}. No saved rate, budget or cash was changed."
            elif record and any(
                word in q for word in ("cash", "liquidity", "forecast")
            ):
                facts = estimating.preview_forecast(
                    session, record, request.app.state.settings
                )
                tools.append(
                    {
                        "tool": "estimate_forecast",
                        "input": {"estimate_id": record.id},
                        "output": facts,
                    }
                )
                answer = f"Including scheduled uncommitted estimated costs, the 30-day base minimum is {project.currency} {facts['scenarios'][0]['lowest_balance']}. Unscheduled estimate costs: {facts['unscheduled_estimated_cost']}. Recorded cash: {facts['recorded_cash']}."
            elif record:
                facts = {
                    "estimate": estimating.estimate_view(record),
                    "cost_control": estimating.cost_control(session, project),
                }
                for line in EstimateFields.model_validate_json(
                    record.fields_json
                ).lines:
                    for comp in line.components:
                        if comp.selection_id:
                            selected = session.get(a.PriceSelection, comp.selection_id)
                            snapshot = json.loads(selected.snapshot_json)
                            sources.append(
                                {
                                    "selection_id": selected.id,
                                    "snapshot_hash": selected.snapshot_hash,
                                    "url": snapshot["payload"].get("source_url"),
                                    "source_type": snapshot["source_type"],
                                }
                            )
                tools.append(
                    {
                        "tool": "estimate_and_budget",
                        "input": {"estimate_id": record.id},
                        "output": facts,
                    }
                )
                answer = f"Estimate revision {record.revision} totals {project.currency} {facts['estimate']['total']}. Variance against the current budget baseline: {facts['cost_control']['forecast_vs_budget']}. See the recorded component build-up and source snapshots."
            else:
                answer = "Select an estimate or material to compare stored prices, explain the budget, preview cash flow or calculate an explicit percentage sensitivity. Missing live-price evidence is never invented."
            event = audit.append(
                session,
                actor,
                "ADVANCED_COPILOT_ANSWER",
                "estimate" if record else "project",
                record.id if record else project.id,
                {
                    "question": data.question,
                    "tools": tools,
                    "sources": sources,
                    "answer": answer,
                },
                project.id,
            )
            return {
                "answer": answer,
                "facts": facts,
                "sources": sources,
                "tools": [t["tool"] for t in tools],
                "explanation_source": "deterministic",
                "audit_event_id": event.id,
            }

    @router.post("/advanced/demo-project", status_code=201)
    def upgrade_demo(request: Request, new_run: bool = False):
        if not request.app.state.settings.demo_mode:
            raise DomainError(
                403, "DEMO_DISABLED", "Demonstration controls are disabled."
            )
        with context(request, True) as (session, actor):
            require_role(actor, "ADMIN")
            existing = session.scalar(
                select(m.Project)
                .where(
                    m.Project.code.like("ADVANCED-UPGRADE-DEMO%"),
                    m.Project.active.is_(True),
                )
                .order_by(m.Project.id.desc())
            )
            if existing and not new_run:
                project_access(session, actor, existing.id)
                latest = session.scalar(
                    select(a.Estimate)
                    .where(a.Estimate.project_id == existing.id)
                    .order_by(a.Estimate.id.desc())
                )
                material = session.scalar(
                    select(a.Material)
                    .where(a.Material.project_id == existing.id)
                    .order_by(a.Material.id)
                )
                return {
                    "project_id": existing.id,
                    "already_created": True,
                    "estimate_id": latest.id if latest else None,
                    "material_id": material.id if material else None,
                }
            project = m.Project(
                code="ADVANCED-UPGRADE-DEMO-" + uuid.uuid4().hex[:8],
                name="Price & QS Upgrade — Fictional Demo",
                budget_minor=minor("1450000"),
                balance_minor=minor("2000000"),
                reserve_minor=minor("100000"),
                run_id="upgrade-" + uuid.uuid4().hex[:8],
            )
            session.add(project)
            session.flush()
            for user in session.scalars(select(m.User).where(m.User.active.is_(True))):
                session.add(m.Membership(user_id=user.id, project_id=project.id))
            material = a.Material(
                project_id=project.id,
                name="16 mm B500B Reinforcement Steel",
                category="Steel",
                unit="tonne",
                specification_json=canonical(
                    {"grade": "B500B", "diameter_mm": "16", "standard": "BS 4449"}
                ),
                created_by=actor.id,
            )
            session.add(material)
            session.flush()
            operator = session.scalar(
                select(m.User).where(m.User.role == "OPERATOR", m.User.active.is_(True))
            )
            if not operator:
                raise ValueError("Create an Operator demo account first")
            record = estimating.create_estimate(
                session,
                operator,
                project,
                "Steel procurement planning — fictional",
                False,
            )
            fields = EstimateFields(
                basis="Fictional upgrade example. Explicit zero tax, waste and markup. All 20 tonnes uncommitted; planned payment day 20.",
                lines=[
                    EstimateLine(
                        id="steel-line",
                        code="STEEL-16",
                        description="20 tonnes of 16 mm B500B reinforcement steel",
                        quantity="20",
                        unit="tonne",
                        due_date=finance.business_date() + timedelta(days=19),
                        components=[
                            RateComponent(
                                id="steel-material",
                                material_id=material.id,
                                description=material.name,
                                unit="tonne",
                                unit_price="70000",
                                source_note="Synthetic starting rate, not a current market offer",
                            )
                        ],
                    )
                ],
            )
            estimating.calculate(session, record, fields)
            audit.append(
                session,
                actor,
                "UPGRADE_DEMO_CREATED",
                "project",
                project.id,
                {"fictional": True},
                project.id,
            )
            return {
                "project_id": project.id,
                "estimate_id": record.id,
                "material_id": material.id,
            }

    return router
