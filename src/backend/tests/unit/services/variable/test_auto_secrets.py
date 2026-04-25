"""Tests for autosecret lifecycle helpers (Vault-backed)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from lfx.services.secret_store.factory import InMemorySecretStore
from langflow.services.variable.auto_secrets import (
    LEGACY_AUTOSECRET_PREFIX,
    NEW_AUTOSECRET_PREFIX as AUTOSECRET_PREFIX,
    autosecret_marker,
    autosecret_vault_path,
    promote_plaintext_secrets_to_variables,
)


USER_ID = uuid4()
FLOW_ID = UUID("4312a8ac-22db-4d86-805e-86d19451c489")
ORG_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
NODE_ID = "APIRequest-abc123"


def _flow_data(field_template: dict, *, field_name: str = "cert_pem") -> dict:
    """Build a minimal flow `data` dict with one node + one templated field."""
    return {
        "nodes": [
            {
                "id": NODE_ID,
                "data": {
                    "node": {
                        "template": {
                            field_name: field_template,
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


@pytest.fixture
def patched_org_lookup():
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=ORG_ID,
    ) as patched:
        yield patched


@pytest.mark.asyncio
async def test_promote_writes_plaintext_to_vault(patched_org_lookup):
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n",
            "load_from_db": False,
        }
    )
    secret_store = InMemorySecretStore()
    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=False)

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == autosecret_marker(FLOW_ID, NODE_ID, "cert_pem")
    assert field["load_from_db"] is True

    stored = await secret_store.get(autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"))
    assert stored == {"value": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n"}


@pytest.mark.asyncio
async def test_promote_empty_value_with_existing_secret_preserves_marker(patched_org_lookup):
    """Issue 1 fix: empty value next to an existing Vault secret = 'untouched'."""
    secret_store = InMemorySecretStore()
    path = autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
    await secret_store.put(path, {"value": "previously-saved-secret"})

    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "",
            "load_from_db": True,
        }
    )

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == autosecret_marker(FLOW_ID, NODE_ID, "cert_pem")
    assert field["load_from_db"] is True
    assert (await secret_store.get(path))["value"] == "previously-saved-secret"


@pytest.mark.asyncio
async def test_promote_empty_value_with_no_secret_clears_field(patched_org_lookup):
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "",
            "load_from_db": True,
        }
    )
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=InMemorySecretStore(),
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == ""
    assert field["load_from_db"] is False


@pytest.mark.asyncio
async def test_promote_existing_marker_passes_through(patched_org_lookup):
    marker = autosecret_marker(FLOW_ID, NODE_ID, "cert_pem")
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": marker,
            "load_from_db": True,
        }
    )

    secret_store = InMemorySecretStore()
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == marker
    path = autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
    assert await secret_store.get(path) is None


@pytest.mark.asyncio
async def test_promote_legacy_marker_clears_field(patched_org_lookup):
    """Dev-data hygiene: legacy underscore-delimited markers reset to empty."""
    legacy = LEGACY_AUTOSECRET_PREFIX + f"{FLOW_ID}_{NODE_ID}_cert_pem"
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": legacy,
            "load_from_db": True,
        }
    )
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=InMemorySecretStore(),
        variable_service=AsyncMock(),
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == ""
    assert field["load_from_db"] is False


@pytest.mark.asyncio
async def test_promote_user_managed_variable_name_passes_through(patched_org_lookup):
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "OPENAI_API_KEY",
            "load_from_db": True,
        },
        field_name="api_key",
    )

    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=True)

    secret_store = InMemorySecretStore()
    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )
    field = out["nodes"][0]["data"]["node"]["template"]["api_key"]
    assert field["value"] == "OPENAI_API_KEY"
    assert await secret_store.list(f"{ORG_ID}/flows/") == []


@pytest.mark.asyncio
async def test_promote_skips_when_org_missing():
    """Defensive: missing flow row → no-op, don't crash the save."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "plaintext",
            "load_from_db": False,
        }
    )
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=None,
    ):
        out = await promote_plaintext_secrets_to_variables(
            flow_data=flow_data,
            flow_id=FLOW_ID,
            user_id=USER_ID,
            secret_store=InMemorySecretStore(),
            variable_service=AsyncMock(),
            session=AsyncMock(),
        )
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == "plaintext"


from langflow.services.variable.auto_secrets import (
    blank_autosecrets_for_export,
    cleanup_orphaned_autosecrets,
    delete_autosecrets_for_flow,
)


@pytest.mark.asyncio
async def test_cleanup_removes_orphans_only(patched_org_lookup):
    secret_store = InMemorySecretStore()
    # Two existing entries — one is still in the template, one is orphaned.
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"),
        {"value": "still-here"},
    )
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "deleted_field"),
        {"value": "orphan"},
    )
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": autosecret_marker(FLOW_ID, NODE_ID, "cert_pem"),
            "load_from_db": True,
        }
    )

    await cleanup_orphaned_autosecrets(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        session=AsyncMock(),
    )

    assert (
        await secret_store.get(
            autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
        )
    ) == {"value": "still-here"}
    assert (
        await secret_store.get(
            autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "deleted_field")
        )
    ) is None


@pytest.mark.asyncio
async def test_cleanup_no_op_when_org_missing():
    secret_store = InMemorySecretStore()
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"),
        {"value": "x"},
    )
    with patch(
        "langflow.services.variable.auto_secrets._get_org_id_for_flow",
        return_value=None,
    ):
        await cleanup_orphaned_autosecrets(
            flow_data=_flow_data({"_input_type": "TextFileSecretInput", "auto_promote": True, "value": ""}),
            flow_id=FLOW_ID,
            user_id=USER_ID,
            secret_store=secret_store,
            session=AsyncMock(),
        )
    # Nothing deleted.
    assert (
        await secret_store.get(
            autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
        )
    ) is not None


@pytest.mark.asyncio
async def test_delete_removes_all_under_flow(patched_org_lookup):
    secret_store = InMemorySecretStore()
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem"),
        {"value": "x"},
    )
    await secret_store.put(
        autosecret_vault_path(ORG_ID, FLOW_ID, "OtherNode", "client_id"),
        {"value": "y"},
    )
    OTHER_FLOW = uuid4()
    await secret_store.put(
        autosecret_vault_path(ORG_ID, OTHER_FLOW, "X", "f"),
        {"value": "z"},
    )

    await delete_autosecrets_for_flow(
        flow_id=FLOW_ID,
        user_id=USER_ID,
        secret_store=secret_store,
        session=AsyncMock(),
    )

    assert await secret_store.get(
        autosecret_vault_path(ORG_ID, FLOW_ID, NODE_ID, "cert_pem")
    ) is None
    assert await secret_store.get(
        autosecret_vault_path(ORG_ID, FLOW_ID, "OtherNode", "client_id")
    ) is None
    assert (
        await secret_store.get(autosecret_vault_path(ORG_ID, OTHER_FLOW, "X", "f"))
    ) == {"value": "z"}


def test_blank_autosecrets_zeros_marker_value():
    """blank_autosecrets_for_export should zero `value` for any auto_promote field
    whose value starts with the autosecret prefix; load_from_db remains True."""
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": autosecret_marker(FLOW_ID, NODE_ID, "cert_pem"),
            "load_from_db": True,
        }
    )
    out = blank_autosecrets_for_export(flow_data)
    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == ""
    # Importer side relies on this flag staying True.
    assert field["load_from_db"] is True


def test_blank_autosecrets_leaves_non_autosecret_values():
    """User-managed Variable references (no autosecret prefix) are not blanked."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "OPENAI_API_KEY",
            "load_from_db": True,
        },
        field_name="api_key",
    )
    out = blank_autosecrets_for_export(flow_data)
    field = out["nodes"][0]["data"]["node"]["template"]["api_key"]
    assert field["value"] == "OPENAI_API_KEY"
