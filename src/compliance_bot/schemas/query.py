"""Week 1 query and response schemas."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DecisionEnum(str, Enum):
    """Allowed output decisions for the baseline chain."""

    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"
    ESCALATE = "ESCALATE"


class BaselineChainInput(BaseModel):
    """Input contract for the Week 1 baseline chain."""

    question: str = Field(..., min_length=1)
    context: str = Field(default="NO_CONTEXT_AVAILABLE")

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class BaselineChainOutput(BaseModel):
    """Structured output for the Week 1 baseline chain."""

    answer: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    decision: DecisionEnum

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("answer must not be blank")
        return normalized

