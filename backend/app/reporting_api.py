"""Read-only financial performance, dated FX and explicit scenario forecasts."""

from datetime import date, timedelta
from decimal import Decimal
import json

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from . import (
    accounting,
    coverage,
    finance,
    performance,
)
from . import (
    advanced_models as a,
)
from . import (
    control_models as c,
)
from . import (
    models as m,
)
from .advanced_math import rate_analysis
from .advanced_schemas import EstimateFields
from .money import decimal, minor, money, published, digest
from .security import DomainError
from .security import project_access
from .report_schemas import PerformanceReport, ExtendedForecast


def reports(session, project, as_of=None):
    as_of = as_of or finance.business_date()
    summary = accounting.summary(session, project)
    revenue = (
        decimal(summary["recognized_revenue"])
        if summary["recognized_revenue"] is not None
        else None
    )
    cost = (
        decimal(summary["incurred_cost"])
        if summary["incurred_cost"] is not None
        else None
    )
    margin = (revenue - cost) / revenue * 100 if revenue and cost is not None else None

    def age(rows, remaining):
        buckets = {
            "not_due": 0,
            "1_30": 0,
            "31_60": 0,
            "61_90": 0,
            "over_90": 0,
            "unscheduled": 0,
        }
        for row in rows:
            amount = remaining(row)
            days = (
                (as_of - date.fromisoformat(row.due_date)).days
                if row.due_date
                else None
            )
            key = (
                "unscheduled"
                if days is None
                else "not_due"
                if days <= 0
                else "1_30"
                if days <= 30
                else "31_60"
                if days <= 60
                else "61_90"
                if days <= 90
                else "over_90"
            )
            buckets[key] += amount
        return {key: money(value) for key, value in buckets.items()}

    ap = list(
        session.scalars(select(c.Payable).where(c.Payable.project_id == project.id))
    )
    ar = list(
        session.scalars(
            select(c.Receivable).where(c.Receivable.project_id == project.id)
        )
    )
    liabilities = sum(
        p.amount_minor
        - p.paid_minor
        - p.credit_minor
        + p.retention_minor
        - p.retention_released_minor
        for p in ap
    )
    liabilities += sum(p.customer_credit_minor for p in ar)
    assets = (
        project.balance_minor
        + sum(p.supplier_credit_minor for p in ap)
        + sum(
            p.amount_minor - p.received_minor - p.credit_minor + p.retention_minor
            for p in ar
        )
    )
    accrual = (
        minor(summary["accrued_liability"])
        if summary["accrued_liability"] is not None
        else None
    )
    baseline = session.scalar(
        select(a.BudgetBaseline)
        .where(a.BudgetBaseline.project_id == project.id)
        .order_by(a.BudgetBaseline.id.desc())
    )
    budget = baseline.amount_minor if baseline else project.budget_minor
    forecast_snapshot = session.scalar(
        select(c.ControlRecord)
        .where(
            c.ControlRecord.project_id == project.id,
            c.ControlRecord.kind == "FINANCIAL_FORECAST",
            c.ControlRecord.status == "APPROVED",
        )
        .order_by(c.ControlRecord.id.desc())
    )
    forecast_view = None
    if forecast_snapshot:
        saved = json.loads(forecast_snapshot.calculated_json)
        state, reason = "UNCHANGED", "Recorded source snapshots still agree"
        try:
            from .performance_schemas import FinancialForecast

            current = performance.build(
                session,
                project,
                FinancialForecast.model_validate_json(forecast_snapshot.payload_json),
            )
            if digest(current) != digest(saved):
                state, reason = (
                    "SOURCE_CHANGED",
                    "Sources changed after this approval; review a new forecast snapshot",
                )
        except (ValueError, DomainError):
            state, reason = (
                "UNAVAILABLE",
                "A supporting source is no longer available for revalidation",
            )
        forecast_view = {
            "control_id": forecast_snapshot.id,
            "snapshot_hash": forecast_snapshot.snapshot_hash,
            **saved,
            "source_status": state,
            "source_status_reason": reason,
        }
    return {
        **summary,
        "position_as_of": str(finance.business_date()),
        "performance_as_of": str(as_of),
        "project_margin_percent": published(margin) if margin is not None else None,
        "project_profit": format(revenue - cost, ".2f")
        if revenue is not None and cost is not None
        else None,
        "working_capital": money(assets - liabilities - accrual)
        if accrual is not None
        else None,
        "current_ratio": published(Decimal(assets) / Decimal(liabilities + accrual))
        if accrual is not None and liabilities + accrual > 0
        else None,
        "budget_utilization_percent": published(cost / (Decimal(budget) / 100) * 100)
        if cost is not None and budget
        else None,
        "ap_aging": age(ap, lambda p: p.amount_minor - p.paid_minor - p.credit_minor),
        "ar_aging": age(
            ar, lambda p: p.amount_minor - p.received_minor - p.credit_minor
        ),
        "retention_payable": money(
            sum(p.retention_minor - p.retention_released_minor for p in ap)
        ),
        "retention_receivable": money(sum(p.retention_minor for p in ar)),
        "accounting_completeness": "REVIEW_REQUIRED: historical recognition, loans, advances and tax balances must be reconciled before treating ratios as complete financial statements",
        "evm": performance.evm(session, project, as_of),
        "forecast_snapshot": forecast_view,
    }


def create_router(context):
    router = APIRouter(prefix="/api/v1", tags=["Performance and reports"])

    @router.get(
        "/finance/performance",
        response_model=PerformanceReport,
        response_model_exclude_unset=True,
    )
    def performance_report(
        request: Request,
        project_id: int,
        as_of: date | None = None,
        reporting_currency: str | None = Query(None, min_length=3, max_length=3),
    ):
        with context(request) as (session, actor):
            project = project_access(session, actor, project_id)
            result = reports(session, project, as_of)
            target = reporting_currency or project.currency
            rate = (
                session.scalar(
                    select(a.ExchangeRate)
                    .where(
                        a.ExchangeRate.project_id == project.id,
                        a.ExchangeRate.base == project.currency,
                        a.ExchangeRate.quote == target,
                        a.ExchangeRate.observed_date
                        <= str(as_of or finance.business_date()),
                    )
                    .order_by(
                        a.ExchangeRate.observed_date.desc(), a.ExchangeRate.id.desc()
                    )
                )
                if target != project.currency
                else None
            )
            result["reporting_currency"] = {
                "currency": target,
                "available": target == project.currency or rate is not None,
                "factor": rate.factor
                if rate
                else "1"
                if target == project.currency
                else None,
                "source": rate.source if rate else None,
                "rate_date": rate.observed_date if rate else None,
                "notice": "Reporting translation only; project-currency transactions and payment authority are unchanged.",
            }
            if rate:
                result["translated"] = {
                    key: money(minor(decimal(result[key]) * decimal(rate.factor)))
                    if result[key] is not None
                    else None
                    for key in (
                        "recorded_cash",
                        "incurred_cost",
                        "recognized_revenue",
                        "accounts_payable",
                        "accounts_receivable",
                    )
                }
            return result

    @router.get(
        "/finance/extended-forecast",
        response_model=ExtendedForecast,
        response_model_exclude_unset=True,
    )
    def extended(
        request: Request,
        project_id: int,
        horizon: int = Query(30, ge=1, le=1095),
        project_end: date | None = None,
        scenario: str = Query(
            "BASE",
            pattern="^(BASE|SUPPLIER_ACCELERATION|PROJECT_DELAY|MATERIAL_ESCALATION|COMBINED)$",
        ),
        delay_days: int = Query(15, ge=0, le=365),
        estimate_id: int | None = None,
        material_percent: str = Query("10", max_length=30),
        use_project_schedule: bool = False,
        use_contract_links: bool = False,
    ):
        with context(request) as (session, actor):
            project = project_access(session, actor, project_id)
            today = finance.business_date()
            schedule_source = None
            if use_project_schedule:
                schedule = session.scalar(
                    select(c.ControlRecord)
                    .where(
                        c.ControlRecord.project_id == project.id,
                        c.ControlRecord.kind == "PROJECT_SCHEDULE",
                        c.ControlRecord.status == "APPROVED",
                    )
                    .order_by(c.ControlRecord.id.desc())
                )
                if not schedule:
                    raise ValueError(
                        "Approve a sourced project schedule before selecting project duration"
                    )
                project_end = date.fromisoformat(
                    json.loads(schedule.payload_json)["completion_date"]
                )
                schedule_source = schedule.id
            if project_end:
                horizon = (project_end - today).days + 1
            overrides = {}
            for row in session.scalars(
                select(m.CashMovement).where(
                    m.CashMovement.project_id == project_id,
                    m.CashMovement.settled.is_(False),
                )
            ):
                due = date.fromisoformat(row.due_date)
                if (
                    scenario in ("SUPPLIER_ACCELERATION", "COMBINED")
                    and row.invoice_id
                    and row.kind == "OUTFLOW"
                ):
                    due -= timedelta(days=7)
                if scenario in ("PROJECT_DELAY", "COMBINED") and row.kind == "INFLOW":
                    due += timedelta(days=delay_days)
                overrides[row.id] = {"due_date": str(due)}
            result = finance.forecast(
                session,
                project,
                request.app.state.settings,
                horizon=horizon,
                movement_overrides=overrides,
            )
            result["scenario"] = scenario
            result["horizon_days"] = horizon
            result["schedule_source_id"] = schedule_source
            result["unscheduled_obligations"] = [
                {
                    "id": o.id,
                    "category": o.category,
                    "direction": o.direction,
                    "amount": money(o.amount_minor),
                    "source_type": o.source_type,
                    "source_id": o.source_id,
                }
                for o in session.scalars(
                    select(c.Obligation).where(
                        c.Obligation.project_id == project_id,
                        c.Obligation.due_date.is_(None),
                        c.Obligation.amount_minor > 0,
                    )
                )
            ]
            result["estimated_overlay"] = []
            from .forecasting import commitments

            result["unscheduled_commitments"] = commitments(session, project)
            result["warnings"] = []
            if estimate_id:
                estimate = accounting.scoped(
                    session, a.Estimate, estimate_id, project.id
                )
                from .forecasting import overlay

                overlay(
                    session,
                    project,
                    estimate,
                    result,
                    use_contract_links=use_contract_links,
                    scenario=scenario,
                    material_percent=material_percent,
                    delay_days=delay_days,
                )
            elif scenario in ("MATERIAL_ESCALATION", "COMBINED"):
                result["warnings"].append(
                    "Select an estimate to apply escalation to uncommitted quantities; contractual prices are preserved"
                )
            result["notice"] = (
                "Scenario projection only. Recorded cash, commitments and the original 30-day payment gate remain unchanged. Material escalation requires a sourced estimate sensitivity on uncommitted quantities."
            )
            return result

    return router
