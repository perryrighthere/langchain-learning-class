"""Week 6 LangGraph workflow integration tests."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool

pytest.importorskip("langgraph")

from compliance_bot.audit.replay import replay_audit_trace
from compliance_bot.chains.citation_chain import build_citation_answer_chain
from compliance_bot.graph.workflow import run_week6_query
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.tools import PolicyRegistryLookupInput, TavilySearchInput


def _write_manifest(path: Path) -> None:
    manifest_payload = {
        "version_tag": "week-06-v1",
        "manifest_hash": "a" * 64,
        "doc_count": 1,
        "chunk_count": 1,
        "metadata_coverage": {"doc_id": 1.0, "jurisdiction": 1.0},
        "chunks": [
            {
                "chunk_id": "chunk-expense-0001",
                "doc_id": "expense-policy-v1",
                "version_tag": "week-06-v1",
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


def test_week6_workflow_replay_matches_decision_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-06-v1.json"
    _write_manifest(manifest_path)

    state = run_week6_query(
        manifest_path=manifest_path,
        question="Which policy section covers expense reimbursement?",
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
    assert replay.stage_counts["graph.tools"] == 1
    assert replay.stage_counts["graph.escalation"] == 1


def test_week6_high_risk_intent_requires_human_review(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-06-v1.json"
    _write_manifest(manifest_path)

    state = run_week6_query(
        manifest_path=manifest_path,
        question="Can we approve an exception override for this expense right now?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
    )

    assert state.tool_plan.high_risk is True
    assert state.requires_human_review is True
    assert state.final_decision == DecisionEnum.ESCALATE
    assert state.escalation_reason is not None


def test_week6_tool_timeout_triggers_safe_fallback_and_audit_log(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-06-v1.json"
    _write_manifest(manifest_path)

    def _slow_policy_registry(
        question: str,
        jurisdiction: str | None = None,
        policy_scope: list[str] | None = None,
        max_results: int = 3,
    ) -> dict[str, object]:
        del question, jurisdiction, policy_scope, max_results
        time.sleep(0.05)
        return {
            "resolved": True,
            "matches": [],
            "summary": "This result should never be used because the tool times out.",
        }

    slow_tool = StructuredTool.from_function(
        func=_slow_policy_registry,
        name="policy_registry_lookup",
        description="Simulated slow policy registry tool.",
        args_schema=PolicyRegistryLookupInput,
    )

    state = run_week6_query(
        manifest_path=manifest_path,
        question="Which policy section covers expense reimbursement?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
        tool_timeout_ms=1,
        policy_registry_tool_override=slow_tool,
    )

    assert state.final_decision == DecisionEnum.ESCALATE
    assert state.requires_human_review is True
    assert any(result.error_code == "tool_timeout" for result in state.tool_results)
    assert any(event.stage == "graph.tools" and event.status == "degraded" for event in state.audit_events)


def test_week6_executes_real_tool_calls_from_planner_output(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-06-v1.json"
    _write_manifest(manifest_path)

    tool_planner = RunnableLambda(
        lambda _: AIMessage(
            content="Use the policy registry before retrieval.",
            tool_calls=[
                {
                    "name": "policy_registry_lookup",
                    "args": {
                        "question": "Which policy section covers expense reimbursement?",
                        "jurisdiction": "US",
                        "policy_scope": ["expense"],
                        "max_results": 1,
                    },
                    "id": "call-policy-1",
                    "type": "tool_call",
                }
            ],
        )
    )

    state = run_week6_query(
        manifest_path=manifest_path,
        question="Which policy section covers expense reimbursement?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
        tool_planner_override=tool_planner,
    )

    assert state.tool_plan.router_mode == "llm_tool_calling"
    assert state.tool_plan.planned_tools == ["policy_registry_lookup"]
    assert state.tool_plan.tool_arguments["policy_registry_lookup"]["max_results"] == 1
    assert [result.tool_name for result in state.tool_results] == ["policy_registry_lookup"]
    assert state.final_decision == DecisionEnum.ANSWERED


def test_week6_executes_tavily_search_tool_call(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-06-v1.json"
    _write_manifest(manifest_path)

    tool_planner = RunnableLambda(
        lambda _: AIMessage(
            content="Use Tavily to get the latest public update.",
            tool_calls=[
                {
                    "name": "tavily_search",
                    "args": {
                        "question": "What is the latest reimbursement update?",
                        "topic": "news",
                        "max_results": 1,
                        "search_depth": "advanced",
                        "days": 7,
                    },
                    "id": "call-tavily-1",
                    "type": "tool_call",
                }
            ],
        )
    )

    tavily_tool = StructuredTool.from_function(
        func=lambda question, topic="general", max_results=3, search_depth="advanced", days=None: {
            "resolved": True,
            "summary": "External search returned: Expense Update Bulletin",
            "answer": "A recent bulletin still requires manager approval.",
            "topic": topic,
            "sources": [
                {
                    "title": "Expense Update Bulletin",
                    "url": "https://example.com/expense-update",
                    "content": "Manager approval remains required.",
                    "score": 0.91,
                }
            ],
            "requires_human_review": False,
        },
        name="tavily_search",
        description="Mock Tavily tool.",
        args_schema=TavilySearchInput,
    )

    state = run_week6_query(
        manifest_path=manifest_path,
        question="What is the latest reimbursement update?",
        jurisdiction="US",
        policy_scope=["expense"],
        min_confidence_for_answer=0.5,
        embedding_provider_mode="none",
        rerank_provider_mode="none",
        llm_provider_mode="none",
        tool_planner_override=tool_planner,
        tavily_search_tool_override=tavily_tool,
    )

    assert state.tool_plan.planned_tools == ["tavily_search"]
    assert state.tool_plan.tool_arguments["tavily_search"]["topic"] == "news"
    assert [result.tool_name for result in state.tool_results] == ["tavily_search"]
    assert "Expense Update Bulletin" in state.tool_context


def test_week6_retry_preserves_trace_and_audit_continuity(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest-week-06-v1.json"
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
            '"retrieval_score":0.82,"version":"week-06-v1"}]}'
        )

    answer_chain = build_citation_answer_chain(RunnableLambda(_flaky_model))

    state = run_week6_query(
        manifest_path=manifest_path,
        question="Which policy section covers expense reimbursement?",
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
