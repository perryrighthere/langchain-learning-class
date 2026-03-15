"""Week 6 exception-log lookup tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from compliance_bot.retrieval.indexer import tokenize
from compliance_bot.schemas.tools import (
    ExceptionLogLookupInput,
    ExceptionLogLookupResult,
    ExceptionLogRecord,
)

DEFAULT_EXCEPTION_LOG_RECORDS = [
    {
        "exception_id": "exc-vendor-001",
        "jurisdiction": "eu",
        "policy_scope": "vendor",
        "status": "open",
        "owner": "compliance-ops",
        "summary": "Vendor onboarding exception requires legal and privacy review before approval.",
    },
    {
        "exception_id": "exc-expense-002",
        "jurisdiction": "us",
        "policy_scope": "expense",
        "status": "closed",
        "owner": "finance-controls",
        "summary": "Travel receipt exception was resolved after director approval.",
    },
]


def load_exception_log_records(path: Path | None = None) -> list[ExceptionLogRecord]:
    """Load sanitized exception-log records from disk or built-in defaults."""

    if path is None:
        payload = DEFAULT_EXCEPTION_LOG_RECORDS
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return [ExceptionLogRecord.model_validate(item) for item in payload]


def lookup_exception_log(
    records: list[ExceptionLogRecord],
    tool_input: ExceptionLogLookupInput,
) -> ExceptionLogLookupResult:
    """Find open exception records relevant to the current compliance question."""

    question_terms = set(tokenize(tool_input.question))
    scope_terms = set(tool_input.policy_scope)
    matched: list[ExceptionLogRecord] = []

    for record in records:
        if tool_input.jurisdiction and record.jurisdiction not in {None, tool_input.jurisdiction}:
            continue
        if scope_terms and record.policy_scope not in scope_terms:
            continue

        record_terms = set(tokenize(record.summary))
        record_terms.add(record.policy_scope)
        if scope_terms or question_terms.intersection(record_terms):
            matched.append(record)

    open_records = [record for record in matched if record.status.lower() != "closed"]
    if open_records:
        summary = ", ".join(record.exception_id for record in open_records)
        return ExceptionLogLookupResult(
            resolved=False,
            matching_records=open_records,
            summary=f"Open exception log entries require review: {summary}",
            requires_human_review=True,
        )

    if matched:
        summary = ", ".join(record.exception_id for record in matched)
        return ExceptionLogLookupResult(
            resolved=True,
            matching_records=matched,
            summary=f"Only resolved exception records matched: {summary}",
            requires_human_review=False,
        )

    return ExceptionLogLookupResult(
        resolved=True,
        matching_records=[],
        summary="No matching exception-log records were found.",
        requires_human_review=False,
    )


def render_exception_log_context(result: ExceptionLogLookupResult) -> str:
    """Render a compact text summary for workflow state and audit logs."""

    if not result.matching_records:
        return result.summary

    lines = [result.summary]
    for record in result.matching_records:
        jurisdiction = record.jurisdiction or "any"
        lines.append(
            " | ".join(
                [
                    f"exception_id={record.exception_id}",
                    f"policy_scope={record.policy_scope}",
                    f"jurisdiction={jurisdiction}",
                    f"status={record.status}",
                    f"owner={record.owner}",
                ]
            )
        )
    return "\n".join(lines)


def build_exception_log_tool(records: list[ExceptionLogRecord]) -> BaseTool:
    """Create a LangChain tool wrapper for exception-log lookup."""

    def _tool_fn(
        question: str,
        jurisdiction: str | None = None,
        policy_scope: list[str] | None = None,
    ) -> dict[str, Any]:
        result = lookup_exception_log(
            records,
            ExceptionLogLookupInput(
                question=question,
                jurisdiction=jurisdiction,
                policy_scope=policy_scope or [],
            ),
        )
        return result.model_dump(mode="python")

    return StructuredTool.from_function(
        func=_tool_fn,
        name="exception_log_lookup",
        description=(
            "Check whether the question touches open compliance exceptions, waivers, or "
            "override requests that require human review."
        ),
        args_schema=ExceptionLogLookupInput,
    )
