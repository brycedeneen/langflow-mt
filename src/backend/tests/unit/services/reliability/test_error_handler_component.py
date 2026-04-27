from datetime import datetime, timezone
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from lfx.custom.custom_component.component import Component
from lfx.schema.error_payload import ErrorPayload
from lfx.template.field.base import Output


def test_error_handler_declares_expected_inputs():
    from lfx.components.reliability.error_handler import ErrorHandler

    component = ErrorHandler()
    input_names = {i.name for i in component.inputs}
    expected = {
        "error_input",
        "max_attempts",
        "alert_mode",
        "bell_audience",
        "bell_specific_user_id",
        "alert_title_template",
        "backoff_strategy",
        "base_delay_seconds",
        "max_delay_seconds",
        "alert_body_template",
    }
    assert input_names == expected


def test_error_handler_has_gave_up_output():
    from lfx.components.reliability.error_handler import ErrorHandler

    component = ErrorHandler()
    output_names = {o.name for o in component.outputs}
    assert "gave_up" in output_names
    gave_up = next(o for o in component.outputs if o.name == "gave_up")
    assert gave_up.types == ["ErrorPayload"]


def test_error_handler_does_not_inject_error_output():
    """ErrorHandler must NOT have an error output (no nested error recovery)."""
    from lfx.components.reliability.error_handler import ErrorHandler

    component = ErrorHandler()
    output_names = {o.name for o in component.outputs}
    assert "error" not in output_names


@pytest.mark.asyncio
async def test_dispatch_alert_bell_flow_owner():
    from lfx.components.reliability.error_handler import ErrorHandler
    from langflow.services.database.models.admin_notification import (
        NotificationAudience,
    )

    notifier = MagicMock()
    notifier.notify = AsyncMock()
    flow_owner_id = uuid4()
    org_id = uuid4()

    component = ErrorHandler()
    component.alert_mode = "Bell"
    component.bell_audience = "Flow owner"
    component.alert_title_template = "Flow '{flow_name}' failed at {component_name}"
    component.alert_body_template = "{error_message}"

    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="...",
        component_id="vtx-1",
        component_display_name="HTTP Request",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=3,
        occurred_at=datetime.now(timezone.utc),
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=flow_owner_id,
        org_id=org_id,
        flow_name="my-flow",
        org_name="acme",
    )

    notifier.notify.assert_awaited_once()
    event = notifier.notify.call_args.args[0]
    assert event.category == "flow_error"
    assert event.severity == "error"
    assert event.org_id == org_id
    assert event.audience == NotificationAudience.PLATFORM_ADMIN
    assert event.audience_user_id == flow_owner_id
    assert event.title == "Flow 'my-flow' failed at HTTP Request"
    assert "boom" in event.body_md


@pytest.mark.asyncio
async def test_dispatch_alert_ignore_does_not_call_notifier():
    from lfx.components.reliability.error_handler import ErrorHandler

    notifier = MagicMock()
    notifier.notify = AsyncMock()

    component = ErrorHandler()
    component.alert_mode = "Ignore"
    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )

    notifier.notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_alert_email_falls_through_to_bell():
    from lfx.components.reliability.error_handler import ErrorHandler

    notifier = MagicMock()
    notifier.notify = AsyncMock()

    component = ErrorHandler()
    component.alert_mode = "Email (Not Implemented)"
    component.bell_audience = "Org admins"
    component.alert_title_template = "x"
    component.alert_body_template = "y"
    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )

    # Falls through to Bell.
    notifier.notify.assert_awaited_once()
    from langflow.services.database.models.admin_notification import NotificationAudience
    event = notifier.notify.call_args.args[0]
    assert event.audience == NotificationAudience.PLATFORM_ADMIN
    assert event.audience_user_id is None  # Org admins = no specific user


@pytest.mark.asyncio
async def test_dispatch_alert_swallows_notifier_exceptions():
    from lfx.components.reliability.error_handler import ErrorHandler

    notifier = MagicMock()
    notifier.notify = AsyncMock(side_effect=RuntimeError("DB down"))

    component = ErrorHandler()
    component.alert_mode = "Bell"
    component.bell_audience = "Flow owner"
    component.alert_title_template = "x"
    component.alert_body_template = "y"
    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    # Should not re-raise — alert dispatch is best-effort.
    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )


@pytest.mark.asyncio
async def test_dispatch_alert_template_error_falls_back_to_inline_message():
    from lfx.components.reliability.error_handler import ErrorHandler

    notifier = MagicMock()
    notifier.notify = AsyncMock()

    component = ErrorHandler()
    component.alert_mode = "Bell"
    component.bell_audience = "Flow owner"
    component.alert_title_template = "Hello {nonexistent_variable}"
    component.alert_body_template = "{also_bad}"
    payload = ErrorPayload(
        error_message="real error here",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )

    # The alert still fired despite the template typos.
    notifier.notify.assert_awaited_once()
    event = notifier.notify.call_args.args[0]
    assert "Template error" in event.title
    assert "real error here" in event.title
    assert "Template error" in event.body_md
    assert "real error here" in event.body_md


@pytest.mark.asyncio
async def test_dispatch_alert_bell_specific_user():
    from lfx.components.reliability.error_handler import ErrorHandler
    from langflow.services.database.models.admin_notification import (
        NotificationAudience,
    )

    notifier = MagicMock()
    notifier.notify = AsyncMock()
    target_user_id = uuid4()

    component = ErrorHandler()
    component.alert_mode = "Bell"
    component.bell_audience = "Specific user"
    component.bell_specific_user_id = str(target_user_id)
    component.alert_title_template = "x"
    component.alert_body_template = "y"

    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )

    notifier.notify.assert_awaited_once()
    event = notifier.notify.call_args.args[0]
    assert event.audience == NotificationAudience.PLATFORM_ADMIN
    assert event.audience_user_id == target_user_id


@pytest.mark.asyncio
async def test_dispatch_alert_specific_user_invalid_uuid_suppresses():
    from lfx.components.reliability.error_handler import ErrorHandler

    notifier = MagicMock()
    notifier.notify = AsyncMock()

    component = ErrorHandler()
    component.alert_mode = "Bell"
    component.bell_audience = "Specific user"
    component.bell_specific_user_id = "not-a-uuid"
    component.alert_title_template = "x"
    component.alert_body_template = "y"

    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )

    # Suppressed: alert NOT broadcast to org admins as a fallback.
    notifier.notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_alert_specific_user_missing_id_suppresses():
    from lfx.components.reliability.error_handler import ErrorHandler

    notifier = MagicMock()
    notifier.notify = AsyncMock()

    component = ErrorHandler()
    component.alert_mode = "Bell"
    component.bell_audience = "Specific user"
    component.bell_specific_user_id = ""  # blank
    component.alert_title_template = "x"
    component.alert_body_template = "y"

    payload = ErrorPayload(
        error_message="boom",
        error_type="ValueError",
        stack_trace="",
        component_id="x",
        component_display_name="x",
        flow_id=uuid4(),
        flow_run_id=uuid4(),
        attempt_number=1,
    )

    await component.dispatch_alert(
        payload=payload,
        notifier=notifier,
        flow_owner_id=uuid4(),
        org_id=uuid4(),
        flow_name="f",
        org_name="o",
    )

    notifier.notify.assert_not_awaited()
