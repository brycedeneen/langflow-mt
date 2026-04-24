"""Tests for tag_id filter on GET /api/v1/templates (OR semantics)."""

from __future__ import annotations

import uuid
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


@pytest.fixture
async def source_flow(platform_admin_user):
    """A flow owned by platform_admin to use as template source."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        flow = Flow(
            name=f"src-flow-t6-{uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=admin_uid,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id

    yield flow_id

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow:
            await session.delete(db_flow)


async def _create_template(
    client: AsyncClient, admin_headers: dict, source_flow_id, name: str
) -> dict:
    # Platform-scoped template (org_id=null) creatable by platform admins.
    resp = await client.post(
        "api/v1/templates",
        json={
            "source_flow_id": str(source_flow_id),
            "name": name,
            "scope": "platform",
        },
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return resp.json()


async def _delete_template(template_id: str) -> None:
    async with session_scope() as session:
        tmpl = await session.get(Template, uuid.UUID(template_id))
        if tmpl:
            await session.delete(tmpl)


async def _create_tag(client: AsyncClient, admin_headers: dict, name: str, color: str) -> dict:
    resp = await client.post(
        "api/v1/admin/tags", json={"name": name, "color": color}, headers=admin_headers
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_template_list_filters_by_single_tag_or(
    client: AsyncClient, admin_headers: dict, source_flow
) -> None:
    t1 = await _create_tag(client, admin_headers, "tt6_a", "red")
    t2 = await _create_tag(client, admin_headers, "tt6_b", "blue")

    tmpl1 = await _create_template(client, admin_headers, source_flow, "tt6_tmpl_a")
    tmpl2 = await _create_template(client, admin_headers, source_flow, "tt6_tmpl_b")
    try:
        await client.put(f"api/v1/templates/{tmpl1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=admin_headers)
        await client.put(f"api/v1/templates/{tmpl2['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=admin_headers)

        resp = await client.get(f"api/v1/templates?tag_id={t1['id']}", headers=admin_headers)
        assert resp.status_code == status.HTTP_200_OK
        ids = {x["id"] for x in resp.json()}
        assert tmpl1["id"] in ids
        assert tmpl2["id"] not in ids
    finally:
        await _delete_template(tmpl1["id"])
        await _delete_template(tmpl2["id"])


@pytest.mark.asyncio
async def test_template_list_or_semantics_across_two_tags(
    client: AsyncClient, admin_headers: dict, source_flow
) -> None:
    t1 = await _create_tag(client, admin_headers, "tt6_or1", "green")
    t2 = await _create_tag(client, admin_headers, "tt6_or2", "sky")

    tmpl1 = await _create_template(client, admin_headers, source_flow, "tt6_or_a")
    tmpl2 = await _create_template(client, admin_headers, source_flow, "tt6_or_b")
    try:
        await client.put(f"api/v1/templates/{tmpl1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=admin_headers)
        await client.put(f"api/v1/templates/{tmpl2['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=admin_headers)

        resp = await client.get(
            f"api/v1/templates?tag_id={t1['id']}&tag_id={t2['id']}",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        ids = {x["id"] for x in resp.json()}
        assert tmpl1["id"] in ids
        assert tmpl2["id"] in ids
    finally:
        await _delete_template(tmpl1["id"])
        await _delete_template(tmpl2["id"])


@pytest.mark.asyncio
async def test_template_list_deduplicates_when_template_has_multiple_matching_tags(
    client: AsyncClient, admin_headers: dict, source_flow
) -> None:
    t1 = await _create_tag(client, admin_headers, "tt6_dup1", "teal")
    t2 = await _create_tag(client, admin_headers, "tt6_dup2", "pink")

    tmpl = await _create_template(client, admin_headers, source_flow, "tt6_dup_tmpl")
    try:
        await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [t1["id"], t2["id"]]},
            headers=admin_headers,
        )
        resp = await client.get(
            f"api/v1/templates?tag_id={t1['id']}&tag_id={t2['id']}",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        matching = [x for x in resp.json() if x["id"] == tmpl["id"]]
        assert len(matching) == 1
    finally:
        await _delete_template(tmpl["id"])
