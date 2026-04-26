"""Super-admin metadata management endpoints.

Covers component metadata (keyed by component_name).
All endpoints require an active superuser.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from langflow.agentic.utils.component_search import build_component_name_resolver
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models import (
    ComponentMetadata,
    User,
)
from langflow.services.database.models.component_metadata import (
    ComponentMetadataRead,
    ComponentMetadataRowRead,
    ComponentMetadataWrite,
)
from langflow.api.utils.core import DbSession

router = APIRouter(tags=["Admin Metadata"], prefix="/metadata")


# ---------------- Components ----------------


async def _live_component_index() -> dict[str, dict]:
    """Return {registry_key: {display_name, category, icon}} from the live catalog."""
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
    aliases = await build_component_name_resolver()
    meta_rows = (await session.exec(select(ComponentMetadata))).all()

    # Bucket metadata rows by their canonical (live) registry key when resolvable;
    # truly stale rows keep their stored name and are flagged orphan downstream.
    meta_by_name: dict[str, ComponentMetadata] = {}
    for m in meta_rows:
        canonical = aliases.get(m.component_name)
        meta_by_name[canonical or m.component_name] = m

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
    aliases = await build_component_name_resolver()
    canonical = aliases.get(component_name) or component_name
    live = (await _live_component_index()).get(canonical)
    meta = (
        await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == canonical
            )
        )
    ).one_or_none()
    if live is None and meta is None:
        raise HTTPException(status_code=404, detail="Component not found")
    return _component_row_read(canonical, live, meta)


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
    aliases = await build_component_name_resolver()
    canonical = aliases.get(component_name) or component_name
    row = (
        await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == canonical
            )
        )
    ).one_or_none()
    if row is None:
        row = ComponentMetadata(
            component_name=canonical,
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
    aliases = await build_component_name_resolver()
    canonical = aliases.get(component_name) or component_name
    row = (
        await session.exec(
            select(ComponentMetadata).where(
                ComponentMetadata.component_name == canonical
            )
        )
    ).one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    return None
