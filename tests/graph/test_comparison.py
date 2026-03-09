"""Week 5 comparison helper tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from compliance_bot.graph.comparison import comparison_workflow_diagram, run_week5_comparison


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


def test_week5_comparison_reports_graph_specific_capabilities(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-05-v1.json"
    _write_manifest(manifest_path)

    payload = run_week5_comparison(
        manifest_path=manifest_path,
        question="Who approves expense reimbursement requests?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
    )

    assert payload["shared_outcome"]["linear_decision"] == "ANSWERED"
    assert payload["shared_outcome"]["graph_decision"] == "ANSWERED"
    assert payload["differences"]["normal_langchain"]["decision_path_available"] is False
    assert payload["differences"]["langgraph"]["decision_path_available"] is True
    assert payload["differences"]["langgraph"]["decision_path"] == payload["differences"][
        "langgraph"
    ]["replay_decision_path"]


def test_comparison_workflow_diagram_mentions_both_modes() -> None:
    diagram = comparison_workflow_diagram()
    assert "Normal LangChain" in diagram
    assert "LangGraph" in diagram
    assert "retry" in diagram
