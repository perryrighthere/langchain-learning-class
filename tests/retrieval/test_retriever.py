"""Week 3 retriever tests."""

from __future__ import annotations

from compliance_bot.retrieval.indexer import RetrievalIndex, build_retrieval_index
from compliance_bot.retrieval.retriever import run_retrieval
from compliance_bot.schemas.ingestion import ChunkRecord, CorpusManifest
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import ProviderCallMetrics, RerankResult
from compliance_bot.schemas.retrieval import RetrievalFilters


def _build_index() -> RetrievalIndex:
    chunks = [
        ChunkRecord(
            chunk_id="chunk-expense-0",
            doc_id="expense-policy-v1",
            version_tag="week-03-v1",
            chunk_index=0,
            content="Expense reimbursement requires manager approval with receipt evidence.",
            metadata={
                "jurisdiction": "US",
                "policy_scope": "expense,reimbursement",
                "section": "4.2",
            },
        ),
        ChunkRecord(
            chunk_id="chunk-expense-1",
            doc_id="expense-policy-v1",
            version_tag="week-03-v1",
            chunk_index=1,
            content="Travel expenses above threshold require director signoff.",
            metadata={
                "jurisdiction": "US",
                "policy_scope": "expense,travel",
                "section": "4.3",
            },
        ),
        ChunkRecord(
            chunk_id="chunk-vendor-0",
            doc_id="vendor-policy-v2",
            version_tag="week-03-v1",
            chunk_index=0,
            content="Vendor data sharing in EU requires DPA and legal review.",
            metadata={
                "jurisdiction": "EU",
                "policy_scope": "vendor,privacy",
                "section": "7.1",
            },
        ),
    ]
    manifest = CorpusManifest(
        version_tag="week-03-v1",
        manifest_hash="a" * 64,
        doc_count=2,
        chunk_count=len(chunks),
        metadata_coverage={
            "doc_id": 1.0,
            "effective_date": 1.0,
            "owner": 1.0,
            "jurisdiction": 1.0,
        },
        chunks=chunks,
    )
    return build_retrieval_index(manifest)


def test_metadata_filters_restrict_out_of_scope_documents() -> None:
    index = _build_index()
    response = run_retrieval(
        index,
        question="Who approves expense reimbursement requests?",
        filters=RetrievalFilters(jurisdiction="US", policy_scope=["expense"]),
        top_k=3,
        min_score_for_answer=0.2,
        trace_id="trace-week3-filters",
    )

    assert response.trace_id == "trace-week3-filters"
    assert response.decision == DecisionEnum.ANSWERED
    assert response.retrieved_chunks
    assert {chunk.doc_id for chunk in response.retrieved_chunks} == {"expense-policy-v1"}
    cited_chunk_ids = {citation.chunk_id for citation in response.citations}
    retrieved_chunk_ids = {chunk.chunk_id for chunk in response.retrieved_chunks}
    assert cited_chunk_ids.issubset(retrieved_chunk_ids)
    assert len(response.audit_events) == 2


def test_retrieval_abstains_when_no_matching_chunks() -> None:
    index = _build_index()
    response = run_retrieval(
        index,
        question="What is the cryptography key rotation schedule?",
        filters=RetrievalFilters(jurisdiction="US", policy_scope=["security"]),
        top_k=3,
    )

    assert response.decision == DecisionEnum.ABSTAINED
    assert response.retrieved_chunks == []
    assert response.citations == []


def test_retrieval_escalates_when_top_score_is_below_threshold() -> None:
    index = _build_index()
    response = run_retrieval(
        index,
        question="manager threshold policy",
        filters=RetrievalFilters(jurisdiction="US", policy_scope=["expense"]),
        top_k=3,
        min_score_for_answer=0.9,
    )

    assert response.retrieved_chunks
    assert response.decision == DecisionEnum.ESCALATE


class _MockEmbeddingProvider:
    provider_name = "siliconflow"
    model = "mock-embedding-model"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            if "Expense" in text:
                vectors.append([1.0, 0.0])
            elif "Travel" in text:
                vectors.append([0.8, 0.2])
            else:
                vectors.append([0.0, 1.0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        if "vendor" in text.lower():
            return [0.0, 1.0]
        return [1.0, 0.0]


class _MockRerankProvider:
    provider_name = "siliconflow"
    model = "mock-rerank-model"

    def rerank(
        self,
        *,
        query: str,
        candidates: list[str],
        top_n: int,
    ) -> tuple[list[RerankResult], ProviderCallMetrics]:
        del query
        del candidates
        return (
            [RerankResult(candidate_index=1, score=0.95)],
            ProviderCallMetrics(
                provider=self.provider_name,
                model=self.model,
                latency_ms=8.2,
                status="ok",
                error_code=None,
            ),
        )


class _FailingRerankProvider:
    provider_name = "siliconflow"
    model = "mock-rerank-model"

    def rerank(
        self,
        *,
        query: str,
        candidates: list[str],
        top_n: int,
    ) -> tuple[list[RerankResult], ProviderCallMetrics]:
        del query
        del candidates
        del top_n
        raise TimeoutError("simulated timeout")


def test_retrieval_uses_provider_embeddings_and_rerank() -> None:
    index = _build_index()
    embedding_provider = _MockEmbeddingProvider()
    index = build_retrieval_index(
        CorpusManifest(
            version_tag="week-03-v1",
            manifest_hash="a" * 64,
            doc_count=2,
            chunk_count=3,
            metadata_coverage={
                "doc_id": 1.0,
                "effective_date": 1.0,
                "owner": 1.0,
                "jurisdiction": 1.0,
            },
            chunks=[
                ChunkRecord(
                    chunk_id="chunk-expense-0",
                    doc_id="expense-policy-v1",
                    version_tag="week-03-v1",
                    chunk_index=0,
                    content="Expense reimbursement requires manager approval with receipt evidence.",
                    metadata={
                        "jurisdiction": "US",
                        "policy_scope": "expense,reimbursement",
                        "section": "4.2",
                    },
                ),
                ChunkRecord(
                    chunk_id="chunk-expense-1",
                    doc_id="expense-policy-v1",
                    version_tag="week-03-v1",
                    chunk_index=1,
                    content="Travel expenses above threshold require director signoff.",
                    metadata={
                        "jurisdiction": "US",
                        "policy_scope": "expense,travel",
                        "section": "4.3",
                    },
                ),
                ChunkRecord(
                    chunk_id="chunk-vendor-0",
                    doc_id="vendor-policy-v2",
                    version_tag="week-03-v1",
                    chunk_index=0,
                    content="Vendor data sharing in EU requires DPA and legal review.",
                    metadata={
                        "jurisdiction": "EU",
                        "policy_scope": "vendor,privacy",
                        "section": "7.1",
                    },
                ),
            ],
        ),
        embedding_provider=embedding_provider,
    )
    response = run_retrieval(
        index,
        question="Who approves expense reimbursement requests?",
        filters=RetrievalFilters(jurisdiction="US", policy_scope=["expense"]),
        embedding_provider=embedding_provider,
        rerank_provider=_MockRerankProvider(),
        top_k=2,
        min_score_for_answer=0.2,
    )

    assert response.decision == DecisionEnum.ANSWERED
    assert response.retrieved_chunks[0].chunk_id == "chunk-expense-1"
    assert any(metric.status == "ok" for metric in response.provider_metrics)


def test_rerank_timeout_falls_back_to_pre_rerank_order() -> None:
    index = _build_index()
    response = run_retrieval(
        index,
        question="Who approves expense reimbursement requests?",
        filters=RetrievalFilters(jurisdiction="US", policy_scope=["expense"]),
        rerank_provider=_FailingRerankProvider(),
        top_k=2,
    )

    assert response.retrieved_chunks[0].chunk_id == "chunk-expense-0"
    assert any(metric.error_code == "rerank_failed" for metric in response.provider_metrics)
