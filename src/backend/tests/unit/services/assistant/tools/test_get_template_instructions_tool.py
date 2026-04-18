"""Unit tests for get_template_instructions tool."""

from __future__ import annotations

import pytest

from langflow.services.assistant.tools.template_metadata import get_template_instructions
from langflow.services.database.models import Flow, Folder, TemplateMetadata
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_returns_usage_notes_when_metadata_exists(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        flow = Flow(name="Onboard-tool-test-a", user_id=active_super_user.id, folder_id=folder.id)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        session.add(
            TemplateMetadata(
                flow_id=flow.id,
                agent_usage_notes="Ask for Slack channel, then wire it.",
                updated_by=active_super_user.id,
            )
        )
        await session.commit()
        flow_id_str = str(flow.id)

    try:
        result = await get_template_instructions(flow_id_str)
        assert result is not None
        assert result["flow_id"] == flow_id_str
        assert result["flow_name"] == "Onboard-tool-test-a"
        assert result["agent_usage_notes"] == "Ask for Slack channel, then wire it."
    finally:
        # best-effort cleanup
        from sqlmodel import select
        async with session_scope() as session:
            row = (await session.exec(select(Flow).where(Flow.name == "Onboard-tool-test-a"))).one_or_none()
            if row is not None:
                await session.delete(row)
                await session.commit()


@pytest.mark.asyncio
async def test_returns_null_notes_when_metadata_absent(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        flow = Flow(name="Onboard-tool-test-b", user_id=active_super_user.id, folder_id=folder.id)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id_str = str(flow.id)

    try:
        result = await get_template_instructions(flow_id_str)
        assert result is not None
        assert result["agent_usage_notes"] is None
    finally:
        from sqlmodel import select
        async with session_scope() as session:
            row = (await session.exec(select(Flow).where(Flow.name == "Onboard-tool-test-b"))).one_or_none()
            if row is not None:
                await session.delete(row)
                await session.commit()


@pytest.mark.asyncio
async def test_returns_none_when_flow_missing():
    result = await get_template_instructions("00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_flow_id_unparseable():
    result = await get_template_instructions("not-a-uuid")
    assert result is None
