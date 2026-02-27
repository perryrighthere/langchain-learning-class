"""Tests for provider registry resolution."""

from __future__ import annotations

import compliance_bot.providers.provider_registry as registry


def test_auto_resolution_returns_none_without_api_key(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    assert registry.resolve_embedding_provider("auto", env={}) is None
    assert registry.resolve_rerank_provider("auto", env={}) is None


def test_none_mode_disables_providers() -> None:
    assert registry.resolve_embedding_provider("none", env={"SILICONFLOW_API_KEY": "k"}) is None
    assert registry.resolve_rerank_provider("none", env={"SILICONFLOW_API_KEY": "k"}) is None


def test_auto_mode_with_key_builds_providers(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        registry,
        "load_siliconflow_embedding_config",
        lambda env: object(),
    )
    monkeypatch.setattr(
        registry,
        "load_siliconflow_rerank_config",
        lambda env: object(),
    )
    monkeypatch.setattr(
        registry,
        "build_siliconflow_embedding_provider",
        lambda config: calls.append("embed") or "embed-provider",
    )
    monkeypatch.setattr(
        registry,
        "build_siliconflow_rerank_provider",
        lambda config: calls.append("rerank") or "rerank-provider",
    )

    embed = registry.resolve_embedding_provider("auto", env={"SILICONFLOW_API_KEY": "k"})
    rerank = registry.resolve_rerank_provider("auto", env={"SILICONFLOW_API_KEY": "k"})

    assert embed == "embed-provider"
    assert rerank == "rerank-provider"
    assert calls == ["embed", "rerank"]
