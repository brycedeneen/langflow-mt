"""Test that GET /api/v1/variables excludes auto-secret Variables."""

import pytest
from httpx import AsyncClient
from langflow.services.variable.auto_secrets import AUTOSECRET_PREFIX
from langflow.services.variable.constants import CREDENTIAL_TYPE


@pytest.mark.usefixtures("active_user")
async def test_read_variables_excludes_autosecret_prefix(
    client: AsyncClient,
    logged_in_headers,
):
    """Auto-secret Variables must not appear in GET /api/v1/variables."""
    # Create a normal user-managed variable
    user_var = {
        "name": "my_api_key",
        "value": "user-value",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }
    r = await client.post("api/v1/variables/", json=user_var, headers=logged_in_headers)
    assert r.status_code == 201, r.text

    # Create an auto-secret variable (name starts with AUTOSECRET_PREFIX)
    auto_var = {
        "name": f"{AUTOSECRET_PREFIX}flow123_node456_cert_pem",
        "value": "-----BEGIN CERTIFICATE-----\nMIIA...\n-----END CERTIFICATE-----",
        "type": CREDENTIAL_TYPE,
        "default_fields": [],
    }
    r = await client.post("api/v1/variables/", json=auto_var, headers=logged_in_headers)
    assert r.status_code == 201, r.text

    # GET /api/v1/variables should return only the user-managed one
    r = await client.get("api/v1/variables/", headers=logged_in_headers)
    assert r.status_code == 200, r.text

    names = [v["name"] for v in r.json()]
    assert "my_api_key" in names, f"Expected user variable in listing, got: {names}"
    assert not any(
        n.startswith(AUTOSECRET_PREFIX) for n in names
    ), f"Auto-secret variable leaked into listing: {names}"
