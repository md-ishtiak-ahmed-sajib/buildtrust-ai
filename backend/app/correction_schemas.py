from datetime import date
from typing import Literal
from pydantic import Field
from .advanced_schemas import Contract, Exact


class CertificateCorrection(Contract):
    kind: Literal["CERTIFICATE_CORRECTION"] = "CERTIFICATE_CORRECTION"
    certificate_id: int
    expected_balance_version: int
    base_amount: Exact
    tax_amount: Exact = "0"
    retention_amount: Exact = "0"
    advance_amount: Exact = "0"
    recognition_date: date
    reference: str = Field(min_length=3, max_length=150)
    reason: str = Field(min_length=5, max_length=4000)
    evidence: str = Field(min_length=10, max_length=4000)


class AcceptedCostCorrection(Contract):
    kind: Literal["ACCEPTED_COST_CORRECTION"] = "ACCEPTED_COST_CORRECTION"
    financial_correction_id: int
    acceptance_id: int
    amount: Exact
    recognition_date: date
    reason: str = Field(min_length=5, max_length=4000)
    evidence: str = Field(min_length=10, max_length=4000)
