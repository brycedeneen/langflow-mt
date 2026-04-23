from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.admin_notification import (
    AdminNotification,
    NotificationCategory,
    NotificationSeverity,
)

router = APIRouter(tags=["Admin · Notifications"])


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
    admin: PlatformAdmin,
    session: DbSession,
    unread: Annotated[bool | None, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    stmt = select(AdminNotification).order_by(AdminNotification.created_at.desc())
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
    total_stmt = select(AdminNotification)
    if unread:
        total_stmt = total_stmt.where(AdminNotification.read_at.is_(None))
    total = len((await session.exec(total_stmt)).all())
    return NotificationListResponse(items=items, total=total)


@router.get("/notifications/unread-count")
async def unread_count(
    admin: PlatformAdmin,
    session: DbSession,
) -> dict[str, int]:
    rows = (
        await session.exec(
            select(AdminNotification).where(AdminNotification.read_at.is_(None))
        )
    ).all()
    return {"unread": len(rows)}


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: UUID,
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    row = await session.get(AdminNotification, notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        row.read_by_user_id = admin.id
        session.add(row)
        await session.commit()


@router.post("/notifications/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    admin: PlatformAdmin,
    session: DbSession,
) -> None:
    now = datetime.now(timezone.utc)
    rows = (
        await session.exec(
            select(AdminNotification).where(AdminNotification.read_at.is_(None))
        )
    ).all()
    for r in rows:
        r.read_at = now
        r.read_by_user_id = admin.id
        session.add(r)
    await session.commit()
