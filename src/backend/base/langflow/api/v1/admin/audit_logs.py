from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from langflow.api.utils.core import PlatformAdmin
from langflow.services.database.models.audit_log import AuditAction, AuditTargetType
from langflow.services.deps import get_audit_service

router = APIRouter(tags=["Admin · Audit Logs"])


class AuditLogRead(BaseModel):
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_email: str
    actor_is_super: bool
    org_id: UUID | None
    target_type: AuditTargetType
    target_id: UUID
    action: AuditAction
    diff: dict
    diff_hash: str
    request_metadata: dict


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    size: int


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    admin: PlatformAdmin,
    org_id: Annotated[UUID | None, Query()] = None,
    actor_user_id: Annotated[UUID | None, Query()] = None,
    target_type: Annotated[AuditTargetType | None, Query()] = None,
    target_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    service = get_audit_service()
    rows, total = await service.query(
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        action=action,
        from_=from_,
        to=to,
        page=page,
        size=size,
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(r, from_attributes=True) for r in rows],
        total=total,
        page=page,
        size=size,
    )


@router.get("/audit-logs/{audit_id}", response_model=AuditLogRead)
async def get_audit_log(
    audit_id: UUID,
    admin: PlatformAdmin,
) -> AuditLogRead:
    from langflow.services.database.models.audit_log import AuditLog
    from langflow.services.deps import get_db_service

    async with get_db_service().async_session_maker() as session:
        row = await session.get(AuditLog, audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="audit log not found")
    return AuditLogRead.model_validate(row, from_attributes=True)
