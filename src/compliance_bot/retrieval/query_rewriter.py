"""Week 3 query rewriting with structured LangChain output."""

from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from compliance_bot.schemas.retrieval import QueryRewriteOutput


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


def build_query_rewriter_chain(
    llm: Runnable[Any, Any],
) -> Runnable[Any, QueryRewriteOutput]:
    """Create an LCEL chain that rewrites retrieval queries into structured output."""

    parser = PydanticOutputParser(pydantic_object=QueryRewriteOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You normalize compliance retrieval queries. Return compact JSON only. "
                    "Keep intent unchanged. Provide up to 2 expanded paraphrases.\n"
                    "{format_instructions}"
                ),
            ),
            ("human", "Question: {question}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    return prompt | llm | RunnableLambda(_to_text) | parser


def fallback_query_rewrite(question: str) -> QueryRewriteOutput:
    """Deterministic non-LLM query rewrite used in tests and offline mode."""

    normalized = " ".join(question.lower().split())
    if not normalized:
        raise ValueError("question must not be blank")

    expansions: list[str] = []
    if "retention" in normalized:
        expansions.append("record retention policy requirements")
    if "vendor" in normalized or "third party" in normalized:
        expansions.append("third party data sharing policy")

    return QueryRewriteOutput(normalized_query=normalized, expanded_queries=expansions)


def invoke_query_rewriter(
    chain: Runnable[Any, QueryRewriteOutput], *, question: str
) -> QueryRewriteOutput:
    """Invoke a query rewriter chain with validated input."""

    normalized = " ".join(question.split())
    if not normalized:
        raise ValueError("question must not be blank")
    return chain.invoke({"question": normalized})


def rewrite_query(
    question: str,
    *,
    chain: Runnable[Any, QueryRewriteOutput] | None = None,
) -> QueryRewriteOutput:
    """Rewrite a query using LCEL chain when available, otherwise deterministic fallback."""

    if chain is None:
        return fallback_query_rewrite(question)
    return invoke_query_rewriter(chain, question=question)
