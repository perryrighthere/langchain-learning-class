"""Tests for the Week 1 baseline chain."""

from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from compliance_bot.chains.baseline_chain import (
    NO_CONTEXT_SENTINEL,
    build_baseline_chain,
    invoke_baseline_chain,
)
from compliance_bot.schemas.query import DecisionEnum


def _stub_model(prompt_value: object) -> str:
    if hasattr(prompt_value, "to_messages"):
        text = "\n".join(
            str(message.content) for message in prompt_value.to_messages()  # type: ignore[attr-defined]
        )
    else:
        text = str(prompt_value)

    if f"Context: {NO_CONTEXT_SENTINEL}" in text:
        return (
            '{"answer":"Insufficient evidence in provided context.",'
            '"confidence":0.0,"decision":"ABSTAINED"}'
        )

    return '{"answer":"Policy allows manager approval for this case.","confidence":0.83,"decision":"ANSWERED"}'


def test_structured_response_is_parseable() -> None:
    chain = build_baseline_chain(RunnableLambda(_stub_model))
    result = invoke_baseline_chain(
        chain,
        question="Can a manager approve this reimbursement?",
        context="Expense policy v1 section 4 allows manager approval.",
    )

    assert result.answer.startswith("Policy allows")
    assert result.confidence == 0.83
    assert result.decision == DecisionEnum.ANSWERED


def test_unknown_context_triggers_abstained() -> None:
    chain = build_baseline_chain(RunnableLambda(_stub_model))
    result = invoke_baseline_chain(
        chain,
        question="Can I share customer data with a vendor?",
        context=None,
    )

    assert result.decision == DecisionEnum.ABSTAINED
    assert result.confidence == 0.0
