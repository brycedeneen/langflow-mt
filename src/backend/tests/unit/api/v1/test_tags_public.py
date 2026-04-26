"""Tests for GET /api/v1/tags (any authenticated user can read the vocabulary)."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_any_authenticated_user_lists_tags(
    client: AsyncClient,
    admin_headers: dict,
    logged_in_headers: dict,
) -> None:
    # Platform admin seeds three tags via the admin endpoint (Task 3).
    for name, color in [("a", "blue"), ("b", "red"), ("c", "green")]:
        resp = await client.post(
            "api/v1/admin/tags",
            json={"name": name, "color": color},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.text

    # A regular logged-in user can list them.
    resp = await client.get("api/v1/tags", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    names = [t["name"] for t in resp.json()]
    assert {"a", "b", "c"}.issubset(set(names))


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client: AsyncClient) -> None:
    resp = await client.get("api/v1/tags")
    # Fork uses auto_error=False on security schemes; missing auth → 403.
    # (See tests/unit/api/v1/admin/test_tags_admin.py for the precedent.)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_ordered_by_name(
    client: AsyncClient,
    admin_headers: dict,
    logged_in_headers: dict,
) -> None:
    for name, color in [("zeta", "red"), ("alpha", "green"), ("mu", "sky")]:
        await client.post(
            "api/v1/admin/tags",
            json={"name": name, "color": color},
            headers=admin_headers,
        )
    resp = await client.get("api/v1/tags", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    names = [t["name"] for t in resp.json()]
    subset = [n for n in names if n in {"alpha", "mu", "zeta"}]
    assert subset == sorted(subset)
