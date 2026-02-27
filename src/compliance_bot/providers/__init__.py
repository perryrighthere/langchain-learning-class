"""Provider adapters for hosted model services."""

from compliance_bot.providers.provider_registry import (
    resolve_embedding_provider,
    resolve_rerank_provider,
)
from compliance_bot.providers.siliconflow_embeddings import (
    DEFAULT_SILICONFLOW_EMBEDDING_MODEL,
    SiliconFlowEmbeddingConfig,
    SiliconFlowEmbeddingProvider,
    build_siliconflow_embedding_provider,
    load_siliconflow_embedding_config,
)
from compliance_bot.providers.siliconflow_rerank import (
    DEFAULT_SILICONFLOW_RERANK_MODEL,
    RerankProviderError,
    SiliconFlowRerankConfig,
    SiliconFlowRerankProvider,
    build_siliconflow_rerank_provider,
    load_siliconflow_rerank_config,
)

__all__ = [
    "resolve_embedding_provider",
    "resolve_rerank_provider",
    "DEFAULT_SILICONFLOW_EMBEDDING_MODEL",
    "SiliconFlowEmbeddingConfig",
    "SiliconFlowEmbeddingProvider",
    "load_siliconflow_embedding_config",
    "build_siliconflow_embedding_provider",
    "DEFAULT_SILICONFLOW_RERANK_MODEL",
    "RerankProviderError",
    "SiliconFlowRerankConfig",
    "SiliconFlowRerankProvider",
    "load_siliconflow_rerank_config",
    "build_siliconflow_rerank_provider",
]
