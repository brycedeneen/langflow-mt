from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, CurrentOrg, DbSession
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.deps import get_settings_service, get_redis_service
from langflow.services.runs.cancel import request_cancel
from langflow.services.runs.deps import get_arq_pool
from langflow.services.runs.enqueue import RunEnqueuer

router = APIRouter(prefix="/runs", tags=["Runs"])


class EnqueueRunRequest(BaseModel):
    flow_id: UUID
    inputs: dict[str, Any] | None = None


class EnqueueRunResponse(BaseModel):
    run_id: UUID
    status: str
    queued_at: datetime


@router.post("", status_code=status.HTTP_201_CREATED, response_model=EnqueueRunResponse)
async def enqueue_run(
    body: EnqueueRunRequest,
    session: DbSession,
    user: CurrentActiveUser,
    org: CurrentOrg,
    arq: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    settings = get_settings_service().settings
    if not settings.distributed_execution:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Distributed execution is disabled")
    enq = RunEnqueuer(db=session, redis=arq, settings=settings)
    try:
        run = await enq.enqueue(
            org_id=org.id,
            flow_id=body.flow_id,
            triggered_by=TriggeredBy.API,
            actor_id=user.id,
            inputs=body.inputs,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return EnqueueRunResponse(run_id=run.id, status=run.status.value, queued_at=run.queued_at)


class RunsListResponse(BaseModel):
    items: list[dict]
    next_cursor: str | None = None


def _serialize(r: FlowRun) -> dict:
    status = r.status.value if hasattr(r.status, "value") else r.status
    triggered_by = r.triggered_by.value if r.triggered_by and hasattr(r.triggered_by, "value") else r.triggered_by
    return {
        "id": str(r.id),
        "organization_id": str(r.organization_id),
        "flow_id": str(r.flow_id),
        "status": status,
        "triggered_by": triggered_by,
        "attempt": r.attempt,
        "cancel_requested": r.cancel_requested,
        "queued_at": r.queued_at.isoformat(),
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "result": r.result,
        "result_ref": r.result_ref,
        "error": r.error,
    }


@router.get("", response_model=RunsListResponse)
async def list_runs(
    session: DbSession,
    org: CurrentOrg,
    flow_id: UUID | None = None,
    status_filter: RunStatus | None = None,
    limit: int = 50,
    cursor: str | None = None,
):
    limit = max(1, min(limit, 200))
    stmt = select(FlowRun).where(FlowRun.organization_id == org.id)
    if flow_id:
        stmt = stmt.where(FlowRun.flow_id == flow_id)
    if status_filter:
        stmt = stmt.where(FlowRun.status == status_filter)
    if cursor:
        stmt = stmt.where(FlowRun.queued_at < datetime.fromisoformat(cursor))
    stmt = stmt.order_by(FlowRun.queued_at.desc()).limit(limit + 1)
    rows = (await session.exec(stmt)).all()
    has_more = len(rows) > limit
    rows = list(rows[:limit])
    next_cursor = rows[-1].queued_at.isoformat() if has_more and rows else None
    return RunsListResponse(items=[_serialize(r) for r in rows], next_cursor=next_cursor)


@router.get("/{run_id}", response_model=dict)
async def get_run(run_id: UUID, session: DbSession, org: CurrentOrg):
    run = await session.get(FlowRun, run_id)
    if run is None or run.organization_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return _serialize(run)


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    session: DbSession,
    org: CurrentOrg,
    redis=Depends(get_redis_service),
):
    run = await session.get(FlowRun, run_id)
    if run is None or run.organization_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    status_value = run.status.value if hasattr(run.status, "value") else run.status
    if status_value in {"succeeded", "failed", "cancelled", "timed_out"}:
        return {"status": status_value}
    run.cancel_requested = True
    await session.commit()
    await request_cancel(redis.client, run_id)
    return {"status": status_value}
