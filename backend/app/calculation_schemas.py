"""Explicit public calculation contracts. Stored approval evidence is not rewritten."""

from pydantic import BaseModel, Field, JsonValue
from .schemas import Money, ForecastResponse, ForecastScenario


class Allowance(BaseModel):
    base: str
    percent: str
    amount: str


class CalculatedComponent(BaseModel):
    id: str
    category: str
    amount: str
    source: int | str


class CalculatedLine(BaseModel):
    id: str
    code: str
    quantity: str
    unit: str
    unit_rate: str
    amount: Money
    cost_unit_rate: str | None = None
    cost_amount: Money | None = None
    cost_build_up: dict[str, Allowance | str] = Field(default_factory=dict)
    components: list[CalculatedComponent]
    categories: dict[str, str]
    build_up: dict[str, Allowance | str]


class RateAnalysis(BaseModel):
    total: Money
    tender_total: Money | None = None
    cost_total: Money | None = None
    cost_policy: str | None = None
    lines: list[CalculatedLine]
    policy: str


class EstimateDifferenceItem(BaseModel):
    code: str
    left: CalculatedLine | None
    right: CalculatedLine | None


class EstimateDifference(BaseModel):
    left: int
    right: int
    total_difference: Money
    items: list[EstimateDifferenceItem]


class ScheduledEstimateCost(BaseModel):
    line_id: str
    due_date: str | None
    amount: Money
    amount_minor: int | None = None  # Legacy additive field, not a new authority.
    cost_amount: Money | None = None
    tax: Money | None = None
    retention: Money | None = None
    advance_recovery: Money | None = None
    uncommitted_quantity: str
    component_id: str | None = None
    contract_link_id: int | None = None
    contract_id: int | None = None
    scope: str | None = None


class EstimateForecast(BaseModel):
    unscheduled_commitments: list["CommitmentExposure"] = Field(default_factory=list)
    estimate_id: int
    estimate_version: int
    currency: str
    recorded_cash: Money
    base: ForecastResponse
    scenarios: list[ForecastScenario]
    scheduled_costs: list[ScheduledEstimateCost]
    unscheduled_estimated_cost: Money
    estimated_overlay: list[ScheduledEstimateCost]
    overlay_cost: Money
    overlay_cash: Money
    overlay_policy: str
    warnings: list[str]
    notice: str


class CommitmentExposure(BaseModel):
    source_type: str
    source_id: int
    amount: Money
    direction: str
    category: str


class CostControl(BaseModel):
    project_id: int
    currency: str
    original_budget: Money
    approved_estimate_budget: Money | None
    current_estimate: Money | None
    estimate_id: int | None
    estimate_status: str | None
    forecast_vs_budget: Money | None
    budget_overrun: bool
    tender_vs_budget: Money | None
    po_line_commitment: Money
    commitment_basis: str
    paid_cash: Money
    current_cost_estimate: Money | None
    current_tender_estimate: Money | None
    actual_incurred_cost: Money | None
    accrued_liabilities: Money | None
    notice: str


class PriceSelectionPreview(BaseModel):
    old_rate: str
    new_rate: str
    difference_percent: str | None
    item_amount: Money
    estimate_total: Money
    estimate_difference: Money
    forecast_minimum: Money
    forecast_difference: Money
    evidence_hash: str
    notice: str


class CostCodePositionRow(BaseModel):
    id: int
    code: str
    name: str
    budget: Money | None
    commitment: Money
    cost: Money
    accrual: Money
    payable: Money
    paid: Money
    recognized_commitment: Money
    remaining_commitment: Money


class CostCodePosition(BaseModel):
    currency: str
    rows: list[CostCodePositionRow]
    exceptions: list[str]
    notice: str


class ProfileSnapshot(BaseModel):
    name: str
    edition: str
    source_url: str
    rules: dict[str, JsonValue]
    verification_status: str


class OpeningApplication(BaseModel):
    reference: str
    each_area_m2: str
    count: str
    deducted: bool
    threshold_m2: str
    comparison: str


class TakeoffResult(BaseModel):
    quantity: str
    gross_quantity: str
    unit: str
    formula: str
    deduction: str
    warnings: list[str]
    calculation_policy: str
    profile_snapshot: ProfileSnapshot
    profile_applied_rules: list[OpeningApplication] = Field(default_factory=list)
