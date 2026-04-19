"""Tests for FlowMutationTools.create_secret_variable.

The variable store API (langflow.services.variable.base.VariableService) requires
a SQLAlchemy session and accepts an optional organization_id (recent multi-tenant
work). We mock both the service and session_scope so the test stays a pure unit
test — see service.py:386 for the real signature.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from langflow.services.assistant.tools.mutation import FlowMutationTools


@pytest.mark.asyncio
async def test_create_secret_variable_writes_to_variable_store(monkeypatch):
    user_id = uuid4()
    org_id = uuid4()
    captured: list[dict] = []

    class FakeVariableService:
        async def create_variable(self, user_id, name, value, *, session, organization_id=None, **_):
            captured.append({
                "user_id": user_id,
                "name": name,
                "value": value,
                "organization_id": organization_id,
                "session": session,
            })
            return {"id": uuid4(), "name": name}

    sentinel_session = object()

    @asynccontextmanager
    async def fake_session_scope():
        yield sentinel_session

    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.session_scope",
        fake_session_scope,
    )

    tools = FlowMutationTools(
        {"nodes": [], "edges": []},
        user_id=user_id,
        org_id=org_id,
    )
    result = await tools.create_secret_variable(name="sftp_password_abc", value="P@ssword1!")

    assert result == {"variable_name": "sftp_password_abc"}
    assert captured == [
        {
            "user_id": user_id,
            "name": "sftp_password_abc",
            "value": "P@ssword1!",
            "organization_id": org_id,
            "session": sentinel_session,
        }
    ]


@pytest.mark.asyncio
async def test_create_secret_variable_works_without_org_id(monkeypatch):
    """org_id is optional — single-tenant installs don't have one."""
    user_id = uuid4()
    captured: list[dict] = []

    class FakeVariableService:
        async def create_variable(self, user_id, name, value, *, session, organization_id=None, **_):
            captured.append({"user_id": user_id, "name": name, "organization_id": organization_id})
            return {"id": uuid4(), "name": name}

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.session_scope",
        fake_session_scope,
    )

    tools = FlowMutationTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.create_secret_variable(name="api_key_xyz", value="secret")

    assert result == {"variable_name": "api_key_xyz"}
    assert captured == [{"user_id": user_id, "name": "api_key_xyz", "organization_id": None}]


@pytest.mark.asyncio
async def test_create_secret_variable_returns_error_when_user_id_missing():
    tools = FlowMutationTools({"nodes": [], "edges": []})
    result = await tools.create_secret_variable(name="x", value="y")
    assert result == {"error": "cannot create secret variable: missing user context"}


@pytest.mark.asyncio
async def test_create_secret_variable_returns_error_on_service_failure(monkeypatch):
    user_id = uuid4()

    class FakeVariableService:
        async def create_variable(self, user_id, name, value, *, session, organization_id=None, **_):
            msg = "duplicate name"
            raise ValueError(msg)

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.session_scope",
        fake_session_scope,
    )

    tools = FlowMutationTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.create_secret_variable(name="x", value="y")
    assert "error" in result
    assert "duplicate name" in result["error"]
