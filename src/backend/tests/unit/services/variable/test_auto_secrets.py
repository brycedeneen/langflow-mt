"""Tests for auto-Variable lifecycle helpers.

These helpers walk flow `data` dicts and promote / clean up / blank values for
fields whose `_input_type == "TextFileSecretInput"`. The Variable service is
mocked; the helpers are pure orchestration.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from langflow.services.variable.auto_secrets import (
    AUTOSECRET_PREFIX,
    autosecret_name,
    promote_plaintext_secrets_to_variables,
)


def _flow_data(field_template: dict) -> dict:
    """Build a minimal flow `data` dict with one node + one templated field."""
    return {
        "nodes": [
            {
                "id": "APIRequest-abc123",
                "data": {
                    "node": {
                        "template": {
                            "cert_pem": field_template,
                        },
                    },
                },
            }
        ],
        "edges": [],
    }


USER_ID = uuid4()
FLOW_ID = uuid4()


def test_autosecret_name_is_deterministic():
    name = autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")
    assert name.startswith(AUTOSECRET_PREFIX)
    assert str(FLOW_ID) in name
    assert "APIRequest-abc123" in name
    assert name.endswith("_cert_pem")


@pytest.mark.asyncio
async def test_promote_creates_variable_for_plaintext_textfilesecret():
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n",
            "load_from_db": False,
        }
    )
    svc = AsyncMock()
    svc.create_variable = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[])

    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    expected_name = autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")
    svc.create_variable.assert_awaited_once()
    call_kwargs = svc.create_variable.await_args.kwargs
    assert call_kwargs["name"] == expected_name
    assert call_kwargs["value"].startswith("-----BEGIN CERTIFICATE-----")
    assert call_kwargs["user_id"] == USER_ID

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == expected_name
    assert field["load_from_db"] is True


@pytest.mark.asyncio
async def test_promote_skips_non_promotable_fields():
    """SecretStrInput with auto_promote=False (or absent) is not promoted."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": False,
            "value": "whatever",
            "load_from_db": False,
        }
    )
    svc = AsyncMock()
    svc.create_variable = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[])
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.create_variable.assert_not_called()
    assert out["nodes"][0]["data"]["node"]["template"]["cert_pem"]["value"] == "whatever"


@pytest.mark.asyncio
async def test_promote_skips_empty_plaintext():
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "",
            "load_from_db": False,
        }
    )
    svc = AsyncMock()
    svc.create_variable = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[])
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.create_variable.assert_not_called()
    assert out["nodes"][0]["data"]["node"]["template"]["cert_pem"]["load_from_db"] is False


@pytest.mark.asyncio
async def test_promote_skips_already_promoted_reference():
    existing_name = autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": existing_name,
            "load_from_db": True,
        }
    )
    svc = AsyncMock()
    svc.create_variable = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[existing_name])
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.create_variable.assert_not_called()
    assert out["nodes"][0]["data"]["node"]["template"]["cert_pem"]["value"] == existing_name


@pytest.mark.asyncio
async def test_promote_upserts_when_value_changed():
    # User edited the field: value is a new plaintext, load_from_db is False
    # (frontend resets it when the user changes the masked value), but an
    # auto-Variable with the expected name already exists — the helper should
    # UPDATE it, not create a duplicate.
    existing_name = autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")
    new_value = "-----BEGIN CERTIFICATE-----\nNEW\n-----END CERTIFICATE-----\n"
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": new_value,
            "load_from_db": False,
        }
    )
    svc = AsyncMock()
    svc.create_variable = AsyncMock()
    svc.update_variable_value = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[existing_name])
    session = AsyncMock()

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.create_variable.assert_not_called()
    svc.update_variable_value.assert_awaited_once()
    call_kwargs = svc.update_variable_value.await_args.kwargs
    assert call_kwargs["name"] == existing_name
    assert call_kwargs["value"] == new_value
    assert out["nodes"][0]["data"]["node"]["template"]["cert_pem"]["value"] == existing_name
    assert out["nodes"][0]["data"]["node"]["template"]["cert_pem"]["load_from_db"] is True


from langflow.services.variable.auto_secrets import cleanup_orphaned_autosecrets


@pytest.mark.asyncio
async def test_cleanup_deletes_autosecrets_for_removed_nodes():
    # Flow currently has one APIRequest node; DB has two autosecrets,
    # one of which references a node that no longer exists.
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem"),
            "load_from_db": True,
        }
    )
    current_name = autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")
    orphan_name = autosecret_name(FLOW_ID, "APIRequest-old999", "cert_pem")

    svc = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(return_value=[current_name, orphan_name])
    svc.delete_variable = AsyncMock()
    session = AsyncMock()

    await cleanup_orphaned_autosecrets(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.delete_variable.assert_awaited_once()
    call_kwargs = svc.delete_variable.await_args.kwargs
    assert call_kwargs["name"] == orphan_name


@pytest.mark.asyncio
async def test_cleanup_no_op_when_no_orphans():
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem"),
            "load_from_db": True,
        }
    )
    svc = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(
        return_value=[autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")]
    )
    svc.delete_variable = AsyncMock()
    session = AsyncMock()

    await cleanup_orphaned_autosecrets(
        flow_data=flow_data,
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    svc.delete_variable.assert_not_called()


from langflow.services.variable.auto_secrets import delete_autosecrets_for_flow


@pytest.mark.asyncio
async def test_delete_autosecrets_for_flow_removes_all_for_that_flow():
    svc = AsyncMock()
    svc.list_autosecret_names_for_flow = AsyncMock(
        return_value=[
            autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem"),
            autosecret_name(FLOW_ID, "APIRequest-abc123", "key_pem"),
        ]
    )
    svc.delete_variable = AsyncMock()
    session = AsyncMock()

    await delete_autosecrets_for_flow(
        flow_id=FLOW_ID,
        user_id=USER_ID,
        variable_service=svc,
        session=session,
    )

    assert svc.delete_variable.await_count == 2


from langflow.services.variable.auto_secrets import blank_autosecrets_for_export


def test_blank_autosecrets_blanks_textfilesecret_refs():
    ref = autosecret_name(FLOW_ID, "APIRequest-abc123", "cert_pem")
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": ref,
            "load_from_db": True,
        }
    )

    out = blank_autosecrets_for_export(flow_data)

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == ""
    assert field["load_from_db"] is True


def test_blank_autosecrets_ignores_non_autosecret_variables():
    # A user-managed Variable referenced via load_from_db should NOT be blanked.
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "my_global_variable",
            "load_from_db": True,
        }
    )

    out = blank_autosecrets_for_export(flow_data)

    field = out["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert field["value"] == "my_global_variable"


from langflow.services.variable.auto_secrets import _iter_promotable_fields


def test_iter_promotable_fields_yields_secret_str_with_auto_promote_true():
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": True,
            "value": "sk-secret",
            "load_from_db": False,
        }
    )
    yielded = list(_iter_promotable_fields(flow_data))
    assert len(yielded) == 1
    assert yielded[0][1] == "cert_pem"  # field name is `cert_pem` per _flow_data


def test_iter_promotable_fields_skips_secret_str_with_auto_promote_false():
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "auto_promote": False,
            "value": "sk-secret",
        }
    )
    assert list(_iter_promotable_fields(flow_data)) == []


def test_iter_promotable_fields_yields_text_file_secret_input_with_auto_promote_true():
    flow_data = _flow_data(
        {
            "_input_type": "TextFileSecretInput",
            "auto_promote": True,
            "value": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n",
        }
    )
    yielded = list(_iter_promotable_fields(flow_data))
    assert len(yielded) == 1


def test_iter_promotable_fields_ignores_missing_auto_promote_key():
    """Legacy flows saved before the feature landed have no auto_promote key.
    They must be treated as non-promotable."""
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
            "value": "sk-legacy",
        }
    )
    assert list(_iter_promotable_fields(flow_data)) == []
