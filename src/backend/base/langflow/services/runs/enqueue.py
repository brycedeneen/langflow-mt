from __future__ import annotations

from uuid import UUID
from typing import Any

from arq.connections import ArqRedis
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.organization.model import Organization
from lfx.services.settings.base import Settings


_TIER_TO_QUEUE_ATTR = {
    "high": "queue_high",
    "default": "queue_default",
    "low": "queue_low",
}
_TIER_TO_PRIORITY = {"high": 1, "default": 5, "low": 9}


class RunEnqueuer:
    def __init__(self, *, db: AsyncSession, redis: ArqRedis, settings: Settings):
        self.db = db
        self.redis = redis
        self.settings = settings

    async def enqueue(
        self,
        *,
        org_id: UUID,
        flow_id: UUID,
        triggered_by: TriggeredBy,
        actor_id: UUID | None,
        inputs: dict[str, Any] | None,
    ) -> FlowRun:
        org = await self.db.get(Organization, org_id)
        flow = await self.db.get(Flow, flow_id)
        if org is None or flow is None or flow.organization_id != org_id:
            raise ValueError("org/flow mismatch")

        run = FlowRun(
            organization_id=org_id,
            flow_id=flow_id,
            triggered_by=triggered_by,
            actor_id=actor_id,
            status=RunStatus.QUEUED,
            priority=_TIER_TO_PRIORITY[org.runs_priority_tier],
            inputs=inputs,
            auto_retry=flow.auto_retry,
            max_retries=flow.max_retries,
            timeout_seconds=flow.timeout_seconds,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        queue_attr = _TIER_TO_QUEUE_ATTR[org.runs_priority_tier]
        queue_name = getattr(self.settings, queue_attr)
        await self.redis.enqueue_job("execute_run", str(run.id), _queue_name=queue_name)
        return run
