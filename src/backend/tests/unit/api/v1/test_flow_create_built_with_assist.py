"""The POST /flows endpoint must honor built_with_assist=True in the body."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models import Flow
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_create_flow_with_built_with_assist_true_persists_the_flag(
    client: AsyncClient, logged_in_headers
):
    response = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={
            "name": "Assist-Created Flow",
            "data": {"nodes": [], "edges": []},
            "built_with_assist": True,
        },
    )
    assert response.status_code in (200, 201)
    flow_id = UUID(response.json()["id"])

    async with session_scope() as session:
        row = (
            await session.exec(select(Flow).where(Flow.id == flow_id))
        ).one()
        assert row.built_with_assist is True


@pytest.mark.asyncio
async def test_create_flow_without_built_with_assist_defaults_to_false(
    client: AsyncClient, logged_in_headers
):
    response = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={
            "name": "Plain Flow",
            "data": {"nodes": [], "edges": []},
        },
    )
    assert response.status_code in (200, 201)
    flow_id = UUID(response.json()["id"])

    async with session_scope() as session:
        row = (
            await session.exec(select(Flow).where(Flow.id == flow_id))
        ).one()
        assert row.built_with_assist is False
