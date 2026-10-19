"""Typed payloads for independently checked accounting controls."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from .advanced_schemas import Contract, Currency, Exact
from .governance_schemas import RuleProfile, SupplierChange, CostCodeAssignment
from .procurement_schemas import ProcurementAuthorization, ProcurementAmendment
from .correction_schemas import CertificateCorrection, AcceptedCostCorrection
from .commercial_schemas import (
    CommercialContract,
    RFQ,
    Bid,
    Recommendation,
    PurchaseAward,
    ContractVariation,
    WorkAcceptance,
    InterimCertificate,
    AdvanceAssignment,
    ContractEstimateLink,
)
from .performance_schemas import (
    EstimateMaturity,
    ObligationInput,
    ObligationScheduleChange,
    PerformanceBaseline,
    Progress,
    Sensitivity,
    ProjectSchedule,
    FinancialForecast,
)


class Sourced(Contract):
    evidence: str = Field(min_length=5, max_length=4000)


class AccountingPolicy(Sourced):
    kind: Literal["ACCOUNTING_POLICY"] = "ACCOUNTING_POLICY"
    currency: Currency = "BDT"
    effective_date: date
    cost_recognition: Literal["ACCEPTANCE"] = "ACCEPTANCE"
    revenue_recognition: Literal["APPROVED_CERTIFICATE"] = "APPROVED_CERTIFICATE"
    tax_treatment: Literal["ZERO", "RECOVERABLE", "NONRECOVERABLE"] = "ZERO"
    tax_percent: Exact = "0"
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    retention_percent: Exact = "0"


class Acceptance(Sourced):
    kind: Literal["ACCEPTANCE"] = "ACCEPTANCE"
    policy_id: int
    receipt_line_id: int
    cost_code_id: int
    recognition_date: date


class InvoiceReconciliation(Sourced):
    kind: Literal["INVOICE_RECONCILIATION"] = "INVOICE_RECONCILIATION"
    policy_id: int
    invoice_id: int
    acceptance_ids: list[int] = Field(min_length=1, max_length=500)
    recognition_date: date
    due_date: date | None = None


class CustomerCertificate(Sourced):
    kind: Literal["CUSTOMER_CERTIFICATE"] = "CUSTOMER_CERTIFICATE"
    policy_id: int
    customer: str = Field(min_length=1, max_length=200)
    certificate_number: str = Field(min_length=1, max_length=100)
    revenue: Exact
    output_tax: Exact = "0"
    retention: Exact = "0"
    recognition_date: date
    due_date: date | None = None


class CustomerReceipt(Sourced):
    kind: Literal["CUSTOMER_RECEIPT"] = "CUSTOMER_RECEIPT"
    receivable_id: int
    expected_receivable_version: int
    amount: Exact
    received_date: date
    reference: str = Field(min_length=3, max_length=150)


class CreditNote(Sourced):
    kind: Literal["CREDIT_NOTE"] = "CREDIT_NOTE"
    payable_id: int
    expected_payable_version: int
    amount: Exact
    cost_code_id: int
    recognition_date: date
    reference: str = Field(min_length=3, max_length=150)
    tax_amount: Exact | None = None
    retention_credit: Exact = "0"
    allocation_evidence: str = Field(default="", max_length=4000)


class RetentionRelease(Sourced):
    kind: Literal["RETENTION_RELEASE"] = "RETENTION_RELEASE"
    payable_id: int
    expected_payable_version: int
    amount: Exact
    recognition_date: date


class OpeningLine(Contract):
    account: Literal[
        "PROJECT_COST",
        "CASH",
        "ACCRUED_LIABILITY",
        "ACCOUNTS_PAYABLE",
        "REVENUE",
        "ACCOUNTS_RECEIVABLE",
        "RETENTION_PAYABLE",
        "RETENTION_RECEIVABLE",
        "ADVANCE",
        "CUSTOMER_ADVANCE",
        "RECOVERABLE_TAX",
        "OUTPUT_TAX",
        "OPENING_EQUITY",
    ]
    debit: Exact = "0"
    credit: Exact = "0"
    cost_code_id: int | None = None


class OpeningBalance(Sourced):
    kind: Literal["OPENING_BALANCE"] = "OPENING_BALANCE"
    recognition_date: date
    entries: list[OpeningLine] = Field(min_length=2, max_length=100)


ControlPayload = Annotated[
    AccountingPolicy
    | Acceptance
    | InvoiceReconciliation
    | CustomerCertificate
    | CustomerReceipt
    | CreditNote
    | RetentionRelease
    | OpeningBalance
    | SupplierChange
    | CostCodeAssignment
    | RuleProfile
    | PerformanceBaseline
    | Progress
    | Sensitivity
    | EstimateMaturity
    | ObligationInput
    | ObligationScheduleChange
    | ProjectSchedule
    | FinancialForecast
    | CommercialContract
    | RFQ
    | Bid
    | Recommendation
    | PurchaseAward
    | ContractVariation
    | WorkAcceptance
    | AdvanceAssignment
    | ContractEstimateLink
    | ProcurementAuthorization
    | ProcurementAmendment
    | CertificateCorrection
    | AcceptedCostCorrection
    | InterimCertificate,
    Field(discriminator="kind"),
]


class ControlInput(Contract):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    payload: ControlPayload
    expected_version: int | None = None


class CostCodeInput(Contract):
    project_id: int
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class InstallmentInput(Contract):
    expected_version: int
    amount: Exact


class ControlResponse(Contract):
    id: int
    project_id: int
    kind: str
    name: str
    status: str
    version: int
    prepared_by: int
    checked_by: int | None
    approved_by: int | None
    contributors: list[int]
    payload: ControlPayload
    calculated: dict
    snapshot_hash: str | None
    created_at: str
