"""Week 5 audit replay helpers and CLI."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from compliance_bot.schemas.audit import AuditEvent

_STAGE_TO_PATH_STEP = {
    "graph.normalize": "normalize",
    "graph.retrieve": "retrieve",
    "graph.retry": "retry_answer",
    "graph.policy_check": "policy_check",
    "graph.finalize": "finalize",
}


class AuditReplaySummary(BaseModel):
    """Replay summary reconstructed from one trace."""

    trace_id: str = Field(..., min_length=1)
    total_events: int = Field(..., ge=0)
    stage_counts: dict[str, int] = Field(default_factory=dict)
    decision_path: list[str] = Field(default_factory=list)
    final_stage: str | None = None


def _decision_step_from_event(event: AuditEvent) -> str | None:
    if event.stage == "graph.answer":
        attempt = event.metadata.get("attempt")
        if isinstance(attempt, int) and attempt >= 1:
            return f"answer_attempt_{attempt}"
        return "answer_attempt_1"
    return _STAGE_TO_PATH_STEP.get(event.stage)


def replay_audit_trace(
    audit_events: list[AuditEvent],
    *,
    trace_id: str,
) -> AuditReplaySummary:
    """Reconstruct workflow decision path from audit events."""

    trace_events = [event for event in audit_events if event.trace_id == trace_id]
    ordered_events = sorted(trace_events, key=lambda item: item.timestamp)
    stage_counts = Counter(event.stage for event in ordered_events)

    decision_path: list[str] = []
    for event in ordered_events:
        step = _decision_step_from_event(event)
        if step is not None:
            decision_path.append(step)

    final_stage = ordered_events[-1].stage if ordered_events else None
    return AuditReplaySummary(
        trace_id=trace_id,
        total_events=len(ordered_events),
        stage_counts=dict(stage_counts),
        decision_path=decision_path,
        final_stage=final_stage,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay Week 5 audit events by trace_id")
    parser.add_argument(
        "--response-path",
        type=Path,
        required=True,
        help="Path to a Week 5 workflow JSON response file",
    )
    parser.add_argument(
        "--trace-id",
        type=str,
        default=None,
        help="Trace id override. Defaults to payload trace_id.",
    )
    return parser


def main() -> None:
    """CLI entrypoint for audit replay summaries."""

    args = _build_parser().parse_args()
    payload = json.loads(args.response_path.read_text(encoding="utf-8"))
    resolved_trace_id = args.trace_id or payload.get("trace_id", "")
    if not resolved_trace_id:
        raise ValueError("trace_id is required in payload or via --trace-id")

    raw_events = payload.get("audit_events", [])
    audit_events = [AuditEvent.model_validate(item) for item in raw_events]
    summary = replay_audit_trace(audit_events, trace_id=resolved_trace_id)
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
