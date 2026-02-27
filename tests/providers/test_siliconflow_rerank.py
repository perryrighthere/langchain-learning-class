"""Tests for SiliconFlow rerank provider adapter."""

from __future__ import annotations

import pytest

from compliance_bot.providers.siliconflow_rerank import (
    RerankProviderError,
    SiliconFlowRerankConfig,
    build_siliconflow_rerank_provider,
    load_siliconflow_rerank_config,
)


def test_load_rerank_config_requires_api_key() -> None:
    with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
        load_siliconflow_rerank_config({})


def test_rerank_provider_maps_response_payload() -> None:
    captured: dict[str, object] = {}

    def _request_fn(
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return {
            "results": [
                {"index": 1, "relevance_score": 0.91},
                {"index": 0, "relevance_score": 0.73},
            ]
        }

    provider = build_siliconflow_rerank_provider(
        SiliconFlowRerankConfig(
            api_key="key",
            model="BAAI/bge-reranker-v2-m3",
            base_url="https://api.siliconflow.cn/v1",
            path="/rerank",
            timeout=21.0,
        ),
        request_fn=_request_fn,
    )

    results, metrics = provider.rerank(
        query="vendor sharing",
        candidates=["a", "b"],
        top_n=2,
    )

    assert captured["url"] == "https://api.siliconflow.cn/v1/rerank"
    assert len(results) == 2
    assert results[0].candidate_index == 1
    assert metrics.status == "ok"
    assert metrics.provider == "siliconflow"


def test_rerank_provider_raises_actionable_error_on_timeout() -> None:
    def _timeout(*args: object, **kwargs: object) -> dict[str, object]:
        del args
        del kwargs
        raise TimeoutError("simulated")

    provider = build_siliconflow_rerank_provider(
        SiliconFlowRerankConfig(api_key="k"),
        request_fn=_timeout,
    )

    with pytest.raises(RerankProviderError, match="timeout"):
        provider.rerank(query="q", candidates=["a"], top_n=1)
