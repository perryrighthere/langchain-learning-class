"""Week 6 escalation rules for tool-enabled workflow execution."""

from __future__ import annotations

from compliance_bot.chains.abstention_policy import DEFAULT_ESCALATE_ANSWER
from compliance_bot.graph.state import ComplianceAgentState
from compliance_bot.schemas.query import DecisionEnum


def apply_escalation_policy(state: ComplianceAgentState) -> ComplianceAgentState:
    """Escalate unresolved, high-risk, or tool-degraded requests to human review."""

    escalation_reasons: list[str] = []
    if state.tool_plan.high_risk:
        escalation_reasons.append("high_risk_intent")
    if any(not result.resolved for result in state.tool_results):
        escalation_reasons.append("tool_unresolved")
    if any(result.status != "ok" for result in state.tool_results):
        escalation_reasons.append("tool_degraded")
    if state.final_decision != DecisionEnum.ANSWERED:
        escalation_reasons.append("answer_not_safe")

    if escalation_reasons:
        state.requires_human_review = True
        state.final_decision = DecisionEnum.ESCALATE
        state.final_answer = DEFAULT_ESCALATE_ANSWER
        state.final_confidence = 0.0
        state.escalation_reason = "+".join(dict.fromkeys(escalation_reasons))
        for reason in escalation_reasons:
            if reason not in state.policy_flags:
                state.policy_flags.append(reason)
        if "human_review_required" not in state.policy_flags:
            state.policy_flags.append("human_review_required")
        return state

    state.requires_human_review = False
    state.escalation_reason = None
    return state
