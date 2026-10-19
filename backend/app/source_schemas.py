"""Typed source and calculation views; archived evidence retains its original JSON."""

from pydantic import BaseModel, Field, JsonValue
from .advanced_schemas import QuotationInput, TakeoffInput
from .calculation_schemas import TakeoffResult
from .schemas import Money


class MaterialView(BaseModel):
    id: int
    project_id: int
    name: str
    category: str
    unit: str
    specification: dict[str, str]
    version: int
    active: bool


class EvidenceRevisionView(BaseModel):
    id: int
    version: int
    evidence: dict[str, JsonValue]
    snapshot_hash: str
    actor_id: int
    created_at: str


class QuotationView(BaseModel):
    id: int
    project_id: int
    material_id: int
    fields: QuotationInput
    version: int
    status: str
    prepared_by: int
    contributors: list[int]
    verified_by: int | None
    filename: str | None
    attachment_hash: str | None
    created_at: str
    evidence_revisions: list[EvidenceRevisionView]


class ProviderView(BaseModel):
    id: str
    source_type: str
    enabled: bool
    notice: str | None = None


class MeasurementProfileView(BaseModel):
    id: int
    code: str
    name: str
    edition: str
    source_url: str
    verification_status: str
    rules: dict[str, JsonValue]


class RecordVersionView(BaseModel):
    id: int
    version: int
    status: str


class SavedMeasurementView(RecordVersionView):
    result: TakeoffResult


class MeasurementView(SavedMeasurementView):
    prepared_by: int
    checked_by: int | None
    fields: TakeoffInput
    created_at: str


class ExchangeRateView(BaseModel):
    id: int
    base: str
    quote: str
    factor: str
    source: str
    date: str


class RecordedExchangeRateView(BaseModel):
    id: int
    project_id: int
    base: str
    quote: str
    factor: str
    source: str
    observed_date: str


class HistoricalSelectionView(BaseModel):
    id: int
    estimate_id: int
    created_at: str
    actor_id: int
    reason: str
    snapshot_hash: str
    snapshot: dict[str, JsonValue]


class CostSourceView(BaseModel):
    id: int
    type: str
    label: str
    version: int
    link_version: int | None
    cost_code_id: int | None


class ReceiptSourceView(BaseModel):
    id: int
    receipt: str
    po: str
    item_code: str
    quantity: str
    unit: str
    po_rate: str
    recognized: int | None


class RecognitionSourceView(BaseModel):
    id: int
    receipt_line_id: int | None
    invoice_id: int | None
    amount: Money
    remaining_quantity: str


class InvoiceSourceView(BaseModel):
    id: int
    number: str
    amount: Money
    status: str
    version: int


class AccountingSources(BaseModel):
    cost_sources: list[CostSourceView]
    receipt_lines: list[ReceiptSourceView]
    recognitions: list[RecognitionSourceView]
    invoices: list[InvoiceSourceView]


class CostCodeView(BaseModel):
    id: int
    code: str
    name: str
    active: bool
    version: int


class SupplierView(BaseModel):
    id: int
    code: str
    name: str
    version: int
    approved: bool
    beneficiary_fingerprint: str
