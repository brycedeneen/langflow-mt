from __future__ import annotations

import asyncio

from lfx.log.logger import logger

from langflow.services.notifier.protocol import UsageAlertEvent, UsageAlertNotifier


class UsageAlertDispatcher:
    """Fan-out dispatcher. A failing notifier is logged but does not block siblings."""

    def __init__(self, notifiers: list[UsageAlertNotifier]) -> None:
        self._notifiers = list(notifiers)

    async def dispatch(self, event: UsageAlertEvent) -> None:
        if not self._notifiers:
            return
        results = await asyncio.gather(
            *(self._safe_notify(n, event) for n in self._notifiers),
            return_exceptions=False,  # _safe_notify swallows
        )
        del results  # kept for future metrics hook

    @staticmethod
    async def _safe_notify(notifier: UsageAlertNotifier, event: UsageAlertEvent) -> None:
        try:
            await notifier.notify(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "notifier=%s failed on event.category=%s org_id=%s: %s",
                type(notifier).__name__,
                event.category,
                event.org_id,
                exc,
            )
