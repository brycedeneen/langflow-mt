from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from taskiq import AsyncBroker

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.organization.model import Organization
from lfx.services.settings.base import Settings


_TIER_TO_PRIORITY = {"high": 1, "default": 5, "low": 9}


class RunEnqueuer:
    def __init__(
        self,
        *,
        db: AsyncSession,
        brokers: Mapping[str, AsyncBroker],
        settings: Settings,
    ):
        self.db = db
        self.brokers = brokers
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
        # Lazy import: avoids module-load cycles between the API enqueuer and
        # the worker_app task module (the latter imports the broker registry,
        # which itself touches Settings).
        from langflow.worker_app.execute import execute_run

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

        broker = self.brokers[org.runs_priority_tier]
        await execute_run.kicker().with_broker(broker).kiq(str(run.id))
        return run
