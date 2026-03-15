"""Week 6 teaching helper: compare normal LangChain vs LangGraph workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from compliance_bot.audit.replay import replay_audit_trace
from compliance_bot.chains.citation_chain import run_week4_query
from compliance_bot.graph.workflow import run_week6_query


def comparison_workflow_diagram() -> str:
    """ASCII diagram for CLI teaching output."""

    return "\n".join(
        [
            "Workflow Comparison",
            "===================",
            "",
            "Normal LangChain (linear)",
            "  question -> retrieval -> grounded_answer -> final_response",
            "",
            "LangGraph (state machine)",
            "  question -> normalize -> tool_plan -> tools -> retrieve -> answer",
            "                                                     |",
            "                                                     +-> retry (on llm_timeout, bounded)",
            "  answer -> policy_check -> escalation -> finalize",
            "  finalize -> replay(trace_id) -> decision_path",
        ]
    )


def run_week5_comparison(
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
) -> dict[str, object]:
    """Run one question through both Week 4 and Week 6 paths and summarize differences."""

    linear = run_week4_query(
        manifest_path=manifest_path,
        question=question,
        jurisdiction=jurisdiction,
        policy_scope=policy_scope,
        top_k=top_k,
        min_score_for_answer=min_score_for_answer,
        min_confidence_for_answer=min_confidence_for_answer,
        embedding_provider_mode=embedding_provider_mode,
        rerank_provider_mode=rerank_provider_mode,
        llm_provider_mode=llm_provider_mode,
    )
    graph_state = run_week6_query(
        manifest_path=manifest_path,
        question=question,
        jurisdiction=jurisdiction,
        policy_scope=policy_scope,
        top_k=top_k,
        min_score_for_answer=min_score_for_answer,
        min_confidence_for_answer=min_confidence_for_answer,
        embedding_provider_mode=embedding_provider_mode,
        rerank_provider_mode=rerank_provider_mode,
        llm_provider_mode=llm_provider_mode,
    )
    replay = replay_audit_trace(graph_state.audit_events, trace_id=graph_state.trace_id)

    shared = {
        "question": question,
        "linear_decision": linear.decision.value,
        "graph_decision": graph_state.final_decision.value,
        "linear_citation_count": len(linear.citations),
        "graph_citation_count": len(graph_state.citations),
        "linear_abstention_reason": linear.abstention_reason,
        "graph_abstention_reason": graph_state.abstention_reason,
    }
    differences = {
        "normal_langchain": {
            "has_graph_state": False,
            "has_retry_state": False,
            "has_replay_summary": False,
            "decision_path_available": False,
            "has_tool_routing": False,
            "has_escalation_node": False,
            "answer_attempt_count": 1,
        },
        "langgraph": {
            "has_graph_state": True,
            "has_retry_state": True,
            "has_replay_summary": True,
            "decision_path_available": True,
            "has_tool_routing": True,
            "has_escalation_node": True,
            "answer_attempt_count": graph_state.answer_attempt,
            "decision_path": graph_state.decision_path,
            "replay_decision_path": replay.decision_path,
        },
    }
    return {
        "shared_outcome": shared,
        "normal_langchain_response": linear.model_dump(mode="json"),
        "langgraph_state_response": graph_state.model_dump(mode="json"),
        "langgraph_replay_summary": replay.model_dump(mode="json"),
        "differences": differences,
    }


def run_week6_comparison(**kwargs: object) -> dict[str, object]:
    """Backward-compatible Week 6 alias for the comparison helper."""

    return run_week5_comparison(**kwargs)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Week 4 normal LangChain flow vs Week 6 LangGraph flow"
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Path to Week 2 corpus manifest JSON",
    )
    parser.add_argument("--question", type=str, required=True)
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
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output JSON only (disable ASCII workflow diagram header).",
    )
    return parser


def main() -> None:
    """CLI entrypoint for Week 6 comparison helper."""

    args = _build_parser().parse_args()
    payload = run_week6_comparison(
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
    )
    if not args.json_only:
        print(comparison_workflow_diagram())
        print()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
