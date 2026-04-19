"""Template metadata table: admin-authored AI-facing guidance for starter-project flows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Column, Uuid
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field

from langflow.services.database.models._metadata import AgentMetadataMixin


class TemplateMetadata(AgentMetadataMixin, table=True):
    __tablename__ = "template_metadata"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        sa_column=Column(Uuid(), ForeignKey("flow.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    )


class TemplateMetadataRead(BaseModel):
    agent_usage_notes: str | None
    agent_summary: str | None
    updated_by: UUID | None
    updated_at: datetime


class TemplateMetadataRowRead(BaseModel):
    flow_id: UUID
    flow_name: str
    flow_description: str | None
    is_starter: bool
    metadata: TemplateMetadataRead | None


class TemplateMetadataWrite(BaseModel):
    agent_usage_notes: str | None = None
    agent_summary: str | None = None
