"""User-facing CRUD for Template rows.

Phase 1: superuser-only for create/update/delete; any active user for list/get.
Password-flagged input fields (`password=True`) are always blanked regardless
of the client-supplied `blanked_fields` list.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.services.auth.utils import (
    get_current_active_superuser,
    get_current_active_user,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template.model import (
    Template,
    TemplateCreate,
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
    _user: User = Depends(get_current_active_user),
) -> list[TemplateRead]:
    stmt = (
        select(Template)
        .where(Template.deleted_at.is_(None))
        .where(Template.scope == "platform")
        .order_by(Template.updated_at.desc())
    )
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
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateReadDetail.model_validate(row, from_attributes=True)


@router.post("", response_model=TemplateReadDetail, status_code=201)
async def create_template(
    body: TemplateCreate,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_superuser),
) -> TemplateReadDetail:
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

    row = Template(
        name=body.name,
        description=body.description,
        icon=body.icon,
        gradient=body.gradient,
        scope="platform",
        org_id=None,
        nodes=blanked_nodes,
        edges=edges,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
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

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return TemplateReadDetail.model_validate(row, from_attributes=True)


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
