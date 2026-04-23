from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.notifier.in_app import InAppNotifier
from langflow.services.notifier.protocol import UsageAlertEvent


@pytest.mark.asyncio
async def test_in_app_notifier_writes_admin_notification_row(session_factory):
    notifier = InAppNotifier(session_factory)
    org_id = uuid4()
    event = UsageAlertEvent(
        category="usage_threshold",
        severity="warning",
        org_id=org_id,
        title="Daily tokens exceeded 10000",
        body_md="Your org crossed the **10000 tokens/day** threshold.",
        metadata={"threshold_id": str(uuid4()), "metric": "tokens", "value": 10050},
    )

    await notifier.notify(event)

    async with session_factory() as session:
        rows = (await session.exec(select(AdminNotification))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.org_id == org_id
    assert row.category == NotificationCategory.USAGE_THRESHOLD
    assert row.severity == NotificationSeverity.WARNING
    assert row.audience == NotificationAudience.SUPER_ADMIN
    assert row.title == event.title
    assert row.body_md == event.body_md
    assert row.metadata_json["metric"] == "tokens"
    assert row.read_at is None
