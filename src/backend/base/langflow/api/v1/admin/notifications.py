from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)

router = APIRouter(tags=["Admin · Notifications"])


def _visible_clause(user) -> Any:
    """Build a SQL clause selecting AdminNotification rows visible to ``user``.

    Visibility rules:
      * Rows directly targeted at the user (``audience_user_id == user.id``)
        are always visible regardless of role.
      * Broadcast rows (``audience_user_id IS NULL``) are visible only when
        the user holds the matching role: super-admin sees ``SUPER_ADMIN``
        rows, platform-admin sees ``PLATFORM_ADMIN`` rows. A user who is
        both sees both.
    """
    clauses: list[Any] = [AdminNotification.audience_user_id == user.id]
    audiences: list[NotificationAudience] = []
    if user.is_superuser:
        audiences.append(NotificationAudience.SUPER_ADMIN)
    if user.is_platform_admin:
        audiences.append(NotificationAudience.PLATFORM_ADMIN)
    if audiences:
        clauses.append(
            (AdminNotification.audience.in_([a.value for a in audiences]))
            & (AdminNotification.audience_user_id.is_(None))
        )
    return or_(*clauses)


class NotificationRead(BaseModel):
    id: UUID
    org_id: UUID | None
    category: NotificationCategory
    severity: NotificationSeverity
    title: str
    body_md: str
    metadata: dict
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user: CurrentActiveUser,
    session: DbSession,
    unread: Annotated[bool | None, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    visible = _visible_clause(user)
    stmt = select(AdminNotification).where(visible).order_by(AdminNotification.created_at.desc())
    if unread:
        stmt = stmt.where(AdminNotification.read_at.is_(None))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.exec(stmt)).all()
    items = [
        NotificationRead(
            id=r.id,
            org_id=r.org_id,
            category=r.category,
            severity=r.severity,
            title=r.title,
            body_md=r.body_md,
            metadata=r.metadata_json,
            created_at=r.created_at,
            read_at=r.read_at,
        )
        for r in rows
    ]
    total_stmt = select(AdminNotification).where(visible)
    if unread:
        total_stmt = total_stmt.where(AdminNotification.read_at.is_(None))
    total = len((await session.exec(total_stmt)).all())
    return NotificationListResponse(items=items, total=total)


@router.get("/notifications/unread-count")
async def unread_count(
    user: CurrentActiveUser,
    session: DbSession,
) -> dict[str, int]:
    rows = (
        await session.exec(
            select(AdminNotification)
            .where(_visible_clause(user))
            .where(AdminNotification.read_at.is_(None))
        )
    ).all()
    return {"unread": len(rows)}


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> None:
    # Fetch via the visibility clause so we never leak existence of rows the
    # caller cannot see (e.g. another user's targeted row, or a role-broadcast
    # the caller's role doesn't include).
    row = (
        await session.exec(
            select(AdminNotification)
            .where(AdminNotification.id == notification_id)
            .where(_visible_clause(user))
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        row.read_by_user_id = user.id
        session.add(row)
        await session.commit()


@router.post("/notifications/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    user: CurrentActiveUser,
    session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    rows = (
        await session.exec(
            select(AdminNotification)
            .where(_visible_clause(user))
            .where(AdminNotification.read_at.is_(None))
        )
    ).all()
    for r in rows:
        r.read_at = now
        r.read_by_user_id = user.id
        session.add(r)
    await session.commit()
