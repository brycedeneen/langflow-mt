from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from langflow.api.utils.core import CurrentActiveUser, CurrentOrg, DbSession
from langflow.services.database.models.flow_run.model import TriggeredBy
from langflow.services.deps import get_settings_service
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
