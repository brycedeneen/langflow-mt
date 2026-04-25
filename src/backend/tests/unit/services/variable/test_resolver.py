"""Tests for resolve_secret_reference dispatch."""

from __future__ import annotations

from unittest import mock
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from langflow.services.variable.auto_secrets import autosecret_marker, autosecret_vault_path


FLOW_ID = UUID("4312a8ac-22db-4d86-805e-86d19451c489")
ORG_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
NODE_ID = "ADPAuth-fMRCo"
FIELD_NAME = "client_secret"


@pytest.mark.asyncio
async def test_resolve_autosecret_returns_vault_value(monkeypatch):
    """A pipe-delimited autosecret marker resolves to the Vault payload's `value`."""
    from langflow.services.variable import resolver as resolver_mod

    secret_store = AsyncMock()
    secret_store.get = AsyncMock(return_value={"value": "the-secret"})

    async def fake_org_lookup(flow_id, *, session):
        return ORG_ID

    monkeypatch.setattr(resolver_mod, "_get_org_id_for_flow", fake_org_lookup)

    component = AsyncMock()  # not invoked for autosecret branch

    result = await resolver_mod.resolve_secret_reference(
        custom_component=component,
        name=autosecret_marker(FLOW_ID, NODE_ID, FIELD_NAME),
        field=FIELD_NAME,
        session=AsyncMock(),
        secret_store=secret_store,
    )
    assert result == "the-secret"
    secret_store.get.assert_awaited_once_with(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, FIELD_NAME),
    )
    component.get_variable.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_autosecret_missing_payload_returns_empty(monkeypatch):
    from langflow.services.variable import resolver as resolver_mod

    secret_store = AsyncMock()
    secret_store.get = AsyncMock(return_value=None)

    async def fake_org_lookup(flow_id, *, session):
        return ORG_ID

    monkeypatch.setattr(resolver_mod, "_get_org_id_for_flow", fake_org_lookup)

    out = await resolver_mod.resolve_secret_reference(
        custom_component=AsyncMock(),
        name=autosecret_marker(FLOW_ID, NODE_ID, FIELD_NAME),
        field=FIELD_NAME,
        session=AsyncMock(),
        secret_store=secret_store,
    )
    assert out == ""


@pytest.mark.asyncio
async def test_resolve_autosecret_org_unresolvable_returns_empty(monkeypatch):
    """Foreign-flow marker (no matching flow row in this org) soft-fails to ''."""
    from langflow.services.variable import resolver as resolver_mod

    async def fake_org_lookup(flow_id, *, session):
        return None

    monkeypatch.setattr(resolver_mod, "_get_org_id_for_flow", fake_org_lookup)

    out = await resolver_mod.resolve_secret_reference(
        custom_component=AsyncMock(),
        name=autosecret_marker(FLOW_ID, NODE_ID, FIELD_NAME),
        field=FIELD_NAME,
        session=AsyncMock(),
        secret_store=AsyncMock(),
    )
    assert out == ""


@pytest.mark.asyncio
async def test_resolve_malformed_marker_returns_empty():
    """Manual JSON edits or partial migrations don't crash the build."""
    from langflow.services.variable import resolver as resolver_mod

    out = await resolver_mod.resolve_secret_reference(
        custom_component=AsyncMock(),
        name="__autosecret|garbage",
        field="x",
        session=AsyncMock(),
        secret_store=AsyncMock(),
    )
    assert out == ""


@pytest.mark.asyncio
async def test_resolve_non_autosecret_delegates_to_component():
    """User-managed Variable names defer to the component's existing get_variable path."""
    from langflow.services.variable import resolver as resolver_mod

    component = AsyncMock()
    component.get_variable = AsyncMock(return_value="env-value")

    session = AsyncMock()
    out = await resolver_mod.resolve_secret_reference(
        custom_component=component,
        name="OPENAI_API_KEY",
        field="api_key",
        session=session,
        secret_store=AsyncMock(),
    )
    assert out == "env-value"
    component.get_variable.assert_awaited_once_with(
        name="OPENAI_API_KEY", field="api_key", session=session,
    )
