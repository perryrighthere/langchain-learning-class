"""Week 6 LangGraph workflow with safe tools and escalation controls."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, TypeVar

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from compliance_bot.audit.events import emit_workflow_audit_event
from compliance_bot.audit.replay import replay_audit_trace
from compliance_bot.chains.abstention_policy import DEFAULT_ABSTAIN_ANSWER
from compliance_bot.chains.citation_chain import (
    build_citation_answer_chain,
    run_citation_answer,
    resolve_answer_llm,
)
from compliance_bot.graph.escalation_node import apply_escalation_policy
from compliance_bot.graph.state import ComplianceAgentState
from compliance_bot.llms.siliconflow import DEFAULT_SILICONFLOW_MODEL
from compliance_bot.providers.provider_registry import (
    resolve_embedding_provider,
    resolve_rerank_provider,
)
from compliance_bot.retrieval.indexer import RetrievalIndex, build_retrieval_index, load_manifest, tokenize
from compliance_bot.retrieval.retriever import (
    QueryEmbeddingProvider,
    RerankProvider,
    run_retrieval,
)
from compliance_bot.schemas.answer import GroundedAnswerDraft
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import RetrievalFilters, RetrievalResponse
from compliance_bot.schemas.tools import (
    ExceptionLogLookupInput,
    ExceptionLogLookupResult,
    PolicyRegistryLookupInput,
    PolicyRegistryLookupResult,
    TavilySearchInput,
    TavilySearchResult,
    ToolExecutionRecord,
    ToolPlan,
)
from compliance_bot.tools.exception_log_tool import (
    build_exception_log_tool,
    load_exception_log_records,
    render_exception_log_context,
)
from compliance_bot.tools.policy_registry_tool import (
    build_policy_registry_tool,
    render_policy_registry_context,
)
from compliance_bot.tools.tavily_search_tool import (
    build_tavily_search_tool,
    has_tavily_api_key,
    render_tavily_context,
)

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:  # pragma: no cover - exercised in environments without langgraph.
    END = None
    START = None
    StateGraph = None


TToolResult = TypeVar(
    "TToolResult",
    PolicyRegistryLookupResult,
    ExceptionLogLookupResult,
    TavilySearchResult,
)

_POLICY_TERMS = {
    "policy",
    "version",
    "latest",
    "active",
    "registry",
    "section",
    "effective",
}
_EXCEPTION_TERMS = {
    "exception",
    "override",
    "waiver",
    "waive",
    "urgent",
    "approve",
    "bypass",
}
_HIGH_RISK_TERMS = {
    "exception",
    "override",
    "waiver",
    "breach",
    "fraud",
    "delete",
    "lawsuit",
    "regulator",
    "share",
    "pii",
}
_REALTIME_TERMS = {
    "latest",
    "today",
    "recent",
    "recently",
    "current",
    "news",
    "update",
    "updates",
    "new",
    "regulator",
    "sanction",
}


@dataclass(frozen=True)
class Week6WorkflowRuntime:
    """Resolved runtime dependencies for the Week 6 graph."""

    index: RetrievalIndex
    embedding_provider: QueryEmbeddingProvider | None
    rerank_provider: RerankProvider | None
    answer_chain: Runnable[Any, GroundedAnswerDraft] | None
    tool_router: Runnable[Any, Any] | None
    policy_registry_tool: BaseTool
    exception_log_tool: BaseTool
    tavily_search_tool: BaseTool | None
    top_k: int
    min_score_for_answer: float
    min_confidence_for_answer: float
    llm_provider: str
    llm_model: str
    tool_timeout_ms: int


def _append_policy_flag(state: ComplianceAgentState, flag: str) -> None:
    token = flag.strip().lower()
    if token and token not in state.policy_flags:
        state.policy_flags.append(token)


def _to_text(model_output: Any) -> str:
    if isinstance(model_output, str):
        return model_output
    if hasattr(model_output, "content"):
        content = model_output.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
    raise TypeError(f"Unsupported model output type: {type(model_output)!r}")


def _heuristic_tool_plan(
    *,
    question: str,
    retrieval_filters: RetrievalFilters,
    realtime_search_available: bool,
) -> ToolPlan:
    terms = set(tokenize(question))
    planned_tools: list[str] = []
    rationale_parts: list[str] = []

    policy_scope = set(retrieval_filters.policy_scope)
    if policy_scope or terms.intersection(_POLICY_TERMS):
        planned_tools.append("policy_registry_lookup")
        rationale_parts.append("policy registry lookup selected")

    if terms.intersection(_EXCEPTION_TERMS):
        planned_tools.append("exception_log_lookup")
        rationale_parts.append("exception log lookup selected")

    realtime_requested = bool(terms.intersection(_REALTIME_TERMS))
    if realtime_requested and realtime_search_available:
        planned_tools.append("tavily_search")
        rationale_parts.append("real-time web search selected")
    elif realtime_requested:
        rationale_parts.append("real-time web search requested but Tavily is not configured")

    high_risk = bool(terms.intersection(_HIGH_RISK_TERMS))
    if realtime_requested and not realtime_search_available:
        high_risk = True
    if high_risk:
        rationale_parts.append("high-risk intent detected")

    if not planned_tools:
        rationale_parts.append("direct retrieval path is sufficient")

    return ToolPlan(
        planned_tools=planned_tools,
        tool_arguments={},
        high_risk=high_risk,
        rationale="; ".join(rationale_parts),
        router_mode="heuristic",
    )


def build_tool_router_chain(
    llm: Runnable[Any, Any],
    *,
    tools: list[BaseTool],
) -> Runnable[Any, Any]:
    """Create a real tool-calling planner that can emit LangChain tool calls."""

    bind_tools = getattr(llm, "bind_tools", None)
    if bind_tools is None:
        raise TypeError("Configured LLM does not support bind_tools().")

    tool_llm = bind_tools(tools)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a compliance workflow planner. "
                    "Use the available tools when they would reduce ambiguity before retrieval and grounded answering. "
                    "You may call zero, one, or multiple tools. "
                    "Use tavily_search for current, recent, latest, or public-web questions. "
                    "If no tool is needed, do not call a tool and briefly explain why."
                ),
            ),
            (
                "human",
                (
                    "Question: {question}\n"
                    "Jurisdiction: {jurisdiction}\n"
                    "Policy scope: {policy_scope}"
                ),
            ),
        ]
    )
    return prompt | tool_llm


def _coerce_policy_scope(value: object, *, fallback: list[str]) -> list[str]:
    if value is None:
        return list(fallback)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(fallback)


def _tool_plan_from_tool_calls(
    *,
    question: str,
    retrieval_filters: RetrievalFilters,
    planner_output: Any,
) -> ToolPlan:
    heuristic_plan = _heuristic_tool_plan(
        question=question,
        retrieval_filters=retrieval_filters,
        realtime_search_available=True,
    )
    tool_calls = getattr(planner_output, "tool_calls", [])
    content = getattr(planner_output, "content", "")
    rationale = _to_text(planner_output) if planner_output is not None and not isinstance(planner_output, str) else str(content or "")
    normalized_rationale = " ".join(rationale.split()) or heuristic_plan.rationale

    if not isinstance(tool_calls, list) or not tool_calls:
        return ToolPlan(
            planned_tools=[],
            tool_arguments={},
            high_risk=heuristic_plan.high_risk,
            rationale=normalized_rationale or "Model selected direct retrieval path.",
            router_mode="llm_tool_calling",
        )

    planned_tools: list[str] = []
    tool_arguments: dict[str, dict[str, object]] = {}
    for raw_call in tool_calls:
        if not isinstance(raw_call, dict):
            continue
        tool_name = str(raw_call.get("name", "")).strip().lower()
        raw_args = raw_call.get("args", {})
        if not tool_name or not isinstance(raw_args, dict):
            continue
        planned_tools.append(tool_name)
        tool_arguments[tool_name] = dict(raw_args)

    if not planned_tools:
        return heuristic_plan

    return ToolPlan(
        planned_tools=planned_tools,
        tool_arguments=tool_arguments,
        high_risk=heuristic_plan.high_risk or "exception_log_lookup" in planned_tools,
        rationale=normalized_rationale or "Model selected tool calls.",
        router_mode="llm_tool_calling",
    )


def _normalize_node(raw_state: dict[str, Any]) -> dict[str, object]:
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


def _build_tool_plan_node(runtime: Week6WorkflowRuntime):
    def _tool_plan_node(raw_state: dict[str, Any]) -> dict[str, object]:
        state = ComplianceAgentState.from_graph_state(raw_state)
        router_status = "ok"
        if runtime.tool_router is None:
            plan = _heuristic_tool_plan(
                question=state.normalized_query or state.question,
                retrieval_filters=state.retrieval_filters,
                realtime_search_available=runtime.tavily_search_tool is not None,
            )
        else:
            try:
                planner_output = runtime.tool_router.invoke(
                    {
                        "question": state.normalized_query or state.question,
                        "jurisdiction": state.retrieval_filters.jurisdiction or "any",
                        "policy_scope": ", ".join(state.retrieval_filters.policy_scope) or "none",
                    }
                )
                plan = _tool_plan_from_tool_calls(
                    question=state.normalized_query or state.question,
                    retrieval_filters=state.retrieval_filters,
                    planner_output=planner_output,
                )
            except Exception:
                plan = _heuristic_tool_plan(
                    question=state.normalized_query or state.question,
                    retrieval_filters=state.retrieval_filters,
                    realtime_search_available=runtime.tavily_search_tool is not None,
                )
                plan.router_mode = "heuristic"
                router_status = "fallback"

        state.tool_plan = plan
        state.decision_path.append("tool_plan")
        if plan.high_risk:
            _append_policy_flag(state, "high_risk_intent")

        state.audit_events.append(
            emit_workflow_audit_event(
                trace_id=state.trace_id,
                stage="graph.tool_plan",
                status=router_status,
                input_payload={
                    "question": state.normalized_query or state.question,
                    "filters": state.retrieval_filters.model_dump(),
                },
                output_payload={
                    "planned_tools": plan.planned_tools,
                    "tool_arguments": plan.tool_arguments,
                    "high_risk": plan.high_risk,
                    "rationale": plan.rationale,
                },
                metadata={
                    "router_mode": plan.router_mode,
                    "router_status": router_status,
                    "llm_provider": runtime.llm_provider if runtime.tool_router is not None else "heuristic",
                    "llm_model": runtime.llm_model if runtime.tool_router is not None else "heuristic",
                },
            )
        )
        return state.as_graph_state()

    return _tool_plan_node


def _invoke_tool_with_timeout(
    *,
    tool: BaseTool,
    tool_input: PolicyRegistryLookupInput | ExceptionLogLookupInput | TavilySearchInput,
    output_model: type[TToolResult],
    timeout_ms: int,
) -> tuple[TToolResult | None, ToolExecutionRecord]:
    start = perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool.invoke, tool_input.model_dump(mode="python"))
            raw_result = future.result(timeout=timeout_ms / 1000.0)
        elapsed_ms = (perf_counter() - start) * 1000.0
        result = output_model.model_validate(raw_result)
        return (
            result,
            ToolExecutionRecord(
                tool_name=tool.name,
                status="ok",
                latency_ms=elapsed_ms,
                resolved=result.resolved,
                summary=result.summary,
                requires_human_review=getattr(result, "requires_human_review", not result.resolved),
            ),
        )
    except FuturesTimeoutError:
        elapsed_ms = (perf_counter() - start) * 1000.0
        return (
            None,
            ToolExecutionRecord(
                tool_name=tool.name,
                status="error",
                latency_ms=elapsed_ms,
                resolved=False,
                summary=f"{tool.name} timed out before returning a safe result.",
                error_code="tool_timeout",
                requires_human_review=True,
            ),
        )
    except Exception as exc:
        elapsed_ms = (perf_counter() - start) * 1000.0
        return (
            None,
            ToolExecutionRecord(
                tool_name=tool.name,
                status="error",
                latency_ms=elapsed_ms,
                resolved=False,
                summary=f"{tool.name} failed: {exc}",
                error_code="tool_failed",
                requires_human_review=True,
            ),
        )


def _build_policy_registry_input(
    *,
    state: ComplianceAgentState,
    raw_args: dict[str, object],
) -> PolicyRegistryLookupInput:
    return PolicyRegistryLookupInput(
        question=str(raw_args.get("question") or state.normalized_query or state.question),
        jurisdiction=(
            str(raw_args["jurisdiction"])
            if raw_args.get("jurisdiction") not in {None, ""}
            else state.retrieval_filters.jurisdiction
        ),
        policy_scope=_coerce_policy_scope(
            raw_args.get("policy_scope"),
            fallback=state.retrieval_filters.policy_scope,
        ),
        max_results=(
            int(raw_args["max_results"])
            if raw_args.get("max_results") is not None
            else 3
        ),
    )


def _build_exception_log_input(
    *,
    state: ComplianceAgentState,
    raw_args: dict[str, object],
) -> ExceptionLogLookupInput:
    return ExceptionLogLookupInput(
        question=str(raw_args.get("question") or state.normalized_query or state.question),
        jurisdiction=(
            str(raw_args["jurisdiction"])
            if raw_args.get("jurisdiction") not in {None, ""}
            else state.retrieval_filters.jurisdiction
        ),
        policy_scope=_coerce_policy_scope(
            raw_args.get("policy_scope"),
            fallback=state.retrieval_filters.policy_scope,
        ),
    )


def _build_tavily_search_input(
    *,
    state: ComplianceAgentState,
    raw_args: dict[str, object],
) -> TavilySearchInput:
    return TavilySearchInput(
        question=str(raw_args.get("question") or state.normalized_query or state.question),
        topic=str(raw_args.get("topic") or "general"),
        max_results=int(raw_args.get("max_results") or 3),
        search_depth=str(raw_args.get("search_depth") or "advanced"),
        days=int(raw_args["days"]) if raw_args.get("days") is not None else None,
    )


def _build_tools_node(runtime: Week6WorkflowRuntime):
    def _tools_node(raw_state: dict[str, Any]) -> dict[str, object]:
        state = ComplianceAgentState.from_graph_state(raw_state)
        state.tool_results = []
        tool_context_lines: list[str] = []
        error_codes: list[str] = []

        for tool_name in state.tool_plan.planned_tools:
            raw_args = state.tool_plan.tool_arguments.get(tool_name, {})
            if tool_name == "policy_registry_lookup":
                tool_input = _build_policy_registry_input(state=state, raw_args=raw_args)
                result, execution = _invoke_tool_with_timeout(
                    tool=runtime.policy_registry_tool,
                    tool_input=tool_input,
                    output_model=PolicyRegistryLookupResult,
                    timeout_ms=runtime.tool_timeout_ms,
                )
                if result is not None:
                    tool_context_lines.append(render_policy_registry_context(result))
            elif tool_name == "exception_log_lookup":
                tool_input = _build_exception_log_input(state=state, raw_args=raw_args)
                result, execution = _invoke_tool_with_timeout(
                    tool=runtime.exception_log_tool,
                    tool_input=tool_input,
                    output_model=ExceptionLogLookupResult,
                    timeout_ms=runtime.tool_timeout_ms,
                )
                if result is not None:
                    tool_context_lines.append(render_exception_log_context(result))
            elif tool_name == "tavily_search" and runtime.tavily_search_tool is not None:
                tool_input = _build_tavily_search_input(state=state, raw_args=raw_args)
                result, execution = _invoke_tool_with_timeout(
                    tool=runtime.tavily_search_tool,
                    tool_input=tool_input,
                    output_model=TavilySearchResult,
                    timeout_ms=runtime.tool_timeout_ms,
                )
                if result is not None:
                    tool_context_lines.append(render_tavily_context(result))
            else:
                execution = ToolExecutionRecord(
                    tool_name=tool_name,
                    status="error",
                    latency_ms=0.0,
                    resolved=False,
                    summary=f"Unsupported tool requested: {tool_name}",
                    error_code="unsupported_tool",
                    requires_human_review=True,
                )

            state.tool_results.append(execution)
            if execution.error_code:
                error_codes.append(execution.error_code)
                _append_policy_flag(state, execution.error_code)
            if execution.requires_human_review:
                _append_policy_flag(state, f"{execution.tool_name}_review")

        state.tool_context = "\n\n".join(tool_context_lines).strip()
        state.decision_path.append("tools")

        status = "ok"
        if any(result.status != "ok" for result in state.tool_results):
            status = "degraded"
        elif any(not result.resolved for result in state.tool_results):
            status = "review_required"

        state.audit_events.append(
            emit_workflow_audit_event(
                trace_id=state.trace_id,
                stage="graph.tools",
                status=status,
                input_payload={
                    "planned_tools": state.tool_plan.planned_tools,
                    "timeout_ms": runtime.tool_timeout_ms,
                },
                output_payload={
                    "tool_results": [result.model_dump(mode="python") for result in state.tool_results],
                    "tool_context_available": bool(state.tool_context),
                },
                metadata={
                    "tool_count": len(state.tool_results),
                    "error_codes": ",".join(error_codes) if error_codes else None,
                },
            )
        )
        return state.as_graph_state()

    return _tools_node


def _build_retrieve_node(runtime: Week6WorkflowRuntime):
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


def _build_answer_node(runtime: Week6WorkflowRuntime):
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
                    "tool_context_available": bool(state.tool_context),
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

    state.decision_path.append("policy_check")
    state.audit_events.append(
        emit_workflow_audit_event(
            trace_id=state.trace_id,
            stage="graph.policy_check",
            status="ok",
            input_payload={
                "decision": state.final_decision.value,
                "abstention_reason": state.abstention_reason,
            },
            output_payload={
                "citation_count": len(state.citations),
                "policy_flags": state.policy_flags,
            },
        )
    )
    return state.as_graph_state()


def _escalation_node(raw_state: dict[str, Any]) -> dict[str, object]:
    state = apply_escalation_policy(ComplianceAgentState.from_graph_state(raw_state))
    state.decision_path.append("escalation")
    state.audit_events.append(
        emit_workflow_audit_event(
            trace_id=state.trace_id,
            stage="graph.escalation",
            status="review_required" if state.requires_human_review else "ok",
            input_payload={
                "tool_plan": state.tool_plan.model_dump(mode="python"),
                "tool_results": [result.model_dump(mode="python") for result in state.tool_results],
                "final_decision_before_finalize": state.final_decision.value,
            },
            output_payload={
                "requires_human_review": state.requires_human_review,
                "escalation_reason": state.escalation_reason,
                "final_decision": state.final_decision.value,
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
                "escalation_reason": state.escalation_reason,
            },
        )
    )
    return state.as_graph_state()


def build_week6_workflow(runtime: Week6WorkflowRuntime):
    """Compile the Week 6 LangGraph workflow."""

    if StateGraph is None or START is None or END is None:
        raise ModuleNotFoundError(
            "Missing dependency 'langgraph'. Install with: pip install langgraph"
        )

    graph = StateGraph(dict)
    graph.add_node("normalize", _normalize_node)
    graph.add_node("tool_plan", _build_tool_plan_node(runtime))
    graph.add_node("tools", _build_tools_node(runtime))
    graph.add_node("retrieve", _build_retrieve_node(runtime))
    graph.add_node("answer", _build_answer_node(runtime))
    graph.add_node("retry", _retry_node)
    graph.add_node("policy_check", _policy_check_node)
    graph.add_node("escalation", _escalation_node)
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "tool_plan")
    graph.add_edge("tool_plan", "tools")
    graph.add_edge("tools", "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_conditional_edges(
        "answer",
        _route_after_answer,
        {"retry": "retry", "policy_check": "policy_check"},
    )
    graph.add_edge("retry", "answer")
    graph.add_edge("policy_check", "escalation")
    graph.add_edge("escalation", "finalize")
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
    tool_planner_override: Runnable[Any, Any] | None,
    tool_timeout_ms: int,
    exception_log_path: Path | None,
    policy_registry_tool_override: BaseTool | None,
    exception_log_tool_override: BaseTool | None,
    tavily_search_tool_override: BaseTool | None,
) -> Week6WorkflowRuntime:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    if not 0.0 <= min_score_for_answer <= 1.0:
        raise ValueError("min_score_for_answer must be within [0, 1]")
    if not 0.0 <= min_confidence_for_answer <= 1.0:
        raise ValueError("min_confidence_for_answer must be within [0, 1]")
    if tool_timeout_ms < 1:
        raise ValueError("tool_timeout_ms must be >= 1")

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
    policy_registry_tool = policy_registry_tool_override or build_policy_registry_tool(index)
    exception_log_tool = exception_log_tool_override or build_exception_log_tool(
        load_exception_log_records(exception_log_path)
    )
    tavily_search_tool = tavily_search_tool_override
    if tavily_search_tool is None and has_tavily_api_key(source):
        tavily_search_tool = build_tavily_search_tool()
    if tool_planner_override is not None:
        tool_router = tool_planner_override
    elif llm is not None:
        try:
            available_tools = [policy_registry_tool, exception_log_tool]
            if tavily_search_tool is not None:
                available_tools.append(tavily_search_tool)
            tool_router = build_tool_router_chain(
                llm,
                tools=available_tools,
            )
        except Exception:
            tool_router = None
    else:
        tool_router = None

    return Week6WorkflowRuntime(
        index=index,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        answer_chain=answer_chain,
        tool_router=tool_router,
        policy_registry_tool=policy_registry_tool,
        exception_log_tool=exception_log_tool,
        tavily_search_tool=tavily_search_tool,
        top_k=top_k,
        min_score_for_answer=min_score_for_answer,
        min_confidence_for_answer=min_confidence_for_answer,
        llm_provider=resolved_llm_provider,
        llm_model=resolved_llm_model,
        tool_timeout_ms=tool_timeout_ms,
    )


def run_week6_query(
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
    tool_planner_override: Runnable[Any, Any] | None = None,
    tool_timeout_ms: int = 250,
    exception_log_path: Path | None = None,
    policy_registry_tool_override: BaseTool | None = None,
    exception_log_tool_override: BaseTool | None = None,
    tavily_search_tool_override: BaseTool | None = None,
) -> ComplianceAgentState:
    """Run the Week 6 graph workflow end to end."""

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
        tool_planner_override=tool_planner_override,
        tool_timeout_ms=tool_timeout_ms,
        exception_log_path=exception_log_path,
        policy_registry_tool_override=policy_registry_tool_override,
        exception_log_tool_override=exception_log_tool_override,
        tavily_search_tool_override=tavily_search_tool_override,
    )
    workflow = build_week6_workflow(runtime)
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


def run_week5_query(**kwargs: Any) -> ComplianceAgentState:
    """Backward-compatible alias for the Week 6 workflow entrypoint."""

    return run_week6_query(**kwargs)


build_week5_workflow = build_week6_workflow


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Week 6 LangGraph compliance workflow")
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
    parser.add_argument("--tool-timeout-ms", type=int, default=250)
    parser.add_argument(
        "--exception-log-path",
        type=Path,
        default=None,
        help="Optional path to sanitized exception log JSON",
    )
    return parser


def main() -> None:
    """CLI entrypoint for Week 6 workflow execution."""

    args = _build_parser().parse_args()
    state = run_week6_query(
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
        tool_timeout_ms=args.tool_timeout_ms,
        exception_log_path=args.exception_log_path,
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
