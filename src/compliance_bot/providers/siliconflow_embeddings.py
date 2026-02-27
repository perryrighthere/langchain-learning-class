"""SiliconFlow embedding provider adapter."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Mapping

from compliance_bot.llms.siliconflow import DEFAULT_SILICONFLOW_BASE_URL

DEFAULT_SILICONFLOW_EMBEDDING_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class SiliconFlowEmbeddingConfig:
    """Runtime config for SiliconFlow embedding API."""

    api_key: str
    model: str = DEFAULT_SILICONFLOW_EMBEDDING_MODEL
    base_url: str = DEFAULT_SILICONFLOW_BASE_URL
    timeout: float = 30.0
    max_retries: int = 2


def load_siliconflow_embedding_config(
    env: Mapping[str, str] | None = None,
) -> SiliconFlowEmbeddingConfig:
    """Load SiliconFlow embedding config from environment."""

    source = env if env is not None else os.environ
    api_key = source.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing SILICONFLOW_API_KEY.")

    model = source.get(
        "SILICONFLOW_EMBEDDING_MODEL", DEFAULT_SILICONFLOW_EMBEDDING_MODEL
    ).strip()
    base_url = source.get("SILICONFLOW_BASE_URL", DEFAULT_SILICONFLOW_BASE_URL).strip()
    timeout = float(source.get("SILICONFLOW_EMBEDDING_TIMEOUT", "30").strip())
    max_retries = int(source.get("SILICONFLOW_EMBEDDING_MAX_RETRIES", "2").strip())

    return SiliconFlowEmbeddingConfig(
        api_key=api_key,
        model=model or DEFAULT_SILICONFLOW_EMBEDDING_MODEL,
        base_url=base_url or DEFAULT_SILICONFLOW_BASE_URL,
        timeout=timeout,
        max_retries=max_retries,
    )


class SiliconFlowEmbeddingProvider:
    """Embedding provider wrapper backed by OpenAI-compatible SiliconFlow API."""

    provider_name = "siliconflow"

    def __init__(self, client: Any, *, model: str) -> None:
        self._client = client
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [list(vector) for vector in self._client.embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(self._client.embed_query(text))


def build_siliconflow_embedding_provider(
    config: SiliconFlowEmbeddingConfig | None = None,
) -> SiliconFlowEmbeddingProvider:
    """Create SiliconFlow embedding provider using langchain-openai client."""

    resolved = config or load_siliconflow_embedding_config()
    try:
        module = importlib.import_module("langchain_openai")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing dependency 'langchain-openai'. Install with: pip install langchain-openai"
        ) from exc

    embeddings_cls = getattr(module, "OpenAIEmbeddings", None)
    if embeddings_cls is None:
        raise ImportError("langchain_openai.OpenAIEmbeddings is unavailable.")

    client = embeddings_cls(
        model=resolved.model,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        timeout=resolved.timeout,
        max_retries=resolved.max_retries,
    )
    return SiliconFlowEmbeddingProvider(client, model=resolved.model)
