"""Tests for the HMAC-signed webhook mirror on submit (Task 12).

These tests don't hit the network — they monkey-patch ``httpx.AsyncClient``
inside the webhook service so we can verify the request shape (URL, headers,
HMAC-signed body, payload contents) end-to-end through the submit endpoint.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.deps import session_scope


_PAYLOAD: dict[str, Any] = {
    "minutes_low": 30,
    "minutes_high": 90,
    "headline_summary": "Build Slack notifier",
    "narrative": "Send build events to Slack",
    "conversation_summary": None,
    "org_notes": "internal-only note",
}


class _CapturingClient:
    """Stand-in for ``httpx.AsyncClient`` that records the .post() call."""

    captured: list[dict[str, Any]] = []

    def __init__(self, *args, **kwargs):  # noqa: ARG002
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
        return None

    async def post(self, url: str, *, content: bytes, headers: dict[str, str]):
        self.__class__.captured.append(
            {"url": url, "content": content, "headers": headers}
        )

        class _Resp:
            status_code = 200
            text = ""

        return _Resp()


@pytest.fixture
def capturing_httpx(monkeypatch):
    """Replace ``httpx.AsyncClient`` inside the webhook module with a capturer."""
    from langflow.services.professional_services import webhook_service

    _CapturingClient.captured = []
    monkeypatch.setattr(webhook_service, "httpx", _make_httpx_stub())
    return _CapturingClient


def _make_httpx_stub():
    class _StubHttpx:
        AsyncClient = _CapturingClient
        Timeout = httpx.Timeout
        TimeoutException = httpx.TimeoutException
        TransportError = httpx.TransportError

    return _StubHttpx


async def _seed_flow(*, organization_id: UUID, user_id: UUID) -> UUID:
    async with session_scope() as session:
        flow = Flow(
            name=f"webhook-test-{user_id.hex[:6]}",
            data={"nodes": [], "edges": []},
            user_id=user_id,
            organization_id=organization_id,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


async def _set_settings_webhook(url: str | None, secret: str | None) -> None:
    """Store the webhook URL/secret on the settings singleton.

    The secret column holds Fernet ciphertext in production (Task 15); we
    encrypt here so the webhook service's ``decrypt_api_key`` round-trip
    succeeds and the HMAC signature uses the right plaintext.
    """
    from langflow.services.auth.utils import encrypt_api_key

    async with session_scope() as session:
        row = (
            await session.exec(
                select(ProfessionalServicesSettings).where(
                    ProfessionalServicesSettings.id == 1
                )
            )
        ).one()
        row.webhook_url = url
        row.webhook_secret_encrypted = (
            encrypt_api_key(secret) if secret is not None else None
        )
        session.add(row)
        await session.commit()


@pytest.mark.asyncio
async def test_webhook_no_op_when_url_unset(
    client: AsyncClient,
    capturing_httpx,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """No webhook URL configured → no HTTP call, submit still 201s."""
    await _set_settings_webhook(None, None)
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
    )
    resp = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_PAYLOAD,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    assert capturing_httpx.captured == []


@pytest.mark.asyncio
async def test_webhook_dispatches_signed_payload(
    client: AsyncClient,
    capturing_httpx,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """Webhook URL + secret configured → POSTs JSON body with HMAC signature."""
    secret = "supersecret-webhook-key"
    await _set_settings_webhook("https://example.test/hook", secret)
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
    )
    resp = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_PAYLOAD,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    body = resp.json()

    assert len(capturing_httpx.captured) == 1
    call = capturing_httpx.captured[0]
    assert call["url"] == "https://example.test/hook"

    # Headers
    headers = call["headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Langflow-Event"] == "pro_service_quote.submitted"
    assert "X-Langflow-Delivery" in headers
    assert "X-Langflow-Timestamp" in headers
    sig = headers["X-Langflow-Signature"]
    assert sig.startswith("sha256=")

    # HMAC verifies
    expected = (
        "sha256="
        + hmac.new(secret.encode("utf-8"), call["content"], hashlib.sha256).hexdigest()
    )
    assert sig == expected

    # Payload shape
    payload = json.loads(call["content"])
    assert payload["event"] == "pro_service_quote.submitted"
    assert payload["quote_id"] == body["id"]
    assert payload["estimate"]["minutes_low"] == 30
    assert payload["estimate"]["minutes_high"] == 90
    assert payload["estimate"]["rate_low_per_hour"] == 200.0
    assert payload["estimate"]["rate_high_per_hour"] == 200.0
    assert payload["estimate"]["currency"] == "USD"
    assert payload["headline_summary"] == "Build Slack notifier"
    # Crucial: notes excluded — receivers may persist payloads in less-trusted
    # places, and only the LLM-redacted narrative/summary fields go through.
    assert "org_notes" not in payload
    assert "admin_notes" not in payload


@pytest.mark.asyncio
async def test_webhook_delivery_failure_swallowed(
    client: AsyncClient,
    monkeypatch,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """A network failure must not break the submit response — webhook is best-effort."""
    await _set_settings_webhook("https://example.test/hook", "k")

    class _FailingClient:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def post(self, *args, **kwargs):  # noqa: ARG002
            raise httpx.ConnectError("boom")

    from langflow.services.professional_services import webhook_service

    class _StubHttpx:
        AsyncClient = _FailingClient
        Timeout = httpx.Timeout
        TimeoutException = httpx.TimeoutException
        TransportError = httpx.TransportError
        ConnectError = httpx.ConnectError

    monkeypatch.setattr(webhook_service, "httpx", _StubHttpx)

    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
    )
    resp = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_PAYLOAD,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text


def test_build_webhook_payload_omits_notes():
    """Pure unit test — payload builder must not include org_notes/admin_notes."""
    from datetime import datetime, timezone

    from langflow.services.database.models.pro_service_quote.model import (
        ProServiceQuote,
        ProServiceQuoteStatus,
    )
    from langflow.services.professional_services.webhook_service import (
        build_webhook_payload,
    )

    quote = ProServiceQuote(
        org_id=UUID("00000000-0000-0000-0000-000000000001"),
        flow_id=UUID("00000000-0000-0000-0000-000000000002"),
        requester_user_id=UUID("00000000-0000-0000-0000-000000000003"),
        status=ProServiceQuoteStatus.OPEN,
        estimated_minutes_low=30,
        estimated_minutes_high=90,
        rate_low_per_hour=None,
        rate_high_per_hour=None,
        headline_summary="h",
        narrative="n",
        conversation_summary=None,
        org_notes="contains internal stuff",
        admin_notes="admin only",
        submitted_at=datetime.now(timezone.utc),
    )
    out = build_webhook_payload(
        quote, base_url="https://lf.test", org_name="Acme", requester_label="alice"
    )
    assert "org_notes" not in out
    assert "admin_notes" not in out
    assert out["headline_summary"] == "h"
    assert out["org"]["name"] == "Acme"
    assert out["requester"]["email"] == "alice"
