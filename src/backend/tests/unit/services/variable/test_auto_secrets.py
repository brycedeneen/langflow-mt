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
async def test_promote_skips_non_textfilesecret_fields():
    flow_data = _flow_data(
        {
            "_input_type": "SecretStrInput",
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
