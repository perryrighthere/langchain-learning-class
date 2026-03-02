"""Week 4 citation-first grounded answering chain and CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from compliance_bot.chains.abstention_policy import (
    controlled_abstention,
    controlled_escalation,
    enforce_grounding_policy,
)
from compliance_bot.llms.siliconflow import (
    DEFAULT_SILICONFLOW_MODEL,
    build_siliconflow_llm,
    load_siliconflow_config,
)
from compliance_bot.providers.provider_registry import (
    resolve_embedding_provider,
    resolve_rerank_provider,
)
from compliance_bot.retrieval.indexer import build_retrieval_index, load_manifest
from compliance_bot.retrieval.retriever import run_retrieval
from compliance_bot.schemas.answer import GroundedAnswerDraft, GroundedAnswerResponse
from compliance_bot.schemas.audit import build_audit_event
from compliance_bot.schemas.query import DecisionEnum
from compliance_bot.schemas.retrieval import Citation, RetrievedChunk, RetrievalFilters, RetrievalResponse


def _to_text(model_output: Any) -> str:
    """Convert chat model output to plain text for JSON parsing."""

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


def _format_evidence_chunks(retrieved_chunks: list[RetrievedChunk]) -> str:
    lines: list[str] = []
    for chunk in retrieved_chunks:
        section = chunk.metadata.get("section") or str(chunk.chunk_index)
        lines.append(
            "\n".join(
                [
                    f"- chunk_id: {chunk.chunk_id}",
                    f"  doc_id: {chunk.doc_id}",
                    f"  version: {chunk.version_tag}",
                    f"  section: {section}",
                    f"  retrieval_score: {chunk.retrieval_score:.4f}",
                    f"  content: {chunk.content}",
                ]
            )
        )
    return "\n\n".join(lines)


def _citation_matches_chunk(citation: Citation, chunk: RetrievedChunk) -> bool:
    if citation.doc_id != chunk.doc_id:
        return False
    if citation.version != chunk.version_tag:
        return False
    quote_span = citation.quote_span.strip().lower()
    content = chunk.content.strip().lower()
    if quote_span and quote_span not in content:
        return False
    return True


def citations_are_grounded(
    citations: list[Citation],
    *,
    retrieved_chunks: list[RetrievedChunk],
) -> bool:
    """Validate citation links against retrieved chunk IDs and versions."""

    if not citations:
        return False

    chunk_lookup = {chunk.chunk_id: chunk for chunk in retrieved_chunks}
    for citation in citations:
        chunk = chunk_lookup.get(citation.chunk_id)
        if chunk is None:
            return False
        if not _citation_matches_chunk(citation, chunk):
            return False
    return True


def build_citation_answer_chain(
    llm: Runnable[Any, Any],
) -> Runnable[Any, GroundedAnswerDraft]:
    """Create Week 4 grounded answer LCEL chain with citation schema output."""

    parser = PydanticOutputParser(pydantic_object=GroundedAnswerDraft)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a compliance assistant. Use only provided evidence chunks. "
                    "If evidence is insufficient, abstain. Never invent citations. "
                    "For ANSWERED, include at least one citation and each citation quote_span "
                    "must be an exact substring from evidence content. "
                    "Return JSON only.\n{format_instructions}"
                ),
            ),
            (
                "human",
                (
                    "Question: {question}\n\n"
                    "Evidence chunks:\n{evidence_chunks}\n\n"
                    "Allowed chunk_ids: {allowed_chunk_ids}"
                ),
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())
    return prompt | llm | RunnableLambda(_to_text) | parser


def invoke_citation_answer_chain(
    chain: Runnable[Any, GroundedAnswerDraft],
    *,
    question: str,
    retrieved_chunks: list[RetrievedChunk],
) -> GroundedAnswerDraft:
    """Invoke citation answer chain with validated inputs."""

    normalized_question = " ".join(question.split())
    if not normalized_question:
        raise ValueError("question must not be blank")
    if not retrieved_chunks:
        raise ValueError("retrieved_chunks must not be empty")

    payload = {
        "question": normalized_question,
        "evidence_chunks": _format_evidence_chunks(retrieved_chunks),
        "allowed_chunk_ids": ", ".join(chunk.chunk_id for chunk in retrieved_chunks),
    }
    return chain.invoke(payload)


def fallback_grounded_answer(
    *,
    question: str,
    retrieved_chunks: list[RetrievedChunk],
) -> GroundedAnswerDraft:
    """Deterministic answer fallback for offline or no-provider mode."""

    del question
    if not retrieved_chunks:
        draft, _ = controlled_abstention("retrieval_insufficient_evidence")
        return draft

    top_chunk = retrieved_chunks[0]
    section = top_chunk.metadata.get("section") or f"chunk-{top_chunk.chunk_index}"
    quote_span = top_chunk.content[:160]
    citation = Citation(
        doc_id=top_chunk.doc_id,
        section=section,
        chunk_id=top_chunk.chunk_id,
        quote_span=quote_span,
        retrieval_score=top_chunk.retrieval_score,
        version=top_chunk.version_tag,
    )
    return GroundedAnswerDraft(
        answer=f"Grounded evidence indicates: {quote_span}",
        confidence=max(0.5, min(0.95, top_chunk.retrieval_score)),
        decision=DecisionEnum.ANSWERED,
        citations=[citation],
    )


def _has_siliconflow_key(env: Mapping[str, str]) -> bool:
    return bool(env.get("SILICONFLOW_API_KEY", "").strip())


def resolve_answer_llm(
    mode: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
) -> Runnable[Any, Any] | None:
    """Resolve Week 4 answer LLM mode (SiliconFlow-first)."""

    source = env if env is not None else os.environ
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"auto", "none", "siliconflow"}:
        raise ValueError("llm provider mode must be one of: auto, none, siliconflow")

    if normalized_mode == "none":
        return None
    if normalized_mode == "siliconflow":
        return build_siliconflow_llm(load_siliconflow_config(source))
    if _has_siliconflow_key(source):
        return build_siliconflow_llm(load_siliconflow_config(source))
    return None


def run_citation_answer(
    retrieval_response: RetrievalResponse,
    *,
    answer_chain: Runnable[Any, GroundedAnswerDraft] | None = None,
    min_confidence_for_answer: float = 0.55,
    llm_provider: str = "none",
    llm_model: str = "fallback",
) -> GroundedAnswerResponse:
    """Run Week 4 grounded answering with citation validation and abstention controls."""

    if not 0.0 <= min_confidence_for_answer <= 1.0:
        raise ValueError("min_confidence_for_answer must be within [0, 1]")

    trace_id = retrieval_response.trace_id
    audit_events = list(retrieval_response.audit_events)
    question = retrieval_response.question
    normalized_query = retrieval_response.normalized_query
    status = "ok"
    error_code: str | None = None
    elapsed_ms = 0.0

    if (
        retrieval_response.decision != DecisionEnum.ANSWERED
        or not retrieval_response.retrieved_chunks
    ):
        draft, abstention_reason = controlled_abstention("retrieval_insufficient_evidence")
        audit_events.append(
            build_audit_event(
                trace_id=trace_id,
                stage="answer_grounding",
                actor="chains.citation_chain",
                status="abstained",
                input_payload=json.dumps(
                    {
                        "question": question,
                        "retrieved_chunk_ids": [
                            chunk.chunk_id for chunk in retrieval_response.retrieved_chunks
                        ],
                    },
                    sort_keys=True,
                ),
                output_payload=json.dumps(
                    {
                        "decision": draft.decision.value,
                        "reason": abstention_reason,
                    },
                    sort_keys=True,
                ),
                metadata={
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "latency_ms": 0.0,
                    "status": "abstained",
                    "min_confidence_for_answer": min_confidence_for_answer,
                },
            )
        )
        return GroundedAnswerResponse(
            trace_id=trace_id,
            question=question,
            normalized_query=normalized_query,
            answer=draft.answer,
            confidence=draft.confidence,
            decision=draft.decision,
            citations=[],
            retrieved_chunks=retrieval_response.retrieved_chunks,
            audit_events=audit_events,
            abstention_reason=abstention_reason,
        )

    try:
        start = perf_counter()
        if answer_chain is None:
            draft = fallback_grounded_answer(
                question=question,
                retrieved_chunks=retrieval_response.retrieved_chunks,
            )
            status = "fallback"
        else:
            draft = invoke_citation_answer_chain(
                answer_chain,
                question=question,
                retrieved_chunks=retrieval_response.retrieved_chunks,
            )
        elapsed_ms = (perf_counter() - start) * 1000.0
    except TimeoutError:
        draft, abstention_reason = controlled_escalation("llm_timeout")
        status = "error"
        error_code = "llm_timeout"
        audit_events.append(
            build_audit_event(
                trace_id=trace_id,
                stage="answer_grounding",
                actor="chains.citation_chain",
                status=status,
                input_payload=question,
                output_payload=draft.answer,
                metadata={
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "latency_ms": elapsed_ms,
                    "status": status,
                    "error_code": error_code,
                },
            )
        )
        return GroundedAnswerResponse(
            trace_id=trace_id,
            question=question,
            normalized_query=normalized_query,
            answer=draft.answer,
            confidence=draft.confidence,
            decision=draft.decision,
            citations=[],
            retrieved_chunks=retrieval_response.retrieved_chunks,
            audit_events=audit_events,
            abstention_reason=abstention_reason,
        )
    except Exception:
        draft, abstention_reason = controlled_escalation("llm_failed")
        status = "error"
        error_code = "llm_failed"
        audit_events.append(
            build_audit_event(
                trace_id=trace_id,
                stage="answer_grounding",
                actor="chains.citation_chain",
                status=status,
                input_payload=question,
                output_payload=draft.answer,
                metadata={
                    "llm_provider": llm_provider,
                    "llm_model": llm_model,
                    "latency_ms": elapsed_ms,
                    "status": status,
                    "error_code": error_code,
                },
            )
        )
        return GroundedAnswerResponse(
            trace_id=trace_id,
            question=question,
            normalized_query=normalized_query,
            answer=draft.answer,
            confidence=draft.confidence,
            decision=draft.decision,
            citations=[],
            retrieved_chunks=retrieval_response.retrieved_chunks,
            audit_events=audit_events,
            abstention_reason=abstention_reason,
        )

    citations_valid = citations_are_grounded(
        draft.citations,
        retrieved_chunks=retrieval_response.retrieved_chunks,
    )
    enforced_draft, abstention_reason = enforce_grounding_policy(
        draft,
        citations_valid=citations_valid,
        min_confidence_for_answer=min_confidence_for_answer,
    )

    audit_events.append(
        build_audit_event(
            trace_id=trace_id,
            stage="answer_grounding",
            actor="chains.citation_chain",
            status=status,
            input_payload=json.dumps(
                {
                    "question": question,
                    "retrieved_chunk_ids": [
                        chunk.chunk_id for chunk in retrieval_response.retrieved_chunks
                    ],
                },
                sort_keys=True,
            ),
            output_payload=json.dumps(
                {
                    "decision": enforced_draft.decision.value,
                    "citation_chunk_ids": [
                        citation.chunk_id for citation in enforced_draft.citations
                    ],
                    "abstention_reason": abstention_reason,
                },
                sort_keys=True,
            ),
            metadata={
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "latency_ms": elapsed_ms,
                "status": status,
                "error_code": error_code,
                "min_confidence_for_answer": min_confidence_for_answer,
                "citations_valid": citations_valid,
            },
        )
    )

    return GroundedAnswerResponse(
        trace_id=trace_id,
        question=question,
        normalized_query=normalized_query,
        answer=enforced_draft.answer,
        confidence=enforced_draft.confidence,
        decision=enforced_draft.decision,
        citations=enforced_draft.citations,
        retrieved_chunks=retrieval_response.retrieved_chunks,
        audit_events=audit_events,
        abstention_reason=abstention_reason,
    )


def run_week4_query(
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
    env: Mapping[str, str] | None = None,
) -> GroundedAnswerResponse:
    """Run retrieval + citation-first answer as a single Week 4 flow."""

    source = env if env is not None else os.environ
    embedding_provider = resolve_embedding_provider(embedding_provider_mode, env=source)
    rerank_provider = resolve_rerank_provider(rerank_provider_mode, env=source)
    llm = resolve_answer_llm(llm_provider_mode, env=source)
    answer_chain = build_citation_answer_chain(llm) if llm is not None else None
    llm_model = source.get("SILICONFLOW_MODEL", DEFAULT_SILICONFLOW_MODEL).strip()

    manifest = load_manifest(manifest_path)
    index = build_retrieval_index(manifest, embedding_provider=embedding_provider)
    retrieval_response = run_retrieval(
        index,
        question=question,
        filters=RetrievalFilters(
            jurisdiction=jurisdiction,
            policy_scope=policy_scope or [],
        ),
        embedding_provider=embedding_provider,  # type: ignore[arg-type]
        rerank_provider=rerank_provider,  # type: ignore[arg-type]
        top_k=top_k,
        min_score_for_answer=min_score_for_answer,
    )

    return run_citation_answer(
        retrieval_response,
        answer_chain=answer_chain,
        min_confidence_for_answer=min_confidence_for_answer,
        llm_provider="siliconflow" if llm is not None else "none",
        llm_model=llm_model if llm is not None else "fallback",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Week 4 grounded compliance answering")
    parser.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Path to Week 2 corpus manifest JSON",
    )
    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="Compliance question to answer",
    )
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
        help="Answer generation provider mode",
    )
    return parser


def main() -> None:
    """CLI entrypoint for Week 4 grounded answer flow."""

    args = _build_parser().parse_args()
    response = run_week4_query(
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
    print(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
