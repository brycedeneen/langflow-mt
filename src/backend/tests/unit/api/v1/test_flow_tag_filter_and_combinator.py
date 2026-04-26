"""Tests for tag_match=all on GET /api/v1/flows."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


async def _mkflow(client: AsyncClient, headers: dict, name: str) -> dict:
    resp = await client.post(
        "api/v1/flows/",
        json={"name": name, "description": "and", "data": {"nodes": [], "edges": []}},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _mktag(client: AsyncClient, admin_headers: dict, name: str, color: str = "blue") -> dict:
    resp = await client.post(
        "api/v1/admin/tags", json={"name": name, "color": color}, headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


@pytest.mark.asyncio
async def test_flow_list_and_combinator_returns_only_all_match(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    t1 = await _mktag(client, admin_headers, "ta1")
    t2 = await _mktag(client, admin_headers, "ta2", "green")

    f1 = await _mkflow(client, logged_in_headers, "tandf1")  # t1 only
    f2 = await _mkflow(client, logged_in_headers, "tandf2")  # t1 AND t2
    f3 = await _mkflow(client, logged_in_headers, "tandf3")  # t2 only

    await client.put(f"api/v1/flows/{f1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f2['id']}/tags", json={"tag_ids": [t1["id"], t2["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f3['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=logged_in_headers)

    # AND: only f2 has both t1 AND t2.
    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}&tag_id={t2['id']}&tag_match=all",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = {x["id"] for x in resp.json()}
    assert f2["id"] in ids
    assert f1["id"] not in ids
    assert f3["id"] not in ids


@pytest.mark.asyncio
async def test_flow_list_default_is_or_semantics(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    t1 = await _mktag(client, admin_headers, "tor1")
    t2 = await _mktag(client, admin_headers, "tor2", "red")

    f1 = await _mkflow(client, logged_in_headers, "torf1")
    f2 = await _mkflow(client, logged_in_headers, "torf2")
    await client.put(f"api/v1/flows/{f1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f2['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=logged_in_headers)

    # No tag_match param → default OR: both f1 and f2 appear.
    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}&tag_id={t2['id']}",
        headers=logged_in_headers,
    )
    ids = {x["id"] for x in resp.json()}
    assert f1["id"] in ids
    assert f2["id"] in ids


@pytest.mark.asyncio
async def test_template_list_and_combinator(
    client: AsyncClient, admin_headers: dict
) -> None:
    """Smoke test for templates.py — same AND semantics should apply."""
    from uuid import uuid4
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.deps import session_scope

    async def _mk_template_source_flow(name: str) -> str:
        async with session_scope() as session:
            flow = Flow(
                id=uuid4(),
                name=f"{name}-src",
                data={"nodes": [], "edges": []},
                user_id=None,
                organization_id=None,
            )
            session.add(flow)
            await session.commit()
            await session.refresh(flow)
            return str(flow.id)

    t1 = await _mktag(client, admin_headers, "tmpt1", "blue")
    t2 = await _mktag(client, admin_headers, "tmpt2", "red")

    # Create 3 templates with different tag intersections.
    created = []
    for name, tag_ids in [
        ("tmp_and_a", [t1["id"]]),
        ("tmp_and_b", [t1["id"], t2["id"]]),
        ("tmp_and_c", [t2["id"]]),
    ]:
        sid = await _mk_template_source_flow(name)
        resp = await client.post(
            "api/v1/templates",
            json={"name": name, "scope": "platform", "source_flow_id": sid},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        tmpl = resp.json()
        await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": tag_ids},
            headers=admin_headers,
        )
        created.append(tmpl)

    try:
        resp = await client.get(
            f"api/v1/templates?tag_id={t1['id']}&tag_id={t2['id']}&tag_match=all",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        ids = {x["id"] for x in resp.json()}
        assert created[1]["id"] in ids
        assert created[0]["id"] not in ids
        assert created[2]["id"] not in ids
    finally:
        for tmpl in created:
            await client.delete(f"api/v1/templates/{tmpl['id']}", headers=admin_headers)
