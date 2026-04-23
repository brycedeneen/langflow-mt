from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_alert_rules_crud_happy_path(
    client: AsyncClient, logged_in_headers_platform_admin: dict, seeded_org
):
    # Create
    create_resp = await client.post(
        f"api/v1/admin/orgs/{seeded_org.id}/alert-rules",
        json={
            "rule_type": "consecutive_failures",
            "config": {"n": 3},
        },
        headers=logged_in_headers_platform_admin,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    assert created["rule_type"] == "consecutive_failures"
    rule_id = created["id"]

    # List
    list_resp = await client.get(
        f"api/v1/admin/orgs/{seeded_org.id}/alert-rules",
        headers=logged_in_headers_platform_admin,
    )
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(r["id"] == rule_id for r in list_resp.json()["items"])

    # Patch
    patch_resp = await client.patch(
        f"api/v1/admin/alert-rules/{rule_id}",
        json={"is_active": False},
        headers=logged_in_headers_platform_admin,
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["is_active"] is False

    # Delete
    del_resp = await client.delete(
        f"api/v1/admin/alert-rules/{rule_id}",
        headers=logged_in_headers_platform_admin,
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_alert_rule_rejects_invalid_consecutive_failures_config(
    client: AsyncClient, logged_in_headers_platform_admin: dict, seeded_org
):
    resp = await client.post(
        f"api/v1/admin/orgs/{seeded_org.id}/alert-rules",
        json={"rule_type": "consecutive_failures", "config": {"n": 0}},
        headers=logged_in_headers_platform_admin,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
