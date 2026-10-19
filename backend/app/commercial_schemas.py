"""Explicit commercial terms. Uploaded descriptions do not confer authority."""

from datetime import date
from typing import Literal

from pydantic import Field

from .advanced_schemas import Contract, Currency, Exact


class Evidence(Contract):
    evidence: str = Field(min_length=5, max_length=4000)


class ContractLine(Contract):
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=3, max_length=500)
    quantity: Exact
    unit: str = Field(min_length=1, max_length=30)
    rate: Exact
    cost_code_id: int
    boq_item_id: int | None = None


class CommercialContract(Evidence):
    kind: Literal["COMMERCIAL_CONTRACT"] = "COMMERCIAL_CONTRACT"
    number: str = Field(min_length=1, max_length=100)
    direction: Literal["SUPPLIER", "CUSTOMER"]
    supplier_id: int | None = None
    customer: str | None = Field(default=None, max_length=200)
    currency: Currency = "BDT"
    policy_id: int
    effective_date: date
    completion_date: date | None = None
    payment_terms_days: int = Field(ge=0, le=365)
    tax_percent: Exact = "0"
    retention_percent: Exact = "0"
    advance_recovery_percent: Exact = "0"
    materials_on_site_allowed: bool = False
    lines: list[ContractLine] = Field(min_length=1, max_length=200)


class RFQ(Evidence):
    kind: Literal["RFQ"] = "RFQ"
    number: str = Field(min_length=1, max_length=100)
    contract_id: int
    item_code: str = Field(min_length=1, max_length=100)
    material_id: int
    quantity: Exact
    delivery_date: date
    closing_date: date
    destination: str = Field(min_length=3, max_length=300)
    country: str = Field(default="BD", pattern=r"^[A-Z]{2}$")
    city: str = Field(default="Dhaka", min_length=1, max_length=120)


class Bid(Evidence):
    kind: Literal["COMMERCIAL_BID"] = "COMMERCIAL_BID"
    rfq_id: int
    supplier_id: int
    observation_id: int
    technical_evidence: str = Field(min_length=5, max_length=4000)


class Recommendation(Evidence):
    kind: Literal["PURCHASE_RECOMMENDATION"] = "PURCHASE_RECOMMENDATION"
    rfq_id: int
    bid_ids: list[int] = Field(min_length=1, max_length=50)
    selected_bid_id: int
    selection_reason: str = Field(min_length=5, max_length=4000)


class PurchaseAward(Evidence):
    kind: Literal["PURCHASE_AWARD"] = "PURCHASE_AWARD"
    recommendation_id: int
    po_number: str = Field(min_length=1, max_length=100)


class ContractVariation(Evidence):
    kind: Literal["CONTRACT_VARIATION"] = "CONTRACT_VARIATION"
    contract_id: int
    number: str = Field(min_length=1, max_length=100)
    item_code: str = Field(min_length=1, max_length=100)
    additional_quantity: Exact
    reprice_quantity: Exact = "0"
    proposed_rate: Exact
    claimed_value: Exact
    reason: str = Field(min_length=5, max_length=4000)
    time_impact_days: int = Field(default=0, ge=-365, le=1095)
    forecast_due_date: date | None = None


class WorkAcceptance(Evidence):
    kind: Literal["WORK_ACCEPTANCE"] = "WORK_ACCEPTANCE"
    contract_id: int
    item_code: str = Field(min_length=1, max_length=100)
    quantity: Exact
    recognition_date: date
    measurement_id: int
    incorporated_acceptance_ids: list[int] = Field(default_factory=list, max_length=100)
    incorporation_evidence: str | None = Field(default=None, max_length=4000)


class AdvanceAssignment(Evidence):
    kind: Literal["ADVANCE_ASSIGNMENT"] = "ADVANCE_ASSIGNMENT"
    contract_id: int
    advance_source_id: int
    amount: Exact
    counterparty_attested: bool


class ForecastSchedule(Contract):
    quantity: Exact
    due_date: date | None = None


class ContractEstimateLink(Evidence):
    kind: Literal["CONTRACT_ESTIMATE_LINK"] = "CONTRACT_ESTIMATE_LINK"
    contract_id: int
    item_code: str = Field(min_length=1, max_length=100)
    estimate_id: int
    estimate_line_id: str = Field(min_length=1, max_length=100)
    complete_cost_scope_confirmed: bool
    due_date: date | None = None
    component_id: str | None = Field(default=None, max_length=100)
    allocation_quantity: Exact | None = None
    source_offset: Exact | None = None
    target_offset: Exact | None = None
    supersedes_id: int | None = None
    schedule: list[ForecastSchedule] = Field(default_factory=list, max_length=100)
    retention_release_date: date | None = None
    advance_assignment_id: int | None = None


class CertificateLine(Contract):
    item_code: str = Field(min_length=1, max_length=100)
    cumulative_quantity: Exact


class InterimCertificate(Evidence):
    kind: Literal["INTERIM_CERTIFICATE"] = "INTERIM_CERTIFICATE"
    contract_id: int
    number: str = Field(min_length=1, max_length=100)
    recognition_date: date
    due_date: date | None = None
    lines: list[CertificateLine] = Field(min_length=1, max_length=200)
    materials_on_site: Exact = "0"
    materials_evidence: str | None = Field(default=None, max_length=4000)
    acceptance_ids: list[int] = Field(default_factory=list, max_length=500)
    materials_acceptance_ids: list[int] = Field(default_factory=list, max_length=500)
    advance_recovery: Exact = "0"
    advance_source_id: int | None = None
    advance_assignment_id: int | None = None
    adjustment: Exact = "0"
    adjustment_reason: str | None = Field(default=None, max_length=4000)
