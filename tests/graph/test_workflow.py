"""Week 5 LangGraph workflow integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.runnables import RunnableLambda

pytest.importorskip("langgraph")

from compliance_bot.audit.replay import replay_audit_trace
from compliance_bot.chains.citation_chain import build_citation_answer_chain
from compliance_bot.graph.workflow import run_week5_query
from compliance_bot.schemas.query import DecisionEnum


def _write_manifest(path: Path) -> None:
    manifest_payload = {
        "version_tag": "week-05-v1",
        "manifest_hash": "a" * 64,
        "doc_count": 1,
        "chunk_count": 1,
        "metadata_coverage": {"doc_id": 1.0, "jurisdiction": 1.0},
        "chunks": [
            {
                "chunk_id": "chunk-expense-0001",
                "doc_id": "expense-policy-v1",
                "version_tag": "week-05-v1",
                "chunk_index": 0,
                "content": (
                    "Expense reimbursement requires manager approval with receipt evidence."
                ),
                "metadata": {
                    "jurisdiction": "US",
                    "policy_scope": "expense,reimbursement",
                    "section": "4.2",
                },
            }
        ],
    }
    path.write_text(json.dumps(manifest_payload), encoding="utf-8")


def test_week5_workflow_replay_matches_decision_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-05-v1.json"
    _write_manifest(manifest_path)

    state = run_week5_query(
        manifest_path=manifest_path,
        question="Who approves expense reimbursement requests?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
    )
    replay = replay_audit_trace(state.audit_events, trace_id=state.trace_id)

    assert state.final_decision == DecisionEnum.ANSWERED
    assert replay.decision_path == state.decision_path
    assert replay.stage_counts["graph.finalize"] == 1


def test_week5_retry_preserves_trace_and_audit_continuity(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-05-v1.json"
    _write_manifest(manifest_path)

    attempts = {"count": 0}

    def _flaky_model(_: object) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("simulated timeout")
        return (
            '{"answer":"Manager approval is required for expense reimbursement.",'
            '"confidence":0.83,'
            '"decision":"ANSWERED",'
            '"citations":[{"doc_id":"expense-policy-v1","section":"4.2",'
            '"chunk_id":"chunk-expense-0001",'
            '"quote_span":"Expense reimbursement requires manager approval with receipt evidence.",'
            '"retrieval_score":0.82,"version":"week-05-v1"}]}'
        )

    answer_chain = build_citation_answer_chain(RunnableLambda(_flaky_model))

    state = run_week5_query(
        manifest_path=manifest_path,
        question="Who approves expense reimbursement requests?",
        jurisdiction="US",
        policy_scope=["expense"],
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
        max_answer_retries=1,
        answer_chain_override=answer_chain,
    )
    replay = replay_audit_trace(state.audit_events, trace_id=state.trace_id)

    assert state.answer_attempt == 2
    assert state.final_decision == DecisionEnum.ANSWERED
    assert any(step == "retry_answer" for step in state.decision_path)
    assert replay.decision_path == state.decision_path
    assert all(event.trace_id == state.trace_id for event in state.audit_events)

    answer_events = [event for event in state.audit_events if event.stage == "answer_grounding"]
    assert len(answer_events) == 2
    assert any(event.metadata.get("error_code") == "llm_timeout" for event in answer_events)
