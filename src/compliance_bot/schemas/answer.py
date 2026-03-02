"""Week 4 schemas for citation-first grounded answering."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from compliance_bot.schemas.audit import AuditEvent
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import Citation, RetrievedChunk


class GroundedAnswerDraft(BaseModel):
    """Structured LLM draft output before grounding policy enforcement."""

    answer: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    decision: DecisionEnum
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("answer must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_answered_has_citation(self) -> GroundedAnswerDraft:
        if self.decision == DecisionEnum.ANSWERED and not self.citations:
            raise ValueError("ANSWERED output must include at least one citation")
        return self


class GroundedAnswerResponse(BaseModel):
    """Week 4 response contract after citation checks and abstention controls."""

    trace_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    normalized_query: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    decision: DecisionEnum
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    abstention_reason: str | None = None

    @model_validator(mode="after")
    def validate_answered_has_citation(self) -> GroundedAnswerResponse:
        if self.decision == DecisionEnum.ANSWERED and not self.citations:
            raise ValueError("ANSWERED response must include at least one citation")
        return self
