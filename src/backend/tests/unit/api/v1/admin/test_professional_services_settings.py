"""Tests for the super-admin Pro-Service Quotes settings endpoints (Task 15).

Covers:

- GET returns the seeded singleton (200/200 default rate band, no webhook).
- PUT updates rates + webhook URL + secret; subsequent GET reflects new
  rates and ``has_webhook_secret=True`` without ever returning the plaintext.
- The persisted ``webhook_secret_encrypted`` is Fernet ciphertext (not the
  plaintext we PUT) and ``decrypt_api_key`` round-trips back to the original.
- Org-admin (non-superuser, even with platform-admin bit) gets 403 on GET,
  PUT, and the test-webhook ping.
- ``test-webhook`` returns 422 ``webhook_not_configured`` when the URL/secret
  are unset.
- ``test-webhook`` happy path: stub ``httpx.AsyncClient`` to return 200,
  expect ``{"status": "ok"}``.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.deps import session_scope


_BASE = "api/v1/admin/professional-services/settings"


async def _read_settings_row() -> ProfessionalServicesSettings:
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ProfessionalServicesSettings).where(
                    ProfessionalServicesSettings.id == 1
                )
            )
        ).one()
        # Detach so the caller can read attributes after the session closes.
        session.expunge(row)
        return row


@pytest.mark.asyncio
async def test_get_settings_returns_seeded_singleton(
    client: AsyncClient, logged_in_headers_super_user: dict
):
    """GET as a superuser → 200 with seeded defaults and no webhook."""
    resp = await client.get(_BASE, headers=logged_in_headers_super_user)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["default_hourly_rate_low"] == "200.00"
    assert body["default_hourly_rate_high"] == "200.00"
    assert body["webhook_url"] is None
    assert body["has_webhook_secret"] is False


@pytest.mark.asyncio
async def test_put_updates_rates_url_and_secret_round_trips_through_encrypt(
    client: AsyncClient, logged_in_headers_super_user: dict
):
    """PUT writes rates + URL + secret; GET reflects them; secret is encrypted on disk."""
    resp = await client.put(
        _BASE,
        headers=logged_in_headers_super_user,
        json={
            "default_hourly_rate_low": "150.00",
            "default_hourly_rate_high": "250.00",
            "webhook_url": "https://example.test/hook",
            "webhook_secret": "shh",
        },
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    put_body = resp.json()
    assert put_body["default_hourly_rate_low"] == "150.00"
    assert put_body["default_hourly_rate_high"] == "250.00"
    assert put_body["webhook_url"] == "https://example.test/hook"
    assert put_body["has_webhook_secret"] is True
    # The PUT response must never echo back the plaintext secret.
    assert "webhook_secret" not in put_body

    # GET sees the new values.
    get_resp = await client.get(_BASE, headers=logged_in_headers_super_user)
    assert get_resp.status_code == status.HTTP_200_OK
    get_body = get_resp.json()
    assert get_body["default_hourly_rate_low"] == "150.00"
    assert get_body["default_hourly_rate_high"] == "250.00"
    assert get_body["webhook_url"] == "https://example.test/hook"
    assert get_body["has_webhook_secret"] is True
    assert "webhook_secret" not in get_body

    # On disk: ciphertext != plaintext, but decrypt_api_key round-trips.
    row = await _read_settings_row()
    assert row.webhook_secret_encrypted is not None
    assert row.webhook_secret_encrypted != "shh"
    assert decrypt_api_key(row.webhook_secret_encrypted) == "shh"


@pytest.mark.asyncio
async def test_put_empty_webhook_secret_does_not_clear_existing(
    client: AsyncClient, logged_in_headers_super_user: dict
):
    """An empty/omitted webhook_secret on PUT must leave the stored secret in place."""
    # Seed a secret first.
    seed_resp = await client.put(
        _BASE,
        headers=logged_in_headers_super_user,
        json={"webhook_secret": "first-secret"},
    )
    assert seed_resp.status_code == status.HTTP_200_OK, seed_resp.text

    # PUT again without a secret field.
    resp = await client.put(
        _BASE,
        headers=logged_in_headers_super_user,
        json={"default_hourly_rate_low": "175.00"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["has_webhook_secret"] is True

    row = await _read_settings_row()
    assert decrypt_api_key(row.webhook_secret_encrypted) == "first-secret"


@pytest.mark.asyncio
async def test_get_forbidden_for_non_superuser(
    client: AsyncClient, org_admin_headers: dict
):
    """A platform-admin-but-not-superuser caller is rejected on GET."""
    resp = await client.get(_BASE, headers=org_admin_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert resp.json()["detail"] == "super_admin_required"


@pytest.mark.asyncio
async def test_put_forbidden_for_non_superuser(
    client: AsyncClient, org_admin_headers: dict
):
    resp = await client.put(
        _BASE,
        headers=org_admin_headers,
        json={"default_hourly_rate_low": "999.00"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_test_webhook_forbidden_for_non_superuser(
    client: AsyncClient, org_admin_headers: dict
):
    resp = await client.post(f"{_BASE}/test-webhook", headers=org_admin_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_test_webhook_unconfigured_returns_422(
    client: AsyncClient, logged_in_headers_super_user: dict
):
    """No URL/secret → 422 webhook_not_configured."""
    # Reset to unconfigured (other tests may have left a webhook in place).
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ProfessionalServicesSettings).where(
                    ProfessionalServicesSettings.id == 1
                )
            )
        ).one()
        row.webhook_url = None
        row.webhook_secret_encrypted = None
        session.add(row)
        await session.commit()

    resp = await client.post(
        f"{_BASE}/test-webhook", headers=logged_in_headers_super_user
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert resp.json()["detail"] == "webhook_not_configured"


@pytest.mark.asyncio
async def test_test_webhook_happy_path(
    client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch
):
    """Configured webhook + 200 response → ``{"status": "ok"}``."""
    # Configure URL + secret.
    cfg = await client.put(
        _BASE,
        headers=logged_in_headers_super_user,
        json={
            "webhook_url": "https://example.test/hook",
            "webhook_secret": "ping-secret",
        },
    )
    assert cfg.status_code == status.HTTP_200_OK, cfg.text

    captured: list[dict[str, Any]] = []

    class _StubClient:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def post(self, url, *, content, headers):
            captured.append({"url": url, "content": content, "headers": headers})

            class _Resp:
                status_code = 200
                text = "ok"

            return _Resp()

    class _StubHttpx:
        AsyncClient = _StubClient
        Timeout = httpx.Timeout
        TimeoutException = httpx.TimeoutException
        TransportError = httpx.TransportError

    from langflow.api.v1.admin import professional_services_settings as mod

    monkeypatch.setattr(mod, "httpx", _StubHttpx)

    resp = await client.post(
        f"{_BASE}/test-webhook", headers=logged_in_headers_super_user
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["status_code"] == 200

    # Verify the request shape.
    assert len(captured) == 1
    call = captured[0]
    assert call["url"] == "https://example.test/hook"
    assert call["headers"]["X-Langflow-Event"] == "pro_service_quote.test_ping"
    assert call["headers"]["X-Langflow-Signature"].startswith("sha256=")


@pytest.mark.asyncio
async def test_test_webhook_network_failure_returns_failed(
    client: AsyncClient, logged_in_headers_super_user: dict, monkeypatch
):
    """Transport failure surfaces as ``{"status": "failed"}`` (not a 5xx)."""
    cfg = await client.put(
        _BASE,
        headers=logged_in_headers_super_user,
        json={
            "webhook_url": "https://example.test/hook",
            "webhook_secret": "ping-secret",
        },
    )
    assert cfg.status_code == status.HTTP_200_OK

    class _FailingClient:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def post(self, *args, **kwargs):  # noqa: ARG002
            raise httpx.ConnectError("boom")

    class _StubHttpx:
        AsyncClient = _FailingClient
        Timeout = httpx.Timeout
        TimeoutException = httpx.TimeoutException
        TransportError = httpx.TransportError

    from langflow.api.v1.admin import professional_services_settings as mod

    monkeypatch.setattr(mod, "httpx", _StubHttpx)

    resp = await client.post(
        f"{_BASE}/test-webhook", headers=logged_in_headers_super_user
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["status"] == "failed"
