"""Admin CRUD for the platform-global tag vocabulary.

Gated by :data:`PlatformAdmin`. Any authenticated user can list tags via the
public list endpoint (see Task 4); only platform admins can mutate via the
routes defined here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils.core import DbSession, PlatformAdmin
from langflow.services.database.models.tag.model import Tag
from langflow.services.database.models.tag.schema import TagRead, TagWrite

router = APIRouter(prefix="/tags", tags=["Admin · Tags"])


def _is_tag_name_conflict(exc: IntegrityError) -> bool:
    """Detect the functional unique-index violation on ``lower(name)``."""
    message = f"{exc.orig} {exc}"
    return "uq_tag_name_lower" in message


@router.get("", response_model=list[TagRead])
async def list_tags(_admin: PlatformAdmin, session: DbSession) -> list[Tag]:
    rows = (await session.exec(select(Tag).order_by(Tag.name))).all()
    return list(rows)


@router.get("/{tag_id}", response_model=TagRead)
async def get_tag(tag_id: UUID, _admin: PlatformAdmin, session: DbSession) -> Tag:
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tag not found")
    return tag


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagWrite,
    admin: PlatformAdmin,
    session: DbSession,
) -> Tag:
    tag = Tag(
        name=payload.name,
        color=payload.color.value,
        description=payload.description,
        created_by=admin.id,
    )
    session.add(tag)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _is_tag_name_conflict(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="tag name already exists",
            ) from exc
        raise
    await session.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagRead)
async def update_tag(
    tag_id: UUID,
    payload: TagWrite,
    _admin: PlatformAdmin,
    session: DbSession,
) -> Tag:
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tag not found")
    tag.name = payload.name
    tag.color = payload.color.value
    tag.description = payload.description
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if _is_tag_name_conflict(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="tag name already exists",
            ) from exc
        raise
    await session.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> None:
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tag not found")
    await session.delete(tag)
    await session.commit()
