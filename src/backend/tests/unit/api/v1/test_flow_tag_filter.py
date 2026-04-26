"""Tests for tag_id filter on GET /api/v1/flows (OR semantics)."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


async def _create_flow(client: AsyncClient, headers: dict, name: str) -> dict:
    resp = await client.post(
        "api/v1/flows/",
        json={"name": name, "description": "t6", "data": {"nodes": [], "edges": []}},
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
async def test_flow_list_filters_by_single_tag_or(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    t1 = await _create_tag(client, admin_headers, "t6_x", "red")
    t2 = await _create_tag(client, admin_headers, "t6_y", "blue")

    f1 = await _create_flow(client, logged_in_headers, "t6_flow_a")
    f2 = await _create_flow(client, logged_in_headers, "t6_flow_b")
    f3 = await _create_flow(client, logged_in_headers, "t6_flow_c")

    # f1 tagged with t1, f2 with t2, f3 with both.
    await client.put(f"api/v1/flows/{f1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f2['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f3['id']}/tags", json={"tag_ids": [t1["id"], t2["id"]]}, headers=logged_in_headers)

    # Filter by t1 only: expect f1 and f3.
    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = {f["id"] for f in resp.json()}
    # Other tests may create flows too; assert our 3 are in the right groups.
    assert f1["id"] in ids
    assert f3["id"] in ids
    assert f2["id"] not in ids


@pytest.mark.asyncio
async def test_flow_list_or_semantics_across_two_tags(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    t1 = await _create_tag(client, admin_headers, "t6_or1", "green")
    t2 = await _create_tag(client, admin_headers, "t6_or2", "sky")

    f1 = await _create_flow(client, logged_in_headers, "t6_or_a")
    f2 = await _create_flow(client, logged_in_headers, "t6_or_b")
    f3 = await _create_flow(client, logged_in_headers, "t6_or_c")
    await client.put(f"api/v1/flows/{f1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f2['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=logged_in_headers)
    # f3 intentionally untagged

    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}&tag_id={t2['id']}",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = {f["id"] for f in resp.json()}
    assert f1["id"] in ids
    assert f2["id"] in ids
    assert f3["id"] not in ids


@pytest.mark.asyncio
async def test_flow_list_returns_each_flow_once_even_if_matches_multiple_tags(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    # Matches both tags — should appear once, not twice, in the response.
    t1 = await _create_tag(client, admin_headers, "t6_dup1", "amber")
    t2 = await _create_tag(client, admin_headers, "t6_dup2", "violet")

    f = await _create_flow(client, logged_in_headers, "t6_dup_flow")
    await client.put(f"api/v1/flows/{f['id']}/tags", json={"tag_ids": [t1["id"], t2["id"]]}, headers=logged_in_headers)

    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}&tag_id={t2['id']}",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    matching = [x for x in resp.json() if x["id"] == f["id"]]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_flow_list_without_tag_id_returns_all(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    # Baseline: no tag_id filter → returns flows (at least non-empty).
    resp = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    # Just verify the shape — existing tests cover content.
    assert isinstance(resp.json(), list)
