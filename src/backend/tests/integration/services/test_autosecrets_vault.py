"""Integration tests for the autosecret Vault round-trip.

Gated on a real Vault dev-mode instance. Skipped when VAULT_ADDR / VAULT_TOKEN
are unset so CI without a Vault dev instance still passes.

Run locally against a Vault dev container:

    docker run -d --name=vault-dev -p 8200:8200 \\
      -e VAULT_DEV_ROOT_TOKEN_ID=devroot \\
      -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \\
      hashicorp/vault:latest

    VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=devroot \\
      uv run pytest src/backend/tests/integration/services/test_autosecrets_vault.py -v
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from langflow.services.variable.auto_secrets import (
    autosecret_marker,
    autosecret_vault_path,
    delete_autosecrets_for_flow,
    promote_plaintext_secrets_to_variables,
)
from langflow.services.variable.resolver import resolve_secret_reference
from lfx.services.secret_store.factory import get_secret_store
from lfx.services.secret_store.settings import SecretStoreSettings

pytestmark = pytest.mark.skipif(
    not os.environ.get("VAULT_ADDR") or not os.environ.get("VAULT_TOKEN"),
    reason="Vault integration tests require VAULT_ADDR and VAULT_TOKEN env vars",
)


@pytest.fixture
def vault_store():
    settings = SecretStoreSettings(
        SECRET_STORE_BACKEND="vault",
        VAULT_ADDR=os.environ["VAULT_ADDR"],
        VAULT_TOKEN=os.environ["VAULT_TOKEN"],
        VAULT_MOUNT_POINT=os.environ.get("VAULT_MOUNT_POINT", "secret"),
    )
    return get_secret_store(settings=settings)


@pytest.fixture
def org_id():
    return uuid4()


@pytest.fixture
def flow_id():
    return uuid4()


def _flow_data(value: str) -> dict:
    return {
        "nodes": [
            {
                "id": "ADPAuth-1",
                "data": {
                    "node": {
                        "template": {
                            "client_secret": {
                                "_input_type": "SecretStrInput",
                                "auto_promote": True,
                                "value": value,
                                "load_from_db": value == "",
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


@pytest.mark.asyncio
async def test_save_then_resolve_round_trip(vault_store, org_id, flow_id):
    user_id = uuid4()
    plaintext = "super-secret-cred-value"

    flow_data = _flow_data(plaintext)
    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=False)

    out = await promote_plaintext_secrets_to_variables(
        flow_data=flow_data,
        flow_id=flow_id,
        organization_id=org_id,
        user_id=user_id,
        secret_store=vault_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )

    field = out["nodes"][0]["data"]["node"]["template"]["client_secret"]
    marker = field["value"]
    assert marker == autosecret_marker(flow_id, "ADPAuth-1", "client_secret")

    # Resolve back through the prefix-dispatch path.
    component = AsyncMock()
    with patch(
        "langflow.services.variable.resolver._get_org_id_for_flow",
        new=AsyncMock(return_value=org_id),
    ):
        resolved = await resolve_secret_reference(
            custom_component=component,
            name=marker,
            field="client_secret",
            session=AsyncMock(),
            secret_store=vault_store,
        )

    assert resolved == plaintext

    # Cleanup
    await delete_autosecrets_for_flow(
        flow_id=flow_id,
        organization_id=org_id,
        user_id=user_id,
        secret_store=vault_store,
        session=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_empty_resave_preserves_secret(vault_store, org_id, flow_id):
    """Issue 1 fix: real-Vault verification."""
    user_id = uuid4()
    plaintext = "round-1-cred"

    variable_service = AsyncMock()
    variable_service.has_user_managed_variable = AsyncMock(return_value=False)

    # First save
    first = await promote_plaintext_secrets_to_variables(
        flow_data=_flow_data(plaintext),
        flow_id=flow_id,
        organization_id=org_id,
        user_id=user_id,
        secret_store=vault_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )
    marker = first["nodes"][0]["data"]["node"]["template"]["client_secret"]["value"]

    # Second save with empty value (simulating frontend round-trip)
    second_data = _flow_data("")
    second = await promote_plaintext_secrets_to_variables(
        flow_data=second_data,
        flow_id=flow_id,
        organization_id=org_id,
        user_id=user_id,
        secret_store=vault_store,
        variable_service=variable_service,
        session=AsyncMock(),
    )

    field = second["nodes"][0]["data"]["node"]["template"]["client_secret"]
    assert field["value"] == marker, "Expected marker preserved across empty re-save"
    assert field["load_from_db"] is True

    # Vault entry intact
    payload = await vault_store.get(
        autosecret_vault_path(org_id, flow_id, "ADPAuth-1", "client_secret")
    )
    assert payload == {"value": plaintext}

    # Cleanup
    await delete_autosecrets_for_flow(
        flow_id=flow_id,
        organization_id=org_id,
        user_id=user_id,
        secret_store=vault_store,
        session=AsyncMock(),
    )
