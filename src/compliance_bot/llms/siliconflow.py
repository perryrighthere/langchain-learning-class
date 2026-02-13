"""SiliconFlow LLM adapter for the compliance bot."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Mapping

DEFAULT_SILICONFLOW_MODEL = "Pro/zai-org/GLM-4.7"
DEFAULT_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"


@dataclass(frozen=True)
class SiliconFlowConfig:
    """Runtime configuration for SiliconFlow-backed chat models."""

    api_key: str
    model: str = DEFAULT_SILICONFLOW_MODEL
    base_url: str = DEFAULT_SILICONFLOW_BASE_URL
    temperature: float = 0.0
    timeout: float = 30.0
    max_retries: int = 2


def load_siliconflow_config(env: Mapping[str, str] | None = None) -> SiliconFlowConfig:
    """Load SiliconFlow settings from environment variables."""

    source = env if env is not None else os.environ
    api_key = source.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing SILICONFLOW_API_KEY.")

    model = source.get("SILICONFLOW_MODEL", DEFAULT_SILICONFLOW_MODEL).strip()
    base_url = source.get("SILICONFLOW_BASE_URL", DEFAULT_SILICONFLOW_BASE_URL).strip()

    return SiliconFlowConfig(
        api_key=api_key,
        model=model or DEFAULT_SILICONFLOW_MODEL,
        base_url=base_url or DEFAULT_SILICONFLOW_BASE_URL,
    )


def build_siliconflow_llm(config: SiliconFlowConfig | None = None) -> Any:
    """Build a SiliconFlow-compatible ChatOpenAI client."""

    resolved_config = config or load_siliconflow_config()
    try:
        module = importlib.import_module("langchain_openai")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing dependency 'langchain-openai'. Install with: pip install langchain-openai"
        ) from exc

    chat_openai_cls = getattr(module, "ChatOpenAI", None)
    if chat_openai_cls is None:
        raise ImportError("langchain_openai.ChatOpenAI is unavailable.")

    return chat_openai_cls(
        model=resolved_config.model,
        api_key=resolved_config.api_key,
        base_url=resolved_config.base_url,
        temperature=resolved_config.temperature,
        timeout=resolved_config.timeout,
        max_retries=resolved_config.max_retries,
    )
