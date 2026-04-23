from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.base import Service
from langflow.services.factory import ServiceFactory
from langflow.services.notifier.dispatcher import UsageAlertDispatcher
from langflow.services.notifier.in_app import InAppNotifier

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


class _UsageAlertDispatcherService(UsageAlertDispatcher, Service):
    """Thin Service wrapper around UsageAlertDispatcher for the service manager."""

    name = "usage_alert_dispatcher"

    def __init__(self, notifiers) -> None:
        UsageAlertDispatcher.__init__(self, notifiers)


class UsageAlertDispatcherFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(_UsageAlertDispatcherService)

    @override
    def create(self, database_service: "DatabaseService") -> _UsageAlertDispatcherService:
        # v1: only InAppNotifier. Future notifiers are added here, gated on settings.
        notifiers = [InAppNotifier(database_service.async_session_maker)]
        return _UsageAlertDispatcherService(notifiers)
