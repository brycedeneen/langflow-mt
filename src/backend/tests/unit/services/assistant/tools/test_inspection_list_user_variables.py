"""Tests for FlowInspectionTools.list_user_variables.

Returns variable names only (never values). Used by the assistant to
detect already-configured credentials before re-asking the user.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from langflow.services.assistant.tools.inspection import FlowInspectionTools


@pytest.mark.asyncio
async def test_list_user_variables_returns_names_only(monkeypatch):
    user_id = uuid4()

    class FakeVariableService:
        async def list_variables(self, user_id, session):  # noqa: ARG002
            return ["adp_client_id", "adp_client_secret", "sftp_password_old"]

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.session_scope",
        fake_session_scope,
    )

    tools = FlowInspectionTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.list_user_variables()

    assert result == {
        "variable_names": ["adp_client_id", "adp_client_secret", "sftp_password_old"]
    }


@pytest.mark.asyncio
async def test_list_user_variables_filters_out_none_entries(monkeypatch):
    """The variable service may return None entries; the tool drops them."""
    user_id = uuid4()

    class FakeVariableService:
        async def list_variables(self, user_id, session):  # noqa: ARG002
            return ["good_one", None, "another_good"]

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.session_scope",
        fake_session_scope,
    )

    tools = FlowInspectionTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.list_user_variables()

    assert result == {"variable_names": ["good_one", "another_good"]}


@pytest.mark.asyncio
async def test_list_user_variables_returns_empty_when_user_has_no_variables(monkeypatch):
    user_id = uuid4()

    class FakeVariableService:
        async def list_variables(self, user_id, session):  # noqa: ARG002
            return []

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.session_scope",
        fake_session_scope,
    )

    tools = FlowInspectionTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.list_user_variables()

    assert result == {"variable_names": []}


@pytest.mark.asyncio
async def test_list_user_variables_returns_error_when_user_id_missing():
    tools = FlowInspectionTools({"nodes": [], "edges": []})
    result = await tools.list_user_variables()
    assert result == {"error": "cannot list variables: missing user context"}


@pytest.mark.asyncio
async def test_list_user_variables_returns_error_on_service_failure(monkeypatch):
    user_id = uuid4()

    class FakeVariableService:
        async def list_variables(self, user_id, session):  # noqa: ARG002
            msg = "db unreachable"
            raise RuntimeError(msg)

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.get_variable_service",
        lambda: FakeVariableService(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.inspection.session_scope",
        fake_session_scope,
    )

    tools = FlowInspectionTools({"nodes": [], "edges": []}, user_id=user_id)
    result = await tools.list_user_variables()
    assert "error" in result
    assert "db unreachable" in result["error"]
