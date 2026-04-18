"""Unit tests for template-summary system-prompt block."""

from __future__ import annotations

import pytest

from langflow.services.assistant.template_prompt import build_available_templates_block
from langflow.services.database.models import Flow, Folder, TemplateMetadata
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


async def _cleanup_flow(name: str) -> None:
    from sqlmodel import select
    async with session_scope() as session:
        row = (await session.exec(select(Flow).where(Flow.name == name))).one_or_none()
        if row is not None:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_empty_when_no_summaries():
    text = await build_available_templates_block()
    assert text == ""


@pytest.mark.asyncio
async def test_block_lists_flows_with_summaries_sorted(active_super_user):
    names = ["Zeta-prompt-Flow", "Alpha-prompt-Flow"]
    ids = []
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        for n in names:
            f = Flow(name=n, user_id=active_super_user.id, folder_id=folder.id)
            session.add(f)
            await session.commit()
            await session.refresh(f)
            ids.append(f.id)
        for fid, n in zip(ids, names):
            session.add(
                TemplateMetadata(
                    flow_id=fid,
                    agent_summary=f"{n.split('-')[0]} summary.",
                    updated_by=active_super_user.id,
                )
            )
        await session.commit()

    try:
        text = await build_available_templates_block()
        assert "## Available Templates" in text
        # Sorted by flow name: Alpha before Zeta
        assert text.index("Alpha-prompt-Flow") < text.index("Zeta-prompt-Flow")
        assert "Alpha summary." in text
        assert "Zeta summary." in text
        for fid in ids:
            assert str(fid) in text
    finally:
        for n in names:
            await _cleanup_flow(n)


@pytest.mark.asyncio
async def test_block_excludes_flows_with_null_summary(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        flow = Flow(name="SilentPromptFlow", user_id=active_super_user.id, folder_id=folder.id)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        session.add(TemplateMetadata(flow_id=flow.id, updated_by=active_super_user.id))
        await session.commit()

    try:
        text = await build_available_templates_block()
        assert "SilentPromptFlow" not in text
    finally:
        await _cleanup_flow("SilentPromptFlow")
