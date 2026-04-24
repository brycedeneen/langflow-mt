"""Pydantic schemas for the Tag admin CRUD router (Task 3).

Kept in the same package as the SQLModel so `from langflow.services.database.models.tag import ...`
returns a complete surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from langflow.services.database.models.tag.model import TagColor

TagName = Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)]


class TagWrite(BaseModel):
    name: TagName
    color: TagColor
    description: str | None = Field(default=None, max_length=1024)


class TagRead(BaseModel):
    id: UUID
    name: str
    color: TagColor
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
