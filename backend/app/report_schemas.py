"""Read contracts for authoritative accounting amounts and scenario outputs."""

from pydantic import BaseModel
from .schemas import Money, ForecastResponse


class AccountingSummary(BaseModel):
    project_id: int
    currency: str
    recorded_cash: Money
    account_balances: dict[str, Money]
    incurred_cost: Money | None
    recognized_revenue: Money | None
    accrued_liability: Money | None
    accounts_payable: Money | None
    accounts_receivable: Money | None
    notice: str


class PayableBalance(BaseModel):
    id: int
    invoice_id: int | None
    certificate_id: int | None
    version: int
    amount: Money
    paid: Money
    credit: Money
    remaining: Money
    retention: Money
    supplier_credit: Money
    currency: str
    due_date: str | None


class ReceivableBalance(BaseModel):
    id: int
    certificate_id: int
    version: int
    amount: Money
    received: Money
    credit: Money
    customer_credit: Money
    remaining: Money
    retention: Money
    currency: str
    due_date: str | None


class BalanceRegister(BaseModel):
    payables: list[PayableBalance]
    receivables: list[ReceivableBalance]


class JournalEntry(BaseModel):
    account: str
    debit: Money
    credit: Money
    cost_code_id: int | None


class JournalResponse(BaseModel):
    id: int
    source_key: str
    business_date: str
    currency: str
    snapshot_hash: str
    entries: list[JournalEntry]


class EVM(BaseModel):
    available: bool
    reason: str | None = None
    as_of: str | None = None
    basis: str | None = None
    baseline_id: int | None = None
    progress_id: int | None = None
    BAC: Money | None = None
    PV: Money | None = None
    EV: Money | None = None
    AC: Money | None = None
    CV: Money | None = None
    SV: Money | None = None
    CPI: str | None = None
    SPI: str | None = None
    EAC: dict[str, Money | None] | None = None
    ETC: dict[str, Money | None] | None = None
    VAC: dict[str, Money | None] | None = None
    TCPI: str | None = None
    notice: str | None = None


class ReportingCurrency(BaseModel):
    currency: str
    available: bool
    factor: str | None
    source: str | None
    rate_date: str | None
    notice: str


class PerformanceReport(AccountingSummary):
    position_as_of: str
    performance_as_of: str
    project_margin_percent: str | None
    project_profit: Money | None
    working_capital: Money | None
    current_ratio: str | None
    budget_utilization_percent: str | None
    ap_aging: dict[str, Money]
    ar_aging: dict[str, Money]
    retention_payable: Money
    retention_receivable: Money
    accounting_completeness: str
    evm: EVM
    reporting_currency: ReportingCurrency
    translated: dict[str, Money | None] | None = None
    forecast_snapshot: dict | None = None


class UnscheduledObligation(BaseModel):
    id: int | None = None
    source_type: str
    source_id: int | str
    amount: Money
    direction: str
    category: str


class EstimatedOverlay(BaseModel):
    cost_amount: Money | None = None
    tax: Money | None = None
    retention: Money | None = None
    advance_recovery: Money | None = None
    component_id: str | None = None
    scope: str | None = None
    line_id: str
    amount: Money
    uncommitted_quantity: str
    due_date: str | None
    contract_link_id: int | None = None
    contract_id: int | None = None


class ExtendedForecast(ForecastResponse):
    unscheduled_commitments: list[UnscheduledObligation] = []
    overlay_cost: Money | None = None
    overlay_cash: Money | None = None
    overlay_policy: str | None = None
    scenario: str
    horizon_days: int
    unscheduled_obligations: list[UnscheduledObligation]
    estimated_overlay: list[EstimatedOverlay]
    warnings: list[str]
    notice: str
    schedule_source_id: int | None = None
