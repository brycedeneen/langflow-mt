"""Tests that GET /api/v1/templates returns templates with populated tags field."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope


async def _create_template_with_source_flow(
    client: AsyncClient, admin_headers: dict, name: str
) -> dict:
    """Create a platform-scoped template via the API. Returns JSON."""
    # Seed a source flow via raw SQLModel session (API create requires one).
    async with session_scope() as session:
        flow = Flow(
            id=uuid4(),
            name=f"{name}-source",
            data={"nodes": [], "edges": []},
            user_id=None,
            organization_id=None,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        source_id = flow.id

    resp = await client.post(
        "api/v1/templates",
        json={"name": name, "scope": "platform", "source_flow_id": str(source_id)},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return resp.json()


async def _cleanup_template(admin_headers: dict, template_id: str, client: AsyncClient) -> None:
    await client.delete(f"api/v1/templates/{template_id}", headers=admin_headers)


@pytest.mark.asyncio
async def test_template_list_includes_tags_after_assignment(
    client: AsyncClient, admin_headers: dict
) -> None:
    t1 = (await client.post(
        "api/v1/admin/tags", json={"name": "tt2_x", "color": "teal"}, headers=admin_headers
    )).json()
    t2 = (await client.post(
        "api/v1/admin/tags", json={"name": "tt2_y", "color": "pink"}, headers=admin_headers
    )).json()

    tmpl = await _create_template_with_source_flow(client, admin_headers, "tt2_tmpl")
    try:
        await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [t1["id"], t2["id"]]},
            headers=admin_headers,
        )
        resp = await client.get("api/v1/templates", headers=admin_headers)
        assert resp.status_code == status.HTTP_200_OK
        mine = [x for x in resp.json() if x["id"] == tmpl["id"]]
        assert len(mine) == 1
        returned_ids = {t["id"] for t in mine[0].get("tags", [])}
        assert returned_ids == {t1["id"], t2["id"]}
    finally:
        await _cleanup_template(admin_headers, tmpl["id"], client)


@pytest.mark.asyncio
async def test_template_list_tags_empty_when_unassigned(
    client: AsyncClient, admin_headers: dict
) -> None:
    tmpl = await _create_template_with_source_flow(client, admin_headers, "tt2_bare")
    try:
        resp = await client.get("api/v1/templates", headers=admin_headers)
        assert resp.status_code == status.HTTP_200_OK
        mine = [x for x in resp.json() if x["id"] == tmpl["id"]]
        assert len(mine) == 1
        assert mine[0].get("tags") == []
    finally:
        await _cleanup_template(admin_headers, tmpl["id"], client)
