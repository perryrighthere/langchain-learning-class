"""Week 6 policy registry lookup tool."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from compliance_bot.retrieval.indexer import RetrievalIndex, tokenize
from compliance_bot.schemas.tools import (
    PolicyRegistryLookupInput,
    PolicyRegistryLookupResult,
    PolicyRegistryMatch,
)


def _metadata_terms(metadata: dict[str, str]) -> set[str]:
    terms: set[str] = set()
    for value in metadata.values():
        terms.update(tokenize(value))
    return terms


def lookup_policy_registry(
    index: RetrievalIndex,
    tool_input: PolicyRegistryLookupInput,
) -> PolicyRegistryLookupResult:
    """Summarize active policies that best match the question and filters."""

    grouped: dict[str, dict[str, Any]] = {}
    question_terms = set(tokenize(tool_input.question))
    scope_terms = set(tool_input.policy_scope)

    for chunk in index.chunks:
        chunk_jurisdiction = chunk.metadata.get("jurisdiction", "").strip().lower()
        if tool_input.jurisdiction and chunk_jurisdiction != tool_input.jurisdiction:
            continue

        chunk_scope_terms = {
            term.strip().lower()
            for term in chunk.metadata.get("policy_scope", "").split(",")
            if term.strip()
        }
        if scope_terms and not scope_terms.intersection(chunk_scope_terms):
            continue

        entry = grouped.setdefault(
            chunk.doc_id,
            {
                "version_tag": chunk.version_tag,
                "jurisdictions": set(),
                "policy_scopes": set(),
                "sections": set(),
                "score_terms": set(),
            },
        )
        entry["jurisdictions"].add(chunk_jurisdiction or "unknown")
        entry["policy_scopes"].update(chunk_scope_terms)
        entry["sections"].add(chunk.metadata.get("section", str(chunk.chunk_index)))
        entry["score_terms"].update(chunk.tokens)
        entry["score_terms"].update(_metadata_terms(chunk.metadata))

    matches: list[PolicyRegistryMatch] = []
    for doc_id, entry in grouped.items():
        score_terms = entry["score_terms"]
        overlap = question_terms.intersection(score_terms)
        score = len(overlap) / max(len(question_terms), 1)
        if scope_terms:
            score = min(1.0, score + 0.2)
        matches.append(
            PolicyRegistryMatch(
                doc_id=doc_id,
                version_tag=entry["version_tag"],
                jurisdictions=sorted(entry["jurisdictions"]),
                policy_scopes=sorted(entry["policy_scopes"]),
                sections=sorted(entry["sections"]),
                match_score=round(score, 4),
            )
        )

    ordered_matches = sorted(
        matches,
        key=lambda item: (-item.match_score, item.doc_id),
    )[: tool_input.max_results]
    if not ordered_matches:
        return PolicyRegistryLookupResult(
            resolved=False,
            matches=[],
            summary="No active policy registry entries matched the requested scope.",
        )

    match_labels = ", ".join(
        f"{match.doc_id}@{match.version_tag}" for match in ordered_matches
    )
    return PolicyRegistryLookupResult(
        resolved=True,
        matches=ordered_matches,
        summary=f"Resolved policy registry matches: {match_labels}",
    )


def render_policy_registry_context(result: PolicyRegistryLookupResult) -> str:
    """Render a compact text summary for audit logs and human review packets."""

    if not result.matches:
        return result.summary

    lines = [result.summary]
    for match in result.matches:
        lines.append(
            " | ".join(
                [
                    f"doc_id={match.doc_id}",
                    f"version={match.version_tag}",
                    f"jurisdictions={','.join(match.jurisdictions)}",
                    f"policy_scopes={','.join(match.policy_scopes)}",
                    f"sections={','.join(match.sections)}",
                    f"match_score={match.match_score:.2f}",
                ]
            )
        )
    return "\n".join(lines)


def build_policy_registry_tool(index: RetrievalIndex) -> BaseTool:
    """Create a LangChain tool wrapper for the local policy registry."""

    def _tool_fn(
        question: str,
        jurisdiction: str | None = None,
        policy_scope: list[str] | None = None,
        max_results: int = 3,
    ) -> dict[str, Any]:
        result = lookup_policy_registry(
            index,
            PolicyRegistryLookupInput(
                question=question,
                jurisdiction=jurisdiction,
                policy_scope=policy_scope or [],
                max_results=max_results,
            ),
        )
        return result.model_dump(mode="python")

    return StructuredTool.from_function(
        func=_tool_fn,
        name="policy_registry_lookup",
        description=(
            "Look up active policy documents, versions, scopes, and sections before answering "
            "a compliance question."
        ),
        args_schema=PolicyRegistryLookupInput,
    )
