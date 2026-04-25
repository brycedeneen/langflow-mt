from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from taskiq import TaskiqDepends

from lfx.log.logger import logger
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_ip_blocked,
    resolve_hostname,
)

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun
from langflow.services.runs.webhook_sign import sign_body
from langflow.worker_app.brokers import broker_webhooks
from langflow.worker_app.delayed_enqueue import schedule_delayed_kick
from langflow.worker_app.deps import get_db_sessionmaker, get_settings, get_redis


_BACKOFF_SCHEDULE_SEC = [10, 30, 120, 600, 1800, 3600]  # 6 attempts max
# Split timeouts so a tarpit endpoint can't pin the connect/pool phase.
_HTTP_TIMEOUT = httpx.Timeout(connect=2.0, read=10.0, write=10.0, pool=2.0)

# Cloud metadata hosts that must always be blocked, by name (in addition to
# IP-range checks performed by `is_ip_blocked`).
_BLOCKED_METADATA_HOSTS = frozenset(
    {"metadata.google.internal", "metadata", "metadata.goog"}
)


_REDACT_HOST_THRESHOLD = 12


def _redact_host(host: str) -> str:
    """Truncate a hostname for logging without leaking full URLs."""
    if len(host) <= _REDACT_HOST_THRESHOLD:
        return host
    return host[:6] + "..." + host[-3:]


def _validate_webhook_url(url: str, *, allow_http: bool = False) -> None:
    """Validate a webhook URL to prevent SSRF.

    Reuses primitives from `lfx.utils.ssrf_protection` (`is_ip_blocked`,
    `resolve_hostname`) rather than calling `validate_url_for_ssrf` directly,
    because that helper is gated on a global `ssrf_protection_enabled` setting
    — for outbound webhook delivery we always want to enforce the checks.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    scheme_ok = scheme == "https" or (scheme == "http" and allow_http)
    if not scheme_ok:
        msg = f"Webhook scheme {scheme!r} is not allowed (require https)"
        raise SSRFProtectionError(msg)

    hostname = parsed.hostname
    if not hostname:
        msg = "Webhook URL has no hostname"
        raise SSRFProtectionError(msg)

    host_lower = hostname.lower()
    if host_lower in _BLOCKED_METADATA_HOSTS:
        msg = f"Webhook host {host_lower!r} is a blocked metadata host"
        raise SSRFProtectionError(msg)

    # Resolve and check every IP. `is_ip_blocked` covers loopback, RFC1918,
    # link-local (incl. 169.254.169.254 AWS metadata), unspecified, multicast,
    # and IPv6 ULA / link-local / multicast.
    for ip in resolve_hostname(host_lower):
        if is_ip_blocked(ip):
            msg = f"Webhook host {host_lower!r} resolves to blocked IP {ip}"
            raise SSRFProtectionError(msg)


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

    # SSRF guard: validate the URL BEFORE issuing the request. This is a
    # permanent failure — do not retry.
    allow_http = bool(settings.webhook_allow_http)
    skip_validation = bool(getattr(settings, "webhook_skip_url_validation", False))
    try:
        if not skip_validation:
            _validate_webhook_url(flow.webhook_url, allow_http=allow_http)
    except SSRFProtectionError as exc:
        host = urlparse(flow.webhook_url).hostname or "<no-host>"
        logger.warning(
            f"[run={run_id}] webhook url blocked event={event} "
            f"host={_redact_host(host)} reason={exc}"
        )
        status_label = "failed"
        last_response = {"error": "webhook_url_blocked"}
        async with sessionmaker() as session:
            run = await session.get(FlowRun, UUID(run_id))
            if run is not None:
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
        return

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=False) as client:
            resp = await client.post(flow.webhook_url, content=body, headers=headers)
        # Bound the body read at the byte level so a malicious receiver
        # streaming gigabytes can't OOM us via `resp.text`.
        last_response = {
            "status_code": resp.status_code,
            "body": resp.content[:500].decode("utf-8", "replace"),
        }
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
