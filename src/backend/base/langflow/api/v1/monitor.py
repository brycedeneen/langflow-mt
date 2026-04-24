from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from sqlalchemy import delete
from sqlmodel import col, select

from langflow.api.utils import DbSession, custom_params
from langflow.api.utils.authz import assert_org_role
from langflow.api.utils.core import CurrentOrg
from langflow.schema.message import MessageResponse
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import MembershipRole
from langflow.services.database.models.message.model import MessageRead, MessageTable, MessageUpdate
from langflow.services.database.models.transactions.crud import transform_transaction_table_for_logs
from langflow.services.database.models.transactions.model import TransactionLogsResponse, TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.database.models.vertex_builds.crud import (
    delete_vertex_builds_by_flow_id,
    get_vertex_builds_by_flow_id,
)
from langflow.services.database.models.vertex_builds.model import VertexBuildMapModel

router = APIRouter(prefix="/monitor", tags=["Monitor"])


async def _require_flow_in_org(session, flow_id: UUID, org_id: UUID) -> Flow:
    """Fetch a flow scoped to the caller's current org or raise 404."""
    flow = (
        await session.exec(select(Flow).where(Flow.id == flow_id, Flow.organization_id == org_id))
    ).first()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.get("/builds")
async def get_vertex_builds(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
) -> VertexBuildMapModel:
    try:
        await _require_flow_in_org(session, flow_id, current_org.id)
        await assert_org_role(current_user, current_org.id, MembershipRole.VIEWER, session=session)
        vertex_builds = await get_vertex_builds_by_flow_id(session, flow_id)
        return VertexBuildMapModel.from_list_of_dicts(vertex_builds)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/builds", status_code=204)
async def delete_vertex_builds(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
) -> None:
    try:
        await _require_flow_in_org(session, flow_id, current_org.id)
        await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
        await delete_vertex_builds_by_flow_id(session, flow_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages/sessions")
async def get_message_sessions(
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
    flow_id: Annotated[UUID | None, Query()] = None,
) -> list[str]:
    try:
        await assert_org_role(current_user, current_org.id, MembershipRole.VIEWER, session=session)
        stmt = select(MessageTable.session_id).distinct()
        stmt = stmt.join(Flow, MessageTable.flow_id == Flow.id)
        stmt = stmt.where(col(MessageTable.session_id).isnot(None))
        stmt = stmt.where(Flow.organization_id == current_org.id)

        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)

        session_ids = await session.exec(stmt)
        return list(session_ids)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages")
async def get_messages(
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    sender: Annotated[str | None, Query()] = None,
    sender_name: Annotated[str | None, Query()] = None,
    order_by: Annotated[str | None, Query()] = "timestamp",
) -> list[MessageResponse]:
    try:
        await assert_org_role(current_user, current_org.id, MembershipRole.VIEWER, session=session)
        stmt = select(MessageTable)
        stmt = stmt.join(Flow, MessageTable.flow_id == Flow.id)
        stmt = stmt.where(Flow.organization_id == current_org.id)

        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)
        if session_id:
            from urllib.parse import unquote

            decoded_session_id = unquote(session_id)
            stmt = stmt.where(MessageTable.session_id == decoded_session_id)
        if sender:
            stmt = stmt.where(MessageTable.sender == sender)
        if sender_name:
            stmt = stmt.where(MessageTable.sender_name == sender_name)
        if order_by:
            order_col = getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(order_col)
        messages = await session.exec(stmt)
        return [MessageResponse.model_validate(d, from_attributes=True) for d in messages]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/messages", status_code=204)
async def delete_messages(
    message_ids: list[UUID],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
) -> None:
    try:
        await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
        # Only delete messages whose owning Flow is in the caller's org.
        allowed_ids = (
            await session.exec(
                select(MessageTable.id)
                .join(Flow, MessageTable.flow_id == Flow.id)
                .where(col(MessageTable.id).in_(message_ids))
                .where(Flow.organization_id == current_org.id)
            )
        ).all()
        if not allowed_ids:
            return
        await session.exec(delete(MessageTable).where(col(MessageTable.id).in_(allowed_ids)))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/messages/{message_id}", response_model=MessageRead)
async def update_message(
    message_id: UUID,
    message: MessageUpdate,
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
):
    try:
        db_message = await session.get(MessageTable, message_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not db_message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Ensure the message's flow is in the caller's org before editing.
    if db_message.flow_id is not None:
        await _require_flow_in_org(session, db_message.flow_id, current_org.id)
    await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)

    try:
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        if "text" in message_dict and message_dict["text"] != db_message.text:
            message_dict["edit"] = True
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        await session.flush()
        await session.refresh(db_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return db_message


@router.patch("/messages/session/{old_session_id}")
async def update_session_id(
    old_session_id: str,
    new_session_id: Annotated[str, Query(..., description="The new session ID to update to")],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
) -> list[MessageResponse]:
    try:
        await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
        # Scope to messages whose flow is in the caller's org.
        stmt = (
            select(MessageTable)
            .join(Flow, MessageTable.flow_id == Flow.id)
            .where(MessageTable.session_id == old_session_id)
            .where(Flow.organization_id == current_org.id)
        )
        messages = (await session.exec(stmt)).all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found with the given session ID")

    try:
        for message in messages:
            message.session_id = new_session_id

        session.add_all(messages)
        await session.flush()
        message_responses = []
        for message in messages:
            await session.refresh(message)
            message_responses.append(MessageResponse.model_validate(message, from_attributes=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return message_responses


@router.delete("/messages/session/{session_id}", status_code=204)
async def delete_messages_session(
    session_id: str,
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
):
    try:
        await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
        # Find the message IDs to delete scoped to the org, then delete by ID.
        allowed_ids = (
            await session.exec(
                select(MessageTable.id)
                .join(Flow, MessageTable.flow_id == Flow.id)
                .where(col(MessageTable.session_id) == session_id)
                .where(Flow.organization_id == current_org.id)
            )
        ).all()
        if allowed_ids:
            await session.exec(
                delete(MessageTable)
                .where(col(MessageTable.id).in_(allowed_ids))
                .execution_options(synchronize_session="fetch")
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"message": "Messages deleted successfully"}


@router.get("/transactions")
async def get_transactions(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    current_org: CurrentOrg,
    params: Annotated[Params | None, Depends(custom_params)],
) -> Page[TransactionLogsResponse]:
    try:
        await _require_flow_in_org(session, flow_id, current_org.id)
        await assert_org_role(current_user, current_org.id, MembershipRole.VIEWER, session=session)
        stmt = (
            select(TransactionTable)
            .where(TransactionTable.flow_id == flow_id)
            .order_by(col(TransactionTable.timestamp).desc())
        )
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
            )
            return await apaginate(session, stmt, params=params, transformer=transform_transaction_table_for_logs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
