from typing import Literal

from pydantic import Field

from .advanced_schemas import Contract, Exact


class SupplierChange(Contract):
    kind: Literal["SUPPLIER_CHANGE"] = "SUPPLIER_CHANGE"
    supplier_id: int | None = None
    expected_supplier_version: int | None = None
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    beneficiary_token: str = Field(min_length=5, max_length=200)
    verification_reference: str = Field(min_length=10, max_length=2000)
    verification_attested: bool
    evidence: str = Field(min_length=10, max_length=4000)


class OpeningRule(Contract):
    calculation: Literal["MASONRY", "FINISHES", "AREA", "DOORS_WINDOWS", "FORMWORK_SLAB"]
    threshold_m2: Exact
    comparison: Literal["GT", "GE"] = "GT"
    multiply_selected_faces: bool = False


class RuleProfile(Contract):
    kind: Literal["RULE_PROFILE"] = "RULE_PROFILE"
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=3, max_length=200)
    edition: str = Field(min_length=3, max_length=200)
    source_url: str = Field(min_length=10, max_length=1000)
    rule_reference: str = Field(min_length=3, max_length=2000)
    reviewer_evidence: str = Field(min_length=10, max_length=4000)
    templates: list[str] = Field(min_length=1, max_length=30)
    deduction_rule: Literal["EXPLICIT_MEASUREMENTS_ONLY"] = "EXPLICIT_MEASUREMENTS_ONLY"
    evidence: str = Field(min_length=10, max_length=4000)
    opening_rules: list[OpeningRule] = Field(default_factory=list, max_length=5)


class CostCodeAssignment(Contract):
    kind: Literal["COST_CODE_ASSIGNMENT"] = "COST_CODE_ASSIGNMENT"
    source_type: Literal["BOQ_ITEM", "PO_LINE", "RECEIPT_LINE", "INVOICE_LINE"]
    source_id: int
    expected_source_version: int
    cost_code_id: int
    expected_link_version: int | None = None
    evidence: str = Field(min_length=10, max_length=4000)
