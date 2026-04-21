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
