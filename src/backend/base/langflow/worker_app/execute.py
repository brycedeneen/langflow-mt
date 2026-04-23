from __future__ import annotations
import asyncio
import os
import socket
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from lfx.log.logger import logger

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
from langflow.services.database.models.organization.model import Organization
from langflow.services.runs.concurrency import OrgConcurrency
from langflow.services.runs.cancel import is_cancel_requested
from langflow.services.runs.payload import PayloadOffloader
from langflow.worker_app.log_sink import RunLogSink


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
HEARTBEAT_INTERVAL = 15.0
CANCEL_POLL_INTERVAL = 2.0
REQUEUE_DELAY = 5.0

# Avoid circular import by duplicating the tier map (same as enqueue._TIER_TO_QUEUE_ATTR)
_TIER_TO_QUEUE_ATTR = {"high": "arq_high_queue", "default": "arq_default_queue", "low": "arq_low_queue"}


async def execute_run(ctx: dict[str, Any], run_id: str) -> None:
    run_uuid = UUID(run_id)
    redis = ctx["redis"]
    session_factory = ctx["db_sessionmaker"]
    storage = ctx["storage"]
    settings = ctx["settings"]
    arq = ctx["arq"]
    graph_runner = ctx.get("graph_runner")  # injection hook for tests

    logger.info(f"[run={run_id}] worker picked up job (worker_id={WORKER_ID})")

    offloader = PayloadOffloader(storage, inline_max_bytes=settings.run_payload_inline_max_bytes)
    concurrency = OrgConcurrency(redis)

    async with session_factory() as session:
        run = await session.get(FlowRun, run_uuid)
        if run is None:
            logger.warning(f"[run={run_id}] FlowRun not found; dropping job")
            return
        if _status_str(run.status) != "queued":
            logger.warning(
                f"[run={run_id}] status={_status_str(run.status)} is not 'queued'; dropping job (duplicate delivery?)"
            )
            return
        org = await session.get(Organization, run.organization_id)
        flow = await session.get(Flow, run.flow_id)
        if org is None or flow is None:
            logger.error(
                f"[run={run_id}] missing org={run.organization_id} or flow={run.flow_id}; dropping job"
            )
            return

        acquired = await concurrency.try_acquire(org.id, limit=org.runs_max_concurrent)
        if not acquired:
            queue = getattr(settings, _TIER_TO_QUEUE_ATTR[org.runs_priority_tier])
            logger.info(
                f"[run={run_id}] org={org.id} at concurrency cap "
                f"(limit={org.runs_max_concurrent}); requeueing to {queue} in {REQUEUE_DELAY}s"
            )
            await arq.enqueue_job("execute_run", run_id, _queue_name=queue, _defer_by=REQUEUE_DELAY)
            return

        run.status = RunStatus.RUNNING
        run.worker_id = WORKER_ID
        run.started_at = datetime.now(timezone.utc)
        run.heartbeat_at = run.started_at
        await session.commit()
        logger.info(
            f"[run={run_id}] RUNNING flow={flow.id} ({flow.name!r}) org={org.id} "
            f"trigger={_status_str(run.triggered_by)} attempt={run.attempt}"
        )

        org_id_captured = org.id
        from langflow.services.runs.metrics import ACTIVE_RUNS
        ACTIVE_RUNS.labels(organization_id=str(org.id)).inc()
        flow_captured = flow
        triggered_by_captured = _status_str(run.triggered_by)
        actor_id_captured = run.actor_id
        inputs = run.inputs
        inputs_ref = run.inputs_ref
        timeout_s = run.timeout_seconds
        session.expunge(flow_captured)

    if inputs_ref:
        inputs = await offloader.load(inputs_ref)

    await _emit_webhook(arq, settings, run_uuid, "run.started")

    sink = RunLogSink(session_factory=session_factory, run_id=run_uuid)
    await sink.start()

    stop_event = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat(session_factory, run_uuid, stop_event))
    cancel_event = asyncio.Event()
    cancel_task = asyncio.create_task(_cancel_watcher(redis, run_uuid, cancel_event, stop_event))

    result_payload: Any = None
    error_payload: dict | None = None
    terminal: RunStatus = RunStatus.FAILED

    try:
        runner = graph_runner or _default_runner
        execution = asyncio.create_task(runner(flow_captured, triggered_by_captured, inputs, actor_id_captured))
        cancel_waiter = asyncio.create_task(cancel_event.wait())

        try:
            done, pending = await asyncio.wait(
                {execution, cancel_waiter}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            cancel_waiter.cancel()

        if cancel_event.is_set():
            execution.cancel()
            with _suppress():
                await execution
            terminal = RunStatus.CANCELLED
            logger.info(f"[run={run_id}] CANCELLED by user request")
        elif execution in done:
            result_payload = execution.result()
            terminal = RunStatus.SUCCEEDED
            logger.info(f"[run={run_id}] SUCCEEDED")
        else:
            execution.cancel()
            with _suppress():
                await execution
            terminal = RunStatus.TIMED_OUT
            error_payload = {"type": "timeout", "message": f"exceeded {timeout_s}s"}
            logger.warning(f"[run={run_id}] TIMED_OUT after {timeout_s}s")

    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        terminal = RunStatus.FAILED
        error_payload = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=20),
        }
        logger.exception(
            f"[run={run_id}] FAILED flow={flow_captured.id} trigger={triggered_by_captured}: "
            f"{type(exc).__name__}: {exc}"
        )
    finally:
        stop_event.set()
        for t in (hb_task, cancel_task):
            with _suppress():
                await t
        await sink.stop()

    async with session_factory() as session:
        run = await session.get(FlowRun, run_uuid)
        run.status = terminal
        run.finished_at = datetime.now(timezone.utc)
        if result_payload is not None:
            inline, ref = await offloader.store(run_uuid, "result", _jsonable(result_payload))
            run.result = inline
            run.result_ref = ref
        if error_payload is not None:
            run.error = error_payload
        await session.commit()

        from langflow.services.runs.metrics import ACTIVE_RUNS, RUN_DURATION, RUNS_TOTAL
        terminal_label = terminal.value if hasattr(terminal, "value") else str(terminal)
        flow_label = str(flow_captured.id)
        RUNS_TOTAL.labels(status=terminal_label, flow_id=flow_label).inc()
        if run.started_at and run.finished_at:
            # Normalise both timestamps to UTC-aware before subtracting; SQLite may
            # return naive datetimes even when stored as UTC.
            started = run.started_at
            finished = run.finished_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            duration = (finished - started).total_seconds()
            RUN_DURATION.labels(status=terminal_label, flow_id=flow_label).observe(duration)
        ACTIVE_RUNS.labels(organization_id=str(org_id_captured)).dec()

        # Metering + threshold/alert eval (kill-switch: settings.metering_enabled).
        try:
            from langflow.services.deps import get_settings_service, get_usage_alert_dispatcher
            if get_settings_service().settings.metering_enabled:
                from langflow.services.metering import record_run_completion_and_eval
                dispatcher = get_usage_alert_dispatcher()
                await record_run_completion_and_eval(session, run=run, dispatcher=dispatcher)
                await session.commit()
        except Exception:  # noqa: BLE001
            # Never let metering break run completion. Log and move on.
            logger.exception(f"[run={run_uuid}] metering post-commit failed")

    await concurrency.release(org_id_captured)

    event_map = {
        RunStatus.SUCCEEDED: "run.succeeded",
        RunStatus.FAILED: "run.failed",
        RunStatus.CANCELLED: "run.cancelled",
        RunStatus.TIMED_OUT: "run.timed_out",
    }
    await _emit_webhook(arq, settings, run_uuid, event_map[terminal])

    if terminal in {RunStatus.FAILED, RunStatus.TIMED_OUT}:
        async with session_factory() as session:
            run = await session.get(FlowRun, run_uuid)
            if run.auto_retry and run.attempt < run.max_retries:
                run.attempt += 1
                run.status = RunStatus.QUEUED
                run.started_at = None
                run.finished_at = None
                run.error = None
                run.result = None
                run.result_ref = None
                run.worker_id = None
                await session.commit()
                backoff = min(30 * (2 ** (run.attempt - 1)), 1800)
                org = await session.get(Organization, run.organization_id)
                queue = getattr(settings, _TIER_TO_QUEUE_ATTR[org.runs_priority_tier])
                await arq.enqueue_job("execute_run", run_id, _queue_name=queue, _defer_by=backoff)
                logger.info(
                    f"[run={run_id}] auto-retry attempt={run.attempt}/{run.max_retries} "
                    f"requeued to {queue} in {backoff}s"
                )


_SIMPLE_API_REQUEST_FIELDS = {"input_value", "input_type", "output_type", "output_component", "tweaks", "session_id"}


def _build_input_request(triggered_by: str, inputs: Any, flow: Flow):
    """Translate a FlowRun.inputs payload into a SimplifiedAPIRequest.

    All trigger types converge on `simple_run_flow`. Each trigger has its own input
    shape; this function normalises them.

    - webhook: inputs is `{"body": <raw webhook body>}`. The body is broadcast to every
      Webhook component in the flow as a tweak `{"data": body}`; input_value is empty.
    - api / schedule / mcp: inputs is a dict with SimplifiedAPIRequest-compatible keys
      (input_value, input_type, output_type, tweaks, session_id, output_component).
      Unknown keys are ignored; missing keys fall back to defaults. `None` is accepted.
    """
    from langflow.api.v1.schemas import SimplifiedAPIRequest
    from langflow.services.database.models.flow.utils import get_all_webhook_components_in_flow

    if triggered_by == "webhook":
        body = None
        if isinstance(inputs, dict):
            body = inputs.get("body")
        tweaks: dict[str, Any] = {}
        for component in get_all_webhook_components_in_flow(flow.data):
            tweaks[component["id"]] = {"data": body}
        return SimplifiedAPIRequest(
            input_value="",
            input_type="chat",
            output_type="chat",
            tweaks=tweaks,
            session_id=None,
        )

    # api / schedule / mcp — accept a SimplifiedAPIRequest-shaped dict with defaults.
    payload = inputs if isinstance(inputs, dict) else {}
    filtered = {k: v for k, v in payload.items() if k in _SIMPLE_API_REQUEST_FIELDS}
    return SimplifiedAPIRequest(**filtered)


async def _default_runner(flow: Flow, triggered_by: str, inputs: Any, actor_id: UUID | None):
    """Execute a Langflow flow for a queued run via `simple_run_flow`.

    All trigger types go through the same shared code path as the in-process webhook/API
    handlers, so distributed and in-process behaviour cannot drift.
    """
    from langflow.api.v1.endpoints import simple_run_flow

    input_request = _build_input_request(triggered_by, inputs, flow)
    api_key_user = _ActorStub(actor_id) if actor_id else None
    logger.debug(
        f"[flow={flow.id}] dispatching trigger={triggered_by} "
        f"input_value={'<set>' if input_request.input_value else '<empty>'} "
        f"tweaks={len(input_request.tweaks.root if input_request.tweaks else {})}"
    )
    response = await simple_run_flow(flow=flow, input_request=input_request, api_key_user=api_key_user)
    return response.model_dump()


class _ActorStub:
    """Minimal user-like object carrying only `.id`, for simple_run_flow."""

    __slots__ = ("id",)

    def __init__(self, user_id: UUID) -> None:
        self.id = user_id


async def _heartbeat(session_factory, run_id: UUID, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
        except asyncio.TimeoutError:
            pass
        async with session_factory() as s:
            run = await s.get(FlowRun, run_id)
            if run is None or _status_str(run.status) != "running":
                return
            run.heartbeat_at = datetime.now(timezone.utc)
            await s.commit()


async def _cancel_watcher(redis, run_id: UUID, cancel_event: asyncio.Event, stop: asyncio.Event) -> None:
    while not stop.is_set():
        if await is_cancel_requested(redis, run_id):
            cancel_event.set()
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=CANCEL_POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass


async def _emit_webhook(arq, settings, run_id: UUID, event: str) -> None:
    await arq.enqueue_job(
        "deliver_webhook", str(run_id), event, _queue_name=settings.arq_webhooks_queue,
    )


def _jsonable(obj: Any) -> Any:
    from fastapi.encoders import jsonable_encoder
    return jsonable_encoder(obj)


def _status_str(s) -> str:
    return s.value if hasattr(s, "value") else str(s)


@contextmanager
def _suppress():
    try:
        yield
    except BaseException:
        pass
