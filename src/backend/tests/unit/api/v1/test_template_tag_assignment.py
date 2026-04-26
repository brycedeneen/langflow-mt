"""Tests for PUT /api/v1/templates/{template_id}/tags (PUT-replaces-set semantics)."""

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
            name=f"src-flow-t5-{uuid4()}",
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


async def _create_platform_template(
    client: AsyncClient, admin_headers: dict, source_flow_id, name: str
) -> dict:
    """POST a minimal platform-scoped template and return the response body."""
    resp = await client.post(
        "api/v1/templates",
        headers=admin_headers,
        json={
            "source_flow_id": str(source_flow_id),
            "name": name,
            "scope": "platform",
        },
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


async def _delete_template(template_id: uuid.UUID) -> None:
    async with session_scope() as session:
        tmpl = await session.get(Template, template_id)
        if tmpl:
            await session.delete(tmpl)


@pytest.mark.asyncio
async def test_assign_tags_replaces_existing(
    client: AsyncClient, admin_headers: dict, source_flow
) -> None:
    tmpl = await _create_platform_template(
        client, admin_headers, source_flow, f"Tmpl-t5-replace-{uuid4().hex[:6]}"
    )
    tmpl_id = uuid.UUID(tmpl["id"])

    try:
        suffix = uuid4().hex[:6]
        t1 = await _create_tag(client, admin_headers, f"tt5_one_{suffix}", "red")
        t2 = await _create_tag(client, admin_headers, f"tt5_two_{suffix}", "blue")
        t3 = await _create_tag(client, admin_headers, f"tt5_three_{suffix}", "green")

        r1 = await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [t1["id"], t2["id"]]},
            headers=admin_headers,
        )
        assert r1.status_code == status.HTTP_200_OK, r1.text
        body1 = r1.json()
        assert body1["id"] == tmpl["id"]
        assert {x["id"] for x in body1["tags"]} == {t1["id"], t2["id"]}

        r2 = await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [t3["id"]]},
            headers=admin_headers,
        )
        assert r2.status_code == status.HTTP_200_OK
        assert {x["id"] for x in r2.json()["tags"]} == {t3["id"]}

        r3 = await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": []},
            headers=admin_headers,
        )
        assert r3.status_code == status.HTTP_200_OK
        assert r3.json()["tags"] == []
    finally:
        await _delete_template(tmpl_id)


@pytest.mark.asyncio
async def test_assign_unknown_tag_returns_422(
    client: AsyncClient, admin_headers: dict, source_flow
) -> None:
    tmpl = await _create_platform_template(
        client, admin_headers, source_flow, f"Tmpl-t5-unknown-{uuid4().hex[:6]}"
    )
    tmpl_id = uuid.UUID(tmpl["id"])

    try:
        resp = await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [str(uuid4())]},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    finally:
        await _delete_template(tmpl_id)


@pytest.mark.asyncio
async def test_assign_tags_to_unknown_template_returns_404(
    client: AsyncClient, admin_headers: dict
) -> None:
    resp = await client.put(
        f"api/v1/templates/{uuid4()}/tags",
        json={"tag_ids": []},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_assign_unauth_returns_403(client: AsyncClient) -> None:
    resp = await client.put(
        f"api/v1/templates/{uuid4()}/tags",
        json={"tag_ids": []},
    )
    # Fork convention: auto_error=False on security schemes → 403.
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_regular_user_cannot_assign_to_platform_template_returns_403(
    client: AsyncClient,
    admin_headers: dict,
    logged_in_headers: dict,
    source_flow,
) -> None:
    tmpl = await _create_platform_template(
        client, admin_headers, source_flow, f"Tmpl-t5-forbidden-{uuid4().hex[:6]}"
    )
    tmpl_id = uuid.UUID(tmpl["id"])

    try:
        t = await _create_tag(
            client, admin_headers, f"tt5_forbid_{uuid4().hex[:6]}", "violet"
        )
        resp = await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [t["id"]]},
            headers=logged_in_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        await _delete_template(tmpl_id)
