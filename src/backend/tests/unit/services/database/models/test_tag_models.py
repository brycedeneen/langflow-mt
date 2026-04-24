"""Unit tests for Tag / FlowTag / TemplateTag SQLModels."""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# Importing models registers the tables on SQLModel.metadata so
# create_all() builds them for the in-memory SQLite test engine.
from langflow.services.database.models import Flow, Organization, User  # noqa: F401
from langflow.services.database.models.tag.model import (
    FlowTag,
    Tag,
    TagColor,
)


@pytest.fixture(name="session")
async def async_session_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable FK enforcement on every new sqlite connection.
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
    finally:
        await engine.dispose()


async def _make_flow(session: AsyncSession) -> Flow:
    user = User(username="tag_admin", password="x", is_superuser=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    org = Organization(name="tag_org", slug="tag_org")
    session.add(org)
    await session.commit()
    await session.refresh(org)

    flow = Flow(
        name="Tagged Flow",
        user_id=user.id,
        organization_id=org.id,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow


@pytest.mark.asyncio
async def test_tag_requires_palette_color(session) -> None:
    tag = Tag(name="finance", color="not-a-color")
    session.add(tag)
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_tag_name_case_insensitive_unique(session) -> None:
    session.add(Tag(name="Finance", color=TagColor.BLUE.value))
    await session.commit()
    session.add(Tag(name="finance", color=TagColor.RED.value))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_flow_tag_cascades_on_flow_delete(session) -> None:
    tag = Tag(name="hr", color=TagColor.GREEN.value)
    flow = await _make_flow(session)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)

    session.add(FlowTag(flow_id=flow.id, tag_id=tag.id))
    await session.commit()

    await session.delete(flow)
    await session.commit()

    remaining = (await session.exec(select(FlowTag).where(FlowTag.tag_id == tag.id))).all()
    assert remaining == []


def test_tag_color_enum_lists_ten_values() -> None:
    assert len(TagColor) == 10
    assert {c.value for c in TagColor} == {
        "slate",
        "red",
        "orange",
        "amber",
        "green",
        "teal",
        "sky",
        "blue",
        "violet",
        "pink",
    }
