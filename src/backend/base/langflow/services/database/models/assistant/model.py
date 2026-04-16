from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Index, String, Text
from sqlmodel import JSON, Column, DateTime, Field, Relationship, SQLModel, func


class AssistantConversation(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "assistant_conversation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(unique=True, index=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True),
    )

    messages: list["AssistantMessage"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )


class AssistantMessage(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "assistant_message"
    __table_args__ = (
        Index("ix_assistant_message_conversation_created", "conversation_id", "created_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(index=True, foreign_key="assistant_conversation.id")
    user_id: UUID | None = Field(default=None)
    role: str = Field(sa_column=Column(String(20), nullable=False))
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tool_calls: dict | list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    tool_call_id: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    tool_result: dict | list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
    )

    conversation: AssistantConversation = Relationship(back_populates="messages")
