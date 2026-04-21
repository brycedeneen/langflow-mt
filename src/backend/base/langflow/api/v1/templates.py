"""User-facing CRUD for Template rows.

Phase 1: superuser-only for create/update/delete; any active user for list/get.
Password-flagged input fields (`password=True`) are always blanked regardless
of the client-supplied `blanked_fields` list.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import selectinload
from sqlmodel import col, select

from langflow.api.utils import DbSession
from langflow.api.v1._template_permissions import user_can_edit_template
from langflow.services.auth.utils import (
    get_current_active_superuser,
    get_current_active_user,
)
from langflow.services.database.models.category.model import Category, TemplateCategory
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.template.model import (
    Template,
    TemplateCreate,
    TemplatePatch,
    TemplateRead,
    TemplateReadDetail,
    TemplateUpdate,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.template.model import BlankedField
    from langflow.services.database.models.user.model import User

router = APIRouter(tags=["Templates"], prefix="/templates")


def _is_password_input(field_cfg: dict) -> bool:
    return bool(field_cfg.get("password"))


def _apply_blanking(
    source_nodes: list[dict],
    blanked_fields: list[dict],
) -> list[dict]:
    """Return a copy of source_nodes with (a) all password=True fields blanked, and
    (b) fields listed in blanked_fields cleared. Non-destructive on the source.
    """
    blank_set = {(bf["node_id"], bf["field_name"]) for bf in blanked_fields}
    out: list[dict] = []
    for node in source_nodes:
        node_copy = {**node}
        node_id = node_copy.get("id")
        template_fields = node_copy.get("data", {}).get("node", {}).get("template", {})
        new_template = {}
        for fname, fcfg in template_fields.items():
            if not isinstance(fcfg, dict):
                new_template[fname] = fcfg
                continue
            fcfg_copy = {**fcfg}
            if _is_password_input(fcfg_copy) or (node_id, fname) in blank_set:
                fcfg_copy["value"] = ""
            new_template[fname] = fcfg_copy
        if "data" in node_copy:
            node_copy["data"] = {
                **node_copy["data"],
                "node": {
                    **node_copy["data"].get("node", {}),
                    "template": new_template,
                },
            }
        out.append(node_copy)
    return out


async def _load_source_and_blank(
    session: AsyncSession,
    source_flow_id: UUID,
    blanked_fields: list[BlankedField],
) -> tuple[list[dict], list[dict]]:
    """Load the source flow (404 if missing) and return (blanked_nodes, edges)."""
    flow = (
        await session.exec(select(Flow).where(Flow.id == source_flow_id))
    ).one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Source flow not found")
    data = flow.data or {}
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    blanked = _apply_blanking(nodes, [bf.model_dump() for bf in blanked_fields])
    return blanked, edges


@router.get("", response_model=list[TemplateRead])
async def list_templates(
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_user),
    category: str | None = Query(default=None, description="Filter by category name (case-insensitive)"),
    scope: Literal["platform", "org", "all"] = Query(default="all", description="Filter by template scope"),
    created_by_me: bool = Query(default=False, description="Return only templates created by the current user"),
    include_archived: bool = Query(default=False, description="Include archived templates"),
) -> list[TemplateRead]:
    # Guard: only platform admins (or own-rows requests) may browse archived templates
    if include_archived and not getattr(current_user, "is_platform_admin", False) and not created_by_me:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins may list archived templates across all users. "
                   "Add ?created_by_me=true to list only your own archived templates.",
        )

    stmt = select(Template).where(Template.deleted_at.is_(None)).options(selectinload(Template.categories))

    if not include_archived:
        stmt = stmt.where(Template.archived_at.is_(None))

    if scope != "all":
        stmt = stmt.where(Template.scope == scope)

    if created_by_me:
        stmt = stmt.where(Template.created_by == current_user.id)

    if category is not None:
        stmt = (
            stmt
            .join(TemplateCategory, TemplateCategory.template_id == Template.id)
            .join(Category, Category.id == TemplateCategory.category_id)
            .where(Category.name.ilike(category))
        )

    stmt = stmt.order_by(Template.name)
    rows = (await session.exec(stmt)).all()
    return [TemplateRead.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{template_id}", response_model=TemplateReadDetail)
async def get_template(
    template_id: UUID,
    *,
    session: DbSession,
    _user: User = Depends(get_current_active_user),
) -> TemplateReadDetail:
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == template_id)
            .where(Template.deleted_at.is_(None))
            .options(selectinload(Template.categories))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateReadDetail.model_validate(row, from_attributes=True)


async def _validate_category_ids(session: AsyncSession, category_ids: list[UUID]) -> None:
    """Raise 422 if any of *category_ids* does not exist in the Category table."""
    if not category_ids:
        return
    existing_ids = set(
        (await session.exec(select(Category.id).where(col(Category.id).in_(category_ids)))).all()
    )
    missing = [str(cid) for cid in category_ids if cid not in existing_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown category_ids: {missing}",
        )


@router.post("", response_model=TemplateReadDetail, status_code=201)
async def create_template(
    body: TemplateCreate,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_user),
) -> TemplateReadDetail:
    # --- Permission check ---
    if body.scope == "platform":
        if not getattr(current_user, "is_platform_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform admins may create platform-scoped templates.",
            )
    elif body.scope == "org":
        if body.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="org_id is required for org-scoped templates.",
            )
        membership = (
            await session.exec(
                select(Membership)
                .where(Membership.user_id == current_user.id)
                .where(Membership.organization_id == body.org_id)
            )
        ).first()
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this organization.",
            )

    # --- Category validation ---
    await _validate_category_ids(session, body.category_ids)

    # --- Name collision check ---
    existing = (
        await session.exec(
            select(Template)
            .where(Template.name == body.name)
            .where(Template.deleted_at.is_(None))
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name already exists")

    blanked_nodes, edges = await _load_source_and_blank(
        session, body.source_flow_id, body.blanked_fields,
    )

    row = Template(
        name=body.name,
        description=body.description,
        icon=body.icon,
        gradient=body.gradient,
        scope=body.scope,
        org_id=body.org_id,
        nodes=blanked_nodes,
        edges=edges,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    session.add(row)
    await session.flush()

    for cat_id in body.category_ids:
        session.add(TemplateCategory(template_id=row.id, category_id=cat_id))

    await session.commit()
    await session.exec(
        select(Template)
        .where(Template.id == row.id)
        .options(selectinload(Template.categories))
    )
    await session.refresh(row)
    # Re-fetch with categories eager-loaded
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == row.id)
            .options(selectinload(Template.categories))
        )
    ).one()
    return TemplateReadDetail.model_validate(row, from_attributes=True)


@router.put("/{template_id}", response_model=TemplateReadDetail)
async def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_superuser),
) -> TemplateReadDetail:
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == template_id)
            .where(Template.deleted_at.is_(None))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    if body.name != row.name:
        existing = (
            await session.exec(
                select(Template)
                .where(Template.name == body.name)
                .where(Template.deleted_at.is_(None))
            )
        ).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Template name already exists")

    blanked_nodes, edges = await _load_source_and_blank(
        session, body.source_flow_id, body.blanked_fields,
    )

    row.name = body.name
    row.description = body.description
    row.icon = body.icon
    row.gradient = body.gradient
    row.nodes = blanked_nodes
    row.edges = edges
    row.updated_by = current_user.id
    row.updated_at = datetime.now(timezone.utc)

    if body.category_ids is not None:
        await _validate_category_ids(session, body.category_ids)
        await session.exec(
            select(TemplateCategory).where(TemplateCategory.template_id == template_id)
        )
        # Delete existing links
        existing_links = (
            await session.exec(
                select(TemplateCategory).where(TemplateCategory.template_id == template_id)
            )
        ).all()
        for link in existing_links:
            await session.delete(link)
        for cat_id in body.category_ids:
            session.add(TemplateCategory(template_id=row.id, category_id=cat_id))

    session.add(row)
    await session.commit()
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == row.id)
            .options(selectinload(Template.categories))
        )
    ).one()
    return TemplateReadDetail.model_validate(row, from_attributes=True)


@router.patch("/{template_id}", response_model=TemplateReadDetail)
async def patch_template(
    template_id: UUID,
    body: TemplatePatch,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_user),
) -> TemplateReadDetail:
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == template_id)
            .where(Template.deleted_at.is_(None))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if not user_can_edit_template(current_user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # Apply partial updates
    if body.name is not None and body.name != row.name:
        # Check for name collision
        existing = (
            await session.exec(
                select(Template)
                .where(Template.name == body.name)
                .where(Template.deleted_at.is_(None))
            )
        ).first()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template name already exists")
        row.name = body.name

    if body.description is not None:
        row.description = body.description
    if body.icon is not None:
        row.icon = body.icon
    if body.gradient is not None:
        row.gradient = body.gradient

    if body.category_ids is not None:
        await _validate_category_ids(session, body.category_ids)
        # Delete all existing category links
        existing_links = (
            await session.exec(
                select(TemplateCategory).where(TemplateCategory.template_id == template_id)
            )
        ).all()
        for link in existing_links:
            await session.delete(link)
        for cat_id in body.category_ids:
            session.add(TemplateCategory(template_id=row.id, category_id=cat_id))

    row.updated_by = current_user.id
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == row.id)
            .options(selectinload(Template.categories))
        )
    ).one()
    return TemplateReadDetail.model_validate(row, from_attributes=True)


@router.post("/{template_id}/archive", response_model=TemplateRead)
async def archive_template(
    template_id: UUID,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_user),
) -> TemplateRead:
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == template_id)
            .where(Template.deleted_at.is_(None))
            .options(selectinload(Template.categories))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if not user_can_edit_template(current_user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if row.archived_at is None:
        row.archived_at = datetime.now(timezone.utc)
        session.add(row)
        await session.commit()
        row = (
            await session.exec(
                select(Template)
                .where(Template.id == template_id)
                .options(selectinload(Template.categories))
            )
        ).one()
    return TemplateRead.model_validate(row, from_attributes=True)


@router.post("/{template_id}/unarchive", response_model=TemplateRead)
async def unarchive_template(
    template_id: UUID,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_user),
) -> TemplateRead:
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == template_id)
            .where(Template.deleted_at.is_(None))
            .options(selectinload(Template.categories))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if not user_can_edit_template(current_user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if row.archived_at is not None:
        row.archived_at = None
        session.add(row)
        await session.commit()
        row = (
            await session.exec(
                select(Template)
                .where(Template.id == template_id)
                .options(selectinload(Template.categories))
            )
        ).one()
    return TemplateRead.model_validate(row, from_attributes=True)


@router.delete("/{template_id}", status_code=204)
async def soft_delete_template(
    template_id: UUID,
    *,
    session: DbSession,
    _user: User = Depends(get_current_active_superuser),
) -> Response:
    row = (
        await session.exec(
            select(Template)
            .where(Template.id == template_id)
            .where(Template.deleted_at.is_(None))
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    row.deleted_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
