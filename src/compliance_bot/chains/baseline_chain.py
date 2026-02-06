"""Week 1 baseline LCEL chain with structured output."""

from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from compliance_bot.schemas.query import BaselineChainInput, BaselineChainOutput

NO_CONTEXT_SENTINEL = "NO_CONTEXT_AVAILABLE"


def normalize_context(context: str | None) -> str:
    """Normalize optional context into a deterministic sentinel value."""

    value = (context or "").strip()
    return value if value else NO_CONTEXT_SENTINEL


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


def build_baseline_chain(llm: Runnable[Any, Any]) -> Runnable[Any, BaselineChainOutput]:
    """Create the Week 1 LCEL chain."""

    parser = PydanticOutputParser(pydantic_object=BaselineChainOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a compliance assistant. Use only provided context. "
                    f"If context is '{NO_CONTEXT_SENTINEL}' or lacks evidence, abstain. "
                    "Always return JSON matching this schema.\n{format_instructions}"
                ),
            ),
            (
                "human",
                "Question: {question}\nContext: {context}",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    return prompt | llm | RunnableLambda(_to_text) | parser


def invoke_baseline_chain(
    chain: Runnable[Any, BaselineChainOutput],
    *,
    question: str,
    context: str | None = None,
) -> BaselineChainOutput:
    """Invoke the baseline chain with validated input."""

    payload = BaselineChainInput(question=question, context=normalize_context(context))
    return chain.invoke(payload.model_dump())

