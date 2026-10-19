"""Stable envelopes for errors, source registers and local operational views."""

from pydantic import BaseModel, Field, JsonValue
from .schemas import DocumentResponse


class FieldError(BaseModel):
    location: list[str | int]
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[FieldError] = Field(default_factory=list)
    request_id: str | None = None
    retry_after: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class RegisterItem(BaseModel):
    id: int
    label: str
    status: str
    created_at: str


class RegisterPage(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[RegisterItem]


class AttemptResponse(BaseModel):
    id: int
    kind: str
    entity_id: int
    attempt: int
    status: str
    started_at: str
    heartbeat_at: str
    lease_until: str
    next_attempt_at: str | None
    finished_at: str | None


class SourceOption(BaseModel):
    id: int
    label: str
    version: int | None = None


class CommercialSources(BaseModel):
    materials: list[SourceOption]
    observations: list[SourceOption]
    measurements: list[SourceOption]
    boq: list[SourceOption]
    acceptances: list[SourceOption]
    advances: list[SourceOption]
    procurement_lines: list[SourceOption]
    obligations: list[SourceOption]
    kinds: list[str]


class DocumentDetail(DocumentResponse):
    data: JsonValue
    text: str


class ExtractionHistory(BaseModel):
    version: int
    fields: JsonValue
    created_at: str


class DocumentExtraction(BaseModel):
    document: DocumentResponse
    data: JsonValue
    revisions: list[ExtractionHistory]
