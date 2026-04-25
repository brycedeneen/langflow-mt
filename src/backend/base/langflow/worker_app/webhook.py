from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from taskiq import TaskiqDepends

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun
from langflow.services.runs.webhook_sign import sign_body
from langflow.worker_app.brokers import broker_webhooks
from langflow.worker_app.delayed_enqueue import schedule_delayed_kick
from langflow.worker_app.deps import get_db_sessionmaker, get_settings, get_redis


_BACKOFF_SCHEDULE_SEC = [10, 30, 120, 600, 1800, 3600]  # 6 attempts max
_HTTP_TIMEOUT = httpx.Timeout(10.0)


def _build_payload(run: FlowRun, event: str) -> dict[str, Any]:
    status = run.status.value if hasattr(run.status, "value") else run.status
    return {
        "event": event,
        "run_id": str(run.id),
        "flow_id": str(run.flow_id),
        "organization_id": str(run.organization_id),
        "status": status,
        "inputs": run.inputs,
        "inputs_ref": run.inputs_ref,
        "result": run.result,
        "result_ref": run.result_ref,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "attempt": run.attempt,
    }


@broker_webhooks.task(task_name="deliver_webhook")
async def deliver_webhook(
    run_id: str,
    event: str,
    attempt: int = 0,
    *,
    sessionmaker=TaskiqDepends(get_db_sessionmaker),
    settings=TaskiqDepends(get_settings),
    redis: Redis = TaskiqDepends(get_redis),
) -> None:
    async with sessionmaker() as session:
        run = await session.get(FlowRun, UUID(run_id))
        if run is None:
            return
        flow = await session.get(Flow, run.flow_id)
        if flow is None or not flow.webhook_url or not flow.webhook_secret:
            return
        payload = _build_payload(run, event)

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Langflow-Event": event,
        "X-Langflow-Delivery": str(uuid4()),
        "X-Langflow-Timestamp": datetime.now(timezone.utc).isoformat(),
        "X-Langflow-Signature": sign_body(body, flow.webhook_secret),
    }

    status_label: str
    last_response: dict[str, Any] | None = None
    should_retry = False
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(flow.webhook_url, content=body, headers=headers)
        last_response = {"status_code": resp.status_code, "body": resp.text[:500]}
        if 200 <= resp.status_code < 300:
            status_label = "delivered"
        elif resp.status_code == 429 or 500 <= resp.status_code < 600:
            status_label = "retrying"
            should_retry = True
        else:
            status_label = "failed"
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        last_response = {"error": str(exc)[:500]}
        status_label = "retrying"
        should_retry = True

    if should_retry and attempt + 1 >= len(_BACKOFF_SCHEDULE_SEC):
        status_label = "failed"
        should_retry = False

    async with sessionmaker() as session:
        run = await session.get(FlowRun, UUID(run_id))
        if run is None:
            return
        state = dict(run.webhook_delivery_state or {})
        state[event] = {
            "status": status_label,
            "attempts": attempt + 1,
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            "last_response": last_response,
        }
        run.webhook_delivery_state = state
        await session.commit()

    from langflow.services.runs.metrics import WEBHOOK_DELIVERY_TOTAL
    WEBHOOK_DELIVERY_TOTAL.labels(event=event, status=status_label).inc()

    if should_retry:
        delay = _BACKOFF_SCHEDULE_SEC[attempt]
        await schedule_delayed_kick(
            redis=redis,
            task_name="deliver_webhook",
            queue_name="webhooks",
            args=[run_id, event, attempt + 1],
            delay_s=delay,
        )
