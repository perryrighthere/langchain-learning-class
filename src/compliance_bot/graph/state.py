"""Week 5 LangGraph state contracts."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from compliance_bot.schemas.audit import AuditEvent
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import (
    Citation,
    ProviderCallMetrics,
    RetrievalFilters,
    RetrievedChunk,
)
from compliance_bot.schemas.tools import ToolExecutionRecord, ToolPlan


class ComplianceAgentState(BaseModel):
    """Deterministic state used by the Week 6 LangGraph workflow."""

    trace_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    normalized_query: str = Field(default="", min_length=0)
    retrieval_filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    retrieval_decision: DecisionEnum = DecisionEnum.ABSTAINED
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    policy_flags: list[str] = Field(default_factory=list)
    tool_plan: ToolPlan = Field(default_factory=ToolPlan)
    tool_results: list[ToolExecutionRecord] = Field(default_factory=list)
    tool_context: str = Field(default="")
    decision_path: list[str] = Field(default_factory=list)
    final_answer: str = Field(default="")
    final_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    final_decision: DecisionEnum = DecisionEnum.ABSTAINED
    abstention_reason: str | None = None
    escalation_reason: str | None = None
    requires_human_review: bool = False
    provider_metrics: list[ProviderCallMetrics] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    answer_attempt: int = Field(default=0, ge=0)
    max_answer_retries: int = Field(default=1, ge=0)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

    @field_validator("policy_flags")
    @classmethod
    def normalize_policy_flags(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized

    @classmethod
    def from_input(
        cls,
        *,
        question: str,
        trace_id: str | None = None,
        retrieval_filters: RetrievalFilters | None = None,
        max_answer_retries: int = 1,
    ) -> ComplianceAgentState:
        """Build initial state for graph execution."""

        return cls(
            trace_id=trace_id or str(uuid4()),
            question=question,
            retrieval_filters=retrieval_filters or RetrievalFilters(),
            max_answer_retries=max_answer_retries,
        )

    def as_graph_state(self) -> dict[str, object]:
        """Render state into a LangGraph-compatible dictionary."""

        return self.model_dump(mode="python")

    @classmethod
    def from_graph_state(cls, state: dict[str, object]) -> ComplianceAgentState:
        """Validate a LangGraph dictionary state."""

        return cls.model_validate(state)
