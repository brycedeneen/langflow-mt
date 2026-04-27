from datetime import datetime, timezone
from uuid import uuid4

import pytest

from lfx.schema.error_payload import ErrorPayload, build_error_payload


def test_error_payload_construction_from_exception():
    flow_id = uuid4()
    flow_run_id = uuid4()
    try:
        raise ValueError("boom")
    except ValueError as exc:
        payload = build_error_payload(
            exc,
            component_id="vtx-1",
            component_display_name="HTTP Request",
            flow_id=flow_id,
            flow_run_id=flow_run_id,
            attempt_number=2,
        )
    assert payload.error_message == "boom"
    assert payload.error_type == "ValueError"
    assert payload.component_id == "vtx-1"
    assert payload.component_display_name == "HTTP Request"
    assert payload.flow_id == flow_id
    assert payload.flow_run_id == flow_run_id
    assert payload.attempt_number == 2
    assert isinstance(payload.occurred_at, datetime)
    assert payload.occurred_at.tzinfo is not None
    assert "ValueError" in payload.stack_trace
    assert "boom" in payload.stack_trace


def test_error_payload_truncates_long_stack_trace():
    flow_id = uuid4()
    flow_run_id = uuid4()
    huge = "x" * 10_000
    try:
        raise RuntimeError(huge)
    except RuntimeError as exc:
        payload = build_error_payload(
            exc,
            component_id="vtx-1",
            component_display_name="HTTP Request",
            flow_id=flow_id,
            flow_run_id=flow_run_id,
            attempt_number=1,
        )
    assert len(payload.stack_trace) <= 4096
    assert payload.stack_trace.endswith("...[truncated]")
