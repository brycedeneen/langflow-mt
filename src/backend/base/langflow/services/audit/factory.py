from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.audit.service import AuditService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


class AuditServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(AuditService)

    @override
    def create(self, database_service: "DatabaseService") -> AuditService:  # noqa: ARG002
        # Pass None so AuditService always resolves the current db service's session maker
        # at call time rather than caching a potentially stale reference.
        return AuditService(None)
