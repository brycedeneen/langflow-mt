"""Pydantic schemas for the per-component ephemeral assistant."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NodeSnapshot(BaseModel):
    """Trimmed node view — enough for schema/value reasoning, no styling/layout."""

    node_id: str
    type: str                         # component class name, e.g. "DataMapperComponent"
    display_name: str
    description: str | None = None
    template: dict[str, Any] = Field(default_factory=dict)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class ThreadMessage(BaseModel):
    """A single prior turn. System messages are built server-side; not accepted on the wire."""

    role: Literal["user", "assistant"]
    content: str
    # Optional list of tool calls the assistant previously emitted (so the model sees
    # its own past proposals when reasoning this turn).
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ComponentAssistRequest(BaseModel):
    flow_id: UUID
    node_id: str
    node_snapshot: NodeSnapshot
    neighbor_snapshots: list[NodeSnapshot] = Field(default_factory=list)
    thread: list[ThreadMessage] = Field(default_factory=list)
    user_message: str

    @field_validator("user_message")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            msg = "user_message must be non-empty"
            raise ValueError(msg)
        return v


class ProposeConfigUpdate(BaseModel):
    """The single tool the model may call. Patch is a field_name → new_value map."""

    node_id: str
    patch: dict[str, Any]
    rationale: str = ""
