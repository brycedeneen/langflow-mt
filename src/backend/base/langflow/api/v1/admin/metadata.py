"""Super-admin metadata management endpoints.

Covers template metadata (keyed by flow_id) and component metadata
(keyed by component_name). All endpoints require an active superuser.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models import (
    ComponentMetadata,
    Flow,
    Folder,
    TemplateMetadata,
    User,
)
from langflow.services.database.models.component_metadata import (
    ComponentMetadataRead,
    ComponentMetadataRowRead,
    ComponentMetadataWrite,
)
from langflow.services.database.models.flow.starter import (
    STARTER_FOLDER_NAME,
    is_flow_a_starter_project_async,
)
from langflow.services.database.models.template_metadata import (
    TemplateMetadataRead,
    TemplateMetadataRowRead,
    TemplateMetadataWrite,
)
from langflow.api.utils.core import DbSession

router = APIRouter(tags=["Admin Metadata"], prefix="/metadata")


def _template_row_read(
    flow: Flow, meta: TemplateMetadata | None, is_starter: bool = True
) -> TemplateMetadataRowRead:
    return TemplateMetadataRowRead(
        flow_id=flow.id,
        flow_name=flow.name,
        flow_description=flow.description,
        is_starter=is_starter,
        metadata=(
            TemplateMetadataRead(
                agent_usage_notes=meta.agent_usage_notes,
                agent_summary=meta.agent_summary,
                updated_by=meta.updated_by,
                updated_at=meta.updated_at,
            )
            if meta is not None
            else None
        ),
    )


@router.get(
    "/templates",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[TemplateMetadataRowRead],
)
async def list_template_metadata(*, session: DbSession) -> list[TemplateMetadataRowRead]:
    """List all starter-project flows and their metadata (nullable)."""
    starter_folders = (
        await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME))
    ).all()
    if not starter_folders:
        return []
    folder_ids = {f.id for f in starter_folders}
    flows = (await session.exec(select(Flow).where(Flow.folder_id.in_(folder_ids)))).all()
    if not flows:
        return []
    flow_ids = [f.id for f in flows]
    metas = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id.in_(flow_ids))
        )
    ).all()
    meta_by_flow = {m.flow_id: m for m in metas}
    return [_template_row_read(f, meta_by_flow.get(f.id), is_starter=True) for f in flows]


@router.get(
    "/templates/{flow_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TemplateMetadataRowRead,
)
async def get_template_metadata(
    flow_id: UUID, *, session: DbSession
) -> TemplateMetadataRowRead:
    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).one_or_none()
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    meta = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
        )
    ).one_or_none()
    is_starter = await is_flow_a_starter_project_async(flow, session)
    return _template_row_read(flow, meta, is_starter=is_starter)


@router.put(
    "/templates/{flow_id}",
    response_model=TemplateMetadataRead,
)
async def upsert_template_metadata(
    flow_id: UUID,
    body: TemplateMetadataWrite,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_superuser),
) -> TemplateMetadataRead:
    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")

    row = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
        )
    ).one_or_none()
    if row is None:
        row = TemplateMetadata(
            flow_id=flow_id,
            agent_usage_notes=body.agent_usage_notes,
            agent_summary=body.agent_summary,
            updated_by=current_user.id,
        )
    else:
        row.agent_usage_notes = body.agent_usage_notes
        row.agent_summary = body.agent_summary
        row.updated_by = current_user.id

    session.add(row)
    await session.commit()
    await session.refresh(row)

    return TemplateMetadataRead(
        agent_usage_notes=row.agent_usage_notes,
        agent_summary=row.agent_summary,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@router.delete(
    "/templates/{flow_id}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template_metadata(flow_id: UUID, *, session: DbSession) -> None:
    row = (
        await session.exec(
            select(TemplateMetadata).where(TemplateMetadata.flow_id == flow_id)
        )
    ).one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    return None


# ---------------- Components ----------------


async def _live_component_index() -> dict[str, dict]:
    """Return {component_name: {display_name, category, icon}} from the live catalog."""
    from langflow.agentic.utils.component_search import list_all_components

    items = await list_all_components()
    return {
        item["name"]: {
            "display_name": item.get("display_name"),
            "category": item.get("type"),
            "icon": item.get("icon"),
        }
        for item in items
    }


def _component_row_read(
    name: str, live: dict | None, meta: ComponentMetadata | None
) -> ComponentMetadataRowRead:
    return ComponentMetadataRowRead(
        component_name=name,
        display_name=(live or {}).get("display_name"),
        category=(live or {}).get("category"),
        icon=(live or {}).get("icon"),
        is_orphan=(live is None and meta is not None),
        metadata=(
            ComponentMetadataRead(
                agent_usage_notes=meta.agent_usage_notes,
                agent_summary=meta.agent_summary,
                updated_by=meta.updated_by,
                updated_at=meta.updated_at,
            )
            if meta is not None
            else None
        ),
    )


@router.get(
    "/components",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=list[ComponentMetadataRowRead],
)
async def list_component_metadata(
    *, session: DbSession
) -> list[ComponentMetadataRowRead]:
    live = await _live_component_index()
    meta_rows = (await session.exec(select(ComponentMetadata))).all()
    meta_by_name = {m.component_name: m for m in meta_rows}

    all_names = set(live.keys()) | set(meta_by_name.keys())
    return [
        _component_row_read(name, live.get(name), meta_by_name.get(name))
        for name in sorted(all_names)
    ]


@router.get(
    "/components/{component_name}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ComponentMetadataRowRead,
)
async def get_component_metadata(
    component_name: str, *, session: DbSession
) -> ComponentMetadataRowRead:
    live = (await _live_component_index()).get(component_name)
    meta = (
        await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == component_name
            )
        )
    ).one_or_none()
    if live is None and meta is None:
        raise HTTPException(status_code=404, detail="Component not found")
    return _component_row_read(component_name, live, meta)


@router.put(
    "/components/{component_name}",
    response_model=ComponentMetadataRead,
)
async def upsert_component_metadata(
    component_name: str,
    body: ComponentMetadataWrite,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_superuser),
) -> ComponentMetadataRead:
    row = (
        await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == component_name
            )
        )
    ).one_or_none()
    if row is None:
        row = ComponentMetadata(
            component_name=component_name,
            agent_usage_notes=body.agent_usage_notes,
            agent_summary=body.agent_summary,
            updated_by=current_user.id,
        )
    else:
        row.agent_usage_notes = body.agent_usage_notes
        row.agent_summary = body.agent_summary
        row.updated_by = current_user.id
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return ComponentMetadataRead(
        agent_usage_notes=row.agent_usage_notes,
        agent_summary=row.agent_summary,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@router.delete(
    "/components/{component_name}",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_component_metadata(
    component_name: str, *, session: DbSession
) -> None:
    row = (
        await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == component_name
            )
        )
    ).one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    return None
