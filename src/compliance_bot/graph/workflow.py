"""Week 5 LangGraph workflow for deterministic audit-ready execution."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from langchain_core.runnables import Runnable

from compliance_bot.audit.events import emit_workflow_audit_event
from compliance_bot.audit.replay import replay_audit_trace
from compliance_bot.chains.abstention_policy import DEFAULT_ABSTAIN_ANSWER
from compliance_bot.chains.citation_chain import (
    build_citation_answer_chain,
    run_citation_answer,
    resolve_answer_llm,
)
from compliance_bot.graph.state import ComplianceAgentState
from compliance_bot.llms.siliconflow import DEFAULT_SILICONFLOW_MODEL
from compliance_bot.providers.provider_registry import (
    resolve_embedding_provider,
    resolve_rerank_provider,
)
from compliance_bot.retrieval.indexer import RetrievalIndex, build_retrieval_index, load_manifest
from compliance_bot.retrieval.retriever import (
    QueryEmbeddingProvider,
    RerankProvider,
    run_retrieval,
)
from compliance_bot.schemas.answer import GroundedAnswerDraft
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import RetrievalFilters, RetrievalResponse

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:  # pragma: no cover - exercised in environments without langgraph.
    END = None
    START = None
    StateGraph = None


@dataclass(frozen=True)
class Week5WorkflowRuntime:
    """Resolved runtime dependencies for the Week 5 graph."""

    index: RetrievalIndex
    embedding_provider: QueryEmbeddingProvider | None
    rerank_provider: RerankProvider | None
    answer_chain: Runnable[Any, GroundedAnswerDraft] | None
    top_k: int
    min_score_for_answer: float
    min_confidence_for_answer: float
    llm_provider: str
    llm_model: str


def _append_policy_flag(state: ComplianceAgentState, flag: str) -> None:
    token = flag.strip().lower()
    if token and token not in state.policy_flags:
        state.policy_flags.append(token)


def _normalize_node(
    raw_state: dict[str, Any],
) -> dict[str, object]:
    state = ComplianceAgentState.from_graph_state(raw_state)
    normalized_query = " ".join(state.question.split())
    if not normalized_query:
        raise ValueError("question must not be blank")

    state.normalized_query = normalized_query
    state.decision_path.append("normalize")
    state.audit_events.append(
        emit_workflow_audit_event(
            trace_id=state.trace_id,
            stage="graph.normalize",
            status="ok",
            input_payload={"question": state.question},
            output_payload={"normalized_query": state.normalized_query},
        )
    )
    return state.as_graph_state()


def _build_retrieve_node(
    runtime: Week5WorkflowRuntime,
):
    def _retrieve_node(raw_state: dict[str, Any]) -> dict[str, object]:
        state = ComplianceAgentState.from_graph_state(raw_state)
        response = run_retrieval(
            runtime.index,
            question=state.normalized_query or state.question,
            filters=state.retrieval_filters,
            embedding_provider=runtime.embedding_provider,
            rerank_provider=runtime.rerank_provider,
            top_k=runtime.top_k,
            min_score_for_answer=runtime.min_score_for_answer,
            trace_id=state.trace_id,
        )

        state.normalized_query = response.normalized_query
        state.retrieval_decision = response.decision
        state.retrieved_chunks = response.retrieved_chunks
        state.citations = response.citations
        state.provider_metrics = response.provider_metrics
        state.audit_events.extend(response.audit_events)
        state.decision_path.append("retrieve")
        if response.decision != DecisionEnum.ANSWERED:
            _append_policy_flag(state, "retrieval_requires_review")

        state.audit_events.append(
            emit_workflow_audit_event(
                trace_id=state.trace_id,
                stage="graph.retrieve",
                status="ok",
                input_payload={
                    "top_k": runtime.top_k,
                    "min_score_for_answer": runtime.min_score_for_answer,
                    "filters": state.retrieval_filters.model_dump(),
                },
                output_payload={
                    "retrieval_decision": response.decision.value,
                    "chunk_count": len(response.retrieved_chunks),
                },
                metadata={
                    "provider_call_count": len(response.provider_metrics),
                    "provider_error_count": sum(
                        1 for metric in response.provider_metrics if metric.status != "ok"
                    ),
                },
            )
        )
        return state.as_graph_state()

    return _retrieve_node


def _build_answer_node(runtime: Week5WorkflowRuntime):
    def _answer_node(raw_state: dict[str, Any]) -> dict[str, object]:
        state = ComplianceAgentState.from_graph_state(raw_state)
        attempt = state.answer_attempt + 1
        retrieval_response = RetrievalResponse(
            trace_id=state.trace_id,
            question=state.question,
            normalized_query=state.normalized_query or state.question,
            decision=state.retrieval_decision,
            citations=state.citations,
            retrieved_chunks=state.retrieved_chunks,
            provider_metrics=state.provider_metrics,
            audit_events=state.audit_events,
        )
        answer_response = run_citation_answer(
            retrieval_response,
            answer_chain=runtime.answer_chain,
            min_confidence_for_answer=runtime.min_confidence_for_answer,
            llm_provider=runtime.llm_provider,
            llm_model=runtime.llm_model,
        )

        state.answer_attempt = attempt
        state.final_answer = answer_response.answer
        state.final_confidence = answer_response.confidence
        state.final_decision = answer_response.decision
        state.citations = answer_response.citations
        state.abstention_reason = answer_response.abstention_reason
        state.audit_events = answer_response.audit_events
        state.decision_path.append(f"answer_attempt_{attempt}")
        if state.abstention_reason:
            _append_policy_flag(state, state.abstention_reason)

        state.audit_events.append(
            emit_workflow_audit_event(
                trace_id=state.trace_id,
                stage="graph.answer",
                status="ok",
                input_payload={
                    "attempt": attempt,
                    "retrieval_decision": state.retrieval_decision.value,
                },
                output_payload={
                    "final_decision": state.final_decision.value,
                    "abstention_reason": state.abstention_reason,
                },
                metadata={
                    "attempt": attempt,
                    "llm_provider": runtime.llm_provider,
                    "llm_model": runtime.llm_model,
                },
            )
        )
        return state.as_graph_state()

    return _answer_node


def _route_after_answer(raw_state: dict[str, Any]) -> str:
    state = ComplianceAgentState.from_graph_state(raw_state)
    if (
        state.abstention_reason == "llm_timeout"
        and state.answer_attempt <= state.max_answer_retries
    ):
        return "retry"
    return "policy_check"


def _retry_node(raw_state: dict[str, Any]) -> dict[str, object]:
    state = ComplianceAgentState.from_graph_state(raw_state)
    state.decision_path.append("retry_answer")
    state.audit_events.append(
        emit_workflow_audit_event(
            trace_id=state.trace_id,
            stage="graph.retry",
            status="retry",
            input_payload={"last_reason": state.abstention_reason},
            output_payload={"next_attempt": state.answer_attempt + 1},
            metadata={"attempt": state.answer_attempt + 1},
        )
    )
    return state.as_graph_state()


def _policy_check_node(raw_state: dict[str, Any]) -> dict[str, object]:
    state = ComplianceAgentState.from_graph_state(raw_state)
    if state.final_decision == DecisionEnum.ANSWERED and not state.citations:
        state.final_decision = DecisionEnum.ABSTAINED
        state.final_answer = DEFAULT_ABSTAIN_ANSWER
        state.final_confidence = 0.0
        state.abstention_reason = "missing_citations_after_answer"
        _append_policy_flag(state, "missing_citations_after_answer")

    state.requires_human_review = state.final_decision != DecisionEnum.ANSWERED
    if state.requires_human_review:
        _append_policy_flag(state, "human_review_required")

    state.decision_path.append("policy_check")
    state.audit_events.append(
        emit_workflow_audit_event(
            trace_id=state.trace_id,
            stage="graph.policy_check",
            status="ok" if not state.requires_human_review else "review_required",
            input_payload={
                "decision": state.final_decision.value,
                "abstention_reason": state.abstention_reason,
            },
            output_payload={
                "requires_human_review": state.requires_human_review,
                "policy_flags": state.policy_flags,
            },
        )
    )
    return state.as_graph_state()


def _finalize_node(raw_state: dict[str, Any]) -> dict[str, object]:
    state = ComplianceAgentState.from_graph_state(raw_state)
    state.decision_path.append("finalize")
    state.audit_events.append(
        emit_workflow_audit_event(
            trace_id=state.trace_id,
            stage="graph.finalize",
            status="ok",
            input_payload={"decision_path_length": len(state.decision_path)},
            output_payload={
                "final_decision": state.final_decision.value,
                "requires_human_review": state.requires_human_review,
            },
        )
    )
    return state.as_graph_state()


def build_week5_workflow(runtime: Week5WorkflowRuntime):
    """Compile the Week 5 LangGraph workflow."""

    if StateGraph is None or START is None or END is None:
        raise ModuleNotFoundError(
            "Missing dependency 'langgraph'. Install with: pip install langgraph"
        )

    graph = StateGraph(dict)
    graph.add_node("normalize", _normalize_node)
    graph.add_node("retrieve", _build_retrieve_node(runtime))
    graph.add_node("answer", _build_answer_node(runtime))
    graph.add_node("retry", _retry_node)
    graph.add_node("policy_check", _policy_check_node)
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_conditional_edges(
        "answer",
        _route_after_answer,
        {"retry": "retry", "policy_check": "policy_check"},
    )
    graph.add_edge("retry", "answer")
    graph.add_edge("policy_check", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _resolve_runtime(
    *,
    manifest_path: Path,
    top_k: int,
    min_score_for_answer: float,
    min_confidence_for_answer: float,
    embedding_provider_mode: str,
    rerank_provider_mode: str,
    llm_provider_mode: str,
    env: Mapping[str, str] | None,
    answer_chain_override: Runnable[Any, GroundedAnswerDraft] | None,
) -> Week5WorkflowRuntime:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not 0.0 <= min_score_for_answer <= 1.0:
        raise ValueError("min_score_for_answer must be within [0, 1]")
    if not 0.0 <= min_confidence_for_answer <= 1.0:
        raise ValueError("min_confidence_for_answer must be within [0, 1]")

    source = env if env is not None else os.environ
    embedding_provider = resolve_embedding_provider(embedding_provider_mode, env=source)
    rerank_provider = resolve_rerank_provider(rerank_provider_mode, env=source)
    llm = resolve_answer_llm(llm_provider_mode, env=source)
    answer_chain = (
        answer_chain_override
        if answer_chain_override is not None
        else (build_citation_answer_chain(llm) if llm is not None else None)
    )

    llm_model = source.get("SILICONFLOW_MODEL", DEFAULT_SILICONFLOW_MODEL).strip()
    if answer_chain_override is not None:
        resolved_llm_provider = "custom"
        resolved_llm_model = "custom"
    elif llm is not None:
        resolved_llm_provider = "siliconflow"
        resolved_llm_model = llm_model or DEFAULT_SILICONFLOW_MODEL
    else:
        resolved_llm_provider = "none"
        resolved_llm_model = "fallback"

    manifest = load_manifest(manifest_path)
    index = build_retrieval_index(manifest, embedding_provider=embedding_provider)
    return Week5WorkflowRuntime(
        index=index,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        answer_chain=answer_chain,
        top_k=top_k,
        min_score_for_answer=min_score_for_answer,
        min_confidence_for_answer=min_confidence_for_answer,
        llm_provider=resolved_llm_provider,
        llm_model=resolved_llm_model,
    )


def run_week5_query(
    *,
    manifest_path: Path,
    question: str,
    jurisdiction: str | None = None,
    policy_scope: list[str] | None = None,
    top_k: int = 4,
    min_score_for_answer: float = 0.3,
    min_confidence_for_answer: float = 0.55,
    embedding_provider_mode: str = "auto",
    rerank_provider_mode: str = "auto",
    llm_provider_mode: str = "auto",
    trace_id: str | None = None,
    max_answer_retries: int = 1,
    env: Mapping[str, str] | None = None,
    answer_chain_override: Runnable[Any, GroundedAnswerDraft] | None = None,
) -> ComplianceAgentState:
    """Run the Week 5 graph workflow end-to-end."""

    runtime = _resolve_runtime(
        manifest_path=manifest_path,
        top_k=top_k,
        min_score_for_answer=min_score_for_answer,
        min_confidence_for_answer=min_confidence_for_answer,
        embedding_provider_mode=embedding_provider_mode,
        rerank_provider_mode=rerank_provider_mode,
        llm_provider_mode=llm_provider_mode,
        env=env,
        answer_chain_override=answer_chain_override,
    )
    workflow = build_week5_workflow(runtime)
    initial_state = ComplianceAgentState.from_input(
        question=question,
        trace_id=trace_id,
        retrieval_filters=RetrievalFilters(
            jurisdiction=jurisdiction,
            policy_scope=policy_scope or [],
        ),
        max_answer_retries=max_answer_retries,
    )
    result = workflow.invoke(initial_state.as_graph_state())
    return ComplianceAgentState.from_graph_state(result)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Week 5 LangGraph compliance workflow")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Path to Week 2 corpus manifest JSON",
    )
    parser.add_argument("--question", type=str, required=True, help="Compliance question")
    parser.add_argument("--jurisdiction", type=str, default=None)
    parser.add_argument(
        "--policy-scope",
        type=str,
        nargs="*",
        default=[],
        help="Policy scope terms (space-separated)",
    )
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--min-score-for-answer", type=float, default=0.3)
    parser.add_argument("--min-confidence-for-answer", type=float, default=0.55)
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "none", "siliconflow"),
        default="auto",
    )
    parser.add_argument(
        "--rerank-provider",
        choices=("auto", "none", "siliconflow"),
        default="auto",
    )
    parser.add_argument(
        "--llm-provider",
        choices=("auto", "none", "siliconflow"),
        default="auto",
    )
    parser.add_argument("--trace-id", type=str, default=None)
    parser.add_argument("--max-answer-retries", type=int, default=1)
    return parser


def main() -> None:
    """CLI entrypoint for Week 5 workflow execution."""

    args = _build_parser().parse_args()
    state = run_week5_query(
        manifest_path=args.manifest_path,
        question=args.question,
        jurisdiction=args.jurisdiction,
        policy_scope=args.policy_scope,
        top_k=args.top_k,
        min_score_for_answer=args.min_score_for_answer,
        min_confidence_for_answer=args.min_confidence_for_answer,
        embedding_provider_mode=args.embedding_provider,
        rerank_provider_mode=args.rerank_provider,
        llm_provider_mode=args.llm_provider,
        trace_id=args.trace_id,
        max_answer_retries=args.max_answer_retries,
    )
    replay = replay_audit_trace(state.audit_events, trace_id=state.trace_id)
    payload = {
        "trace_id": state.trace_id,
        "state": state.model_dump(mode="json"),
        "replay": replay.model_dump(mode="json"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
