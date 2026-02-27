"""Week 3 metadata-aware retriever with provider-backed ranking and fallbacks."""

from __future__ import annotations

import json
from math import sqrt
from typing import Any, Protocol
from uuid import uuid4

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from compliance_bot.providers.siliconflow_rerank import RerankProviderError
from compliance_bot.retrieval.indexer import IndexedChunk, RetrievalIndex, tokenize
from compliance_bot.retrieval.query_rewriter import rewrite_query
from compliance_bot.schemas.audit import build_audit_event
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import (
    Citation,
    ProviderCallMetrics,
    QueryRewriteOutput,
    RetrievedChunk,
    RetrievalFilters,
    RetrievalResponse,
)


class QueryEmbeddingProvider(Protocol):
    """Provider contract for query embeddings."""

    provider_name: str
    model: str

    def embed_query(self, text: str) -> list[float]:
        """Embed one query string into vector space."""


class RerankProvider(Protocol):
    """Provider contract for reranking candidate chunks."""

    provider_name: str
    model: str

    def rerank(
        self,
        *,
        query: str,
        candidates: list[str],
        top_n: int,
    ) -> tuple[list[Any], ProviderCallMetrics]:
        """Return rerank results and provider metrics."""


class RetrieverConfig(BaseModel):
    """Named retriever config entry used for labs and benchmarks."""

    name: str = Field(..., min_length=1)
    top_k: int = Field(..., ge=1)
    min_score_for_answer: float = Field(..., ge=0.0, le=1.0)


RETRIEVER_CONFIG_REGISTRY: dict[str, RetrieverConfig] = {
    "balanced": RetrieverConfig(name="balanced", top_k=4, min_score_for_answer=0.3),
    "high-recall": RetrieverConfig(
        name="high-recall",
        top_k=6,
        min_score_for_answer=0.2,
    ),
    "low-latency": RetrieverConfig(name="low-latency", top_k=3, min_score_for_answer=0.35),
}


def get_retriever_config(name: str = "balanced") -> RetrieverConfig:
    """Resolve a named retriever config."""

    try:
        return RETRIEVER_CONFIG_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(RETRIEVER_CONFIG_REGISTRY))
        raise ValueError(f"unknown retriever config '{name}'. available: {available}") from exc


def _parse_policy_scope(raw: str | None) -> set[str]:
    if not raw:
        return set()

    normalized = raw.replace("|", ",").replace(";", ",")
    values = {item.strip().lower() for item in normalized.split(",") if item.strip()}
    return values


def _matches_filters(chunk: IndexedChunk, filters: RetrievalFilters) -> bool:
    if filters.jurisdiction is not None:
        jurisdiction = chunk.metadata.get("jurisdiction", "").strip().lower()
        if jurisdiction != filters.jurisdiction:
            return False

    if filters.policy_scope:
        chunk_scope = _parse_policy_scope(chunk.metadata.get("policy_scope"))
        if not chunk_scope:
            return False
        if not chunk_scope.intersection(filters.policy_scope):
            return False

    return True


def _score_chunk_lexical(chunk: IndexedChunk, query_tokens: set[str]) -> tuple[float, list[str]]:
    if not query_tokens:
        return 0.0, []

    overlap = sorted(query_tokens.intersection(chunk.tokens))
    if not overlap:
        return 0.0, []

    score = len(overlap) / len(query_tokens)
    return min(score, 1.0), overlap


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _norm(values: list[float]) -> float:
    return sqrt(sum(v * v for v in values))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    norm_product = _norm(left) * _norm(right)
    if norm_product == 0.0:
        return 0.0
    return _dot(left, right) / norm_product


def _score_chunk_vector(
    chunk: IndexedChunk,
    query_vector: list[float] | None,
) -> float:
    if query_vector is None or chunk.vector is None:
        return 0.0
    if len(query_vector) != len(chunk.vector):
        return 0.0

    cosine = _cosine_similarity(query_vector, chunk.vector)
    # Normalize cosine [-1, 1] into [0, 1] for stable decision thresholds.
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


class MetadataKeywordRetriever(BaseRetriever):
    """LangChain retriever that applies metadata filters before lexical ranking."""

    index: RetrievalIndex
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    top_k: int = 4

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        del run_manager
        query_tokens = set(tokenize(query))
        ranked: list[tuple[float, IndexedChunk, list[str]]] = []

        for chunk in self.index.chunks:
            if not _matches_filters(chunk, self.filters):
                continue

            score, matched_terms = _score_chunk_lexical(chunk, query_tokens)
            if score <= 0.0:
                continue
            ranked.append((score, chunk, matched_terms))

        ranked.sort(key=lambda item: (-item[0], item[1].doc_id, item[1].chunk_index))

        documents: list[Document] = []
        for score, chunk, matched_terms in ranked[: self.top_k]:
            documents.append(
                Document(
                    page_content=chunk.content,
                    metadata={
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "version_tag": chunk.version_tag,
                        "chunk_index": chunk.chunk_index,
                        "retrieval_score": score,
                        "matched_terms": matched_terms,
                        **chunk.metadata,
                    },
                )
            )

        return documents


def _dedupe_queries(rewrite_output: QueryRewriteOutput) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for query in [rewrite_output.normalized_query, *rewrite_output.expanded_queries]:
        normalized = " ".join(query.split())
        if not normalized or normalized in seen:
            continue
        ordered.append(normalized)
        seen.add(normalized)

    return ordered


def _to_retrieved_chunk(
    chunk: IndexedChunk,
    *,
    retrieval_score: float,
    matched_terms: list[str],
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        version_tag=chunk.version_tag,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        retrieval_score=max(0.0, min(1.0, retrieval_score)),
        metadata={str(key): str(value) for key, value in chunk.metadata.items()},
        matched_terms=matched_terms,
    )


def _to_citation(chunk: RetrievedChunk) -> Citation:
    section = chunk.metadata.get("section") or f"chunk-{chunk.chunk_index}"
    quote_span = chunk.content[:160]

    return Citation(
        doc_id=chunk.doc_id,
        section=section,
        chunk_id=chunk.chunk_id,
        quote_span=quote_span,
        retrieval_score=chunk.retrieval_score,
        version=chunk.version_tag,
    )


def _choose_decision(
    retrieved_chunks: list[RetrievedChunk], *, min_score_for_answer: float
) -> DecisionEnum:
    if not retrieved_chunks:
        return DecisionEnum.ABSTAINED

    if retrieved_chunks[0].retrieval_score < min_score_for_answer:
        return DecisionEnum.ESCALATE

    return DecisionEnum.ANSWERED


def _default_provider_metrics(
    *, provider: str, model: str, status: str, error_code: str | None = None
) -> ProviderCallMetrics:
    return ProviderCallMetrics(
        provider=provider,
        model=model,
        latency_ms=0.0,
        status=status,
        error_code=error_code,
    )


def run_retrieval(
    index: RetrievalIndex,
    *,
    question: str,
    filters: RetrievalFilters | None = None,
    query_rewriter: Runnable[Any, QueryRewriteOutput] | None = None,
    embedding_provider: QueryEmbeddingProvider | None = None,
    rerank_provider: RerankProvider | None = None,
    top_k: int | None = None,
    min_score_for_answer: float | None = None,
    trace_id: str | None = None,
) -> RetrievalResponse:
    """Run Week 3 retrieval with provider-backed scoring and safe fallbacks."""

    normalized_question = " ".join(question.split())
    if not normalized_question:
        raise ValueError("question must not be blank")

    resolved_trace_id = trace_id or str(uuid4())
    resolved_filters = filters or RetrievalFilters()
    config = get_retriever_config()
    resolved_top_k = top_k if top_k is not None else config.top_k
    resolved_min_score = (
        min_score_for_answer
        if min_score_for_answer is not None
        else config.min_score_for_answer
    )

    rewrite_output = rewrite_query(
        normalized_question,
        chain=query_rewriter,
    )
    query_variants = _dedupe_queries(rewrite_output)

    provider_metrics: list[ProviderCallMetrics] = []
    audit_events = [
        build_audit_event(
            trace_id=resolved_trace_id,
            stage="query_rewrite",
            actor="retrieval.query_rewriter",
            status="ok",
            input_payload=normalized_question,
            output_payload=json.dumps(rewrite_output.model_dump(), sort_keys=True),
        )
    ]

    best_by_chunk: dict[str, RetrievedChunk] = {}
    for query_variant in query_variants:
        query_tokens = set(tokenize(query_variant))
        query_vector: list[float] | None = None

        if embedding_provider is not None and index.vector_dim > 0:
            try:
                query_vector = embedding_provider.embed_query(query_variant)
                provider_metrics.append(
                    _default_provider_metrics(
                        provider=getattr(embedding_provider, "provider_name", "embedding-provider"),
                        model=getattr(embedding_provider, "model", "unknown"),
                        status="ok",
                    )
                )
            except Exception:
                provider_metrics.append(
                    _default_provider_metrics(
                        provider=getattr(embedding_provider, "provider_name", "embedding-provider"),
                        model=getattr(embedding_provider, "model", "unknown"),
                        status="error",
                        error_code="embed_query_failed",
                    )
                )

        for chunk in index.chunks:
            if not _matches_filters(chunk, resolved_filters):
                continue

            lexical_score, matched_terms = _score_chunk_lexical(chunk, query_tokens)
            vector_score = _score_chunk_vector(chunk, query_vector)
            score = max(lexical_score, vector_score)
            if score <= 0.0:
                continue

            candidate = _to_retrieved_chunk(
                chunk,
                retrieval_score=score,
                matched_terms=matched_terms,
            )
            current = best_by_chunk.get(candidate.chunk_id)
            if current is None or candidate.retrieval_score > current.retrieval_score:
                best_by_chunk[candidate.chunk_id] = candidate

    pre_rerank_chunks = sorted(
        best_by_chunk.values(),
        key=lambda item: (-item.retrieval_score, item.doc_id, item.chunk_index),
    )

    retrieved_chunks = pre_rerank_chunks[:resolved_top_k]
    if rerank_provider is not None and pre_rerank_chunks:
        rerank_candidates = pre_rerank_chunks[: max(resolved_top_k * 2, resolved_top_k)]
        try:
            rerank_results, rerank_metrics = rerank_provider.rerank(
                query=rewrite_output.normalized_query,
                candidates=[chunk.content for chunk in rerank_candidates],
                top_n=resolved_top_k,
            )
            provider_metrics.append(rerank_metrics)
            ordered_by_rerank: list[RetrievedChunk] = []
            for result in rerank_results:
                if result.candidate_index < 0 or result.candidate_index >= len(rerank_candidates):
                    continue
                chunk = rerank_candidates[result.candidate_index]
                ordered_by_rerank.append(
                    chunk.model_copy(update={"retrieval_score": max(0.0, min(1.0, float(result.score)))})
                )

            deduped: dict[str, RetrievedChunk] = {chunk.chunk_id: chunk for chunk in ordered_by_rerank}
            if deduped:
                retrieved_chunks = list(deduped.values())[:resolved_top_k]
        except (RerankProviderError, TimeoutError, ValueError):
            provider_metrics.append(
                _default_provider_metrics(
                    provider=getattr(rerank_provider, "provider_name", "rerank-provider"),
                    model=getattr(rerank_provider, "model", "unknown"),
                    status="error",
                    error_code="rerank_failed",
                )
            )

    decision = _choose_decision(
        retrieved_chunks,
        min_score_for_answer=resolved_min_score,
    )
    citations = [_to_citation(chunk) for chunk in retrieved_chunks]

    audit_events.append(
        build_audit_event(
            trace_id=resolved_trace_id,
            stage="retrieval_rank",
            actor="retrieval.retriever",
            status="ok",
            input_payload=json.dumps(
                {
                    "queries": query_variants,
                    "top_k": resolved_top_k,
                    "filters": resolved_filters.model_dump(),
                },
                sort_keys=True,
            ),
            output_payload=json.dumps(
                {
                    "decision": decision.value,
                    "chunk_ids": [chunk.chunk_id for chunk in retrieved_chunks],
                },
                sort_keys=True,
            ),
            metadata={
                "provider_call_count": len(provider_metrics),
                "provider_errors": sum(1 for item in provider_metrics if item.status != "ok"),
            },
        )
    )

    return RetrievalResponse(
        trace_id=resolved_trace_id,
        question=normalized_question,
        normalized_query=rewrite_output.normalized_query,
        decision=decision,
        citations=citations,
        retrieved_chunks=retrieved_chunks,
        provider_metrics=provider_metrics,
        audit_events=audit_events,
    )
