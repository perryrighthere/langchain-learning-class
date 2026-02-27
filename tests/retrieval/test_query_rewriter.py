"""Week 3 query rewriter tests."""

from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from compliance_bot.retrieval.query_rewriter import (
    build_query_rewriter_chain,
    fallback_query_rewrite,
    invoke_query_rewriter,
)


def _stub_model(_: object) -> str:
    return (
        '{"normalized_query":"vendor data sharing requirements",'
        '"expanded_queries":["third party data sharing policy",'
        '"vendor risk review policy"]}'
    )


def test_query_rewriter_structured_output_is_parseable() -> None:
    chain = build_query_rewriter_chain(RunnableLambda(_stub_model))
    result = invoke_query_rewriter(
        chain,
        question="Can I share customer data with a vendor?",
    )

    assert result.normalized_query == "vendor data sharing requirements"
    assert len(result.expanded_queries) == 2


def test_fallback_query_rewriter_normalizes_and_expands() -> None:
    result = fallback_query_rewrite(" Vendor retention for third party logs ")

    assert result.normalized_query == "vendor retention for third party logs"
    assert "record retention policy requirements" in result.expanded_queries
