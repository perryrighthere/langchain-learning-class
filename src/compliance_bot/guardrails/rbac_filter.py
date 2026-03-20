"""Week 7 role-aware retrieval scope controls."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field, field_validator

from compliance_bot.schemas.retrieval import RetrievalFilters


DEFAULT_USER_ROLE = "employee"

_ROLE_SCOPE_POLICY: Final[dict[str, set[str] | None]] = {
    "employee": {"expense", "travel", "retention", "records"},
    "manager": {"expense", "travel", "retention", "records"},
    "finance_manager": {"expense", "travel", "retention", "records"},
    "legal_reviewer": {"vendor", "privacy", "retention", "records"},
    "privacy_officer": {"vendor", "privacy", "retention"},
    "compliance_analyst": {
        "expense",
        "travel",
        "retention",
        "records",
        "vendor",
        "privacy",
    },
    "admin": None,
}


class RoleAccessDecision(BaseModel):
    """Structured RBAC evaluation result for retrieval filters."""

    user_role: str = Field(..., min_length=1)
    allowed_policy_scope: list[str] = Field(default_factory=list)
    denied_policy_scope: list[str] = Field(default_factory=list)
    effective_policy_scope: list[str] = Field(default_factory=list)
    blocked: bool = False
    requires_human_review: bool = False
    rationale: str = Field(..., min_length=1)

    @field_validator("allowed_policy_scope", "denied_policy_scope", "effective_policy_scope")
    @classmethod
    def normalize_scope_lists(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            token = item.strip().lower()
            if token and token not in seen:
                normalized.append(token)
                seen.add(token)
        return normalized


def apply_role_access_policy(
    filters: RetrievalFilters,
) -> tuple[RetrievalFilters, RoleAccessDecision]:
    """Restrict retrieval scopes according to the caller role."""

    resolved_role = filters.user_role or DEFAULT_USER_ROLE
    allowed_scope = _ROLE_SCOPE_POLICY.get(resolved_role, _ROLE_SCOPE_POLICY[DEFAULT_USER_ROLE])
    requested_scope = set(filters.policy_scope)

    if allowed_scope is None:
        decision = RoleAccessDecision(
            user_role=resolved_role,
            allowed_policy_scope=[],
            denied_policy_scope=[],
            effective_policy_scope=filters.policy_scope,
            blocked=False,
            requires_human_review=False,
            rationale="Administrator role bypasses scope restrictions.",
        )
        return filters.model_copy(update={"user_role": resolved_role}), decision

    denied_scope = sorted(requested_scope - allowed_scope)
    if requested_scope:
        effective_scope = sorted(requested_scope.intersection(allowed_scope))
    else:
        effective_scope = sorted(allowed_scope)

    blocked = bool(requested_scope) and not effective_scope
    requires_human_review = blocked or bool(denied_scope)

    if blocked:
        rationale = (
            "Requested policy scope is not allowed for the caller role and retrieval was blocked."
        )
    elif denied_scope:
        rationale = "Requested policy scope was reduced to the subset allowed for the caller role."
    elif not requested_scope:
        rationale = "No policy scope was supplied, so the role allow-list was applied."
    else:
        rationale = "Requested policy scope is allowed for the caller role."

    decision = RoleAccessDecision(
        user_role=resolved_role,
        allowed_policy_scope=sorted(allowed_scope),
        denied_policy_scope=denied_scope,
        effective_policy_scope=effective_scope,
        blocked=blocked,
        requires_human_review=requires_human_review,
        rationale=rationale,
    )
    updated_filters = filters.model_copy(
        update={
            "user_role": resolved_role,
            "policy_scope": effective_scope,
        }
    )
    return updated_filters, decision
