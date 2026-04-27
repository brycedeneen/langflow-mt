from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

_STACK_TRACE_MAX_BYTES = 4096
_TRUNCATION_MARKER = "...[truncated]"


@dataclass(frozen=True)
class ErrorPayload:
    """Structured error emitted by a failing component's `error` output port."""

    error_message: str
    error_type: str
    stack_trace: str
    component_id: str
    component_display_name: str
    flow_id: UUID
    flow_run_id: UUID | None
    attempt_number: int
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


def build_error_payload(
    exc: BaseException,
    *,
    component_id: str,
    component_display_name: str,
    flow_id: UUID,
    flow_run_id: UUID | None,
    attempt_number: int,
) -> ErrorPayload:
    """Construct an ErrorPayload from an exception, truncating the trace."""
    raw_trace = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    if len(raw_trace) > _STACK_TRACE_MAX_BYTES:
        keep = _STACK_TRACE_MAX_BYTES - len(_TRUNCATION_MARKER)
        trace = raw_trace[:keep] + _TRUNCATION_MARKER
    else:
        trace = raw_trace
    return ErrorPayload(
        error_message=str(exc),
        error_type=type(exc).__name__,
        stack_trace=trace,
        component_id=component_id,
        component_display_name=component_display_name,
        flow_id=flow_id,
        flow_run_id=flow_run_id,
        attempt_number=attempt_number,
    )
