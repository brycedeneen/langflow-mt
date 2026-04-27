"""End-to-end bell dispatch test — capture-mode notifier (Path B).

Verifies that when ErrorHandler is wired with alert_mode="Bell", running a
graph whose upstream component always fails causes ``dispatch_alert`` to
construct a ``UsageAlertEvent`` with the correct fields and pass it to the
notifier.

The test harness monkey-patches ``Graph._load_flow_metadata`` to return a
stub ``_FlowMeta`` with known ``flow_owner_id`` / ``org_id`` and a
capture-only notifier that appends events to a list instead of writing to the
database.  No real DB session is needed.
"""
from __future__ import annotations

import uuid

import pytest

from langflow.services.database.models.admin_notification import NotificationAudience
from langflow.services.notifier.protocol import UsageAlertEvent


@pytest.mark.asyncio
async def test_bell_flow_owner_dispatch(graph_build_helper):
    """Bell alert for 'Flow owner' audience produces a UsageAlertEvent with:

    - ``category == "flow_error"``
    - ``severity == "error"``
    - ``org_id`` matching the helper's org_id
    - ``audience == NotificationAudience.PLATFORM_ADMIN``
    - ``audience_user_id == helper's flow_owner_id``
    - ``title`` containing the failing component's display name
    """
    known_owner_id = uuid.uuid4()
    known_org_id = uuid.uuid4()

    helper = graph_build_helper.__class__(
        flow_owner_id=known_owner_id,
        org_id=known_org_id,
    )
    helper.install_capture_notifier()

    flaky = helper.add_flaky_component(
        name="Flaky", fail_count=99, error_output_enabled=True
    )
    # max_attempts=0: no retries — alert fires on the first failure.
    handler = helper.add_error_handler(
        max_attempts=0,
        alert_mode="Bell",
        bell_audience="Flow owner",
        name="handler",
        _spy_dispatch=False,  # let the real dispatch_alert run
    )
    helper.connect(flaky, "error", handler, "error_input")
    # Provide a sink for the normal output path (suppressed on error).
    sink_normal = helper.add_text_capture(name="sink_normal")
    helper.connect(flaky, "result", sink_normal, "input")
    # Provide a sink for gave_up.
    sink_gave_up = helper.add_text_capture(name="sink_gave_up")
    helper.connect(handler, "gave_up", sink_gave_up, "input")

    flow_run = await helper.run()

    # Sanity: run completed (partial success — error handled).
    assert flow_run.status.value == "partial_success", (
        f"Expected partial_success, got {flow_run.status.value}"
    )

    events = helper.captured_events
    assert len(events) == 1, (
        f"Expected exactly 1 captured event, got {len(events)}: {events}"
    )

    event: UsageAlertEvent = events[0]

    assert event.category == "flow_error", f"category mismatch: {event.category!r}"
    assert event.severity == "error", f"severity mismatch: {event.severity!r}"
    assert event.org_id == known_org_id, (
        f"org_id mismatch: expected {known_org_id}, got {event.org_id}"
    )
    assert event.audience == NotificationAudience.PLATFORM_ADMIN, (
        f"audience mismatch: {event.audience!r}"
    )
    assert event.audience_user_id == known_owner_id, (
        f"audience_user_id mismatch: expected {known_owner_id}, got {event.audience_user_id}"
    )
    # The default title template is "Flow '{flow_name}' failed at {component_name}".
    # component_display_name on FlakyComponent is "FlakyComponent".
    assert "FlakyComponent" in event.title, (
        f"Expected 'FlakyComponent' in title, got: {event.title!r}"
    )


@pytest.mark.asyncio
async def test_bell_org_admins_dispatch(graph_build_helper):
    """Bell alert for 'Org admins' audience produces a UsageAlertEvent with:

    - ``audience_user_id is None``  (org-wide broadcast, no specific user)
    - ``audience == NotificationAudience.PLATFORM_ADMIN``
    - all other fields consistent with 'Flow owner' test
    """
    known_owner_id = uuid.uuid4()
    known_org_id = uuid.uuid4()

    helper = graph_build_helper.__class__(
        flow_owner_id=known_owner_id,
        org_id=known_org_id,
    )
    helper.install_capture_notifier()

    flaky = helper.add_flaky_component(
        name="Flaky", fail_count=99, error_output_enabled=True
    )
    handler = helper.add_error_handler(
        max_attempts=0,
        alert_mode="Bell",
        bell_audience="Org admins",
        name="handler",
        _spy_dispatch=False,
    )
    helper.connect(flaky, "error", handler, "error_input")
    sink_normal = helper.add_text_capture(name="sink_normal")
    helper.connect(flaky, "result", sink_normal, "input")
    sink_gave_up = helper.add_text_capture(name="sink_gave_up")
    helper.connect(handler, "gave_up", sink_gave_up, "input")

    flow_run = await helper.run()

    assert flow_run.status.value == "partial_success", (
        f"Expected partial_success, got {flow_run.status.value}"
    )

    events = helper.captured_events
    assert len(events) == 1, (
        f"Expected exactly 1 captured event, got {len(events)}: {events}"
    )

    event: UsageAlertEvent = events[0]

    assert event.category == "flow_error"
    assert event.severity == "error"
    assert event.org_id == known_org_id
    assert event.audience == NotificationAudience.PLATFORM_ADMIN
    # Org admins broadcast: no specific user_id targeted.
    assert event.audience_user_id is None, (
        f"Expected audience_user_id=None for Org admins, got {event.audience_user_id!r}"
    )
    assert "FlakyComponent" in event.title
