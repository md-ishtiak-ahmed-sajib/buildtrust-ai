"""Additive estimating records. Approved procurement and settlement tables stay separate."""

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base
from .money import utcnow


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]
    category: Mapped[str]
    unit: Mapped[str]
    specification_json: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)


class PriceSearch(Base):
    __tablename__ = "price_searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    fingerprint: Mapped[str] = mapped_column(index=True)
    request_json: Mapped[str] = mapped_column(Text)
    states_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(default="QUEUED")
    created_at: Mapped[str] = mapped_column(default=utcnow)
    updated_at: Mapped[str] = mapped_column(default=utcnow)


class Quotation(Base):
    __tablename__ = "supplier_quotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    fields_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="DRAFT")
    version: Mapped[int] = mapped_column(default=1)
    prepared_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    storage_name: Mapped[str | None]
    original_filename: Mapped[str | None]
    attachment_hash: Mapped[str | None]
    created_at: Mapped[str] = mapped_column(default=utcnow)


class PriceObservation(Base):
    __tablename__ = "price_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    search_id: Mapped[int | None] = mapped_column(ForeignKey("price_searches.id"))
    quotation_id: Mapped[int | None] = mapped_column(
        ForeignKey("supplier_quotations.id")
    )
    provider: Mapped[str]
    source_type: Mapped[str]
    payload_json: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str]
    retrieved_at: Mapped[str] = mapped_column(default=utcnow)


class MaterialEquivalent(Base):
    __tablename__ = "material_equivalents"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("price_observations.id"), unique=True
    )
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str]
    material_version: Mapped[int]
    created_at: Mapped[str] = mapped_column(default=utcnow)


class ExchangeRate(Base):
    __tablename__ = "exchange_rate_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    base: Mapped[str]
    quote: Mapped[str]
    factor: Mapped[str]
    source: Mapped[str]
    observed_date: Mapped[str]
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)


class MeasurementProfile(Base):
    __tablename__ = "measurement_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    edition: Mapped[str]
    source_url: Mapped[str]
    rules_json: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(
        default="REQUIRES_PROFESSIONAL_REVIEW"
    )


class TakeoffSheet(Base):
    __tablename__ = "takeoff_sheets"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("measurement_profiles.id"))
    fields_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    prepared_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    checked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="DRAFT")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Estimate(Base):
    __tablename__ = "estimate_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    estimate_key: Mapped[str]
    revision: Mapped[int] = mapped_column(default=1)
    version: Mapped[int] = mapped_column(default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("estimate_versions.id"))
    name: Mapped[str]
    status: Mapped[str] = mapped_column(default="DRAFT")
    fields_json: Mapped[str] = mapped_column(Text)
    calculated_json: Mapped[str] = mapped_column(Text)
    total_minor: Mapped[int] = mapped_column(default=0)
    prepared_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    checked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    snapshot_hash: Mapped[str | None]
    approval_snapshot_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "estimate_key", "revision"),)


class PriceSelection(Base):
    __tablename__ = "price_selections"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimate_versions.id"))
    observation_id: Mapped[int] = mapped_column(ForeignKey("price_observations.id"))
    line_id: Mapped[str]
    component_id: Mapped[str]
    snapshot_json: Mapped[str] = mapped_column(Text)
    snapshot_hash: Mapped[str]
    reason: Mapped[str]
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)


class BudgetBaseline(Base):
    __tablename__ = "budget_baselines"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    estimate_id: Mapped[int] = mapped_column(
        ForeignKey("estimate_versions.id"), unique=True
    )
    amount_minor: Mapped[int]
    snapshot_hash: Mapped[str]
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(default=utcnow)
