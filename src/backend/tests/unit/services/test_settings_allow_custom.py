"""Regression: LANGFLOW_ALLOW_CUSTOM_COMPONENTS must default to False and parse env-var truthy values."""

from __future__ import annotations

import pytest

from langflow.services.settings.base import Settings


def test_allow_custom_components_defaults_to_false(monkeypatch):
    monkeypatch.delenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", raising=False)
    assert Settings().allow_custom_components is False


@pytest.mark.parametrize("truthy", ["true", "True", "1", "TRUE"])
def test_allow_custom_components_parses_truthy(monkeypatch, truthy):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", truthy)
    assert Settings().allow_custom_components is True


@pytest.mark.parametrize("falsy", ["false", "0", "False", "FALSE"])
def test_allow_custom_components_parses_falsy(monkeypatch, falsy):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", falsy)
    assert Settings().allow_custom_components is False


async def test_config_endpoint_surfaces_allow_custom_components(client, logged_in_headers):
    """GET /api/v1/config must expose the allow_custom_components flag so
    the frontend guard hook can read it."""
    resp = await client.get("api/v1/config", headers=logged_in_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "allow_custom_components" in body
    assert body["allow_custom_components"] is False  # default fleet posture


async def test_public_config_endpoint_surfaces_allow_custom_components(client):
    """Pre-auth clients must see the flag too so the guard hook can gate UI
    before login. Locks in the BaseConfigResponse placement decision — if a
    future refactor moves the field to ConfigResponse only, this test fails
    and the public playground stops enforcing the gate."""
    resp = await client.get("api/v1/config")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["type"] == "public"
    assert body["allow_custom_components"] is False
