"""Integration tests for admin template metadata endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models import Flow, Folder, TemplateMetadata
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


@pytest.fixture
async def starter_flow(client, active_super_user):  # noqa: ARG001
    async with session_scope() as session:
        folder = (
            await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME))
        ).one_or_none()
        if folder is None:
            folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
            session.add(folder)
            await session.flush()
            await session.refresh(folder)
        flow = Flow(
            name="Starter Slack Flow",
            description="Starter project for Slack",
            user_id=active_super_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id
        flow_name = flow.name

    yield {"id": flow_id, "name": flow_name}

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow:
            await session.delete(db_flow)


@pytest.fixture
async def non_starter_flow(client, active_super_user):  # noqa: ARG001
    async with session_scope() as session:
        folder = Folder(name="My Projects", user_id=active_super_user.id)
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        flow = Flow(
            name="User Flow",
            user_id=active_super_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id
        folder_id = folder.id

    yield {"id": flow_id}

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow:
            await session.delete(db_flow)
        db_folder = await session.get(Folder, folder_id)
        if db_folder:
            await session.delete(db_folder)


@pytest.mark.asyncio
async def test_list_templates_returns_starter_flows_with_metadata_null(
    client: AsyncClient, logged_in_headers_super_user, starter_flow
):
    response = await client.get(
        "/api/v1/admin/metadata/templates", headers=logged_in_headers_super_user
    )
    assert response.status_code == 200
    rows = response.json()
    starter_row = next((r for r in rows if r["flow_id"] == str(starter_flow["id"])), None)
    assert starter_row is not None
    assert starter_row["flow_name"] == starter_flow["name"]
    assert starter_row["is_starter"] is True
    assert starter_row["metadata"] is None


@pytest.mark.asyncio
async def test_list_templates_excludes_non_starter_flows(
    client: AsyncClient, logged_in_headers_super_user, non_starter_flow
):
    response = await client.get(
        "/api/v1/admin/metadata/templates", headers=logged_in_headers_super_user
    )
    rows = response.json()
    assert all(r["flow_id"] != str(non_starter_flow["id"]) for r in rows)


@pytest.mark.asyncio
async def test_list_templates_requires_superuser(
    client: AsyncClient, logged_in_headers
):
    response = await client.get(
        "/api/v1/admin/metadata/templates", headers=logged_in_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_template_returns_404_for_unknown_flow(
    client: AsyncClient, logged_in_headers_super_user
):
    response = await client.get(
        "/api/v1/admin/metadata/templates/00000000-0000-0000-0000-000000000000",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_put_template_creates_metadata_row(
    client: AsyncClient, logged_in_headers_super_user, starter_flow, session
):
    response = await client.put(
        f"/api/v1/admin/metadata/templates/{starter_flow['id']}",
        headers=logged_in_headers_super_user,
        json={
            "agent_usage_notes": "Use for Slack onboarding.",
            "agent_summary": "Onboarding notifier.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_summary"] == "Onboarding notifier."

    async with session_scope() as db:
        row = (
            await db.exec(
                select(TemplateMetadata).where(TemplateMetadata.flow_id == starter_flow["id"])
            )
        ).one_or_none()
    assert row is not None
    assert row.agent_usage_notes == "Use for Slack onboarding."


@pytest.mark.asyncio
async def test_put_template_updates_existing_row(
    client: AsyncClient, logged_in_headers_super_user, starter_flow, active_super_user
):
    async with session_scope() as db:
        db.add(
            TemplateMetadata(
                flow_id=starter_flow["id"],
                agent_summary="Old",
                updated_by=active_super_user.id,
            )
        )
        await db.commit()

    response = await client.put(
        f"/api/v1/admin/metadata/templates/{starter_flow['id']}",
        headers=logged_in_headers_super_user,
        json={"agent_summary": "New"},
    )
    assert response.status_code == 200
    assert response.json()["agent_summary"] == "New"

    async with session_scope() as db:
        rows = (
            await db.exec(
                select(TemplateMetadata).where(TemplateMetadata.flow_id == starter_flow["id"])
            )
        ).all()
    assert len(rows) == 1
    assert rows[0].agent_summary == "New"


@pytest.mark.asyncio
async def test_delete_template_removes_row_but_keeps_flow(
    client: AsyncClient, logged_in_headers_super_user, starter_flow, active_super_user
):
    async with session_scope() as db:
        db.add(TemplateMetadata(flow_id=starter_flow["id"], updated_by=active_super_user.id))
        await db.commit()

    response = await client.delete(
        f"/api/v1/admin/metadata/templates/{starter_flow['id']}",
        headers=logged_in_headers_super_user,
    )
    assert response.status_code == 204

    async with session_scope() as db:
        meta_rows = (
            await db.exec(
                select(TemplateMetadata).where(TemplateMetadata.flow_id == starter_flow["id"])
            )
        ).all()
        flow_still_there = (
            await db.exec(select(Flow).where(Flow.id == starter_flow["id"]))
        ).one_or_none()
    assert meta_rows == []
    assert flow_still_there is not None
