"""Unit tests for the apply_template assistant tool."""

from __future__ import annotations

import pytest
from sqlmodel import select

from langflow.services.assistant.tools.template_apply import apply_template
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_apply_template_happy_path(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(
            name="Slack Tpl",
            user_id=active_super_user.id,
            folder_id=folder.id,
            data={
                "nodes": [{"id": "Webhook-aaaaa", "data": {"id": "Webhook-aaaaa", "type": "Webhook"}}],
                "edges": [],
            },
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        target = Flow(name="Empty", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_flow_id=template_id)
    assert "applied_patch" in result
    assert result["template_name"] == "Slack Tpl"
    assert len(result["applied_patch"]["added_nodes"]) == 1
    # Ensure the target flow was updated + pointer set
    async with session_scope() as session:
        from uuid import UUID
        updated = (await session.exec(select(Flow).where(Flow.id == UUID(target_id)))).one()
        assert updated.based_on_template_id == UUID(template_id)
        assert len(updated.data["nodes"]) == 1
        # The node's id was regenerated (not equal to the template's)
        assert updated.data["nodes"][0]["id"] != "Webhook-aaaaa"


@pytest.mark.asyncio
async def test_apply_template_refuses_non_empty_target(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(
            name="Tpl",
            user_id=active_super_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(template)
        target = Flow(
            name="Not empty",
            user_id=active_super_user.id,
            data={
                "nodes": [{"id": "Existing-11111", "data": {"id": "Existing-11111", "type": "Existing"}}],
                "edges": [],
            },
        )
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_flow_id=template_id)
    assert "error" in result
    assert "not empty" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_refuses_non_starter_source(active_super_user):
    async with session_scope() as session:
        other_folder = Folder(name="My Projects", user_id=active_super_user.id)
        session.add(other_folder)
        await session.commit()
        await session.refresh(other_folder)
        template = Flow(
            name="Not a tpl",
            user_id=active_super_user.id,
            folder_id=other_folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(template)
        target = Flow(name="Blank", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_flow_id=template_id)
    assert "error" in result
    assert "template" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_unknown_flow_id_errors():
    result = await apply_template(
        target_flow_id="00000000-0000-0000-0000-000000000000",
        template_flow_id="00000000-0000-0000-0000-000000000001",
    )
    assert "error" in result
