from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import attributes

from langflow.services.audit.context import audit_ctx
from langflow.services.audit.diff import (
    build_update_diff,
    hash_value,
    serialize_entity_snapshot,
)
from langflow.services.audit.service import AuditLogEntry
from langflow.services.database.models.audit_log import AuditAction, AuditTargetType
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.database.models.variable.model import Variable
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.api_key.model import ApiKey

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Mapper class -> (target_type, extra_fields)
_AUDITED: dict[type, AuditTargetType] = {
    Flow: AuditTargetType.FLOW,
    Template: AuditTargetType.TEMPLATE,
    Variable: AuditTargetType.VARIABLE,
    Organization: AuditTargetType.ORGANIZATION,
    Membership: AuditTargetType.MEMBERSHIP,
    ApiKey: AuditTargetType.API_KEY,
}

_listeners_registered = False


def register_audit_listener(async_sessionmaker) -> None:
    """Attach the after_commit listener to the session factory's sync Session class."""
    global _listeners_registered
    if _listeners_registered:
        return
    from sqlalchemy.orm import Session

    event.listen(Session, "after_commit", _on_commit)
    # Record dirty snapshots before flush so we can diff per field.
    event.listen(Session, "before_flush", _capture_pre_flush_snapshots)
    _listeners_registered = True


def _capture_pre_flush_snapshots(session: "Session", flush_context, instances) -> None:
    """Snapshot pre-flush values for dirty instances so the after_commit diff can run."""
    ctx = audit_ctx.get()
    if ctx is None:
        return
    # Stash on session.info so after_commit can retrieve it.
    snapshots: dict[tuple[int, str], dict[str, Any]] = session.info.setdefault(
        "_audit_pre_flush_snapshots", {}
    )
    for inst in session.dirty:
        cls = type(inst)
        if cls not in _AUDITED:
            continue
        before: dict[str, Any] = {}
        mapper = inspect(cls)
        for prop in mapper.column_attrs:
            hist = attributes.get_history(inst, prop.key)
            if hist.deleted:
                before[prop.key] = hist.deleted[0]
            else:
                before[prop.key] = getattr(inst, prop.key)
        snapshots[(id(inst), cls.__name__)] = before


def _on_commit(session: "Session") -> None:
    ctx = audit_ctx.get()
    if ctx is None:
        return

    # Collect entries from this transaction's changes.
    entries: list[AuditLogEntry] = []

    # Creates: captured at before_flush time via session.info
    for inst in list(session.info.get("_audit_new", [])):
        target = _AUDITED.get(type(inst))
        if target is None:
            continue
        entries.append(_create_entry(ctx, inst, target))

    # Updates
    snaps = session.info.get("_audit_pre_flush_snapshots", {})
    for inst in list(session.info.get("_audit_dirty", [])):
        target = _AUDITED.get(type(inst))
        if target is None:
            continue
        before = snaps.get((id(inst), type(inst).__name__), {})
        entries.append(_update_entry(ctx, inst, target, before))

    # Deletes
    for inst in list(session.info.get("_audit_deleted", [])):
        target = _AUDITED.get(type(inst))
        if target is None:
            continue
        entries.append(_delete_entry(ctx, inst, target))

    # Clean scratch
    for key in ("_audit_new", "_audit_dirty", "_audit_deleted", "_audit_pre_flush_snapshots"):
        session.info.pop(key, None)

    if not entries:
        return

    from langflow.services.deps import get_audit_service, get_settings_service

    if not get_settings_service().settings.audit_log_enabled:
        return

    service = get_audit_service()
    # after_commit is sync; schedule the async record on the running loop if present.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(service.record_batch(entries))
    except RuntimeError:
        asyncio.run(service.record_batch(entries))


def register_dirty_capture(async_sessionmaker) -> None:
    """Capture new/dirty/deleted instances before the session state is cleared by commit.

    We use before_flush (not before_commit) because by the time before_commit fires,
    the session has already auto-flushed and session.new/dirty/deleted are cleared.
    """
    from sqlalchemy.orm import Session

    # Guard against duplicate registration (idempotent)
    if not hasattr(register_dirty_capture, "_registered"):
        def _before_flush(session: Session, flush_context, instances) -> None:
            ctx = audit_ctx.get()
            if ctx is None:
                return
            # Accumulate across multiple flushes in the same transaction
            new_list = session.info.setdefault("_audit_new", [])
            dirty_list = session.info.setdefault("_audit_dirty", [])
            deleted_list = session.info.setdefault("_audit_deleted", [])
            for inst in session.new:
                if type(inst) in _AUDITED and inst not in new_list:
                    new_list.append(inst)
            for inst in session.dirty:
                if type(inst) in _AUDITED and inst not in dirty_list:
                    dirty_list.append(inst)
            for inst in session.deleted:
                if type(inst) in _AUDITED and inst not in deleted_list:
                    deleted_list.append(inst)

        event.listen(Session, "before_flush", _before_flush)
        register_dirty_capture._registered = True


# ---- entry builders ----

def _base_ctx_fields(ctx, org_id_from_instance) -> dict[str, Any]:
    return {
        "actor_user_id": ctx.user_id,
        "actor_email": ctx.user_email or "",
        "actor_is_super": ctx.is_super,
        "org_id": ctx.org_id or org_id_from_instance,
        "request_metadata": {
            "ip": ctx.ip,
            "user_agent": ctx.user_agent,
            "request_id": ctx.request_id,
            "path": ctx.path,
            "method": ctx.method,
        },
    }


def _infer_org_id(inst: Any) -> Any:
    for name in ("org_id", "organization_id"):
        v = getattr(inst, name, None)
        if v is not None:
            return v
    return None


def _create_entry(ctx, inst, target: AuditTargetType) -> AuditLogEntry:
    snap = serialize_entity_snapshot(inst)
    return AuditLogEntry(
        target_type=target,
        target_id=getattr(inst, "id"),
        action=AuditAction.CREATE,
        diff={"after": snap},
        **_base_ctx_fields(ctx, _infer_org_id(inst)),
    )


def _update_entry(ctx, inst, target: AuditTargetType, before_values: dict[str, Any]) -> AuditLogEntry:
    current = {k: getattr(inst, k, None) for k in before_values.keys()} if before_values else {}
    action, diff_body = _classify_update(inst, target, before_values, current)
    hint = ctx.action_hints.get((target.value, getattr(inst, "id")))
    if hint:
        action = AuditAction(hint)
    return AuditLogEntry(
        target_type=target,
        target_id=getattr(inst, "id"),
        action=action,
        diff=diff_body,
        **_base_ctx_fields(ctx, _infer_org_id(inst)),
    )


def _delete_entry(ctx, inst, target: AuditTargetType) -> AuditLogEntry:
    snap = serialize_entity_snapshot(inst)
    return AuditLogEntry(
        target_type=target,
        target_id=getattr(inst, "id"),
        action=AuditAction.DELETE,
        diff={"before": snap},
        **_base_ctx_fields(ctx, _infer_org_id(inst)),
    )


def _classify_update(
    inst: Any, target: AuditTargetType, before: dict[str, Any], current: dict[str, Any]
) -> tuple[AuditAction, dict[str, Any]]:
    # Template archive/unarchive: archived_at flip
    if target is AuditTargetType.TEMPLATE and "archived_at" in before:
        was = before.get("archived_at")
        now = current.get("archived_at")
        if was is None and now is not None:
            return AuditAction.ARCHIVE, {"archived": True}
        if was is not None and now is None:
            return AuditAction.UNARCHIVE, {"archived": False}
    # Membership role change → assign_role
    if target is AuditTargetType.MEMBERSHIP and "role" in before and before["role"] != current.get("role"):
        return AuditAction.ASSIGN_ROLE, {
            "role": {"before": str(before["role"]), "after": str(current.get("role"))}
        }
    diff = build_update_diff(
        target_type=target.value, before_values=before, after_values=current
    )
    return AuditAction.UPDATE, diff
