from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
)
from langflow.services.notifier.in_app import InAppNotifier
from langflow.services.notifier.protocol import UsageAlertEvent


@pytest.mark.asyncio
async def test_in_app_notifier_uses_event_audience(session_factory):
    notifier = InAppNotifier(session_factory)
    user_id = uuid4()
    event = UsageAlertEvent(
        category="flow_error",
        severity="error",
        org_id=uuid4(),
        title="t",
        body_md="b",
        metadata={},
        audience=NotificationAudience.PLATFORM_ADMIN,
        audience_user_id=user_id,
    )
    await notifier.notify(event)
    async with session_factory() as s:
        rows = (await s.exec(select(AdminNotification))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.audience == NotificationAudience.PLATFORM_ADMIN
    assert row.audience_user_id == user_id
    assert row.category == NotificationCategory.FLOW_ERROR


@pytest.mark.asyncio
async def test_in_app_notifier_defaults_audience_to_super_admin(session_factory):
    """Unset audience falls back to legacy SUPER_ADMIN for compatibility."""
    notifier = InAppNotifier(session_factory)
    event = UsageAlertEvent(
        category="usage_threshold",
        severity="warning",
        org_id=uuid4(),
        title="t",
        body_md="b",
        metadata={},
    )
    await notifier.notify(event)
    async with session_factory() as s:
        rows = (await s.exec(select(AdminNotification))).all()
    assert len(rows) == 1
    assert rows[0].audience == NotificationAudience.SUPER_ADMIN
    assert rows[0].audience_user_id is None
