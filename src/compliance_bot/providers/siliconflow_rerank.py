"""SiliconFlow rerank provider adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping
from urllib import request

from compliance_bot.llms.siliconflow import DEFAULT_SILICONFLOW_BASE_URL
from compliance_bot.schemas.retrieval import ProviderCallMetrics, RerankResult

DEFAULT_SILICONFLOW_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


@dataclass(frozen=True)
class SiliconFlowRerankConfig:
    """Runtime config for SiliconFlow rerank API."""

    api_key: str
    model: str = DEFAULT_SILICONFLOW_RERANK_MODEL
    base_url: str = DEFAULT_SILICONFLOW_BASE_URL
    path: str = "/rerank"
    timeout: float = 30.0


class RerankProviderError(RuntimeError):
    """Raised when provider rerank call fails."""


RerankRequestFn = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


def load_siliconflow_rerank_config(
    env: Mapping[str, str] | None = None,
) -> SiliconFlowRerankConfig:
    """Load SiliconFlow rerank config from environment."""

    source = env if env is not None else os.environ
    api_key = source.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing SILICONFLOW_API_KEY.")

    model = source.get("SILICONFLOW_RERANK_MODEL", DEFAULT_SILICONFLOW_RERANK_MODEL).strip()
    base_url = source.get("SILICONFLOW_BASE_URL", DEFAULT_SILICONFLOW_BASE_URL).strip()
    path = source.get("SILICONFLOW_RERANK_PATH", "/rerank").strip() or "/rerank"
    timeout = float(source.get("SILICONFLOW_RERANK_TIMEOUT", "30").strip())

    return SiliconFlowRerankConfig(
        api_key=api_key,
        model=model or DEFAULT_SILICONFLOW_RERANK_MODEL,
        base_url=base_url or DEFAULT_SILICONFLOW_BASE_URL,
        path=path,
        timeout=timeout,
    )


def _default_rerank_request(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


class SiliconFlowRerankProvider:
    """Rerank provider wrapper for SiliconFlow HTTP API."""

    provider_name = "siliconflow"

    def __init__(
        self,
        config: SiliconFlowRerankConfig,
        *,
        request_fn: RerankRequestFn | None = None,
    ) -> None:
        self._config = config
        self._request_fn = request_fn or _default_rerank_request

    @property
    def model(self) -> str:
        return self._config.model

    def rerank(
        self,
        *,
        query: str,
        candidates: list[str],
        top_n: int,
    ) -> tuple[list[RerankResult], ProviderCallMetrics]:
        if top_n <= 0:
            raise ValueError("top_n must be > 0")
        if not candidates:
            return [], ProviderCallMetrics(
                provider=self.provider_name,
                model=self._config.model,
                latency_ms=0.0,
                status="ok",
                error_code=None,
            )

        payload = {
            "model": self._config.model,
            "query": query,
            "documents": candidates,
            "top_n": min(top_n, len(candidates)),
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._config.base_url.rstrip('/')}{self._config.path}"

        start = perf_counter()
        try:
            response_payload = self._request_fn(url, payload, headers, self._config.timeout)
        except TimeoutError as exc:
            latency = (perf_counter() - start) * 1000.0
            raise RerankProviderError(
                f"siliconflow rerank timeout after {latency:.2f}ms"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive path
            latency = (perf_counter() - start) * 1000.0
            raise RerankProviderError(
                f"siliconflow rerank request failed after {latency:.2f}ms: {exc}"
            ) from exc

        latency = (perf_counter() - start) * 1000.0
        items = response_payload.get("results", [])
        if not isinstance(items, list):
            raise RerankProviderError("siliconflow rerank response missing 'results' list")

        results: list[RerankResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            score = item.get("relevance_score")
            if not isinstance(index, int):
                continue
            try:
                score_value = float(score)
            except (TypeError, ValueError):
                continue
            results.append(RerankResult(candidate_index=index, score=score_value))

        metrics = ProviderCallMetrics(
            provider=self.provider_name,
            model=self._config.model,
            latency_ms=latency,
            status="ok",
            error_code=None,
        )
        return results, metrics


def build_siliconflow_rerank_provider(
    config: SiliconFlowRerankConfig | None = None,
    *,
    request_fn: RerankRequestFn | None = None,
) -> SiliconFlowRerankProvider:
    """Create SiliconFlow rerank provider."""

    return SiliconFlowRerankProvider(
        config or load_siliconflow_rerank_config(),
        request_fn=request_fn,
    )
