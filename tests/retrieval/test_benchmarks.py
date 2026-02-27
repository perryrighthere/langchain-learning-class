"""Week 3 benchmark tests."""

from __future__ import annotations

from compliance_bot.retrieval.benchmarks import run_retrieval_benchmarks
from compliance_bot.retrieval.indexer import RetrievalIndex, build_retrieval_index
from compliance_bot.schemas.ingestion import ChunkRecord, CorpusManifest
from compliance_bot.schemas.retrieval import RetrievalBenchmarkCase, RetrievalFilters


def _build_index() -> RetrievalIndex:
    chunks = [
        ChunkRecord(
            chunk_id="chunk-expense-0",
            doc_id="expense-policy-v1",
            version_tag="week-03-v1",
            chunk_index=0,
            content="Expense reimbursement requires manager approval with receipt evidence.",
            metadata={"jurisdiction": "US", "policy_scope": "expense"},
        ),
        ChunkRecord(
            chunk_id="chunk-vendor-0",
            doc_id="vendor-policy-v2",
            version_tag="week-03-v1",
            chunk_index=0,
            content="Vendor onboarding requires legal review and DPA before data sharing.",
            metadata={"jurisdiction": "US", "policy_scope": "vendor"},
        ),
    ]
    manifest = CorpusManifest(
        version_tag="week-03-v1",
        manifest_hash="b" * 64,
        doc_count=2,
        chunk_count=2,
        metadata_coverage={
            "doc_id": 1.0,
            "effective_date": 1.0,
            "owner": 1.0,
            "jurisdiction": 1.0,
        },
        chunks=chunks,
    )
    return build_retrieval_index(manifest)


def test_benchmark_report_passes_when_quality_gates_are_met() -> None:
    index = _build_index()
    cases = [
        RetrievalBenchmarkCase(
            case_id="case-expense",
            question="Who approves expense reimbursements?",
            expected_doc_ids=["expense-policy-v1"],
            filters=RetrievalFilters(jurisdiction="US", policy_scope=["expense"]),
        ),
        RetrievalBenchmarkCase(
            case_id="case-vendor",
            question="What is required before vendor data sharing?",
            expected_doc_ids=["vendor-policy-v2"],
            filters=RetrievalFilters(jurisdiction="US", policy_scope=["vendor"]),
        ),
    ]

    report = run_retrieval_benchmarks(
        index,
        cases=cases,
        top_k=2,
        recall_floor=0.5,
        latency_ceiling_ms=1000.0,
    )

    assert report.avg_recall_at_k >= 0.5
    assert report.meets_quality_gate is True
    assert len(report.results) == 2


def test_benchmark_report_fails_when_recall_gate_is_not_met() -> None:
    index = _build_index()
    cases = [
        RetrievalBenchmarkCase(
            case_id="case-miss",
            question="Who approves expense reimbursements?",
            expected_doc_ids=["non-existent-doc"],
            filters=RetrievalFilters(jurisdiction="US", policy_scope=["expense"]),
        )
    ]

    report = run_retrieval_benchmarks(
        index,
        cases=cases,
        top_k=1,
        recall_floor=1.0,
        latency_ceiling_ms=1000.0,
    )

    assert report.avg_recall_at_k == 0.0
    assert report.meets_quality_gate is False
