"""Week 3 retrieval foundation modules."""

from compliance_bot.retrieval.indexer import RetrievalIndex, build_retrieval_index, load_manifest
from compliance_bot.retrieval.query_rewriter import (
    build_query_rewriter_chain,
    fallback_query_rewrite,
    invoke_query_rewriter,
    rewrite_query,
)
from compliance_bot.retrieval.retriever import (
    MetadataKeywordRetriever,
    RETRIEVER_CONFIG_REGISTRY,
    get_retriever_config,
    run_retrieval,
)

__all__ = [
    "RetrievalIndex",
    "load_manifest",
    "build_retrieval_index",
    "build_query_rewriter_chain",
    "fallback_query_rewrite",
    "invoke_query_rewriter",
    "rewrite_query",
    "MetadataKeywordRetriever",
    "RETRIEVER_CONFIG_REGISTRY",
    "get_retriever_config",
    "run_retrieval",
]
