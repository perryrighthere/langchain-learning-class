"""Week 5 helpers for emitting workflow audit events."""

from __future__ import annotations

import json
from typing import Any, Mapping

from compliance_bot.schemas.audit import AuditEvent, build_audit_event

AuditMetadata = dict[str, str | int | float | bool | None]


def _serialize_payload(payload: str | Mapping[str, Any]) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, default=str, sort_keys=True)


def emit_workflow_audit_event(
    *,
    trace_id: str,
    stage: str,
    status: str,
    input_payload: str | Mapping[str, Any],
    output_payload: str | Mapping[str, Any],
    metadata: AuditMetadata | None = None,
) -> AuditEvent:
    """Create a deterministic workflow-scoped audit event."""

    return build_audit_event(
        trace_id=trace_id,
        stage=stage,
        actor="graph.workflow",
        status=status,
        input_payload=_serialize_payload(input_payload),
        output_payload=_serialize_payload(output_payload),
        metadata=metadata or {},
    )
