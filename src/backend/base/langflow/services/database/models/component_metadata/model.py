"""Component metadata table: admin-authored AI-facing guidance keyed by component name."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field

from langflow.services.database.models._metadata import AgentMetadataMixin


class ComponentMetadata(AgentMetadataMixin, table=True):
    __tablename__ = "component_metadata"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    component_name: str = Field(max_length=128, unique=True, index=True)
    integration_minutes_low: int | None = Field(default=None, nullable=True)
    integration_minutes_high: int | None = Field(default=None, nullable=True)


class ComponentMetadataRead(BaseModel):
    agent_usage_notes: str | None
    agent_summary: str | None
    updated_by: UUID | None
    updated_at: datetime


class ComponentMetadataRowRead(BaseModel):
    component_name: str
    display_name: str | None
    category: str | None
    icon: str | None
    is_orphan: bool
    metadata: ComponentMetadataRead | None


class ComponentMetadataWrite(BaseModel):
    agent_usage_notes: str | None = None
    agent_summary: str | None = None
