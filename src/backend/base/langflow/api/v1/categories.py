"""CRUD router for Category rows.

Categories are the canonical tag taxonomy for Templates.
List/get is open to any active user; create/patch/delete require platform admin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession, DbSessionReadOnly, PlatformAdmin
from langflow.services.database.models.category.model import (
    Category,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=list[CategoryRead])
async def list_categories(
    _user: CurrentActiveUser,
    session: DbSessionReadOnly,
) -> list[Category]:
    stmt = select(Category).order_by(func.lower(Category.name))
    result = await session.exec(stmt)
    return list(result.all())


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: UUID,
    _user: CurrentActiveUser,
    session: DbSessionReadOnly,
) -> Category:
    obj = await session.get(Category, category_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    return obj


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    admin: PlatformAdmin,
    session: DbSession,
) -> Category:
    obj = Category(
        name=payload.name,
        icon=payload.icon,
        color=payload.color,
        description=payload.description,
        created_by=admin.id,
    )
    session.add(obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category name already exists")
    await session.refresh(obj)
    return obj


@router.patch("/{category_id}", response_model=CategoryRead)
async def patch_category(
    category_id: UUID,
    payload: CategoryUpdate,
    _admin: PlatformAdmin,
    session: DbSession,
) -> Category:
    obj = await session.get(Category, category_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)
    obj.updated_at = datetime.now(timezone.utc)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category name already exists")
    await session.refresh(obj)
    return obj


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> None:
    obj = await session.get(Category, category_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    await session.delete(obj)
    await session.commit()
