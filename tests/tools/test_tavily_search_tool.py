"""Tests for the Week 6 Tavily search tool."""

from __future__ import annotations

import pytest

from compliance_bot.schemas.tools import TavilySearchInput
from compliance_bot.tools.tavily_search_tool import (
    TavilySearchConfig,
    has_tavily_api_key,
    load_tavily_search_config,
    search_tavily,
)


def test_tavily_config_requires_api_key() -> None:
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        load_tavily_search_config({})


def test_has_tavily_api_key_detects_configured_env() -> None:
    assert has_tavily_api_key({"TAVILY_API_KEY": "test-key"}) is True
    assert has_tavily_api_key({}) is False


def test_search_tavily_maps_results_into_schema() -> None:
    captured: dict[str, object] = {}

    def _request(
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {
            "answer": "The latest public guidance still requires manager approval.",
            "results": [
                {
                    "title": "Expense Policy Update",
                    "url": "https://example.com/expense-update",
                    "content": "Manager approval remains mandatory for reimbursement.",
                    "score": 0.92,
                }
            ],
        }

    result = search_tavily(
        TavilySearchInput(
            question="What is the latest expense reimbursement guidance?",
            topic="news",
            max_results=1,
            search_depth="advanced",
            days=7,
        ),
        config=TavilySearchConfig(api_key="test-key"),
        request_fn=_request,
    )

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"] == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    assert captured["payload"] == {
        "query": "What is the latest expense reimbursement guidance?",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 1,
        "include_answer": True,
        "days": 7,
    }
    assert result.resolved is True
    assert result.topic == "news"
    assert result.answer == "The latest public guidance still requires manager approval."
    assert result.sources[0].url == "https://example.com/expense-update"


def test_search_tavily_returns_unresolved_when_no_results() -> None:
    result = search_tavily(
        TavilySearchInput(question="latest update on vendor sanctions"),
        config=TavilySearchConfig(api_key="test-key"),
        request_fn=lambda *_: {"answer": None, "results": []},
    )

    assert result.resolved is False
    assert result.sources == []
