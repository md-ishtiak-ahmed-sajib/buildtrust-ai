from typing import Literal
from pydantic import Field
from .advanced_schemas import Contract, Exact


class ProcurementAuthorization(Contract):
    kind: Literal["PROCUREMENT_AUTHORIZATION"] = "PROCUREMENT_AUTHORIZATION"
    boq_item_id: int
    expected_boq_version: int
    additional_quantity: Exact = "0"
    extra_value: Exact = "0"
    reason: str = Field(min_length=5, max_length=4000)
    evidence: str = Field(min_length=5, max_length=4000)


class ProcurementAmendment(Contract):
    kind: Literal["PROCUREMENT_AMENDMENT"] = "PROCUREMENT_AMENDMENT"
    po_line_id: int
    expected_po_version: int
    boq_item_id: int
    retire_quantity: Exact
    replacement_quantity: Exact = "0"
    replacement_rate: Exact = "0"
    successor_po_number: str = Field(default="", max_length=100)
    tax_percent: Exact = "0"
    retention_percent: Exact = "0"
    discount: Exact = "0"
    reason: str = Field(min_length=5, max_length=4000)
    evidence: str = Field(min_length=5, max_length=4000)
