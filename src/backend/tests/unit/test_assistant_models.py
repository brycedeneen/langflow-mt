from datetime import datetime, timezone
from uuid import uuid4

from langflow.services.database.models.assistant.model import (
    AssistantConversation,
    AssistantMessage,
)


def test_create_conversation_with_flow_and_org():
    flow_id = uuid4()
    org_id = uuid4()
    conv = AssistantConversation(flow_id=flow_id, org_id=org_id)

    assert conv.id is not None
    assert conv.flow_id == flow_id
    assert conv.org_id == org_id


def test_create_user_message():
    conv_id = uuid4()
    user_id = uuid4()
    msg = AssistantMessage(
        conversation_id=conv_id,
        user_id=user_id,
        role="user",
        content="Hello, assistant!",
    )

    assert msg.id is not None
    assert msg.conversation_id == conv_id
    assert msg.user_id == user_id
    assert msg.role == "user"
    assert msg.content == "Hello, assistant!"
    assert msg.tool_calls is None
    assert msg.tool_call_id is None
    assert msg.tool_result is None


def test_create_tool_message():
    conv_id = uuid4()
    tool_result = {"output": "42"}
    msg = AssistantMessage(
        conversation_id=conv_id,
        user_id=None,
        role="tool",
        content=None,
        tool_call_id="call_abc123",
        tool_result=tool_result,
    )

    assert msg.role == "tool"
    assert msg.user_id is None
    assert msg.tool_call_id == "call_abc123"
    assert msg.tool_result == tool_result


def test_messages_ordered_by_created_at():
    conv_id = uuid4()
    t1 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    t3 = datetime(2025, 1, 1, 0, 0, 2, tzinfo=timezone.utc)

    msgs = [
        AssistantMessage(conversation_id=conv_id, role="user", content="third", created_at=t3),
        AssistantMessage(conversation_id=conv_id, role="user", content="first", created_at=t1),
        AssistantMessage(conversation_id=conv_id, role="assistant", content="second", created_at=t2),
    ]

    sorted_msgs = sorted(msgs, key=lambda m: m.created_at)
    assert [m.content for m in sorted_msgs] == ["first", "second", "third"]


def test_conversation_has_expected_fields():
    expected_fields = {"id", "flow_id", "org_id", "created_at", "updated_at"}
    assert expected_fields.issubset(AssistantConversation.model_fields)
    # Relationship is not in model_fields but is a class attribute
    assert hasattr(AssistantConversation, "messages")


def test_message_has_expected_fields():
    expected_fields = {"id", "conversation_id", "user_id", "created_at"}
    assert expected_fields.issubset(AssistantMessage.model_fields)
    # sa_column fields and relationships are class attributes
    for attr in ("role", "content", "tool_calls", "tool_call_id", "tool_result", "conversation"):
        assert hasattr(AssistantMessage, attr)
