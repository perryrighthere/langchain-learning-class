"""Week 4 citation-first answer chain tests."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.runnables import RunnableLambda

from compliance_bot.chains.citation_chain import (
    build_citation_answer_chain,
    citations_are_grounded,
    invoke_citation_answer_chain,
    run_citation_answer,
    run_week4_query,
)
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import RetrievedChunk, RetrievalResponse


def _retrieved_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="chunk-expense-0",
            doc_id="expense-policy-v1",
            version_tag="week-04-v1",
            chunk_index=0,
            content="Expense reimbursement requires manager approval with receipt evidence.",
            retrieval_score=0.82,
            metadata={"section": "4.2", "jurisdiction": "US", "policy_scope": "expense"},
            matched_terms=["expense", "approval"],
        )
    ]


def _retrieval_response(decision: DecisionEnum = DecisionEnum.ANSWERED) -> RetrievalResponse:
    return RetrievalResponse(
        trace_id="trace-week4-001",
        question="Who approves expense reimbursements?",
        normalized_query="who approves expense reimbursements",
        decision=decision,
        citations=[],
        retrieved_chunks=_retrieved_chunks(),
        provider_metrics=[],
        audit_events=[],
    )


def test_citation_answer_chain_structured_output_is_parseable() -> None:
    chain = build_citation_answer_chain(
        RunnableLambda(
            lambda _: (
                '{"answer":"Manager approval is required for expense reimbursement.",'
                '"confidence":0.78,'
                '"decision":"ANSWERED",'
                '"citations":[{"doc_id":"expense-policy-v1","section":"4.2",'
                '"chunk_id":"chunk-expense-0",'
                '"quote_span":"Expense reimbursement requires manager approval with receipt evidence.",'
                '"retrieval_score":0.82,"version":"week-04-v1"}]}'
            )
        )
    )

    result = invoke_citation_answer_chain(
        chain,
        question="Who approves expense reimbursements?",
        retrieved_chunks=_retrieved_chunks(),
    )

    assert result.decision == DecisionEnum.ANSWERED
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-expense-0"


def test_invalid_citation_chunk_forces_controlled_abstention() -> None:
    chain = build_citation_answer_chain(
        RunnableLambda(
            lambda _: (
                '{"answer":"Manager approval is required for expense reimbursement.",'
                '"confidence":0.89,'
                '"decision":"ANSWERED",'
                '"citations":[{"doc_id":"expense-policy-v1","section":"4.2",'
                '"chunk_id":"chunk-does-not-exist",'
                '"quote_span":"Expense reimbursement requires manager approval with receipt evidence.",'
                '"retrieval_score":0.82,"version":"week-04-v1"}]}'
            )
        )
    )

    response = run_citation_answer(
        _retrieval_response(),
        answer_chain=chain,
        min_confidence_for_answer=0.55,
        llm_provider="siliconflow",
        llm_model="Qwen/Qwen3-14B",
    )

    assert response.decision == DecisionEnum.ABSTAINED
    assert response.citations == []
    assert response.abstention_reason == "citation_validation_failed"


def test_retrieval_abstained_short_circuits_answer_generation() -> None:
    response = run_citation_answer(
        _retrieval_response(decision=DecisionEnum.ABSTAINED),
        answer_chain=None,
        min_confidence_for_answer=0.55,
    )

    assert response.decision == DecisionEnum.ABSTAINED
    assert response.abstention_reason == "retrieval_insufficient_evidence"


def test_llm_timeout_maps_to_escalate_with_audit_error() -> None:
    def _raise_timeout(_: object) -> str:
        raise TimeoutError("simulated timeout")

    response = run_citation_answer(
        _retrieval_response(),
        answer_chain=RunnableLambda(_raise_timeout),
        min_confidence_for_answer=0.55,
        llm_provider="siliconflow",
        llm_model="Qwen/Qwen3-14B",
    )

    assert response.decision == DecisionEnum.ESCALATE
    assert response.abstention_reason == "llm_timeout"
    assert any(
        event.metadata.get("error_code") == "llm_timeout" for event in response.audit_events
    )


def test_fallback_answer_has_grounded_citations_when_not_abstained() -> None:
    response = run_citation_answer(
        _retrieval_response(),
        answer_chain=None,
        min_confidence_for_answer=0.55,
    )

    assert response.decision == DecisionEnum.ANSWERED
    assert citations_are_grounded(
        response.citations,
        retrieved_chunks=response.retrieved_chunks,
    )


def test_run_week4_query_integrates_retrieval_and_grounded_answer(tmp_path: Path) -> None:
    manifest_path = Path(tmp_path) / "manifest-week-04-v1.json"
    manifest_payload = {
        "version_tag": "week-04-v1",
        "manifest_hash": "a" * 64,
        "doc_count": 1,
        "chunk_count": 1,
        "metadata_coverage": {"doc_id": 1.0, "jurisdiction": 1.0},
        "chunks": [
            {
                "chunk_id": "chunk-expense-0001",
                "doc_id": "expense-policy-v1",
                "version_tag": "week-04-v1",
                "chunk_index": 0,
                "content": "Expense reimbursement requires manager approval with receipt evidence.",
                "metadata": {
                    "jurisdiction": "US",
                    "policy_scope": "expense,reimbursement",
                    "section": "4.2",
                },
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    response = run_week4_query(
        manifest_path=manifest_path,
        question="Who approves expense reimbursement requests?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
    )

    assert response.decision == DecisionEnum.ANSWERED
    assert response.citations
    assert citations_are_grounded(
        response.citations,
        retrieved_chunks=response.retrieved_chunks,
    )
