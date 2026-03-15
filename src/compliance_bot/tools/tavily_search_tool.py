"""Week 6 Tavily-backed real-time search tool."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from langchain_core.tools import BaseTool, StructuredTool

from compliance_bot.schemas.tools import (
    TavilySearchInput,
    TavilySearchResult,
    TavilySearchSource,
)

DEFAULT_TAVILY_BASE_URL = "https://api.tavily.com/search"
DEFAULT_TAVILY_TOPIC = "general"
DEFAULT_TAVILY_SEARCH_DEPTH = "advanced"
DEFAULT_TAVILY_TIMEOUT_SECONDS = 10.0
DEFAULT_TAVILY_MAX_RESULTS = 3

RequestFn = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


@dataclass(frozen=True)
class TavilySearchConfig:
    """Runtime config for Tavily search."""

    api_key: str
    base_url: str = DEFAULT_TAVILY_BASE_URL
    topic: str = DEFAULT_TAVILY_TOPIC
    search_depth: str = DEFAULT_TAVILY_SEARCH_DEPTH
    max_results: int = DEFAULT_TAVILY_MAX_RESULTS
    timeout_seconds: float = DEFAULT_TAVILY_TIMEOUT_SECONDS


def has_tavily_api_key(env: Mapping[str, str] | None = None) -> bool:
    """Return True when Tavily search is configured."""

    source = env if env is not None else os.environ
    return bool(source.get("TAVILY_API_KEY", "").strip())


def load_tavily_search_config(env: Mapping[str, str] | None = None) -> TavilySearchConfig:
    """Load Tavily search config from environment variables."""

    source = env if env is not None else os.environ
    api_key = source.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing TAVILY_API_KEY.")

    base_url = source.get("TAVILY_BASE_URL", DEFAULT_TAVILY_BASE_URL).strip()
    topic = source.get("TAVILY_TOPIC", DEFAULT_TAVILY_TOPIC).strip()
    search_depth = source.get("TAVILY_SEARCH_DEPTH", DEFAULT_TAVILY_SEARCH_DEPTH).strip()
    max_results = int(source.get("TAVILY_MAX_RESULTS", str(DEFAULT_TAVILY_MAX_RESULTS)))
    timeout_seconds = float(
        source.get("TAVILY_TIMEOUT_SECONDS", str(DEFAULT_TAVILY_TIMEOUT_SECONDS))
    )
    return TavilySearchConfig(
        api_key=api_key,
        base_url=base_url or DEFAULT_TAVILY_BASE_URL,
        topic=topic or DEFAULT_TAVILY_TOPIC,
        search_depth=search_depth or DEFAULT_TAVILY_SEARCH_DEPTH,
        max_results=max_results,
        timeout_seconds=timeout_seconds,
    )


def _default_request(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def search_tavily(
    tool_input: TavilySearchInput,
    *,
    config: TavilySearchConfig,
    request_fn: RequestFn | None = None,
) -> TavilySearchResult:
    """Call Tavily search and map the response into a stable schema."""

    payload: dict[str, Any] = {
        "query": tool_input.question,
        "topic": tool_input.topic or config.topic,
        "search_depth": tool_input.search_depth or config.search_depth,
        "max_results": tool_input.max_results,
        "include_answer": True,
    }
    if tool_input.days is not None:
        payload["days"] = tool_input.days

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    caller = request_fn or _default_request
    try:
        raw = caller(config.base_url, headers, payload, config.timeout_seconds)
    except TimeoutError as exc:
        raise TimeoutError("tavily search timed out") from exc
    except (HTTPError, URLError, OSError) as exc:
        raise RuntimeError(f"tavily search failed: {exc}") from exc

    raw_results = raw.get("results", [])
    sources = [
        TavilySearchSource(
            title=str(item.get("title", "")).strip() or "Untitled",
            url=str(item.get("url", "")).strip() or "missing-url",
            content=str(item.get("content", "")).strip() or "No snippet returned.",
            score=float(item.get("score", 0.0) or 0.0),
        )
        for item in raw_results
        if isinstance(item, dict)
    ]
    if not sources:
        return TavilySearchResult(
            resolved=False,
            summary="No external search results were returned.",
            answer=None,
            topic=str(payload["topic"]),
            sources=[],
            requires_human_review=False,
        )

    answer = raw.get("answer")
    summary = ", ".join(source.title for source in sources[:3])
    return TavilySearchResult(
        resolved=True,
        summary=f"External search returned: {summary}",
        answer=str(answer).strip() if isinstance(answer, str) and answer.strip() else None,
        topic=str(payload["topic"]),
        sources=sources,
        requires_human_review=False,
    )


def render_tavily_context(result: TavilySearchResult) -> str:
    """Render search output into compact workflow context."""

    if not result.sources:
        return result.summary

    lines = [result.summary]
    if result.answer:
        lines.append(f"answer={result.answer}")
    for source in result.sources:
        lines.append(
            " | ".join(
                [
                    f"title={source.title}",
                    f"url={source.url}",
                    f"score={source.score:.2f}",
                    f"content={source.content}",
                ]
            )
        )
    return "\n".join(lines)


def build_tavily_search_tool(
    config: TavilySearchConfig | None = None,
    *,
    request_fn: RequestFn | None = None,
) -> BaseTool:
    """Create a LangChain tool wrapper for Tavily search."""

    resolved_config = config or load_tavily_search_config()

    def _tool_fn(
        question: str,
        topic: str = DEFAULT_TAVILY_TOPIC,
        max_results: int = DEFAULT_TAVILY_MAX_RESULTS,
        search_depth: str = DEFAULT_TAVILY_SEARCH_DEPTH,
        days: int | None = None,
    ) -> dict[str, Any]:
        result = search_tavily(
            TavilySearchInput(
                question=question,
                topic=topic,
                max_results=max_results,
                search_depth=search_depth,
                days=days,
            ),
            config=resolved_config,
            request_fn=request_fn,
        )
        return result.model_dump(mode="python")

    return StructuredTool.from_function(
        func=_tool_fn,
        name="tavily_search",
        description=(
            "Search the public web for latest or real-time compliance developments when local "
            "policy data may be outdated or insufficient."
        ),
        args_schema=TavilySearchInput,
    )
