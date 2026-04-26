"""Super-admin settings endpoints for the Pro-Service Quotes feature.

Phase C.3 (Task 15) of the Pro-Service Quotes plan. The settings row is the
global singleton at ``professional_services_settings.id=1``: default rate
band, optional outbound webhook URL, and an HMAC secret for signing webhook
bodies.

Gating: ``is_superuser`` only — these are global infra controls, not
per-platform settings, so a platform admin without the superuser bit cannot
read or mutate them. Webhook secrets are stored Fernet-encrypted via the
existing ``encrypt_api_key`` helper (despite the name, it is a general
string-encryption utility); the plaintext is never returned by GET.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.auth.utils import decrypt_api_key, encrypt_api_key
from langflow.services.professional_services.settings_service import (
    read_settings_singleton_async,
)
from langflow.services.runs.webhook_sign import sign_body

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin · Professional Services"])

_HTTP_TIMEOUT = httpx.Timeout(10.0)


class SettingsRead(BaseModel):
    """Public shape of the settings singleton.

    ``has_webhook_secret`` is a boolean flag — the plaintext secret is never
    returned over the wire. Callers that want to rotate the secret PUT a new
    value; the only signal that a secret is set is this flag.
    """

    default_hourly_rate_low: Decimal | None
    default_hourly_rate_high: Decimal | None
    webhook_url: str | None
    has_webhook_secret: bool


class SettingsWrite(BaseModel):
    """Partial-update payload — all fields optional.

    ``webhook_secret`` is write-only; supplying a non-empty value re-encrypts
    and replaces the stored ciphertext. Pass an empty string to leave the
    existing secret untouched (matches the UX where a blank field on the
    settings form means "unchanged").
    """

    default_hourly_rate_low: Decimal | None = None
    default_hourly_rate_high: Decimal | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None


def _require_superuser(user) -> None:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="super_admin_required")


def _serialize(row) -> SettingsRead:
    return SettingsRead(
        default_hourly_rate_low=row.default_hourly_rate_low,
        default_hourly_rate_high=row.default_hourly_rate_high,
        webhook_url=row.webhook_url,
        has_webhook_secret=bool(row.webhook_secret_encrypted),
    )


@router.get(
    "/professional-services/settings",
    response_model=SettingsRead,
)
async def get_professional_services_settings(
    user: CurrentActiveUser,
    session: DbSession,
) -> SettingsRead:
    _require_superuser(user)
    row = await read_settings_singleton_async(session)
    return _serialize(row)


@router.put(
    "/professional-services/settings",
    response_model=SettingsRead,
)
async def put_professional_services_settings(
    payload: SettingsWrite,
    user: CurrentActiveUser,
    session: DbSession,
) -> SettingsRead:
    _require_superuser(user)
    row = await read_settings_singleton_async(session)

    if payload.default_hourly_rate_low is not None:
        row.default_hourly_rate_low = payload.default_hourly_rate_low
    if payload.default_hourly_rate_high is not None:
        row.default_hourly_rate_high = payload.default_hourly_rate_high
    if payload.webhook_url is not None:
        # Empty string clears the URL (admins can disable the webhook by
        # blanking the field). None means "no change" per partial-update.
        row.webhook_url = payload.webhook_url or None
    if payload.webhook_secret:
        # Non-empty plaintext → encrypt and rotate. Empty string / None means
        # leave the existing secret in place.
        row.webhook_secret_encrypted = encrypt_api_key(payload.webhook_secret)

    row.updated_by_user_id = user.id
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _serialize(row)


@router.post("/professional-services/settings/test-webhook")
async def test_professional_services_webhook(
    user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Send a synthetic ``pro_service_quote.test_ping`` to the configured URL.

    Returns ``{"status": "ok"|"failed", "status_code"?: int, "detail"?: str}``.
    The detail is truncated to 500 chars so we don't echo a massive HTML
    error page back into the admin UI.
    """
    _require_superuser(user)
    row = await read_settings_singleton_async(session)
    if not row.webhook_url or not row.webhook_secret_encrypted:
        raise HTTPException(status_code=422, detail="webhook_not_configured")

    secret = decrypt_api_key(row.webhook_secret_encrypted)
    payload = {
        "event": "pro_service_quote.test_ping",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Langflow-Event": "pro_service_quote.test_ping",
        "X-Langflow-Delivery": str(uuid4()),
        "X-Langflow-Timestamp": datetime.now(timezone.utc).isoformat(),
        "X-Langflow-Signature": sign_body(body, secret),
    }
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(row.webhook_url, content=body, headers=headers)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning(
            "pro_service_quote_test_webhook_failed url=%s err=%s",
            row.webhook_url,
            exc,
        )
        return {"status": "failed", "detail": str(exc)[:500]}

    status_label = "ok" if 200 <= resp.status_code < 300 else "failed"
    return {
        "status": status_label,
        "status_code": resp.status_code,
        "detail": (resp.text or "")[:500],
    }
