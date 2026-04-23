from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID


NotificationCategoryValue = Literal["usage_threshold", "alert_rule"]
NotificationSeverityValue = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class UsageAlertEvent:
    category: NotificationCategoryValue
    severity: NotificationSeverityValue
    org_id: UUID
    title: str
    body_md: str
    metadata: dict[str, Any]


class UsageAlertNotifier(Protocol):
    """Pluggable sink for usage/alert notifications.

    Implementations must be idempotent-safe: the dispatcher may retry on
    transient failures, and a notifier raising must not block siblings.
    """

    async def notify(self, event: UsageAlertEvent) -> None: ...
