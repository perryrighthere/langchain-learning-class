"""Week 5 audit replay tests."""

from __future__ import annotations

from compliance_bot.audit.events import emit_workflow_audit_event
from compliance_bot.audit.replay import replay_audit_trace


def test_replay_reconstructs_decision_path_from_workflow_stages() -> None:
    trace_id = "trace-week5-replay-001"
    events = [
        emit_workflow_audit_event(
            trace_id=trace_id,
            stage="graph.normalize",
            status="ok",
            input_payload={"question": "Who approves expense reimbursement?"},
            output_payload={"normalized_query": "who approves expense reimbursement"},
        ),
        emit_workflow_audit_event(
            trace_id=trace_id,
            stage="graph.retrieve",
            status="ok",
            input_payload={"top_k": 4},
            output_payload={"retrieval_decision": "ANSWERED"},
        ),
        emit_workflow_audit_event(
            trace_id=trace_id,
            stage="graph.answer",
            status="ok",
            input_payload={"attempt": 1},
            output_payload={"final_decision": "ANSWERED"},
            metadata={"attempt": 1},
        ),
        emit_workflow_audit_event(
            trace_id=trace_id,
            stage="graph.policy_check",
            status="ok",
            input_payload={"decision": "ANSWERED"},
            output_payload={"requires_human_review": False},
        ),
        emit_workflow_audit_event(
            trace_id=trace_id,
            stage="graph.finalize",
            status="ok",
            input_payload={"decision_path_length": 4},
            output_payload={"final_decision": "ANSWERED"},
        ),
    ]

    replay = replay_audit_trace(events, trace_id=trace_id)

    assert replay.trace_id == trace_id
    assert replay.total_events == 5
    assert replay.stage_counts["graph.answer"] == 1
    assert replay.decision_path == [
        "normalize",
        "retrieve",
        "answer_attempt_1",
        "policy_check",
        "finalize",
    ]
