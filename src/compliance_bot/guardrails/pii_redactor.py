"""Week 7 sensitive-data redaction utilities."""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, Field, field_validator


_REDACTION_PATTERNS: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = (
    (
        "email",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "[REDACTED_EMAIL]",
    ),
    (
        "phone",
        re.compile(
            r"(?<!\w)(?:\+?\d{1,2}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]\d{4}(?!\w)"
        ),
        "[REDACTED_PHONE]",
    ),
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
    (
        "account_number",
        re.compile(r"\b\d{13,16}\b"),
        "[REDACTED_ACCOUNT]",
    ),
)


class RedactionResult(BaseModel):
    """Structured text-redaction result."""

    redacted_text: str = Field(..., min_length=1)
    applied_labels: list[str] = Field(default_factory=list)
    redaction_count: int = Field(default=0, ge=0)

    @field_validator("applied_labels")
    @classmethod
    def normalize_applied_labels(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized


def redact_sensitive_text(text: str) -> RedactionResult:
    """Redact common PII markers from one text field."""

    normalized = " ".join(text.split())
    if not normalized:
        raise ValueError("text must not be blank")

    redacted_text = normalized
    applied_labels: list[str] = []
    redaction_count = 0

    for label, pattern, replacement in _REDACTION_PATTERNS:
        redacted_text, replacements = pattern.subn(replacement, redacted_text)
        if replacements > 0:
            applied_labels.append(label)
            redaction_count += replacements

    return RedactionResult(
        redacted_text=redacted_text,
        applied_labels=applied_labels,
        redaction_count=redaction_count,
    )
