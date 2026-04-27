from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.notifier.protocol import UsageAlertEvent, UsageAlertNotifier

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from sqlmodel.ext.asyncio.session import AsyncSession


class InAppNotifier(UsageAlertNotifier):
    """Persists UsageAlertEvent into the admin_notification table, audience=super_admin."""

    def __init__(
        self,
        session_factory: "Callable[[], AbstractAsyncContextManager[AsyncSession]]",
    ) -> None:
        self._session_factory = session_factory

    async def notify(self, event: UsageAlertEvent) -> None:
        row = AdminNotification(
            org_id=event.org_id,
            category=NotificationCategory(event.category),
            severity=NotificationSeverity(event.severity),
            title=event.title,
            body_md=event.body_md,
            metadata_json=dict(event.metadata),
            audience=event.audience,
            audience_user_id=event.audience_user_id,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
