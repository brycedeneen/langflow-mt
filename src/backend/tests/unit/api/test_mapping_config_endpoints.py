"""Tests for POST /api/v1/validate/validate-mapping-config."""

import pytest
from fastapi import status
from httpx import AsyncClient


VALID_CFG = {
    "driver_index": 0,
    "inputs": [
        {
            "alias": "workers",
            "schema_source": "autodetect",
            "schema": {"fields": [{"name": "user_id", "type": "str", "required": True}]},
        }
    ],
    "destination_schema": [
        {"name": "External_ID", "type": "str", "required": True, "default": None},
    ],
    "mappings": [
        {
            "destination": "External_ID",
            "transform": "direct",
            "sources": [{"input": "workers", "field": "user_id"}],
            "config": {},
        }
    ],
}

ENDPOINT = "api/v1/validate/validate-mapping-config"


async def test_validate_mapping_config_valid_returns_empty_errors(
    client: AsyncClient, logged_in_headers, active_user
):
    """Valid config returns HTTP 200 with empty error list."""
    r = await client.post(ENDPOINT, json=VALID_CFG, headers=logged_in_headers)
    assert r.status_code == status.HTTP_200_OK
    assert r.json() == {"errors": []}


async def test_validate_mapping_config_unknown_transform_returns_422(
    client: AsyncClient, logged_in_headers, active_user
):
    """Unknown transform value triggers HTTP 422 with a path pointing at mappings."""
    bad_mapping = {**VALID_CFG["mappings"][0], "transform": "bogus"}
    cfg = {**VALID_CFG, "mappings": [bad_mapping]}

    r = await client.post(ENDPOINT, json=cfg, headers=logged_in_headers)
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = r.json()
    errors = body["errors"]
    assert len(errors) >= 1
    # The pydantic error for a bad Literal hits the 'transform' field inside mappings
    paths = [" ".join(str(p) for p in e["path"]) for e in errors]
    assert any("mappings" in p or "transform" in p or "bogus" in e["message"] for p, e in zip(paths, errors))


async def test_validate_mapping_config_missing_required_dest_returns_422(
    client: AsyncClient, logged_in_headers, active_user
):
    """Required destination field with no mapping triggers HTTP 422 mentioning that field."""
    cfg = {
        **VALID_CFG,
        "destination_schema": [
            {"name": "External_ID", "type": "str", "required": True, "default": None},
            {"name": "Email", "type": "str", "required": True, "default": None},
        ],
        # Only External_ID is mapped; Email is required but unmapped
        "mappings": VALID_CFG["mappings"],
    }

    r = await client.post(ENDPOINT, json=cfg, headers=logged_in_headers)
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = r.json()
    assert any("Email" in e["message"] for e in body["errors"])


async def test_validate_mapping_config_requires_auth(client: AsyncClient):
    """Unauthenticated request (no auth header) is rejected — Langflow returns 403."""
    r = await client.post(ENDPOINT, json=VALID_CFG)
    # Langflow returns 403 for missing credentials (401 is for invalid/expired tokens)
    assert r.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# POST /api/v1/validate/jsonschema-to-fields  (Task 4)
# ---------------------------------------------------------------------------

SCHEMA_ENDPOINT = "api/v1/validate/jsonschema-to-fields"

BASIC_SCHEMA = {
    "type": "object",
    "properties": {
        "user_id": {"type": "integer"},
        "name": {"type": "string"},
        "active": {"type": "boolean"},
    },
    "required": ["user_id"],
}


async def test_jsonschema_to_fields_basic_object(
    client: AsyncClient, logged_in_headers, active_user
):
    """Basic object schema produces flat field list with correct types and required flag."""
    r = await client.post(SCHEMA_ENDPOINT, json=BASIC_SCHEMA, headers=logged_in_headers)
    assert r.status_code == status.HTTP_200_OK

    body = r.json()
    assert "fields" in body
    fields = {f["name"]: f for f in body["fields"]}

    assert fields["user_id"]["type"] == "int"
    assert fields["user_id"]["required"] is True

    assert fields["name"]["type"] == "str"
    assert fields["name"]["required"] is False

    assert fields["active"]["type"] == "bool"
    assert fields["active"]["required"] is False


async def test_jsonschema_to_fields_datetime_format(
    client: AsyncClient, logged_in_headers, active_user
):
    """format:date-time and format:date are mapped to 'datetime' and 'date' types."""
    schema = {
        "type": "object",
        "properties": {
            "created_at": {"type": "string", "format": "date-time"},
            "birth_date": {"type": "string", "format": "date"},
            "label": {"type": "string"},
        },
    }
    r = await client.post(SCHEMA_ENDPOINT, json=schema, headers=logged_in_headers)
    assert r.status_code == status.HTTP_200_OK

    fields = {f["name"]: f for f in r.json()["fields"]}
    assert fields["created_at"]["type"] == "datetime"
    assert fields["birth_date"]["type"] == "date"
    assert fields["label"]["type"] == "str"


async def test_jsonschema_to_fields_malformed_schema_returns_400(
    client: AsyncClient, logged_in_headers, active_user
):
    """A schema that fails $ref resolution / shape validation returns HTTP 400."""
    bad_schema = {"$ref": "#/definitions/DoesNotExist"}
    r = await client.post(SCHEMA_ENDPOINT, json=bad_schema, headers=logged_in_headers)
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    body = r.json()
    assert "detail" in body
