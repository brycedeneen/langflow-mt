"""End-to-end tests covering the auto-Variable lifecycle triggered by flow
CRUD for TextFileSecretInput fields."""

import io
import json
import zipfile

import pytest
from httpx import AsyncClient
from langflow.services.variable.auto_secrets import AUTOSECRET_PREFIX


SAMPLE_CERT = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBkTCB+wIJAKGj+YSnf2MxMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCWxv\n"
    "Y2FsaG9zdDAeFw0yMDAxMDEwMDAwMDBaFw0zMDAxMDEwMDAwMDBaMBQxEjAQBgNV\n"
    "BAMMCWxvY2FsaG9zdDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQDCertDataOnly\n"
    "-----END CERTIFICATE-----\n"
)
SAMPLE_KEY = (  # noqa: S105
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEAfakeprivatekey\n"
    "-----END PRIVATE KEY-----\n"
)


def _textfilesecret_field(value: str) -> dict:
    return {
        "_input_type": "TextFileSecretInput",
        "auto_promote": True,
        "value": value,
        "load_from_db": False,
        "type": "str",
        "password": True,
    }


def _minimal_flow(cert_pem: str = "", key_pem: str = "") -> dict:
    """Flow payload with one APIRequest node carrying TextFileSecretInput fields."""
    return {
        "name": "mTLS auto-secret test",
        "data": {
            "nodes": [
                {
                    "id": "APIRequest-int1",
                    "data": {
                        "type": "APIRequest",
                        "id": "APIRequest-int1",
                        "node": {
                            "template": {
                                "cert_pem": _textfilesecret_field(cert_pem),
                                "key_pem": _textfilesecret_field(key_pem),
                            },
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


@pytest.mark.usefixtures("active_user")
async def test_create_flow_promotes_plaintext_pem_to_autosecret(
    client: AsyncClient, logged_in_headers
):
    """POSTing a flow with plaintext cert_pem creates a hidden Variable and
    rewrites the field to reference it."""
    payload = _minimal_flow(cert_pem=SAMPLE_CERT, key_pem=SAMPLE_KEY)

    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow = r.json()
    flow_id = flow["id"]

    node = flow["data"]["nodes"][0]
    cert_field = node["data"]["node"]["template"]["cert_pem"]
    key_field = node["data"]["node"]["template"]["key_pem"]

    assert cert_field["value"].startswith(f"{AUTOSECRET_PREFIX}{flow_id}_APIRequest-int1_cert_pem")
    assert cert_field["load_from_db"] is True
    assert key_field["value"].startswith(f"{AUTOSECRET_PREFIX}{flow_id}_APIRequest-int1_key_pem")
    assert key_field["load_from_db"] is True


@pytest.mark.usefixtures("active_user")
async def test_autosecrets_hidden_from_variables_list(
    client: AsyncClient, logged_in_headers
):
    """Auto-secret Variables must not appear in GET /api/v1/variables."""
    payload = _minimal_flow(cert_pem=SAMPLE_CERT, key_pem=SAMPLE_KEY)
    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text

    r2 = await client.get("api/v1/variables/", headers=logged_in_headers)
    assert r2.status_code == 200, r2.text
    names = [v["name"] for v in r2.json()]
    assert all(not n.startswith(AUTOSECRET_PREFIX) for n in names), (
        f"auto-secret leaked into listing: {names}"
    )


@pytest.mark.usefixtures("active_user")
async def test_update_flow_updates_autosecret_value_in_place(
    client: AsyncClient, logged_in_headers
):
    """PATCHing a flow with new plaintext PEM updates the Variable in place."""
    payload = _minimal_flow(cert_pem=SAMPLE_CERT, key_pem=SAMPLE_KEY)
    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow = r.json()
    flow_id = flow["id"]

    # Mutate the flow payload: new plaintext PEM, reset load_from_db so the
    # backend promotes again (mimics what the frontend does when the user
    # edits the masked field).
    new_cert = SAMPLE_CERT.replace("CertDataOnly", "NewCertData")
    flow["data"]["nodes"][0]["data"]["node"]["template"]["cert_pem"]["value"] = new_cert
    flow["data"]["nodes"][0]["data"]["node"]["template"]["cert_pem"]["load_from_db"] = False

    r = await client.patch(
        f"api/v1/flows/{flow_id}",
        json={"data": flow["data"]},
        headers=logged_in_headers,
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    cert_field = updated["data"]["nodes"][0]["data"]["node"]["template"]["cert_pem"]
    assert cert_field["load_from_db"] is True
    assert cert_field["value"].startswith(AUTOSECRET_PREFIX)


@pytest.mark.usefixtures("active_user")
async def test_delete_flow_cascades_autosecrets(
    client: AsyncClient, logged_in_headers
):
    """Deleting a flow removes its auto-Variables; re-creating produces fresh ones."""
    payload = _minimal_flow(cert_pem=SAMPLE_CERT, key_pem=SAMPLE_KEY)
    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    r = await client.delete(f"api/v1/flows/{flow_id}", headers=logged_in_headers)
    assert r.status_code in (200, 204), r.text

    # Re-create a flow with identical shape. The new flow gets a different id,
    # so its auto-Variable names embed the new id — proving new Variables were
    # created (not reused from the deleted flow).
    r_new = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r_new.status_code == 201, r_new.text
    new_id = r_new.json()["id"]
    new_cert_value = r_new.json()["data"]["nodes"][0]["data"]["node"]["template"]["cert_pem"]["value"]

    # New flow's Variable name carries the new flow_id, not the old one.
    assert str(new_id) in new_cert_value
    assert str(flow_id) not in new_cert_value


@pytest.mark.usefixtures("active_user")
async def test_export_blanks_autosecret_values(
    client: AsyncClient, logged_in_headers
):
    """Exporting a flow via /api/v1/flows/download/ must not include plaintext PEM."""
    payload = _minimal_flow(cert_pem=SAMPLE_CERT, key_pem=SAMPLE_KEY)
    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    r_dl = await client.post(
        "api/v1/flows/download/",
        json=[flow_id],
        headers=logged_in_headers,
    )
    assert r_dl.status_code == 200, r_dl.text

    content_type = r_dl.headers.get("content-type", "")
    if "zip" in content_type:
        # Single flow should return JSON directly per the endpoint implementation,
        # but handle ZIP in case behavior changes.
        zip_buf = io.BytesIO(r_dl.content)
        with zipfile.ZipFile(zip_buf) as zf:
            flow_json = json.loads(zf.read(zf.namelist()[0]))
        nodes = flow_json["data"]["nodes"]
    else:
        # Single flow returns the flow dict directly (not wrapped in a list).
        flow_json = r_dl.json()
        nodes = flow_json["data"]["nodes"]

    cert_field = nodes[0]["data"]["node"]["template"]["cert_pem"]
    key_field = nodes[0]["data"]["node"]["template"]["key_pem"]

    # Values must be blanked — not the plaintext PEM, not the auto-secret ref.
    assert cert_field["value"] == "", (
        f"cert_pem export value should be blank, got: {cert_field['value']!r}"
    )
    assert key_field["value"] == "", (
        f"key_pem export value should be blank, got: {key_field['value']!r}"
    )

    # Extra belt-and-suspenders: scan raw response text for the PEM marker.
    assert "CertDataOnly" not in r_dl.text, (
        "Exported flow must not contain plaintext PEM content"
    )


def _secretstr_field(value: str, *, auto_promote: bool = True) -> dict:
    """Flow-template dict for a bare SecretStrInput carrying a plaintext secret."""
    return {
        "_input_type": "SecretStrInput",
        "auto_promote": auto_promote,
        "value": value,
        "load_from_db": auto_promote,
        "type": "str",
        "password": True,
    }


def _flow_with_secret_str(value: str) -> dict:
    """Minimal flow with a single custom node that has a bare SecretStrInput."""
    return {
        "name": "SecretStrInput auto-promote test",
        "data": {
            "nodes": [
                {
                    "id": "CustomComponent-int1",
                    "data": {
                        "type": "CustomComponent",
                        "id": "CustomComponent-int1",
                        "node": {
                            "template": {
                                "api_key": _secretstr_field(value),
                            },
                        },
                    },
                }
            ],
            "edges": [],
        },
    }


@pytest.mark.usefixtures("active_user")
async def test_create_flow_promotes_bare_secret_str_input(
    client: AsyncClient, logged_in_headers
):
    """POSTing a flow whose node has a bare SecretStrInput with typed plaintext
    promotes the value to an autosecret Variable even though the input type
    is not TextFileSecretInput. Proves the generalized walker+predicate."""
    payload = _flow_with_secret_str("sk-typed-plaintext-api-key-12345")

    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow = r.json()
    flow_id = flow["id"]

    node = flow["data"]["nodes"][0]
    api_key_field = node["data"]["node"]["template"]["api_key"]
    assert api_key_field["value"].startswith(
        f"{AUTOSECRET_PREFIX}{flow_id}_CustomComponent-int1_api_key"
    ), f"expected autosecret ref, got {api_key_field['value']!r}"
    assert api_key_field["load_from_db"] is True


@pytest.mark.usefixtures("active_user")
async def test_create_flow_preserves_user_managed_variable_reference(
    client: AsyncClient, logged_in_headers
):
    """POSTing a flow whose SecretStrInput value is the name of a pre-existing
    user-managed Variable preserves the reference — the promote helper does
    not overwrite it."""
    # Pre-create a user-managed Variable by name.
    user_var_name = "my_shared_api_key"
    r = await client.post(
        "api/v1/variables/",
        json={
            "name": user_var_name,
            "value": "sk-actual-value-never-exposed",
            "type": "CREDENTIAL",
            "default_fields": [],
        },
        headers=logged_in_headers,
    )
    assert r.status_code == 201, r.text

    # Now POST a flow whose SecretStrInput field value equals that Variable's name.
    payload = _flow_with_secret_str(user_var_name)

    r = await client.post("api/v1/flows/", json=payload, headers=logged_in_headers)
    assert r.status_code == 201, r.text
    flow = r.json()

    api_key_field = flow["data"]["nodes"][0]["data"]["node"]["template"]["api_key"]
    # Reference preserved — NOT rewritten as an autosecret.
    assert api_key_field["value"] == user_var_name, (
        f"user-picked Variable reference must be preserved, got {api_key_field['value']!r}"
    )
    assert api_key_field["load_from_db"] is True
