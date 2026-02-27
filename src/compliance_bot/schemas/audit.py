"""Audit schemas used by retrieval and later workflow stages."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """Deterministic audit event emitted at major pipeline stages."""

    event_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    stage: str = Field(..., min_length=1)
    timestamp: datetime
    input_hash: str = Field(..., min_length=64, max_length=64)
    output_hash: str = Field(..., min_length=64, max_length=64)
    actor: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


def build_audit_event(
    *,
    trace_id: str,
    stage: str,
    actor: str,
    status: str,
    input_payload: str,
    output_payload: str,
    metadata: dict[str, str | int | float | bool | None] | None = None,
) -> AuditEvent:
    """Create an audit event with stable hash fields."""

    return AuditEvent(
        event_id=str(uuid4()),
        trace_id=trace_id,
        stage=stage,
        timestamp=datetime.now(timezone.utc),
        input_hash=sha256(input_payload.encode("utf-8")).hexdigest(),
        output_hash=sha256(output_payload.encode("utf-8")).hexdigest(),
        actor=actor,
        status=status,
        metadata=metadata or {},
    )
