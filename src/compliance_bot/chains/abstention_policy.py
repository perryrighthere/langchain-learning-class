"""Week 4 abstention and escalation controls for grounded answering."""

from __future__ import annotations

from compliance_bot.schemas.answer import GroundedAnswerDraft
from compliance_bot.schemas.query import DecisionEnum

DEFAULT_ABSTAIN_ANSWER = (
    "I do not have enough verified policy evidence to answer this request safely."
)
DEFAULT_ESCALATE_ANSWER = (
    "I cannot produce a reliable grounded answer right now. Please escalate to a human reviewer."
)


def controlled_abstention(reason: str) -> tuple[GroundedAnswerDraft, str]:
    """Create a deterministic abstained response."""

    return (
        GroundedAnswerDraft(
            answer=DEFAULT_ABSTAIN_ANSWER,
            confidence=0.0,
            decision=DecisionEnum.ABSTAINED,
            citations=[],
        ),
        reason,
    )


def controlled_escalation(reason: str) -> tuple[GroundedAnswerDraft, str]:
    """Create a deterministic escalated response."""

    return (
        GroundedAnswerDraft(
            answer=DEFAULT_ESCALATE_ANSWER,
            confidence=0.0,
            decision=DecisionEnum.ESCALATE,
            citations=[],
        ),
        reason,
    )


def enforce_grounding_policy(
    draft: GroundedAnswerDraft,
    *,
    citations_valid: bool,
    min_confidence_for_answer: float,
) -> tuple[GroundedAnswerDraft, str | None]:
    """Enforce citation-first grounding and confidence controls."""

    if draft.decision != DecisionEnum.ANSWERED:
        return controlled_abstention("llm_abstained_or_escalated")

    if draft.confidence < min_confidence_for_answer:
        return controlled_abstention("low_confidence")

    if not citations_valid:
        return controlled_abstention("citation_validation_failed")

    return draft, None
