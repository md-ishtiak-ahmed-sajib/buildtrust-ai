from datetime import date
from typing import Literal

from pydantic import Field

from .advanced_schemas import Contract, Currency, Exact


class PlannedValue(Contract):
    date: date
    value: Exact


class PerformanceBaseline(Contract):
    kind: Literal["PERFORMANCE_BASELINE"] = "PERFORMANCE_BASELINE"
    bac: Exact
    approved_estimate_id: int | None = None
    planned_values: list[PlannedValue] = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=10, max_length=4000)


class Progress(Contract):
    kind: Literal["PROGRESS"] = "PROGRESS"
    baseline_id: int
    as_of: date
    earned_value: Exact
    physical_progress_evidence: str = Field(min_length=10, max_length=4000)
    bottom_up_remaining: Exact | None = None
    bottom_up_source: str = Field(default="", max_length=4000)
    evidence: str = Field(min_length=10, max_length=4000)


class Sensitivity(Contract):
    kind: Literal["SENSITIVITY"] = "SENSITIVITY"
    estimate_id: int
    material_percent: Exact = "0"
    labour_percent: Exact = "0"
    equipment_percent: Exact = "0"
    transport_percent: Exact = "0"
    fx_percent: Exact = "0"
    waste_points: Exact = "0"
    delay_days: int = Field(default=0, ge=0, le=365)
    evidence: str = Field(min_length=10, max_length=4000)


class EstimateMaturity(Contract):
    kind: Literal["ESTIMATE_MATURITY"] = "ESTIMATE_MATURITY"
    estimate_id: int
    design_definition: str = Field(min_length=10, max_length=4000)
    input_evidence: list[str] = Field(min_length=1, max_length=100)
    uncertainty_basis: str = Field(min_length=10, max_length=4000)
    claimed_classification: str = Field(default="", max_length=200)
    classification_source: str = Field(default="", max_length=2000)
    evidence: str = Field(min_length=10, max_length=4000)
    historical_estimate_ids: list[int] = Field(default_factory=list, max_length=20)


class ObligationInput(Contract):
    kind: Literal["OBLIGATION"] = "OBLIGATION"
    direction: Literal["INFLOW", "OUTFLOW"]
    category: Literal[
        "PAYROLL",
        "EQUIPMENT",
        "LOAN",
        "TAX",
        "RETENTION",
        "PROCUREMENT",
        "RECEIVABLE",
        "OTHER",
    ]
    amount: Exact
    due_date: date | None = None
    currency: Currency = "BDT"
    evidence: str = Field(min_length=10, max_length=4000)


class ObligationScheduleChange(Contract):
    kind: Literal["OBLIGATION_SCHEDULE_CHANGE"] = "OBLIGATION_SCHEDULE_CHANGE"
    obligation_id: int
    expected_obligation_version: int
    due_date: date | None = None
    reason: str = Field(min_length=5, max_length=4000)
    evidence: str = Field(min_length=10, max_length=4000)


class ProjectSchedule(Contract):
    kind: Literal["PROJECT_SCHEDULE"] = "PROJECT_SCHEDULE"
    start_date: date
    completion_date: date
    evidence: str = Field(min_length=10, max_length=4000)


class FinancialForecast(Contract):
    kind: Literal["FINANCIAL_FORECAST"] = "FINANCIAL_FORECAST"
    customer_contract_ids: list[int] = Field(min_length=1, max_length=100)
    cost_method: Literal[
        "APPROVED_ESTIMATE",
        "remaining_at_budget",
        "cpi_based",
        "combined_cpi_spi",
        "bottom_up",
    ] = "APPROVED_ESTIMATE"
    estimate_id: int | None = None
    as_of: date
    complete_scope_confirmed: bool
    evidence: str = Field(min_length=10, max_length=4000)
