from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from langflow.api.utils.authz import assert_org_role
from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.api.v1.admin.audit_logs import AuditLogListResponse, AuditLogRead
from langflow.services.database.models.audit_log.model import AuditAction, AuditTargetType
from langflow.services.database.models.membership.model import MembershipRole
from langflow.services.deps import get_audit_service

router = APIRouter(tags=["AuditLogs"])


@router.get("/orgs/{org_id}/audit-logs", response_model=AuditLogListResponse)
async def list_org_audit_logs(
    *,
    session: DbSession,
    org_id: UUID,
    current_user: CurrentActiveUser,
    actor_user_id: Annotated[UUID | None, Query()] = None,
    target_type: Annotated[AuditTargetType | None, Query()] = None,
    target_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    """List audit log entries scoped to a single organization (Admin+ in that org).

    The endpoint forces ``org_id={org_id}`` server-side, ignoring any client-provided
    overrides, so callers cannot exfiltrate other orgs' audit entries.
    """
    await assert_org_role(current_user, org_id, MembershipRole.ADMIN, session=session)

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
