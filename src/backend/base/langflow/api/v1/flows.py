from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path as StdlibPath
from typing import Annotated, Literal
from uuid import UUID, uuid4

import orjson
from aiofile import async_open
from anyio import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from lfx.log import logger
from lfx.services.secret_store import get_secret_store
from lfx.utils.flow_validation import CustomComponentNotAllowedError, validate_flow_components
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import and_, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    cascade_delete_flow,
    cascade_delete_flows,
    remove_api_keys,
    resolve_component_gate_flags,
    validate_is_component,
)
from langflow.api.utils.authz import assert_org_role
from langflow.api.utils.core import CurrentOrg
from langflow.api.v1.admin.audit_logs import AuditLogListResponse, AuditLogRead
from langflow.api.v1.schemas import FlowListCreate
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.audit_log import AuditTargetType
from langflow.services.database.models.audit_log.model import AuditAction
from langflow.services.database.models.flow.model import (
    AccessTypeEnum,
    Flow,
    FlowCreate,
    FlowHeader,
    FlowRead,
    FlowUpdate,
)
from langflow.services.database.models.tag.model import FlowTag, Tag
from langflow.services.database.models.tag.schema import TagRead
from langflow.services.database.models.flow.utils import generate_webhook_api_key, get_webhook_component_in_flow

# TODO: Full-version import/export is planned as a follow-up feature. When implemented,
# re-add imports for create_flow_version_entry, get_flow_version_list, strip_version_data,
# and FlowVersionError from the flow_version modules.
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.utils import get_default_folder_id
from langflow.services.database.models.membership.model import MembershipRole
from langflow.services.database.models.template.model import Template
from langflow.services.deps import get_audit_service, get_settings_service, get_storage_service, get_variable_service
from langflow.services.storage.service import StorageService
from langflow.services.variable.auto_secrets import (
    blank_autosecrets_for_export,
    cleanup_orphaned_autosecrets,
    delete_autosecrets_for_flow,
    promote_plaintext_secrets_to_variables,
)
from langflow.utils.compression import compress_response

# build router
router = APIRouter(prefix="/flows", tags=["Flows"])


class _FlowTagAssignBody(BaseModel):
    tag_ids: list[UUID]


class _FlowWithTagsRead(BaseModel):
    id: UUID
    tags: list[TagRead]


def _get_safe_flow_path(fs_path: str, user_id: UUID, storage_service: StorageService) -> Path:
    """Get a safe filesystem path for flow storage, restricted to user's flows directory.

    Allows both absolute and relative paths, but ensures they're within the user's flows directory.
    """
    if not fs_path:
        raise HTTPException(status_code=400, detail="fs_path cannot be empty")

    # Normalize path separators first (before security checks to prevent backslash bypass)
    normalized_path = fs_path.replace("\\", "/")

    # Reject directory traversal and null bytes (check normalized path)
    if ".." in normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid fs_path: directory traversal (..) is not allowed",
        )
    if "\x00" in normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid fs_path: null bytes are not allowed",
        )

    # Build the safe base directory path
    base_dir = storage_service.data_dir / "flows" / str(user_id)
    base_dir_str = str(base_dir)

    # Normalize base directory path (resolve to absolute, handle symlinks)
    # resolve() doesn't require the path to exist, it just resolves symlinks
    try:
        base_dir_stdlib = StdlibPath(base_dir_str).resolve()
        base_dir_resolved = str(base_dir_stdlib)
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid base directory: {e}") from e

    # Determine if path is absolute (Unix or Windows style)
    is_absolute = normalized_path.startswith("/") or (len(normalized_path) > 1 and normalized_path[1] == ":")

    if is_absolute:
        # Absolute path - resolve and validate it's within base directory
        try:
            requested_path = StdlibPath(normalized_path).resolve()
            requested_resolved = str(requested_path)
            try:
                # Ensure it's a subpath of the base directory
                requested_path.relative_to(base_dir_stdlib)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=(f"Absolute path must be within your flows directory: {base_dir_resolved}"),
                ) from None
            return Path(requested_resolved)
        except (OSError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid file save path: {e}. "
                    f"Verify that the path is within your flows directory: {base_dir_resolved}"
                ),
            ) from e
    else:
        # Relative path - validate that it's within the base directory
        relative_part = normalized_path.lstrip("/")
        safe_path = base_dir / relative_part if relative_part else base_dir
        safe_path_stdlib = base_dir_stdlib / relative_part if relative_part else base_dir_stdlib
        try:
            final_resolved_str = str(safe_path_stdlib.resolve())

            # Ensure resolved path stays within base (prevent symlink attacks)
            if not final_resolved_str.startswith(base_dir_resolved):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid path: resolves outside allowed directory",
                )
        except (OSError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

        return safe_path


async def _verify_fs_path(path: str | None, user_id: UUID, storage_service: StorageService) -> None:
    """Verify and prepare the filesystem path for flow storage."""
    if path is not None:
        # Empty strings should be rejected (None is allowed, empty string is not)
        if path == "":
            raise HTTPException(status_code=400, detail="fs_path cannot be empty")
        safe_path = _get_safe_flow_path(path, user_id, storage_service)
        await safe_path.parent.mkdir(parents=True, exist_ok=True)
        if not await safe_path.exists():
            await safe_path.touch()


async def _save_flow_to_fs(flow: Flow, user_id: UUID, storage_service: StorageService) -> None:
    """Save flow data to the filesystem at the validated path."""
    if not flow.fs_path:
        return

    try:
        safe_path = _get_safe_flow_path(flow.fs_path, user_id, storage_service)
        await safe_path.parent.mkdir(parents=True, exist_ok=True)
        # async_open expects a string path, not a Path object
        async with async_open(str(safe_path), "w") as f:
            await f.write(flow.model_dump_json())
    except HTTPException:
        raise
    except OSError as e:
        await logger.aexception("Failed to write flow %s to path %s", flow.name, flow.fs_path)
        raise HTTPException(status_code=500, detail=f"Failed to write flow to filesystem: {e}") from e


async def _provision_webhook_api_key(
    org_id: str,
    flow_id: str,
    has_webhook: bool,
) -> str | None:
    """Provision a webhook API key for a flow if it has a webhook component.

    Returns the API key (existing or newly generated), or None if no webhook.
    """
    if not has_webhook:
        return None

    store = get_secret_store()
    path = f"{org_id}/webhooks/{flow_id}"

    existing = await store.get(path)
    if existing and "api_key" in existing:
        return existing["api_key"]

    key = generate_webhook_api_key()
    await store.put(path, {
        "api_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return key


async def _cleanup_webhook_api_key(org_id: str, flow_id: str) -> None:
    """Best-effort delete of a flow's webhook API key from the secret store."""
    try:
        store = get_secret_store()
        await store.delete(f"{org_id}/webhooks/{flow_id}")
    except Exception:
        logger.warning(f"Failed to clean up webhook API key for flow {flow_id}")


async def _new_flow(
    *,
    session: AsyncSession,
    flow: FlowCreate,
    user_id: UUID,
    organization_id: UUID,
    storage_service: StorageService,
    flow_id: UUID | None = None,
    fail_on_endpoint_conflict: bool = False,
    validate_folder: bool = False,
):
    """Create or upsert a flow.

    Args:
        session: Database session.
        flow: Flow creation data.
        user_id: created_by attribution for the new flow.
        organization_id: Org that owns the new flow; scopes all uniqueness / folder checks.
        storage_service: Service for filesystem operations.
        flow_id: Allows PUT upsert to create flows with a specific ID for syncing between instances.
        fail_on_endpoint_conflict: PUT should fail predictably on conflicts rather than silently renaming.
        validate_folder: Validates folder_id exists in the org when upserting from external sources.
    """
    try:
        # Validate fs_path if provided (will raise HTTPException if invalid)
        await _verify_fs_path(flow.fs_path, user_id, storage_service)

        # Validate folder_id if requested (org-scoped)
        if validate_folder and flow.folder_id is not None:
            folder = (
                await session.exec(
                    select(Folder).where(
                        Folder.id == flow.folder_id, Folder.organization_id == organization_id
                    )
                )
            ).first()
            if not folder:
                raise HTTPException(status_code=400, detail="Folder not found")

        # Stamp created_by (ignore any user_id from body for security)
        flow.user_id = user_id

        # Name uniqueness is scoped to the organization.
        if (
            await session.exec(
                select(Flow).where(Flow.name == flow.name, Flow.organization_id == organization_id)
            )
        ).first():
            flows = (
                await session.exec(
                    select(Flow)
                    .where(Flow.name.like(f"{flow.name} (%"))  # type: ignore[attr-defined]
                    .where(Flow.organization_id == organization_id)
                )
            ).all()
            if flows:
                # Use regex to extract numbers only from flows that follow the copy naming pattern:
                # "{original_name} ({number})"
                # This avoids extracting numbers from the original flow name if it naturally contains parentheses
                #
                # Examples:
                # - For flow "My Flow": matches "My Flow (1)", "My Flow (2)" → extracts 1, 2
                # - For flow "Analytics (Q1)": matches "Analytics (Q1) (1)" → extracts 1
                #   but does NOT match "Analytics (Q1)" → avoids extracting the original "1"
                extract_number = re.compile(rf"^{re.escape(flow.name)} \((\d+)\)$")
                numbers = []
                for _flow in flows:
                    result = extract_number.search(_flow.name)
                    if result:
                        numbers.append(int(result.groups(1)[0]))
                if numbers:
                    flow.name = f"{flow.name} ({max(numbers) + 1})"
                else:
                    flow.name = f"{flow.name} (1)"
            else:
                flow.name = f"{flow.name} (1)"

        # Endpoint-name uniqueness is scoped to the organization.
        if (
            flow.endpoint_name
            and (
                await session.exec(
                    select(Flow).where(
                        Flow.endpoint_name == flow.endpoint_name,
                        Flow.organization_id == organization_id,
                    )
                )
            ).first()
        ):
            if fail_on_endpoint_conflict:
                raise HTTPException(status_code=409, detail="Endpoint name must be unique")

            # Auto-rename endpoint
            flows = (
                await session.exec(
                    select(Flow)
                    .where(Flow.endpoint_name.like(f"{flow.endpoint_name}-%"))  # type: ignore[union-attr]
                    .where(Flow.organization_id == organization_id)
                )
            ).all()
            if flows:
                # The endpoint name is like "my-endpoint","my-endpoint-1", "my-endpoint-2"
                # so we need to get the highest number and add 1
                # we need to get the last part of the endpoint name
                numbers = [int(flow.endpoint_name.split("-")[-1]) for flow in flows]
                flow.endpoint_name = f"{flow.endpoint_name}-{max(numbers) + 1}"
            else:
                flow.endpoint_name = f"{flow.endpoint_name}-1"

        db_flow = Flow.model_validate(flow, from_attributes=True)

        # Use specified ID if provided (for PUT upsert)
        if flow_id is not None:
            db_flow.id = flow_id

        db_flow.organization_id = organization_id

        db_flow.updated_at = datetime.now(timezone.utc)

        # Provision webhook API key if flow has a webhook component
        webhook_component = get_webhook_component_in_flow(db_flow.data or {})
        db_flow.webhook = webhook_component is not None
        if db_flow.webhook:
            await _provision_webhook_api_key(
                org_id=str(organization_id),
                flow_id=str(db_flow.id),
                has_webhook=True,
            )

        # Validate folder_id exists in the org, else fall back to default folder
        if db_flow.folder_id is not None:
            folder_exists = (
                await session.exec(
                    select(Folder).where(
                        Folder.id == db_flow.folder_id, Folder.organization_id == organization_id
                    )
                )
            ).first()
            if not folder_exists:
                db_flow.folder_id = None

        if db_flow.folder_id is None:
            # Make sure flows always have a folder (auto-create default folder if needed)
            db_flow.folder_id = await get_default_folder_id(session, user_id)

        session.add(db_flow)

        # Persist and refresh
        await session.flush()
        await session.refresh(db_flow)
        # Explicitly materialize the tags collection so FlowRead can serialize it
        # without triggering a lazy-load in async context (MissingGreenlet).
        await session.refresh(db_flow, attribute_names=["tags"])
        await _save_flow_to_fs(db_flow, user_id, storage_service)

        # Convert to FlowRead while session is still active
        return FlowRead.model_validate(db_flow, from_attributes=True)
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/", response_model=FlowRead, status_code=201)
async def create_flow(
    *,
    session: DbSession,
    flow: FlowCreate,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
    # Gate: block custom-component code on creation for non-admin callers.
    # Mirrors the execution-path gate in langflow.api.utils.core.build_graph_from_data.
    try:
        allow_custom, is_pa = resolve_component_gate_flags(current_user)
        validate_flow_components(
            flow.data or {},
            allow_custom=allow_custom,
            caller_is_platform_admin=is_pa,
        )
    except CustomComponentNotAllowedError as err:
        raise HTTPException(
            status_code=403,
            detail="Custom components are not allowed on this deployment.",
        ) from err

    # Guard: reject creation if the referenced template is archived
    if flow.based_on_template_id is not None:
        t = await session.get(Template, flow.based_on_template_id)
        if t is not None and t.archived_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="template is archived",
            )

    try:
        flow_id = uuid4()

        if flow.data is not None:
            flow.data = await promote_plaintext_secrets_to_variables(
                flow_data=flow.data,
                flow_id=flow_id,
                user_id=current_user.id,
                secret_store=get_secret_store(),
                variable_service=get_variable_service(),
                session=session,
            )

        return await _new_flow(
            session=session,
            flow=flow,
            user_id=current_user.id,
            organization_id=current_org.id,
            storage_service=storage_service,
            flow_id=flow_id,
        )
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # if the column has id in it, we want the other column
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]

            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[FlowRead] | Page[FlowRead] | list[FlowHeader], status_code=200)
async def read_flows(
    *,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
    session: DbSession,
    remove_example_flows: bool = False,
    components_only: bool = False,
    get_all: bool = True,
    folder_id: UUID | None = None,
    params: Annotated[Params, Depends()],
    header_flows: bool = False,
    tag_id: Annotated[list[UUID] | None, Query()] = None,
    tag_match: Annotated[Literal["any", "all"], Query()] = "any",
):
    """Retrieve a list of flows with pagination support.

    Args:
        current_user (User): The current authenticated user.
        session (Session): The database session.
        settings_service (SettingsService): The settings service.
        components_only (bool, optional): Whether to return only components. Defaults to False.

        get_all (bool, optional): Whether to return all flows without pagination. Defaults to True.
        **This field must be True because of backward compatibility with the frontend - Release: 1.0.20**

        folder_id (UUID, optional): The project ID. Defaults to None.
        params (Params): Pagination parameters.
        remove_example_flows (bool, optional): Whether to remove example flows. Defaults to False.
        header_flows (bool, optional): Whether to return only specific headers of the flows. Defaults to False.

    Returns:
        list[FlowRead] | Page[FlowRead] | list[FlowHeader]
        A list of flows or a paginated response containing the list of flows or a list of flow headers.
    """
    try:
        default_folder = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
        default_folder_id = default_folder.id if default_folder else None

        starter_folder = (await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME))).first()
        starter_folder_id = starter_folder.id if starter_folder else None

        if not starter_folder and not default_folder:
            raise HTTPException(
                status_code=404,
                detail="Starter project and default project not found. Please create a project and add flows to it.",
            )

        if not folder_id:
            folder_id = default_folder_id

        # Absolute org scoping — org_id is non-nullable on flow after the
        # multi_tenant_foundation backfill, so no legacy NULL leg is needed.
        # selectinload(Flow.tags) eager-loads tags so FlowRead/FlowHeader can
        # serialize them without triggering a lazy load in async context.
        stmt = (
            select(Flow)
            .options(selectinload(Flow.tags))
            .where(Flow.organization_id == current_org.id)
        )

        if remove_example_flows:
            stmt = stmt.where(Flow.folder_id != starter_folder_id)

        if components_only:
            stmt = stmt.where(Flow.is_component == True)  # noqa: E712

        if tag_id:
            if tag_match == "all":
                n = len(set(tag_id))
                subq = (
                    select(FlowTag.flow_id)
                    .where(col(FlowTag.tag_id).in_(tag_id))
                    .group_by(FlowTag.flow_id)
                    .having(func.count(func.distinct(FlowTag.tag_id)) == n)
                    .scalar_subquery()
                )
                stmt = stmt.where(col(Flow.id).in_(subq))
            else:
                stmt = (
                    stmt.join(FlowTag, FlowTag.flow_id == Flow.id)
                    .where(col(FlowTag.tag_id).in_(tag_id))
                    .distinct()
                )

        if get_all:
            flows = (await session.exec(stmt)).all()
            flows = validate_is_component(flows)
            if components_only:
                flows = [flow for flow in flows if flow.is_component]
            if remove_example_flows and starter_folder_id:
                flows = [flow for flow in flows if flow.folder_id != starter_folder_id]
            if header_flows:
                # Convert to FlowHeader objects and compress the response
                flow_headers = [FlowHeader.model_validate(flow, from_attributes=True) for flow in flows]
                return compress_response(flow_headers)

            # Convert to FlowRead while session is still active to avoid detached instance errors
            flow_reads = [FlowRead.model_validate(flow, from_attributes=True) for flow in flows]
            return compress_response(flow_reads)

        stmt = stmt.where(Flow.folder_id == folder_id)

        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
            )
            return await apaginate(session, stmt, params=params)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _read_flow(
    session: AsyncSession,
    flow_id: UUID,
    organization_id: UUID,
):
    """Read a flow, scoped to the caller's organization."""
    stmt = (
        select(Flow)
        .options(selectinload(Flow.tags))
        .where(Flow.id == flow_id, Flow.organization_id == organization_id)
    )
    return (await session.exec(stmt)).first()


@router.get("/{flow_id}", response_model=FlowRead, status_code=200)
async def read_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
):
    """Read a flow (Viewer+ in the flow's organization)."""
    flow = await _read_flow(session, flow_id, current_org.id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    await assert_org_role(current_user, flow.organization_id, MembershipRole.VIEWER, session=session)
    return FlowRead.model_validate(flow, from_attributes=True)


@router.get("/public_flow/{flow_id}", response_model=FlowRead, status_code=200)
async def read_public_flow(
    *,
    session: DbSession,
    flow_id: UUID,
):
    """Read a public flow — no auth required; access_type == PUBLIC is the ACL."""
    flow = (
        await session.exec(
            select(Flow).options(selectinload(Flow.tags)).where(Flow.id == flow_id)
        )
    ).first()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.access_type is not AccessTypeEnum.PUBLIC:
        raise HTTPException(status_code=403, detail="Flow is not public")
    return FlowRead.model_validate(flow, from_attributes=True)


@router.patch("/{flow_id}", response_model=FlowRead, status_code=200)
async def update_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    flow: FlowUpdate,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Update a flow (Member+ in the flow's organization)."""
    settings_service = get_settings_service()
    try:
        db_flow = await _read_flow(session, flow_id, current_org.id)

        if not db_flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        await assert_org_role(current_user, db_flow.organization_id, MembershipRole.MEMBER, session=session)

        update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

        # Specifically handle endpoint_name when it's explicitly set to null or empty string
        if flow.endpoint_name is None or flow.endpoint_name == "":
            update_data["endpoint_name"] = None

        if settings_service.settings.remove_api_keys:
            update_data = remove_api_keys(update_data)

        if "data" in update_data and update_data["data"] is not None:
            var_svc = get_variable_service()
            sec_store = get_secret_store()
            update_data["data"] = await promote_plaintext_secrets_to_variables(
                flow_data=update_data["data"],
                flow_id=db_flow.id,
                user_id=current_user.id,
                secret_store=sec_store,
                variable_service=var_svc,
                session=session,
            )
            await cleanup_orphaned_autosecrets(
                flow_data=update_data["data"],
                flow_id=db_flow.id,
                user_id=current_user.id,
                secret_store=sec_store,
                session=session,
            )

        for key, value in update_data.items():
            setattr(db_flow, key, value)

        # Validate fs_path if it was changed (will raise HTTPException if invalid)
        if "fs_path" in update_data:
            await _verify_fs_path(db_flow.fs_path, current_user.id, storage_service)

        webhook_component = get_webhook_component_in_flow(db_flow.data)
        db_flow.webhook = webhook_component is not None
        if db_flow.webhook and db_flow.organization_id:
            await _provision_webhook_api_key(
                org_id=str(db_flow.organization_id),
                flow_id=str(db_flow.id),
                has_webhook=True,
            )
        db_flow.updated_at = datetime.now(timezone.utc)

        # Validate folder_id exists in the org, else fall back to default folder
        if db_flow.folder_id is not None:
            folder_exists = (
                await session.exec(
                    select(Folder).where(
                        Folder.id == db_flow.folder_id, Folder.organization_id == current_org.id
                    )
                )
            ).first()
            if not folder_exists:
                db_flow.folder_id = None

        if db_flow.folder_id is None:
            # Make sure flows always have a folder (auto-create default folder if needed)
            db_flow.folder_id = await get_default_folder_id(session, current_user.id)

        session.add(db_flow)
        await session.flush()
        await session.refresh(db_flow)
        # Ensure tags is materialized for FlowRead serialization in async context.
        await session.refresh(db_flow, attribute_names=["tags"])
        await _save_flow_to_fs(db_flow, current_user.id, storage_service)

        # Convert to FlowRead while session is still active to avoid detached instance errors
        flow_read = FlowRead.model_validate(db_flow, from_attributes=True)

    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # if the column has id in it, we want the other column
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]
            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e

        if hasattr(e, "status_code"):
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    return flow_read


@router.put("/{flow_id}", response_model=FlowRead, include_in_schema=False)
async def upsert_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    flow: FlowCreate,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Create or update a flow with a specific ID (upsert).

    - If the flow doesn't exist: creates it (Member+ in current org).
    - If the flow exists in the caller's org: updates it (Member+).
    - If the flow exists in another org: returns 404 (no existence leak).

    Returns 201 for creation, 200 for update.
    """
    from fastapi.responses import JSONResponse

    await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)

    try:
        # Single SELECT (not org-scoped) so we can distinguish three cases without a second round-trip:
        #   - row in this org -> update
        #   - row in another org -> 404 (no existence leak)
        #   - no row anywhere -> create
        stmt = select(Flow).options(selectinload(Flow.tags)).where(Flow.id == flow_id)
        any_flow = (await session.exec(stmt)).first()

        if any_flow is not None and any_flow.organization_id == current_org.id:
            flow_read = await _update_existing_flow(
                session=session,
                existing_flow=any_flow,
                flow=flow,
                current_user=current_user,
                organization_id=current_org.id,
                storage_service=storage_service,
            )
            status_code = 200
        else:
            if any_flow is not None:
                # Exists in another org — 404 to avoid existence leak.
                raise HTTPException(status_code=404, detail="Flow not found")
            flow_read = await _new_flow(
                session=session,
                flow=flow,
                user_id=current_user.id,
                organization_id=current_org.id,
                storage_service=storage_service,
                flow_id=flow_id,
                fail_on_endpoint_conflict=True,
                validate_folder=True,
            )
            status_code = 201

        return JSONResponse(status_code=status_code, content=jsonable_encoder(flow_read))

    except HTTPException:
        raise
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]
            raise HTTPException(
                status_code=409, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _update_existing_flow(
    *,
    session: AsyncSession,
    existing_flow: Flow,
    flow: FlowCreate,
    current_user,
    organization_id: UUID,
    storage_service: StorageService,
) -> FlowRead:
    """Update an existing flow (PUT update path).

    Similar to update_flow but:
    - Fails on name/endpoint_name conflict with OTHER flows in the same org (409)
    - Keeps existing folder_id if not provided in request
    """
    settings_service = get_settings_service()
    user_id = current_user.id

    # Validate fs_path if provided (use `is not None` to catch empty strings)
    if flow.fs_path is not None:
        await _verify_fs_path(flow.fs_path, user_id, storage_service)

    # Validate folder_id if provided (org-scoped)
    if flow.folder_id is not None:
        folder = (
            await session.exec(
                select(Folder).where(
                    Folder.id == flow.folder_id, Folder.organization_id == organization_id
                )
            )
        ).first()
        if not folder:
            raise HTTPException(status_code=400, detail="Folder not found")

    # Check name uniqueness within the org (excluding current flow)
    if flow.name and flow.name != existing_flow.name:
        name_conflict = (
            await session.exec(
                select(Flow).where(
                    Flow.name == flow.name,
                    Flow.organization_id == organization_id,
                    Flow.id != existing_flow.id,
                )
            )
        ).first()
        if name_conflict:
            raise HTTPException(status_code=409, detail="Name must be unique")

    # Check endpoint_name uniqueness within the org (excluding current flow)
    if flow.endpoint_name and flow.endpoint_name != existing_flow.endpoint_name:
        endpoint_conflict = (
            await session.exec(
                select(Flow).where(
                    Flow.endpoint_name == flow.endpoint_name,
                    Flow.organization_id == organization_id,
                    Flow.id != existing_flow.id,
                )
            )
        ).first()
        if endpoint_conflict:
            raise HTTPException(status_code=409, detail="Endpoint name must be unique")

    # Build update data
    update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

    # Handle endpoint_name explicitly set to null or empty string (allow clearing)
    if flow.endpoint_name is None or flow.endpoint_name == "":
        update_data["endpoint_name"] = None

    # Remove id and user_id from update data (security)
    update_data.pop("id", None)
    update_data.pop("user_id", None)

    # If folder_id not provided, keep existing
    if "folder_id" not in update_data or update_data.get("folder_id") is None:
        update_data.pop("folder_id", None)

    if settings_service.settings.remove_api_keys:
        update_data = remove_api_keys(update_data)

    for key, value in update_data.items():
        setattr(existing_flow, key, value)

    webhook_component = get_webhook_component_in_flow(existing_flow.data or {})
    existing_flow.webhook = webhook_component is not None
    existing_flow.updated_at = datetime.now(timezone.utc)

    session.add(existing_flow)
    await session.flush()
    await session.refresh(existing_flow)
    # Ensure tags is materialized for FlowRead serialization in async context.
    await session.refresh(existing_flow, attribute_names=["tags"])
    await _save_flow_to_fs(existing_flow, user_id, storage_service)

    return FlowRead.model_validate(existing_flow, from_attributes=True)


@router.post("/{flow_id}/webhook-api-key", status_code=200)
async def generate_or_reset_webhook_api_key(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
):
    """Generate or reset the webhook API key for a flow (Member+).

    Returns the new API key. The key is only shown once — if the user loses it,
    they must generate a new one (which invalidates the previous key).
    """
    flow = await _read_flow(session, flow_id, current_org.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    await assert_org_role(current_user, flow.organization_id, MembershipRole.MEMBER, session=session)
    if not flow.webhook:
        raise HTTPException(status_code=400, detail="Flow does not have a webhook component")

    store = get_secret_store()
    path = f"{flow.organization_id}/webhooks/{flow_id}"

    # Always generate a new key (reset behavior)
    key = generate_webhook_api_key()
    await store.put(path, {
        "api_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"api_key": key}


@router.put("/{flow_id}/tags", response_model=_FlowWithTagsRead)
async def assign_flow_tags(
    *,
    session: DbSession,
    flow_id: UUID,
    body: _FlowTagAssignBody,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
) -> _FlowWithTagsRead:
    """Replace the full set of tags associated with a flow (PUT-replaces-set)."""
    flow = await _read_flow(
        session=session,
        flow_id=flow_id,
        user_id=current_user.id,
        organization_id=current_org.id,
    )
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    tag_ids = list(body.tag_ids)
    if tag_ids:
        found = (await session.exec(select(Tag).where(col(Tag.id).in_(tag_ids)))).all()
        if len(found) != len(set(tag_ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="one or more tag_ids do not exist",
            )
        tags_by_id = {t.id: t for t in found}
    else:
        tags_by_id = {}

    await session.exec(sa_delete(FlowTag).where(FlowTag.flow_id == flow_id))
    for tid in tag_ids:
        session.add(FlowTag(flow_id=flow_id, tag_id=tid))
    await session.commit()

    return _FlowWithTagsRead(
        id=flow.id,
        tags=[TagRead.model_validate(tags_by_id[tid]) for tid in tag_ids],
    )


@router.delete("/{flow_id}", status_code=200)
async def delete_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
):
    """Delete a flow (Member+ in the flow's organization)."""
    flow = await _read_flow(session, flow_id, current_org.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    await assert_org_role(current_user, flow.organization_id, MembershipRole.MEMBER, session=session)
    # Clean up webhook API key from secret store
    if flow.webhook and flow.organization_id:
        await _cleanup_webhook_api_key(
            org_id=str(flow.organization_id),
            flow_id=str(flow.id),
        )
    await delete_autosecrets_for_flow(
        flow_id=flow.id,
        user_id=current_user.id,
        secret_store=get_secret_store(),
        session=session,
    )
    await cascade_delete_flow(session, flow.id)
    return {"message": "Flow deleted successfully"}


@router.post("/batch/", response_model=list[FlowRead], status_code=201)
async def create_flows(
    *,
    session: DbSession,
    flow_list: FlowListCreate,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
):
    """Create multiple new flows (Member+)."""
    await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
    db_flows = []
    for flow in flow_list.flows:
        flow.user_id = current_user.id
        db_flow = Flow.model_validate(flow, from_attributes=True)
        db_flow.organization_id = current_org.id
        session.add(db_flow)
        db_flows.append(db_flow)

    await session.flush()
    for db_flow in db_flows:
        await session.refresh(db_flow)
        # Ensure tags is materialized for FlowRead serialization in async context.
        await session.refresh(db_flow, attribute_names=["tags"])

    return [FlowRead.model_validate(db_flow, from_attributes=True) for db_flow in db_flows]


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile, File(...)],
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
    folder_id: UUID | None = None,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Upload flows from a file (Member+)."""
    await assert_org_role(current_user, current_org.id, MembershipRole.MEMBER, session=session)
    contents = await file.read()
    data = orjson.loads(contents)

    flow_list = FlowListCreate(**data) if "flows" in data else FlowListCreate(flows=[FlowCreate(**data)])

    # TODO: Full-version import is planned as a follow-up feature.
    # When implemented, extract raw flow dicts here to read embedded "version"
    # arrays and create FlowVersion entries for each imported flow.

    # Gate: block custom-component code on upload for non-admin callers.
    # Pre-pass validation across ALL flows in the batch BEFORE any DB insert —
    # atomic rejection: one bad flow anywhere fails the whole upload.
    allow_custom, is_pa = resolve_component_gate_flags(current_user)
    for flow in flow_list.flows:
        try:
            validate_flow_components(
                flow.data or {},
                allow_custom=allow_custom,
                caller_is_platform_admin=is_pa,
            )
        except CustomComponentNotAllowedError as err:
            raise HTTPException(
                status_code=403,
                detail="Custom components are not allowed on this deployment.",
            ) from err

    try:
        flow_reads = []
        for flow in flow_list.flows:
            flow.user_id = current_user.id
            if folder_id:
                flow.folder_id = folder_id
            flow_read = await _new_flow(
                session=session,
                flow=flow,
                user_id=current_user.id,
                organization_id=current_org.id,
                storage_service=storage_service,
            )
            flow_reads.append(flow_read)
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            # Get the name of the column that failed
            columns = str(e).split("UNIQUE constraint failed: ")[1].split(".")[1].split("\n")[0]
            # UNIQUE constraint failed: flow.user_id, flow.name
            # or UNIQUE constraint failed: flow.name
            # if the column has id in it, we want the other column
            column = columns.split(",")[1] if "id" in columns.split(",")[0] else columns.split(",")[0]

            raise HTTPException(
                status_code=400, detail=f"{column.capitalize().replace('_', ' ')} must be unique"
            ) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e

    return flow_reads


@router.delete("/")
async def delete_multiple_flows(
    flow_ids: list[UUID],
    user: CurrentActiveUser,
    current_org: CurrentOrg,
    db: DbSession,
):
    """Delete multiple flows by their IDs.

    Args:
        flow_ids (List[str]): The list of flow IDs to delete.
        user (User, optional): The user making the request. Defaults to the current active user.
        db (Session, optional): The database session.

    Returns:
        dict: A dictionary containing the number of flows deleted.

    """
    try:
        await assert_org_role(user, current_org.id, MembershipRole.MEMBER, session=db)
        flow_ids_in_org = (
            await db.exec(
                select(Flow.id)
                .where(col(Flow.id).in_(flow_ids))
                .where(Flow.organization_id == current_org.id)
            )
        ).all()
        await cascade_delete_flows(db, flow_ids_in_org)
        await db.flush()
        return {"deleted": len(flow_ids_in_org)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/download/", status_code=200)
async def download_multiple_file(
    flow_ids: list[UUID],
    user: CurrentActiveUser,
    current_org: CurrentOrg,
    db: DbSession,
):
    """Download flows as a zip file (Viewer+ in the current org)."""
    await assert_org_role(user, current_org.id, MembershipRole.VIEWER, session=db)
    flows = (
        await db.exec(
            select(Flow).where(
                and_(
                    Flow.organization_id == current_org.id,
                    Flow.id.in_(flow_ids),  # type: ignore[attr-defined]
                )
            )
        )
    ).all()

    if not flows:
        raise HTTPException(status_code=404, detail="No flows found.")

    flows_without_api_keys = []
    for flow in flows:
        flow_dict = flow.model_dump()
        if flow_dict.get("data"):
            flow_dict["data"] = blank_autosecrets_for_export(flow_dict["data"])
        flows_without_api_keys.append(remove_api_keys(flow_dict))

    if len(flows_without_api_keys) > 1:
        # Create a byte stream to hold the ZIP file
        zip_stream = io.BytesIO()

        # Create a ZIP file
        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            for flow in flows_without_api_keys:
                # Convert the flow object to JSON
                flow_json = json.dumps(jsonable_encoder(flow))

                # Write the JSON to the ZIP file
                zip_file.writestr(f"{flow['name']}.json", flow_json)

        # Seek to the beginning of the byte stream
        zip_stream.seek(0)

        # Generate the filename with the current datetime
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_langflow_flows.zip"

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    return flows_without_api_keys[0]


all_starter_folder_flows_response: Response | None = None


@router.get("/basic_examples/", response_model=list[FlowRead], status_code=200)
async def read_basic_examples(
    *,
    session: DbSession,
):
    """Retrieve a list of basic example flows.

    Args:
        session (Session): The database session.

    Returns:
        list[FlowRead]: A list of basic example flows.
    """
    try:
        global all_starter_folder_flows_response  # noqa: PLW0603

        if all_starter_folder_flows_response:
            return all_starter_folder_flows_response
        # Get the starter folder
        starter_folder = (await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME))).first()

        if not starter_folder:
            return []

        # Get all flows in the starter folder
        all_starter_folder_flows = (
            await session.exec(
                select(Flow)
                .options(selectinload(Flow.tags))
                .where(Flow.folder_id == starter_folder.id)
            )
        ).all()

        flow_reads = [FlowRead.model_validate(flow, from_attributes=True) for flow in all_starter_folder_flows]
        all_starter_folder_flows_response = compress_response(flow_reads)

        # Return compressed response using our utility function
        return all_starter_folder_flows_response  # noqa: TRY300

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/expand/", status_code=200, dependencies=[Depends(get_current_active_user)], include_in_schema=False)
async def expand_compact_flow_endpoint(
    compact_data: dict,
):
    """Expand a compact flow format to full flow format.

    This endpoint takes a minimal flow representation (as generated by AI agents)
    and expands it to the full format expected by the Langflow UI.

    The compact format only requires:
    - nodes: list of {id, type, values?}
    - edges: list of {source, source_output, target, target_input}

    The endpoint returns the full flow data with complete component templates.

    Example input:
    ```json
    {
        "nodes": [
            {"id": "1", "type": "ChatInput"},
            {"id": "2", "type": "OpenAIModel", "values": {"model_name": "gpt-4"}}
        ],
        "edges": [
            {"source": "1", "source_output": "message", "target": "2", "target_input": "input_value"}
        ]
    }
    ```
    """
    from lfx.interface.components import component_cache, get_and_cache_all_types_dict

    from langflow.processing.expand_flow import expand_compact_flow

    # Ensure component cache is loaded
    if component_cache.all_types_dict is None:
        settings_service = get_settings_service()
        await get_and_cache_all_types_dict(settings_service)

    if component_cache.all_types_dict is None:
        raise HTTPException(status_code=500, detail="Component cache not initialized")

    try:
        return expand_compact_flow(compact_data, component_cache.all_types_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{flow_id}/audit-logs", response_model=AuditLogListResponse)
async def list_flow_audit_logs(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
    action: Annotated[AuditAction | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    """List audit log entries for a single flow (Viewer+ on the flow's organization).

    The endpoint forces ``target_type=FLOW`` and ``target_id={flow_id}`` server-side,
    ignoring any client-provided overrides, so callers cannot exfiltrate other targets'
    audit entries.
    """
    # Resolve the flow by id alone so authz can be checked against the flow's actual
    # ``organization_id`` and a non-member receives 403 (rather than the 404 a strictly
    # org-scoped lookup would produce).
    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    await assert_org_role(current_user, flow.organization_id, MembershipRole.VIEWER, session=session)

    service = get_audit_service()
    rows, total = await service.query(
        org_id=flow.organization_id,
        target_type=AuditTargetType.FLOW,
        target_id=flow_id,
        action=action,
        from_=from_,
        to=to,
        page=page,
        size=size,
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(r, from_attributes=True) for r in rows],
        total=total,
        page=page,
        size=size,
    )
