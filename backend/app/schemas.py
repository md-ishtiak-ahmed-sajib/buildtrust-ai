from datetime import date
from typing import Literal, Annotated, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from .money import decimal


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class ItemInput(BaseModel):
    item_code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    quantity: str
    unit: str = Field(min_length=1, max_length=30)
    unit_rate: str = "0"
    amount: str | None = None

    @field_validator("quantity", "unit_rate", "amount", mode="before")
    @classmethod
    def exact_number(cls, value):
        if value is None:
            return value
        result = decimal(value)
        if result < 0 or result.as_tuple().exponent < -8:
            raise ValueError(
                "Use nonnegative decimals with at most 8 fractional digits"
            )
        return str(result)

    @model_validator(mode="after")
    def positive_quantity(self):
        if decimal(self.quantity) <= 0:
            raise ValueError("Quantity must be positive")
        return self


class DocumentInput(BaseModel):
    document_type: Literal["BOQ", "PO", "GRN", "INVOICE", "VARIATION"]
    supplier_code: str = Field(default="", max_length=80)
    po_number: str = Field(default="", max_length=100)
    receipt_number: str = Field(default="", max_length=100)
    invoice_number: str = Field(default="", max_length=100)
    invoice_date: date | None = None
    currency: str = Field(default="BDT", pattern="^[A-Z]{3}$")
    beneficiary_fingerprint: str = Field(default="", max_length=128)
    subtotal: str = "0"
    tax: str = "0"
    retention: str = "0"
    discount: str = "0"
    grand_total: str = "0"
    tax_percent: str = "0"
    retention_percent: str = "0"
    notes: str = Field(default="", max_length=20000)
    items: list[ItemInput] = Field(min_length=1, max_length=500)

    @field_validator(
        "subtotal",
        "tax",
        "retention",
        "discount",
        "grand_total",
        "tax_percent",
        "retention_percent",
        mode="before",
    )
    @classmethod
    def exact_money(cls, value):
        result = decimal(value)
        if result < 0:
            raise ValueError("Negative financial values are unsupported")
        return str(result)

    @model_validator(mode="after")
    def document_requirements(self):
        if self.document_type == "INVOICE" and not (
            self.invoice_number
            and self.invoice_date
            and self.supplier_code
            and self.po_number
            and self.beneficiary_fingerprint
            and decimal(self.grand_total) > 0
        ):
            raise ValueError(
                "Invoice identity, date, PO, supplier, beneficiary, and positive total are required"
            )
        if self.document_type == "PO" and not (self.po_number and self.supplier_code):
            raise ValueError("PO number and supplier are required")
        if self.document_type == "GRN" and not (self.po_number and self.receipt_number):
            raise ValueError("Receipt number and PO are required")
        if decimal(self.tax_percent) > 100 or decimal(self.retention_percent) > 100:
            raise ValueError("Percentages cannot exceed 100")
        codes = [item.item_code for item in self.items]
        if len(codes) != len(set(codes)):
            raise ValueError("Combine duplicate item codes into one line")
        return self


class CorrectionRequest(BaseModel):
    version: int = Field(ge=1)
    data: DocumentInput


class AnalyzeRequest(BaseModel):
    invoice_id: int = Field(gt=0)


class ProposalRequest(AnalyzeRequest):
    pass


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    project_id: int
    invoice_id: int | None = None


class Finding(BaseModel):
    code: str
    severity: Literal["INFO", "WARNING", "BLOCK"]
    message: str
    evidence: list[dict] = Field(default_factory=list)


class FieldEvidence(BaseModel):
    path: str
    value: str
    source_document_id: int
    page: int | None = None
    row: int | None = None
    extraction_method: str
    confidence: float | None = None
    human_reviewed: bool
    reviewed_by: int | None = None


class ReceiptResponse(BaseModel):
    payment_id: int
    proposal_id: int
    invoice_id: int | None
    payable_id: int | None = None
    certificate_id: int | None = None
    invoice_number: str
    supplier: str
    amount: str
    currency: str
    beneficiary_fingerprint: str
    mock_transaction_id: str
    provider: str
    status: Literal["SETTLED"] = "SETTLED"
    simulation: Literal[True] = True
    executed_at: str
    balance_after: str


Money = Annotated[str, Field(pattern=r"^-?\d+\.\d{2}$")]


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    approval_limit: Money


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse


class ProjectResponse(BaseModel):
    id: int
    code: str
    name: str
    client: str
    currency: str
    budget: Money
    balance: Money
    minimum_reserve: Money
    run_id: str
    active: bool


class DocumentResponse(BaseModel):
    id: int
    project_id: int
    document_type: str
    original_filename: str
    sha256: str
    extraction_status: str
    version: int
    reviewed_by: int | None
    confirmed_by: int | None
    created_at: str


class DailyProjection(BaseModel):
    date: str
    opening: Money
    inflows: Money
    outflows: Money
    closing: Money
    obligations: list[dict[str, Any]]


class ForecastScenario(BaseModel):
    name: str
    days: list[DailyProjection]
    lowest_balance: Money
    pressure_date: str
    reserve_maintained: bool
    shortfall_obligations: list[dict[str, Any]]


class ForecastResponse(BaseModel):
    project_id: int
    currency: str
    as_of: str
    recorded_balance: Money
    reserved: Money
    available_cash: Money
    proposed_payment: Money
    minimum_reserve: Money
    receivable_delay_days: int
    policy_receivable_delay_days: int = 15
    cost_pressure_percent: str
    scenarios: list[ForecastScenario]
    payment_eligible: bool
    currency_mismatch: bool
    recommendation: str
    assumption_notice: str


class ComparisonResponse(BaseModel):
    invoice_line_id: int
    item_code: str
    description: str
    unit: str
    boq_quantity: str
    po_quantity: str
    accepted_quantity: str
    previously_allocated: str
    available_entitlement: str
    invoice_quantity: str
    excess_quantity: str
    quantity_variance_percent: str | None
    contract_rate: str
    invoice_rate: str
    claimed_amount: Money
    verified_amount: Money
    difference: Money
    severity: str
    evidence: list[dict[str, Any]]


class VerificationResponse(BaseModel):
    invoice_id: int
    invoice_number: str
    analysis_version: int
    status: str
    currency: str
    claimed_amount: Money
    verified_amount: Money
    difference: Money
    comparisons: list[ComparisonResponse]
    findings: list[Finding]
    cashflow: ForecastResponse
    payment_eligible: bool
    explanation_source: str
    explanation: str
    suggested_action: str
    analyzed_at: str | None = None


class ProposalResponse(BaseModel):
    id: int
    project_id: int
    invoice_id: int | None
    payable_id: int | None = None
    certificate_id: int | None = None
    invoice_number: str
    supplier: str
    amount: Money
    currency: str
    status: str
    requested_by: int
    beneficiary_fingerprint: str
    snapshot_hash: str
    expires_at: str
    created_at: str
    version: int
    approvals: list[dict[str, Any]]
    payment_id: int | None


class WorkflowStepResponse(BaseModel):
    id: int
    name: str
    tool: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any]
    started_at: str
    finished_at: str | None


class WorkflowResponse(BaseModel):
    id: int
    invoice_id: int
    status: str
    error: str | None
    created_at: str
    result: dict[str, Any]
    steps: list[WorkflowStepResponse]
