"""Tests for SiliconFlow embedding provider adapter."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from compliance_bot.providers.siliconflow_embeddings import (
    DEFAULT_SILICONFLOW_EMBEDDING_MODEL,
    SiliconFlowEmbeddingConfig,
    build_siliconflow_embedding_provider,
    load_siliconflow_embedding_config,
)


def test_load_embedding_config_requires_api_key() -> None:
    with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
        load_siliconflow_embedding_config({})


def test_load_embedding_config_uses_defaults() -> None:
    config = load_siliconflow_embedding_config({"SILICONFLOW_API_KEY": "test"})

    assert config.api_key == "test"
    assert config.model == DEFAULT_SILICONFLOW_EMBEDDING_MODEL


def test_build_embedding_provider_passes_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyEmbeddings:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]

        def embed_query(self, text: str) -> list[float]:
            del text
            return [0.3, 0.4]

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: SimpleNamespace(OpenAIEmbeddings=DummyEmbeddings),
    )

    provider = build_siliconflow_embedding_provider(
        SiliconFlowEmbeddingConfig(
            api_key="key",
            model="BAAI/bge-m3",
            base_url="https://api.siliconflow.cn/v1",
            timeout=12.0,
            max_retries=5,
        )
    )

    assert provider.model == "BAAI/bge-m3"
    assert provider.embed_query("x") == [0.3, 0.4]
    assert provider.embed_documents(["a", "b"]) == [[0.1, 0.2], [0.1, 0.2]]
