"""Tests for SiliconFlow provider integration."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from compliance_bot.llms.siliconflow import (
    DEFAULT_SILICONFLOW_BASE_URL,
    DEFAULT_SILICONFLOW_MODEL,
    SiliconFlowConfig,
    build_siliconflow_llm,
    load_siliconflow_config,
)


def test_load_config_requires_api_key() -> None:
    with pytest.raises(ValueError, match="SILICONFLOW_API_KEY"):
        load_siliconflow_config({})


def test_load_config_uses_defaults() -> None:
    config = load_siliconflow_config({"SILICONFLOW_API_KEY": "test-key"})

    assert config.api_key == "test-key"
    assert config.model == DEFAULT_SILICONFLOW_MODEL
    assert config.base_url == DEFAULT_SILICONFLOW_BASE_URL


def test_load_config_respects_env_overrides() -> None:
    config = load_siliconflow_config(
        {
            "SILICONFLOW_API_KEY": "k",
            "SILICONFLOW_MODEL": "Qwen/Qwen3-14B",
            "SILICONFLOW_BASE_URL": "https://api.siliconflow.cn/v1",
        }
    )

    assert config.model == "Qwen/Qwen3-14B"
    assert config.base_url == "https://api.siliconflow.cn/v1"


def test_build_llm_gives_actionable_error_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_module(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", _missing_module)

    with pytest.raises(ModuleNotFoundError, match="langchain-openai"):
        build_siliconflow_llm(SiliconFlowConfig(api_key="key"))


def test_build_llm_passes_configuration_to_chat_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: SimpleNamespace(ChatOpenAI=DummyChatOpenAI),
    )

    config = SiliconFlowConfig(
        api_key="key",
        model="Qwen/Qwen3-14B",
        base_url="https://api.siliconflow.cn/v1",
        temperature=0.1,
        timeout=42.0,
        max_retries=4,
    )
    llm = build_siliconflow_llm(config)

    assert isinstance(llm, DummyChatOpenAI)
    assert llm.kwargs["model"] == "Qwen/Qwen3-14B"
    assert llm.kwargs["api_key"] == "key"
    assert llm.kwargs["base_url"] == "https://api.siliconflow.cn/v1"
    assert llm.kwargs["temperature"] == 0.1
    assert llm.kwargs["timeout"] == 42.0
    assert llm.kwargs["max_retries"] == 4

