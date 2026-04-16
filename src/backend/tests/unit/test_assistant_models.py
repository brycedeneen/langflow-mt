from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

from langflow.services.database.models.assistant.model import (
    AssistantConversation,
    AssistantMessage,
)


@pytest.fixture
async def async_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_conversation_with_flow_and_org(async_session):
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    async_session.add(conv)
    await async_session.commit()
    await async_session.refresh(conv)

    assert conv.id is not None
    assert conv.flow_id == flow_id
    assert conv.org_id == org_id
    assert conv.created_at is not None
    assert conv.updated_at is not None


@pytest.mark.asyncio
async def test_create_user_message(async_session):
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    async_session.add(conv)
    await async_session.commit()
    await async_session.refresh(conv)

    user_id = uuid4()
    msg = AssistantMessage(
        conversation_id=conv.id,
        user_id=user_id,
        role="user",
        content="Hello, assistant!",
    )
    async_session.add(msg)
    await async_session.commit()
    await async_session.refresh(msg)

    assert msg.id is not None
    assert msg.conversation_id == conv.id
    assert msg.user_id == user_id
    assert msg.role == "user"
    assert msg.content == "Hello, assistant!"
    assert msg.tool_calls is None
    assert msg.tool_call_id is None
    assert msg.tool_result is None
    assert msg.created_at is not None
    assert msg.conversation == conv


@pytest.mark.asyncio
async def test_create_tool_message(async_session):
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    async_session.add(conv)
    await async_session.commit()
    await async_session.refresh(conv)

    tool_result = {"output": "42"}
    msg = AssistantMessage(
        conversation_id=conv.id,
        user_id=None,
        role="tool",
        content=None,
        tool_call_id="call_abc123",
        tool_result=tool_result,
    )
    async_session.add(msg)
    await async_session.commit()
    await async_session.refresh(msg)

    assert msg.id is not None
    assert msg.role == "tool"
    assert msg.user_id is None
    assert msg.tool_call_id == "call_abc123"
    assert msg.tool_result == tool_result
    assert msg.created_at is not None


@pytest.mark.asyncio
async def test_messages_ordered_by_created_at(async_session):
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)
    async_session.add(conv)
    await async_session.commit()
    await async_session.refresh(conv)

    t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    t3 = datetime(2025, 1, 1, 0, 0, 2, tzinfo=timezone.utc)

    msgs = [
        AssistantMessage(conversation_id=conv.id, role="user", content="third", created_at=t3),
        AssistantMessage(conversation_id=conv.id, role="user", content="first", created_at=t1),
        AssistantMessage(conversation_id=conv.id, role="assistant", content="second", created_at=t2),
    ]

    for msg in msgs:
        async_session.add(msg)
    await async_session.commit()

    stmt = select(AssistantMessage).where(AssistantMessage.conversation_id == conv.id).order_by(AssistantMessage.created_at)
    result = await async_session.exec(stmt)
    sorted_msgs = result.all()
    assert [m.content for m in sorted_msgs] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_conversation_has_expected_fields(async_session):
    expected_fields = {"id", "flow_id", "org_id", "created_at", "updated_at"}
    assert expected_fields.issubset(AssistantConversation.model_fields)
    # Relationship is not in model_fields but is a class attribute
    assert hasattr(AssistantConversation, "messages")


@pytest.mark.asyncio
async def test_message_has_expected_fields(async_session):
    expected_fields = {"id", "conversation_id", "user_id", "created_at"}
    assert expected_fields.issubset(AssistantMessage.model_fields)
    # sa_column fields and relationships are class attributes
    for attr in ("role", "content", "tool_calls", "tool_call_id", "tool_result", "conversation"):
        assert hasattr(AssistantMessage, attr)
