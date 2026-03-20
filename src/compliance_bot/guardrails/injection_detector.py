"""Week 7 prompt-injection detection for guardrailed workflow entry."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


DEFAULT_GUARDRAIL_REFUSAL_ANSWER = (
    "I cannot follow instructions that attempt to bypass compliance guardrails or reveal "
    "system behavior. Please restate the policy question without meta-instructions."
)

_BLOCK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous_instructions",
        re.compile(r"\bignore\s+(all\s+)?(previous|prior)\s+instructions\b", re.IGNORECASE),
    ),
    (
        "reveal_system_prompt",
        re.compile(r"\b(system|developer)\s+prompt\b", re.IGNORECASE),
    ),
    (
        "guardrail_bypass",
        re.compile(r"\b(bypass|override|disable)\b.{0,32}\b(policy|guardrail|safety)\b", re.IGNORECASE),
    ),
    (
        "tool_or_secret_exfiltration",
        re.compile(r"\b(reveal|print|dump|show)\b.{0,40}\b(prompt|secret|api key|tool)\b", re.IGNORECASE),
    ),
)


class InjectionDetectionResult(BaseModel):
    """Deterministic prompt-injection inspection result."""

    blocked: bool = False
    matched_rules: list[str] = Field(default_factory=list)
    sanitized_question: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)

    @field_validator("matched_rules")
    @classmethod
    def normalize_matched_rules(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized


def detect_prompt_injection(question: str) -> InjectionDetectionResult:
    """Detect prompt-injection attempts with explicit block reasons."""

    normalized_question = " ".join(question.split())
    if not normalized_question:
        raise ValueError("question must not be blank")

    matched_rules = [
        rule_name
        for rule_name, pattern in _BLOCK_RULES
        if pattern.search(normalized_question)
    ]
    if matched_rules:
        return InjectionDetectionResult(
            blocked=True,
            matched_rules=matched_rules,
            sanitized_question=normalized_question,
            rationale=(
                "Blocked prompt because it contains guardrail bypass or prompt exfiltration patterns: "
                + ", ".join(matched_rules)
            ),
        )

    return InjectionDetectionResult(
        blocked=False,
        matched_rules=[],
        sanitized_question=normalized_question,
        rationale="No prompt-injection patterns detected.",
    )
