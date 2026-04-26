"""Public read-only list of the platform-global tag vocabulary.

Any authenticated user can read the tag list; only platform admins can
mutate it (see admin/tags.py for the CRUD endpoints).
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSessionReadOnly
from langflow.services.database.models.tag.model import Tag
from langflow.services.database.models.tag.schema import TagRead

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get("", response_model=list[TagRead])
async def list_tags(_user: CurrentActiveUser, session: DbSessionReadOnly) -> list[Tag]:
    rows = (await session.exec(select(Tag).order_by(Tag.name))).all()
    return list(rows)
