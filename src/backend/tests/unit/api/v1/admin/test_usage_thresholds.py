from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_usage_thresholds_crud_happy_path(
    client: AsyncClient, logged_in_headers_platform_admin: dict, seeded_org
):
    # Create
    create_resp = await client.post(
        f"api/v1/admin/orgs/{seeded_org.id}/usage/thresholds",
        json={"metric": "runs", "period": "daily", "threshold_value": 100},
        headers=logged_in_headers_platform_admin,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    assert created["metric"] == "runs"
    threshold_id = created["id"]

    # List
    list_resp = await client.get(
        f"api/v1/admin/orgs/{seeded_org.id}/usage/thresholds",
        headers=logged_in_headers_platform_admin,
    )
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(t["id"] == threshold_id for t in list_resp.json()["items"])

    # Patch
    patch_resp = await client.patch(
        f"api/v1/admin/usage/thresholds/{threshold_id}",
        json={"threshold_value": 200, "is_active": False},
        headers=logged_in_headers_platform_admin,
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.json()["threshold_value"] == 200
    assert patch_resp.json()["is_active"] is False

    # Delete
    del_resp = await client.delete(
        f"api/v1/admin/usage/thresholds/{threshold_id}",
        headers=logged_in_headers_platform_admin,
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_usage_thresholds_reject_non_admin(
    client: AsyncClient, logged_in_headers: dict, seeded_org
):
    resp = await client.get(
        f"api/v1/admin/orgs/{seeded_org.id}/usage/thresholds", headers=logged_in_headers
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
