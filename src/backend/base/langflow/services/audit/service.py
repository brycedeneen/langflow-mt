from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger

from langflow.services.audit.diff import compute_diff_hash, truncate_diff
from langflow.services.base import Service
from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass
class AuditLogEntry:
    actor_user_id: UUID | None
    actor_email: str
    actor_is_super: bool
    org_id: UUID | None
    target_type: AuditTargetType
    target_id: UUID
    action: AuditAction
    diff: dict[str, Any]
    request_metadata: dict[str, Any]


class AuditService(Service):
    name = "audit_service"

    def __init__(
        self,
        session_factory: "Callable[[], AbstractAsyncContextManager[AsyncSession]] | None" = None,
    ) -> None:
        self._session_factory = session_factory

    def _get_session_factory(self):
        """Return the session factory, always resolving the current db service."""
        if self._session_factory is not None:
            return self._session_factory
        from langflow.services.deps import get_db_service
        return get_db_service().async_session_maker

    async def record_batch(self, entries: list[AuditLogEntry]) -> None:
        if not entries:
            return
        try:
            async with self._get_session_factory()() as session:
                for e in entries:
                    diff_capped = truncate_diff(e.diff)
                    row = AuditLog(
                        occurred_at=datetime.now(timezone.utc),
                        actor_user_id=e.actor_user_id,
                        actor_email=e.actor_email,
                        actor_is_super=e.actor_is_super,
                        org_id=e.org_id,
                        target_type=e.target_type,
                        target_id=e.target_id,
                        action=e.action,
                        diff=diff_capped,
                        diff_hash=compute_diff_hash(diff_capped),
                        request_metadata=e.request_metadata,
                    )
                    session.add(row)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("audit_write_failed entries=%d: %s", len(entries), exc)

    async def query(
        self,
        *,
        org_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        target_type: AuditTargetType | None = None,
        target_id: UUID | None = None,
        action: AuditAction | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        from sqlmodel import select

        async with self._get_session_factory()() as session:
            stmt = select(AuditLog)
            if org_id is not None:
                stmt = stmt.where(AuditLog.org_id == org_id)
            if actor_user_id is not None:
                stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
            if target_type is not None:
                stmt = stmt.where(AuditLog.target_type == target_type)
            if target_id is not None:
                stmt = stmt.where(AuditLog.target_id == target_id)
            if action is not None:
                stmt = stmt.where(AuditLog.action == action)
            if from_ is not None:
                stmt = stmt.where(AuditLog.occurred_at >= from_)
            if to is not None:
                stmt = stmt.where(AuditLog.occurred_at <= to)

            all_rows = (await session.exec(stmt.order_by(AuditLog.occurred_at.desc()))).all()
            total = len(all_rows)
            start = (page - 1) * size
            return all_rows[start : start + size], total
