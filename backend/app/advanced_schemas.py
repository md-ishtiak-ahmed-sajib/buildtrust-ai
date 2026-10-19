from datetime import date
from typing import Annotated, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    BeforeValidator,
    field_validator,
    model_validator,
)
from .money import decimal
from .calculation_schemas import RateAnalysis


def exact(value):
    return format(decimal(value), "f")


Exact = Annotated[str, BeforeValidator(exact)]
Currency = Literal["BDT", "USD", "EUR", "GBP", "INR", "CNY"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class MaterialInput(Contract):
    project_id: int
    name: str = Field(min_length=2, max_length=200)
    category: str = Field(default="Materials", max_length=100)
    unit: str = Field(default="tonne", max_length=30)
    specification: dict[str, str] = Field(default_factory=dict, max_length=30)
    expected_version: int | None = None


class SearchInput(Contract):
    quantity: Exact = "1"
    unit: str | None = None
    country: str = Field(default="BD", pattern=r"^[A-Z]{2}$")
    city: str = Field(default="Dhaka", min_length=1, max_length=120)
    currency: Currency = "BDT"
    delivery_location: str = Field(default="Dhaka", max_length=200)
    mode: Literal["LIVE", "DEMO"] = "LIVE"

    @field_validator("quantity")
    @classmethod
    def positive(cls, v):
        if decimal(v) <= 0:
            raise ValueError("Quantity must be positive")
        return v


class QuotationInput(Contract):
    material_id: int
    supplier: str = Field(min_length=1, max_length=200)
    number: str = Field(default="", max_length=100)
    title: str = Field(min_length=1, max_length=300)
    source_type: Literal["SUPPLIER_QUOTE", "OFFICIAL_REFERENCE"] = "SUPPLIER_QUOTE"
    price: Exact | None = None
    currency: Currency = "BDT"
    unit: str | None = None
    quoted_quantity: Exact = "1"
    minimum_quantity: Exact = "1"
    package_weight_kg: Exact | None = None
    density_kg_m3: Exact | None = None
    density_assumption: str = Field(default="", max_length=500)
    specification: dict[str, str] = Field(default_factory=dict, max_length=30)
    country: str = "BD"
    city: str = Field(default="Dhaka", max_length=120)
    can_deliver: bool | None = None
    delivery_days: int | None = Field(default=None, ge=0, le=3650)
    freight_basis: Literal["INCLUDED", "EXCLUDED", "UNKNOWN"] = "UNKNOWN"
    freight: Exact | None = None
    tax_basis: Literal["INCLUDED", "EXCLUDED", "UNKNOWN"] = "UNKNOWN"
    tax: Exact | None = None
    tax_recoverable: bool = False
    handling: Exact | None = None
    other_cost: Exact | None = None
    quotation_date: date | None = None
    valid_until: date | None = None
    source_url: str | None = Field(default=None, max_length=2000)
    edition: str = Field(default="", max_length=100)
    chapter: str = Field(default="", max_length=100)
    item_code: str = Field(default="", max_length=100)
    locality: str = Field(default="", max_length=100)
    effective_date: date | None = None
    rate_category: Literal["MATERIAL", "WORK_ITEM", "COMPOSITE"] = "MATERIAL"
    notes: str = Field(default="", max_length=2000)
    expected_version: int | None = None

    @model_validator(mode="after")
    def sensible_financial_inputs(self):
        for key in (
            "price",
            "quoted_quantity",
            "minimum_quantity",
            "package_weight_kg",
            "density_kg_m3",
            "freight",
            "tax",
            "handling",
            "other_cost",
        ):
            value = getattr(self, key)
            if value is not None and (
                decimal(value) < 0
                or (
                    key
                    in (
                        "price",
                        "quoted_quantity",
                        "package_weight_kg",
                        "density_kg_m3",
                    )
                    and decimal(value) == 0
                )
            ):
                raise ValueError(
                    f"{key} must be positive or nonnegative as appropriate"
                )
        if (
            self.quotation_date
            and self.valid_until
            and self.valid_until < self.quotation_date
        ):
            raise ValueError("Quotation expiry precedes its issue date")
        return self


class VersionAction(Contract):
    expected_version: int
    reason: str = Field(default="", max_length=2000)


class EquivalentInput(Contract):
    observation_id: int
    reason: str = Field(min_length=10, max_length=2000)


class FXInput(Contract):
    project_id: int
    base: Currency
    quote: Currency = "BDT"
    factor: Exact
    observed_date: date
    source: str = Field(min_length=5, max_length=4000)


class FXFetchInput(Contract):
    project_id: int
    base: Currency
    quote: Currency = "BDT"


class OpeningMeasurement(Contract):
    width: Exact
    height: Exact
    count: Exact = "1"
    reference: str = Field(default="", max_length=200)


class TakeoffInput(Contract):
    project_id: int
    profile_id: int
    name: str = Field(min_length=1, max_length=200)
    calculation: Literal[
        "RECTANGULAR_VOLUME",
        "CIRCULAR_VOLUME",
        "AREA",
        "LENGTH",
        "COUNT",
        "REBAR",
        "FORMWORK_COLUMN",
        "FORMWORK_BEAM",
        "FORMWORK_SLAB",
        "FORMWORK_FOOTING",
        "EARTHWORK",
        "BACKFILL",
        "DISPOSAL",
        "COMPACTION",
        "MASONRY",
        "FINISHES",
        "DOORS_WINDOWS",
        "ROOFING",
        "PAVEMENT",
        "TRIANGULAR_PRISM",
        "FRUSTUM",
        "ANNULAR_VOLUME",
        "REBAR_SCHEDULE",
    ]
    dimensions: dict[str, Exact] = Field(default_factory=dict, max_length=30)
    dimension_unit: Literal["m", "mm", "cm", "ft"] = "m"
    deduction: Exact = "0"
    deduction_reason: str = Field(default="", max_length=1000)
    assumptions: str = Field(default="", max_length=2000)
    element: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=200)
    drawing_reference: str = Field(default="", max_length=200)
    revision: str = Field(default="1", max_length=100)
    mass_method: Literal["APPROXIMATION", "SPECIFIED", "DENSITY"] = "APPROXIMATION"
    nominal_mass_source: str = Field(default="", max_length=500)
    reinforcement_schedule: list[dict[str, Exact]] = Field(
        default_factory=list, max_length=500
    )
    openings: list[OpeningMeasurement] = Field(default_factory=list, max_length=200)


class RateComponent(Contract):
    id: str = Field(min_length=1, max_length=80)
    category: Literal[
        "MATERIAL", "LABOUR", "EQUIPMENT", "SUBCONTRACT", "TRANSPORT", "OTHER"
    ] = "MATERIAL"
    description: str = Field(min_length=1, max_length=300)
    material_id: int | None = None
    consumption: Exact = "1"
    unit: str = Field(default="tonne", max_length=30)
    unit_price: Exact = "0"
    wastage_percent: Exact = "0"
    selection_id: int | None = None
    source_note: str = Field(default="", max_length=1000)


class EstimateLine(Contract):
    id: str = Field(min_length=1, max_length=80)
    section: str = Field(default="Works", max_length=200)
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    kind: Literal["MEASURED", "PROVISIONAL_SUM", "PRIME_COST"] = "MEASURED"
    cost_code: str = Field(default="", max_length=100)
    unit: str = Field(default="tonne", max_length=30)
    quantity: Exact = "1"
    legacy_boq_item_id: int | None = None
    takeoff_sheet_id: int | None = None
    due_date: date | None = None
    notes: str = Field(default="", max_length=2000)
    drawing_reference: str = Field(default="", max_length=200)
    components: list[RateComponent] = Field(default_factory=list, max_length=100)


class EstimateFields(Contract):
    basis: str = Field(default="", max_length=5000)
    estimate_type: Literal[
        "PRELIMINARY", "DETAILED", "ENGINEER", "TENDER", "REVISED"
    ] = "DETAILED"
    inclusions: str = Field(default="", max_length=2000)
    exclusions: str = Field(default="", max_length=2000)
    uncertainty: str = Field(default="", max_length=2000)
    site_overhead_percent: Exact = "0"
    general_overhead_percent: Exact = "0"
    profit_percent: Exact = "0"
    tax_percent: Exact = "0"
    contingency_percent: Exact = "0"
    tax_treatment: Literal[
        "UNKNOWN", "NONRECOVERABLE_COST", "RECOVERABLE", "OUTPUT"
    ] = "UNKNOWN"
    lines: list[EstimateLine] = Field(default_factory=list, max_length=500)


class EstimateCreate(Contract):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    import_boq: bool = True


class EstimateUpdate(Contract):
    expected_version: int
    name: str = Field(min_length=1, max_length=200)
    fields: EstimateFields


class SelectPriceInput(Contract):
    estimate_id: int
    expected_version: int
    line_id: str
    component_id: str
    observation_id: int
    search_id: int | None = None
    reason: str = Field(default="", max_length=2000)


class SearchResponse(Contract):
    id: int
    status: str
    material_id: int
    request: SearchInput
    states: dict
    created_at: str
    updated_at: str
    cached: bool = False


class PriceFinding(Contract):
    observation_id: int
    provider: str
    source_type: str
    payload: dict
    evidence_hash: str
    retrieved_at: str
    compatibility: str
    reasons: list[str]
    normalized_unit_price: str | None = None
    landed_unit_cost: str | None = None
    cost_breakdown: dict
    conversions: list[dict]
    eligible: bool
    score: str = "0"
    scoring: dict = Field(default_factory=dict)
    recommended: bool = False
    lowest_comparable: bool = False


class PriceComparison(Contract):
    material: dict
    offers: list[PriceFinding]
    recommended_observation_id: int | None
    notice: str
    mode: str
    policy: str
    currency: str
    displayed_request: dict = Field(default_factory=dict)
    searched_at: str | None = None


class EstimateResponse(Contract):
    id: int
    project_id: int
    estimate_key: str
    revision: int
    version: int
    name: str
    status: str
    prepared_by: int
    contributors: list[int] = Field(default_factory=list)
    checked_by: int | None
    approved_by: int | None
    snapshot_hash: str | None
    total: str
    cost_total: str | None = None
    tender_total: str | None = None
    fields: EstimateFields
    calculated: RateAnalysis
    created_at: str


class UpgradeAsk(Contract):
    project_id: int
    estimate_id: int | None = None
    material_id: int | None = None
    question: str = Field(min_length=3, max_length=1000)
    measurement: TakeoffInput | None = None
