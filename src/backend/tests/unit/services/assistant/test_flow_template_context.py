"""Unit tests for build_flow_template_context."""

from __future__ import annotations

import pytest
from uuid import uuid4

from langflow.services.assistant.flow_template_context import build_flow_template_context
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_none():
    assert await build_flow_template_context(None) == ""


@pytest.mark.asyncio
async def test_returns_empty_for_unknown_template():
    assert await build_flow_template_context(uuid4()) == ""


@pytest.mark.asyncio
async def test_returns_block_for_template_with_notes(active_super_user):  # noqa: ARG001
    from langflow.services.database.models.template.model import Template

    t = Template(name="My Tpl", nodes=[], edges=[], scope="platform", agent_usage_notes="Use carefully")

    async with session_scope() as session:
        session.add(t)
        await session.commit()
        await session.refresh(t)

    try:
        block = await build_flow_template_context(t.id)
        assert "My Tpl" in block
        assert "Use carefully" in block
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            row = (
                await session.exec(select(Template).where(Template.name == "My Tpl"))
            ).one_or_none()
            if row:
                await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_returns_empty_for_template_without_notes(active_super_user):  # noqa: ARG001
    from langflow.services.database.models.template.model import Template

    t = Template(name="Notes-less", nodes=[], edges=[], scope="platform")

    async with session_scope() as session:
        session.add(t)
        await session.commit()
        await session.refresh(t)

    try:
        assert await build_flow_template_context(t.id) == ""
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            row = (
                await session.exec(select(Template).where(Template.name == "Notes-less"))
            ).one_or_none()
            if row:
                await session.delete(row)
            await session.commit()
