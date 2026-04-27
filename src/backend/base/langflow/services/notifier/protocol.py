from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from langflow.services.database.models.admin_notification import NotificationAudience


NotificationCategoryValue = Literal[
    "usage_threshold",
    "alert_rule",
    "system",
    "professional_services_request",
    "flow_error",
]
NotificationSeverityValue = Literal["info", "warning", "critical", "error"]


@dataclass(frozen=True)
class UsageAlertEvent:
    category: NotificationCategoryValue
    severity: NotificationSeverityValue
    org_id: UUID
    title: str
    body_md: str
    metadata: dict[str, Any]
    audience: NotificationAudience = NotificationAudience.SUPER_ADMIN
    audience_user_id: UUID | None = None


class UsageAlertNotifier(Protocol):
    """Pluggable sink for usage/alert notifications.

    Implementations must be idempotent-safe: the dispatcher may retry on
    transient failures, and a notifier raising must not block siblings.
    """

    async def notify(self, event: UsageAlertEvent) -> None: ...
