"""Provider registry and default resolution for Week 3 retrieval."""

from __future__ import annotations

import os
from typing import Mapping

from compliance_bot.providers.siliconflow_embeddings import (
    SiliconFlowEmbeddingProvider,
    build_siliconflow_embedding_provider,
    load_siliconflow_embedding_config,
)
from compliance_bot.providers.siliconflow_rerank import (
    SiliconFlowRerankProvider,
    build_siliconflow_rerank_provider,
    load_siliconflow_rerank_config,
)


def _has_siliconflow_key(env: Mapping[str, str]) -> bool:
    return bool(env.get("SILICONFLOW_API_KEY", "").strip())


def resolve_embedding_provider(
    mode: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
) -> SiliconFlowEmbeddingProvider | None:
    """Resolve embedding provider from mode and environment."""

    source = env if env is not None else os.environ
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"auto", "none", "siliconflow"}:
        raise ValueError("embedding provider mode must be one of: auto, none, siliconflow")

    if normalized_mode == "none":
        return None
    if normalized_mode == "siliconflow":
        return build_siliconflow_embedding_provider(
            load_siliconflow_embedding_config(source)
        )

    if _has_siliconflow_key(source):
        return build_siliconflow_embedding_provider(
            load_siliconflow_embedding_config(source)
        )
    return None


def resolve_rerank_provider(
    mode: str = "auto",
    *,
    env: Mapping[str, str] | None = None,
) -> SiliconFlowRerankProvider | None:
    """Resolve rerank provider from mode and environment."""

    source = env if env is not None else os.environ
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"auto", "none", "siliconflow"}:
        raise ValueError("rerank provider mode must be one of: auto, none, siliconflow")

    if normalized_mode == "none":
        return None
    if normalized_mode == "siliconflow":
        return build_siliconflow_rerank_provider(load_siliconflow_rerank_config(source))

    if _has_siliconflow_key(source):
        return build_siliconflow_rerank_provider(load_siliconflow_rerank_config(source))
    return None
