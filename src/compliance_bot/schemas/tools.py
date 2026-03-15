"""Week 6 tool routing and tool execution schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ToolPlan(BaseModel):
    """Deterministic routing plan for Week 6 tool execution."""

    planned_tools: list[str] = Field(default_factory=list)
    tool_arguments: dict[str, dict[str, object]] = Field(default_factory=dict)
    high_risk: bool = False
    rationale: str = Field(default="Direct retrieval path is sufficient.")
    router_mode: str = Field(default="heuristic", min_length=1)

    @field_validator("planned_tools")
    @classmethod
    def normalize_planned_tools(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized

    @field_validator("tool_arguments")
    @classmethod
    def normalize_tool_arguments(
        cls, value: dict[str, dict[str, object]]
    ) -> dict[str, dict[str, object]]:
        normalized: dict[str, dict[str, object]] = {}
        for key, item in value.items():
            tool_name = key.strip().lower()
            if not tool_name or not isinstance(item, dict):
                continue
            normalized[tool_name] = dict(item)
        return normalized

    @field_validator("rationale")
    @classmethod
    def normalize_rationale(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("rationale must not be blank")
        return normalized


class PolicyRegistryLookupInput(BaseModel):
    """Input contract for the policy registry tool."""

    question: str = Field(..., min_length=1)
    jurisdiction: str | None = None
    policy_scope: list[str] = Field(default_factory=list)
    max_results: int = Field(default=3, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("policy_scope")
    @classmethod
    def normalize_policy_scope(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized


class PolicyRegistryMatch(BaseModel):
    """One policy registry hit exposed to the workflow."""

    doc_id: str = Field(..., min_length=1)
    version_tag: str = Field(..., min_length=1)
    jurisdictions: list[str] = Field(default_factory=list)
    policy_scopes: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    match_score: float = Field(..., ge=0.0, le=1.0)


class PolicyRegistryLookupResult(BaseModel):
    """Result contract for the policy registry tool."""

    resolved: bool
    matches: list[PolicyRegistryMatch] = Field(default_factory=list)
    summary: str = Field(..., min_length=1)


class ExceptionLogRecord(BaseModel):
    """One exception-log entry used for human-review decisions."""

    exception_id: str = Field(..., min_length=1)
    jurisdiction: str | None = None
    policy_scope: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    owner: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)

    @field_validator("jurisdiction")
    @classmethod
    def normalize_exception_jurisdiction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("policy_scope", "status", "owner", "summary")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("exception-log field must not be blank")
        return normalized


class ExceptionLogLookupInput(BaseModel):
    """Input contract for the exception-log tool."""

    question: str = Field(..., min_length=1)
    jurisdiction: str | None = None
    policy_scope: list[str] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def normalize_exception_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized

    @field_validator("jurisdiction")
    @classmethod
    def normalize_exception_lookup_jurisdiction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("policy_scope")
    @classmethod
    def normalize_exception_policy_scope(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized


class ExceptionLogLookupResult(BaseModel):
    """Result contract for the exception-log tool."""

    resolved: bool
    matching_records: list[ExceptionLogRecord] = Field(default_factory=list)
    summary: str = Field(..., min_length=1)
    requires_human_review: bool = False


class TavilySearchInput(BaseModel):
    """Input contract for real-time Tavily search."""

    question: str = Field(..., min_length=1)
    topic: str = Field(default="general", min_length=1)
    max_results: int = Field(default=3, ge=1, le=10)
    search_depth: str = Field(default="advanced", min_length=1)
    days: int | None = Field(default=None, ge=1, le=30)

    @field_validator("question", "topic", "search_depth")
    @classmethod
    def normalize_search_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("search field must not be blank")
        return normalized


class TavilySearchSource(BaseModel):
    """One Tavily result mapped into the workflow."""

    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    score: float = Field(default=0.0, ge=0.0)


class TavilySearchResult(BaseModel):
    """Structured Tavily search result for workflow use."""

    resolved: bool
    summary: str = Field(..., min_length=1)
    answer: str | None = None
    topic: str = Field(..., min_length=1)
    sources: list[TavilySearchSource] = Field(default_factory=list)
    requires_human_review: bool = False


class ToolExecutionRecord(BaseModel):
    """Serializable execution summary for one tool call."""

    tool_name: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    latency_ms: float = Field(..., ge=0.0)
    resolved: bool
    summary: str = Field(..., min_length=1)
    error_code: str | None = None
    requires_human_review: bool = False
