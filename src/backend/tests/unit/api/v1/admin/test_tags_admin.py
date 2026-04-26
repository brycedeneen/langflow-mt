"""Tests for /api/v1/admin/tags (PlatformAdmin-gated tag vocabulary CRUD)."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_regular_user_cannot_create_tag(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    resp = await client.post(
        "api/v1/admin/tags",
        json={"name": "finance", "color": "blue"},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client: AsyncClient) -> None:
    # Fork convention: missing credentials return 403 (not 401) for admin
    # routes — see test_audit_logs / test_notifications / test_users etc.
    # The auth dep uses auto_error=False on the OAuth2 scheme and bubbles up a
    # 403 when no token is present.
    resp = await client.post(
        "api/v1/admin/tags",
        json={"name": "finance", "color": "blue"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_platform_admin_creates_and_reads_tag(
    client: AsyncClient, admin_headers: dict
) -> None:
    resp = await client.post(
        "api/v1/admin/tags",
        json={"name": "finance", "color": "blue", "description": "cost center"},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    body = resp.json()
    assert body["name"] == "finance"
    assert body["color"] == "blue"
    tag_id = body["id"]

    r2 = await client.get(f"api/v1/admin/tags/{tag_id}", headers=admin_headers)
    assert r2.status_code == status.HTTP_200_OK
    assert r2.json()["description"] == "cost center"


@pytest.mark.asyncio
async def test_list_orders_by_name(
    client: AsyncClient, admin_headers: dict
) -> None:
    for name, color in [("zeta", "red"), ("alpha", "green"), ("mu", "sky")]:
        await client.post(
            "api/v1/admin/tags", json={"name": name, "color": color}, headers=admin_headers
        )
    resp = await client.get("api/v1/admin/tags", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    names = [t["name"] for t in resp.json()]
    # include just the three we created — other tests may have left rows
    subset = [n for n in names if n in {"alpha", "mu", "zeta"}]
    assert subset == sorted(subset)


@pytest.mark.asyncio
async def test_create_duplicate_name_case_insensitive_returns_409(
    client: AsyncClient, admin_headers: dict
) -> None:
    await client.post(
        "api/v1/admin/tags", json={"name": "HR", "color": "green"}, headers=admin_headers
    )
    resp = await client.post(
        "api/v1/admin/tags", json={"name": "hr", "color": "red"}, headers=admin_headers
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_create_invalid_color_returns_422(
    client: AsyncClient, admin_headers: dict
) -> None:
    resp = await client.post(
        "api/v1/admin/tags",
        json={"name": "bad", "color": "purple"},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_put_updates_tag(
    client: AsyncClient, admin_headers: dict
) -> None:
    created = (
        await client.post(
            "api/v1/admin/tags",
            json={"name": "ops", "color": "slate"},
            headers=admin_headers,
        )
    ).json()
    resp = await client.put(
        f"api/v1/admin/tags/{created['id']}",
        json={"name": "ops", "color": "red"},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["color"] == "red"


@pytest.mark.asyncio
async def test_delete_tag_returns_204_and_subsequent_get_404s(
    client: AsyncClient, admin_headers: dict
) -> None:
    created = (
        await client.post(
            "api/v1/admin/tags",
            json={"name": "temp", "color": "amber"},
            headers=admin_headers,
        )
    ).json()
    resp = await client.delete(
        f"api/v1/admin/tags/{created['id']}", headers=admin_headers
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    resp2 = await client.get(f"api/v1/admin/tags/{created['id']}", headers=admin_headers)
    assert resp2.status_code == status.HTTP_404_NOT_FOUND
