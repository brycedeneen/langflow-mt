"""Starter-project detection for flows.

The codebase historically identifies starter projects by folder membership
rather than a boolean column. This helper centralizes that lookup so callers
don't have to know the folder name or re-implement the query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import Session, select

from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

__all__ = [
    "STARTER_FOLDER_NAME",
    "is_flow_a_starter_project",
    "is_flow_a_starter_project_async",
    "list_starter_project_flows",
]


def is_flow_a_starter_project(flow: Flow, session: Session) -> bool:
    """Return True when the flow lives in the starter-projects folder."""
    if flow.folder_id is None:
        return False
    folder = session.exec(select(Folder).where(Folder.id == flow.folder_id)).one_or_none()
    return folder is not None and folder.name == STARTER_FOLDER_NAME


async def is_flow_a_starter_project_async(flow: Flow, session: AsyncSession) -> bool:
    """Async variant: return True when the flow lives in the starter-projects folder."""
    if flow.folder_id is None:
        return False
    folder = (
        await session.exec(select(Folder).where(Folder.id == flow.folder_id))
    ).one_or_none()
    return folder is not None and folder.name == STARTER_FOLDER_NAME


def list_starter_project_flows(session: Session) -> list[Flow]:
    """Return every flow that belongs to a starter-projects folder."""
    starter_folders = session.exec(
        select(Folder).where(Folder.name == STARTER_FOLDER_NAME)
    ).all()
    if not starter_folders:
        return []
    folder_ids = {f.id for f in starter_folders}
    return session.exec(select(Flow).where(Flow.folder_id.in_(folder_ids))).all()
