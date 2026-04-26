"""Tests for PUT /api/v1/flows/{flow_id}/tags (PUT-replaces-set semantics)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict, name: str) -> dict:
    """POST a minimal flow and return the response body."""
    resp = await client.post(
        "api/v1/flows/",
        json={"name": name, "description": "t5", "data": {"nodes": [], "edges": []}},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return resp.json()


async def _create_tag(client: AsyncClient, admin_headers: dict, name: str, color: str) -> dict:
    resp = await client.post(
        "api/v1/admin/tags",
        json={"name": name, "color": color},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_assign_tags_replaces_existing(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    # Regular user creates a flow (they own it).
    flow = await _create_flow(client, logged_in_headers, f"flow_t5_replace_{uuid4().hex[:6]}")

    # Admin seeds three tags (only admin can mutate vocabulary).
    suffix = uuid4().hex[:6]
    t1 = await _create_tag(client, admin_headers, f"t5_one_{suffix}", "red")
    t2 = await _create_tag(client, admin_headers, f"t5_two_{suffix}", "blue")
    t3 = await _create_tag(client, admin_headers, f"t5_three_{suffix}", "green")

    # First assignment: two tags.
    r1 = await client.put(
        f"api/v1/flows/{flow['id']}/tags",
        json={"tag_ids": [t1["id"], t2["id"]]},
        headers=logged_in_headers,
    )
    assert r1.status_code == status.HTTP_200_OK, r1.text
    body1 = r1.json()
    assert body1["id"] == flow["id"]
    assert {x["id"] for x in body1["tags"]} == {t1["id"], t2["id"]}

    # Second assignment: replace with a single different tag.
    r2 = await client.put(
        f"api/v1/flows/{flow['id']}/tags",
        json={"tag_ids": [t3["id"]]},
        headers=logged_in_headers,
    )
    assert r2.status_code == status.HTTP_200_OK, r2.text
    assert {x["id"] for x in r2.json()["tags"]} == {t3["id"]}

    # Third: empty the set.
    r3 = await client.put(
        f"api/v1/flows/{flow['id']}/tags",
        json={"tag_ids": []},
        headers=logged_in_headers,
    )
    assert r3.status_code == status.HTTP_200_OK
    assert r3.json()["tags"] == []


@pytest.mark.asyncio
async def test_assign_unknown_tag_returns_422(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    flow = await _create_flow(client, logged_in_headers, f"flow_t5_unknown_{uuid4().hex[:6]}")
    resp = await client.put(
        f"api/v1/flows/{flow['id']}/tags",
        json={"tag_ids": [str(uuid4())]},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_assign_tags_to_unknown_flow_returns_404(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    resp = await client.put(
        f"api/v1/flows/{uuid4()}/tags",
        json={"tag_ids": []},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_assign_unauth_returns_403(client: AsyncClient) -> None:
    resp = await client.put(
        f"api/v1/flows/{uuid4()}/tags",
        json={"tag_ids": []},
    )
    # Fork convention: auto_error=False on security schemes → 403, not 401.
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_cannot_assign_to_anothers_flow_returns_404(
    client: AsyncClient, two_org_fixture, admin_headers: dict
) -> None:
    actor_dict, _, other_dict, _ = two_org_fixture
    # `other` user creates a flow in their org.
    other_flow = await _create_flow(
        client, other_dict["headers"], f"flow_t5_cross_org_{uuid4().hex[:6]}"
    )
    # `actor` user (different org) tries to assign tags — should 404 (not visible).
    t = await _create_tag(client, admin_headers, f"t5_cross_{uuid4().hex[:6]}", "amber")
    resp = await client.put(
        f"api/v1/flows/{other_flow['id']}/tags",
        json={"tag_ids": [t["id"]]},
        headers=actor_dict["headers"],
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
