"""Week 3 retrieval schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from compliance_bot.schemas.audit import AuditEvent
from compliance_bot.schemas.query import DecisionEnum


class RetrievalFilters(BaseModel):
    """Metadata filters applied before ranking."""

    jurisdiction: str | None = None
    policy_scope: list[str] = Field(default_factory=list)

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("policy_scope")
    @classmethod
    def normalize_policy_scope(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized


class QueryRewriteOutput(BaseModel):
    """Structured output for the query rewriting stage."""

    normalized_query: str = Field(..., min_length=1)
    expanded_queries: list[str] = Field(default_factory=list)

    @field_validator("normalized_query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("normalized_query must not be blank")
        return normalized

    @field_validator("expanded_queries")
    @classmethod
    def normalize_expanded_queries(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            query = " ".join(item.split())
            if query and query not in seen:
                normalized.append(query)
                seen.add(query)
        return normalized


class Citation(BaseModel):
    """Evidence citation produced from retrieval output."""

    doc_id: str = Field(..., min_length=1)
    section: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    quote_span: str = Field(..., min_length=1)
    retrieval_score: float = Field(..., ge=0.0, le=1.0)
    version: str = Field(..., min_length=1)


class RerankResult(BaseModel):
    """One rerank result mapped back to candidate index."""

    candidate_index: int = Field(..., ge=0)
    score: float


class ProviderCallMetrics(BaseModel):
    """Provider call telemetry for practical hosted model integrations."""

    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    latency_ms: float = Field(..., ge=0.0)
    status: str = Field(..., min_length=1)
    error_code: str | None = None


class RetrievedChunk(BaseModel):
    """Ranked retrieval chunk used as grounding evidence."""

    chunk_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    version_tag: str = Field(..., min_length=1)
    chunk_index: int = Field(..., ge=0)
    content: str = Field(..., min_length=1)
    retrieval_score: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, str] = Field(default_factory=dict)
    matched_terms: list[str] = Field(default_factory=list)


class RetrievalResponse(BaseModel):
    """Top-level retrieval stage response."""

    trace_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    normalized_query: str = Field(..., min_length=1)
    decision: DecisionEnum
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    provider_metrics: list[ProviderCallMetrics] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)


class RetrievalBenchmarkCase(BaseModel):
    """One benchmark case for recall and latency evaluation."""

    case_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    expected_doc_ids: list[str] = Field(default_factory=list)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)


class RetrievalBenchmarkResult(BaseModel):
    """Per-case benchmark result."""

    case_id: str = Field(..., min_length=1)
    recall_at_k: float = Field(..., ge=0.0, le=1.0)
    reciprocal_rank: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float = Field(..., ge=0.0)
    decision: DecisionEnum
    top_doc_ids: list[str] = Field(default_factory=list)


class RetrievalBenchmarkReport(BaseModel):
    """Aggregate benchmark report for Week 3 retrieval gates."""

    top_k: int = Field(..., ge=1)
    avg_recall_at_k: float = Field(..., ge=0.0, le=1.0)
    avg_reciprocal_rank: float = Field(..., ge=0.0, le=1.0)
    p95_latency_ms: float = Field(..., ge=0.0)
    recall_floor: float = Field(..., ge=0.0, le=1.0)
    latency_ceiling_ms: float = Field(..., ge=0.0)
    meets_quality_gate: bool
    results: list[RetrievalBenchmarkResult] = Field(default_factory=list)
