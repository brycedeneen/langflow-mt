"""Unit tests for build_flow_template_context."""

from __future__ import annotations

import pytest
from uuid import uuid4

from langflow.services.assistant.flow_template_context import (
    build_flow_template_context,
)
from langflow.services.database.models import Flow, Folder, TemplateMetadata
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_is_none():
    result = await build_flow_template_context(None)
    assert result == ""


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_set_but_no_metadata_row(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(name="Tpl-no-meta", user_id=active_super_user.id, folder_id=folder.id)
        session.add(template)
        await session.commit()
        await session.refresh(template)
        template_id = template.id

    result = await build_flow_template_context(template_id)
    assert result == ""


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_references_missing_flow():
    # No flow in DB with this id → helper still returns "" gracefully
    result = await build_flow_template_context(uuid4())
    assert result == ""


@pytest.mark.asyncio
async def test_returns_instructions_block_when_pointer_and_metadata_present(
    active_super_user,
):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(
            name="Slack Notifier",
            user_id=active_super_user.id,
            folder_id=folder.id,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        session.add(
            TemplateMetadata(
                flow_id=template.id,
                agent_usage_notes="Ask for the Slack channel first.",
                updated_by=active_super_user.id,
            )
        )
        await session.commit()
        template_id = template.id

    result = await build_flow_template_context(template_id)
    assert "## Current Flow Template" in result
    assert '"Slack Notifier"' in result
    assert "Ask for the Slack channel first." in result
