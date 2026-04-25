import time

import pytest, httpx, respx
from datetime import datetime, timezone
from uuid import uuid4


@pytest.fixture
async def run_with_webhook(engine_and_factory):
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org); await s.commit()
        flow = Flow(
            id=uuid4(), name="f", data={}, organization_id=org.id,
            webhook_url="https://hook.test/endpoint", webhook_secret="s3cret",
        )
        s.add(flow); await s.commit()
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id,
            triggered_by=TriggeredBy.API, status=RunStatus.SUCCEEDED,
            started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
        )
        s.add(run); await s.commit()
        await s.refresh(run)
    return run


@pytest.mark.asyncio
async def test_deliver_webhook_success(engine_and_factory, worker_ctx, run_with_webhook):
    from langflow.worker_app.webhook import deliver_webhook
    from langflow.services.database.models.flow_run.model import FlowRun

    with respx.mock:
        route = respx.post("https://hook.test/endpoint").mock(return_value=httpx.Response(200))
        await deliver_webhook(
            str(run_with_webhook.id),
            "run.succeeded",
            0,
            sessionmaker=worker_ctx["db_sessionmaker"],
            settings=worker_ctx["settings"],
            redis=worker_ctx["redis"],
        )
        assert route.called

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, run_with_webhook.id)
    assert row.webhook_delivery_state["run.succeeded"]["status"] == "delivered"
    assert row.webhook_delivery_state["run.succeeded"]["attempts"] == 1


@pytest.mark.asyncio
async def test_deliver_webhook_5xx_schedules_retry(engine_and_factory, worker_ctx, run_with_webhook):
    from langflow.worker_app.webhook import deliver_webhook
    from langflow.services.database.models.flow_run.model import FlowRun

    with respx.mock:
        respx.post("https://hook.test/endpoint").mock(return_value=httpx.Response(500))
        await deliver_webhook(
            str(run_with_webhook.id),
            "run.succeeded",
            0,
            sessionmaker=worker_ctx["db_sessionmaker"],
            settings=worker_ctx["settings"],
            redis=worker_ctx["redis"],
        )

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, run_with_webhook.id)
    assert row.webhook_delivery_state["run.succeeded"]["status"] == "retrying"
    # A retry kick was written to the delay:webhooks ZSET with the first
    # backoff step (10s) as its score offset.
    items_with_scores = await worker_ctx["redis"].zrange(
        "delay:webhooks", 0, -1, withscores=True
    )
    assert len(items_with_scores) == 1
    _, score = items_with_scores[0]
    expected_window = (time.time() + 9.5, time.time() + 11)  # 10s ± slack
    assert expected_window[0] < score < expected_window[1]


@pytest.mark.asyncio
async def test_deliver_webhook_final_attempt_fails(engine_and_factory, worker_ctx, run_with_webhook):
    from langflow.worker_app.webhook import deliver_webhook
    from langflow.services.database.models.flow_run.model import FlowRun

    with respx.mock:
        respx.post("https://hook.test/endpoint").mock(return_value=httpx.Response(500))
        # attempt=5 → attempt+1=6 == len(_BACKOFF_SCHEDULE_SEC) → no more retries
        await deliver_webhook(
            str(run_with_webhook.id),
            "run.succeeded",
            5,
            sessionmaker=worker_ctx["db_sessionmaker"],
            settings=worker_ctx["settings"],
            redis=worker_ctx["redis"],
        )

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, run_with_webhook.id)
    assert row.webhook_delivery_state["run.succeeded"]["status"] == "failed"
