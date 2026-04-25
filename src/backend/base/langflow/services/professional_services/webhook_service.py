"""Webhook delivery for pro-service-quote.submitted events.

Synchronous best-effort dispatch invoked by the submit handler **after** the
DB commit. Failures are logged at WARNING and otherwise silent — the in-product
quote row is the source of truth, and v1 explicitly does not retry.

Key safety properties:

- The org/admin notes are **never** included in the payload. Receivers may
  persist payloads in less-trusted places (Slack/email/log aggregators), and
  the spec says only the LLM-redacted ``headline_summary`` / ``narrative`` /
  ``conversation_summary`` fields go through.
- Body is canonical JSON (no spaces) so HMAC-SHA256 stays deterministic.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.pro_service_quote.model import ProServiceQuote
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.database.models.user.model import User
from langflow.services.runs.webhook_sign import sign_body

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(10.0)


def _decrypt_secret(enc: str) -> str:
    """Return the webhook secret in plaintext.

    TODO Phase C.3: wire the encryption helper that the admin-settings PUT
    handler uses on write. For v1 the column stores plaintext (the field is
    named ``webhook_secret_encrypted`` to reserve room for the upgrade
    without a column rename).
    """
    return enc


def build_webhook_payload(
    quote: ProServiceQuote,
    *,
    base_url: str,
    org_name: str,
    requester_label: str,
) -> dict[str, Any]:
    """Build the JSON-serializable webhook body for a submitted quote.

    Notes fields (``org_notes``, ``admin_notes``) are deliberately omitted.
    """
    flow_url = f"{base_url}/flow/{quote.flow_id}" if (base_url and quote.flow_id) else None
    return {
        "event": "pro_service_quote.submitted",
        "quote_id": str(quote.id),
        "org": {"id": str(quote.org_id), "name": org_name},
        "flow": {
            "id": str(quote.flow_id) if quote.flow_id else None,
            "url": flow_url,
        },
        "requester": {
            "id": str(quote.requester_user_id),
            "email": requester_label,
        },
        "estimate": {
            "minutes_low": quote.estimated_minutes_low,
            "minutes_high": quote.estimated_minutes_high,
            "rate_low_per_hour": (
                float(quote.rate_low_per_hour) if quote.rate_low_per_hour is not None else None
            ),
            "rate_high_per_hour": (
                float(quote.rate_high_per_hour) if quote.rate_high_per_hour is not None else None
            ),
            "currency": "USD",
        },
        "headline_summary": quote.headline_summary,
        "narrative": quote.narrative,
        "conversation_summary": quote.conversation_summary,
    }


async def deliver_quote_webhook(
    *,
    settings_row: ProfessionalServicesSettings,
    quote: ProServiceQuote,
    org: Organization | None,
    requester: User | None,
    base_url: str,
) -> None:
    """POST the HMAC-signed payload to the configured webhook URL.

    No-op when ``webhook_url`` or ``webhook_secret_encrypted`` is unset.
    Network failures are caught and logged at WARNING — never re-raised.
    """
    if not settings_row.webhook_url or not settings_row.webhook_secret_encrypted:
        return

    secret = _decrypt_secret(settings_row.webhook_secret_encrypted)
    requester_label = ""
    if requester is not None:
        requester_label = (
            getattr(requester, "email", None)
            or getattr(requester, "username", None)
            or ""
        )
    body = build_webhook_payload(
        quote,
        base_url=base_url,
        org_name=org.name if org else "",
        requester_label=requester_label,
    )
    payload_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Langflow-Event": "pro_service_quote.submitted",
        "X-Langflow-Delivery": str(uuid4()),
        "X-Langflow-Timestamp": datetime.now(timezone.utc).isoformat(),
        "X-Langflow-Signature": sign_body(payload_bytes, secret),
    }
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            await client.post(
                settings_row.webhook_url, content=payload_bytes, headers=headers
            )
    except (
        httpx.TimeoutException,
        httpx.TransportError,
    ) as exc:  # broad: includes ConnectError
        logger.warning(
            "pro_service_quote_webhook_delivery_failed quote_id=%s err=%s",
            quote.id,
            exc,
        )


def fire_quote_webhook(*, quote_id: UUID, base_url: str) -> None:  # noqa: ARG001
    """Legacy entry point retained for the route handler — kept as a no-op shim.

    The actual submit handler now invokes ``deliver_quote_webhook`` directly
    with already-loaded entities so we don't re-query inside the webhook layer.
    """
    return None
