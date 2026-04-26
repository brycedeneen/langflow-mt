"""Tests for FlowMutationTools.set_field_value auto_promote validation.

When the assist references an unknown variable name on a SecretStrInput
field, the autopromotion ladder used to store the literal string in Vault,
producing the "Stored — type to replace" UI bug and downstream runtime
failures (e.g. `[SSL] PEM lib` for cert/key fields). The validation guards
against that by rejecting unknown names server-side and surfacing the list
of valid variable names so the model can retry in one step.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest

from langflow.services.assistant.tools.mutation import FlowMutationTools


def _flow_with_auto_promote_field(
    *,
    field_name: str = "client_certificate",
    auto_promote: bool = True,
) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "ADPAuth-abc12",
                "data": {
                    "type": "ADPAuth",
                    "node": {
                        "template": {
                            field_name: {
                                "type": "str",
                                "value": "",
                                "load_from_db": True,
                                "auto_promote": auto_promote,
                            },
                        },
                    },
                },
            },
        ],
        "edges": [],
    }


def _patch_variable_service(
    monkeypatch,
    *,
    known: set[str],
    all_names: list[str | None] | None = None,
):
    """Stub the variable service. ``known`` is the set of user-managed names
    (those for which has_user_managed_variable returns True). ``all_names``
    is what list_variables returns (defaults to ``sorted(known)``)."""

    class FakeVariableService:
        async def has_user_managed_variable(self, *, name, user_id, session):
            return name in known

        async def list_variables(self, user_id, session, *, organization_id=None):
            if all_names is not None:
                return all_names
            return sorted(known)

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


@pytest.mark.asyncio
async def test_known_variable_name_passes_through(monkeypatch):
    """A value that matches a user-managed variable is written verbatim."""
    _patch_variable_service(monkeypatch, known={"adp_client_cert"})
    flow = _flow_with_auto_promote_field()
    tools = FlowMutationTools(flow, user_id=uuid4(), org_id=uuid4())

    result = await tools.set_field_value("ADPAuth-abc12", "client_certificate", "adp_client_cert")

    assert "error" not in result
    assert result["updated_node_id"] == "ADPAuth-abc12"
    field = flow["nodes"][0]["data"]["node"]["template"]["client_certificate"]
    assert field["value"] == "adp_client_cert"


@pytest.mark.asyncio
async def test_unknown_variable_name_returns_error_with_available_list(monkeypatch):
    """An unknown name on an auto_promote field is rejected, and the
    response carries the user's actual variable names so the model can
    self-correct in one retry."""
    _patch_variable_service(
        monkeypatch,
        known={"adp_client_id", "adp_client_secret", "adp_client_cert", "adp_client_key"},
    )
    flow = _flow_with_auto_promote_field()
    tools = FlowMutationTools(flow, user_id=uuid4(), org_id=uuid4())

    # Wrong name (matches the old prompt's adp_client_certificate spelling)
    result = await tools.set_field_value(
        "ADPAuth-abc12", "client_certificate", "adp_client_certificate",
    )

    assert "error" in result
    assert "adp_client_certificate" in result["error"]
    assert result["available_user_variables"] == [
        "adp_client_cert",
        "adp_client_id",
        "adp_client_key",
        "adp_client_secret",
    ]
    # Field must NOT have been mutated — the bug is precisely that the wrong
    # value lands in the template and gets autopromoted on save.
    field = flow["nodes"][0]["data"]["node"]["template"]["client_certificate"]
    assert field["value"] == ""


@pytest.mark.asyncio
async def test_autosecret_prefixed_names_filtered_from_available(monkeypatch):
    """list_variables returns autosecret markers too; the assist response
    must not advertise them as pickable variable names."""
    _patch_variable_service(
        monkeypatch,
        known={"adp_client_cert"},
        all_names=[
            "adp_client_cert",
            "__autosecret|<flow>|<node>|<field>",
            None,
        ],
    )
    flow = _flow_with_auto_promote_field()
    tools = FlowMutationTools(flow, user_id=uuid4(), org_id=uuid4())

    result = await tools.set_field_value(
        "ADPAuth-abc12", "client_certificate", "nope",
    )

    assert "error" in result
    assert result["available_user_variables"] == ["adp_client_cert"]


@pytest.mark.asyncio
async def test_empty_value_skips_validation(monkeypatch):
    """Clearing a field is always allowed; no DB hit."""
    called = {"hit": False}

    class _Boom:
        async def has_user_managed_variable(self, **_):
            called["hit"] = True
            return False

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: _Boom(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.session_scope",
        fake_session_scope,
    )

    flow = _flow_with_auto_promote_field()
    tools = FlowMutationTools(flow, user_id=uuid4(), org_id=uuid4())

    result = await tools.set_field_value("ADPAuth-abc12", "client_certificate", "")
    assert "error" not in result
    assert called["hit"] is False


@pytest.mark.asyncio
async def test_non_auto_promote_field_skips_validation(monkeypatch):
    """Plain str fields don't go through autopromotion, so no validation."""
    called = {"hit": False}

    class _Boom:
        async def has_user_managed_variable(self, **_):
            called["hit"] = True
            return False

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: _Boom(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.session_scope",
        fake_session_scope,
    )

    flow = _flow_with_auto_promote_field(field_name="some_url", auto_promote=False)
    tools = FlowMutationTools(flow, user_id=uuid4(), org_id=uuid4())

    result = await tools.set_field_value("ADPAuth-abc12", "some_url", "https://example.com")
    assert "error" not in result
    assert called["hit"] is False
    field = flow["nodes"][0]["data"]["node"]["template"]["some_url"]
    assert field["value"] == "https://example.com"


@pytest.mark.asyncio
async def test_missing_user_context_skips_validation(monkeypatch):
    """Without user_id we can't look up variables; fall back to the dumb
    write so non-multi-tenant code paths still work. (Mirrors how
    create_secret_variable handles missing user_id.)"""
    called = {"hit": False}

    class _Boom:
        async def has_user_managed_variable(self, **_):
            called["hit"] = True
            return False

    @asynccontextmanager
    async def fake_session_scope():
        yield object()

    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.get_variable_service",
        lambda: _Boom(),
    )
    monkeypatch.setattr(
        "langflow.services.assistant.tools.mutation.session_scope",
        fake_session_scope,
    )

    flow = _flow_with_auto_promote_field()
    tools = FlowMutationTools(flow, user_id=None, org_id=None)

    result = await tools.set_field_value("ADPAuth-abc12", "client_certificate", "anything")
    assert "error" not in result
    assert called["hit"] is False
