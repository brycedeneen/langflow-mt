"""Tests that GET /api/v1/flows/ returns flows with populated tags field."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_flow_read_includes_tags_after_assignment(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    # Seed two tags via admin CRUD.
    t1 = (await client.post(
        "api/v1/admin/tags", json={"name": "ft2_alpha", "color": "blue"}, headers=admin_headers
    )).json()
    t2 = (await client.post(
        "api/v1/admin/tags", json={"name": "ft2_beta", "color": "green"}, headers=admin_headers
    )).json()

    # Regular user creates a flow and assigns both tags.
    create_resp = await client.post(
        "api/v1/flows/",
        json={"name": "ft2_flow", "description": "t2", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED, create_resp.text
    flow = create_resp.json()
    assign_resp = await client.put(
        f"api/v1/flows/{flow['id']}/tags",
        json={"tag_ids": [t1["id"], t2["id"]]},
        headers=logged_in_headers,
    )
    assert assign_resp.status_code == status.HTTP_200_OK

    # GET /api/v1/flows/ should return the flow with both tags populated.
    resp = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    # Default response is a raw list when get_all=True.
    mine = [f for f in body if f["id"] == flow["id"]]
    assert len(mine) == 1
    returned_tags = mine[0].get("tags") or []
    returned_ids = {t["id"] for t in returned_tags}
    assert returned_ids == {t1["id"], t2["id"]}
    # Each tag carries the full TagRead shape.
    sample = returned_tags[0]
    assert set(sample.keys()) >= {"id", "name", "color"}


@pytest.mark.asyncio
async def test_flow_read_tags_empty_list_when_unassigned(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    flow = (await client.post(
        "api/v1/flows/",
        json={"name": "ft2_notags", "description": "", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )).json()

    resp = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    mine = [f for f in resp.json() if f["id"] == flow["id"]]
    assert len(mine) == 1
    assert mine[0].get("tags") == []
