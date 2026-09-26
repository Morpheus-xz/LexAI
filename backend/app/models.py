"""
Pydantic models — all request and response shapes in one validated place.

Validation is a first-class security control: bounded string lengths,
non-empty document text, and explicitly typed fields mean malformed or
hostile input is rejected at the edge before business logic runs.

Shared validators are functions, not copy-pasted methods. Each model
that needs the same rule calls the same function.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.config import MAX_DOCUMENT_CHARS


def _require_non_empty_text(v: str, field_name: str = "document") -> str:
    """
    Shared validator: strips whitespace and rejects blank text.
    Used by every model that accepts a document — defined once, called
    by each model's @field_validator. Never copy-pasted.
    """
    stripped = v.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be blank or whitespace only")
    return stripped


class DocumentInput(BaseModel):
    """A single legal document submitted for analysis."""

    text: str = Field(
        ...,
        min_length=20,
        max_length=MAX_DOCUMENT_CHARS,
        description="Raw text of the legal document",
    )
    label: Optional[str] = Field(
        None, max_length=80, description="Optional user-supplied name"
    )

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        return _require_non_empty_text(v, "text")


class SimplifyRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=MAX_DOCUMENT_CHARS)
    focus: Optional[str] = Field(
        None,
        max_length=200,
        description="Optional aspect to focus on, e.g. 'payment terms'",
    )

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        return _require_non_empty_text(v)


class AskRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=MAX_DOCUMENT_CHARS)
    question: str = Field(..., min_length=5, max_length=500)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        return _require_non_empty_text(v)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        return _require_non_empty_text(v, "question")


class CompareRequest(BaseModel):
    doc_a: str = Field(
        ...,
        min_length=20,
        max_length=MAX_DOCUMENT_CHARS,
        description="First document text",
    )
    doc_b: str = Field(
        ...,
        min_length=20,
        max_length=MAX_DOCUMENT_CHARS,
        description="Second document text",
    )
    label_a: Optional[str] = Field(None, max_length=80)
    label_b: Optional[str] = Field(None, max_length=80)

    @field_validator("doc_a", "doc_b")
    @classmethod
    def docs_not_blank(cls, v: str) -> str:
        return _require_non_empty_text(v, "document")


class RiskFlag(BaseModel):
    keyword: str
    category: str
    context: str


class ClauseItem(BaseModel):
    title: str
    content: str
    char_start: int


class DocumentStats(BaseModel):
    word_count: int
    estimated_reading_minutes: int
    sentence_count: int
    paragraph_count: int
    character_count: int


class AnalysisResponse(BaseModel):
    stats: DocumentStats
    risk_flags: list[RiskFlag]
    obligations: list[str]
    rights: list[str]
    key_dates: list[str]
    clauses: list[ClauseItem]
    ai_summary: str
    disclaimer: str


class SimplifyResponse(BaseModel):
    plain_english: str
    key_points: list[str]
    disclaimer: str


class AskResponse(BaseModel):
    answer: str
    confidence: str  # "high" | "medium" | "low — consult a professional"
    disclaimer: str


class CompareStructural(BaseModel):
    risk_count: int
    obligation_count: int
    right_count: int
    clause_count: int
    dates: list[str]


class CompareResponse(BaseModel):
    doc_a_structural: CompareStructural
    doc_b_structural: CompareStructural
    ai_comparison: str
    key_differences: list[str]
    recommendation: str
    disclaimer: str


class SummarizeResponse(BaseModel):
    executive_summary: str
    key_points: list[str]
    important_clauses: list[str]
    action_items: list[str]
    disclaimer: str


class PrepareResponse(BaseModel):
    document_summary: str
    questions_for_lawyer: list[str]
    checklist: list[str]
    red_flags: list[str]
    disclaimer: str


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    storage_backend: str


class SavedDocumentSummary(BaseModel):
    """Lightweight listing entry for the session document history."""

    id: str
    label: str
    preview: str


class SavedDocumentDetail(BaseModel):
    """Full document retrieved from the session document history."""

    id: str
    label: str
    text: str
