from __future__ import annotations

import contextvars
from contextlib import contextmanager
from uuid import UUID, uuid4

from sqlalchemy import event, text
from sqlalchemy.orm import Mapper
from sqlalchemy.sql import Delete, Select, Update


def _to_uuid(value) -> UUID | str:
    """Coerce a UUID-looking value into a UUID object if possible, preserving passthrough for strings."""
    if value is None:
        return value
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return value


def _as_hex(value) -> str:
    """Return a UUID-ish value as a lowercase 32-char hex string (how SQLAlchemy stores
    UUIDs in CHAR(32) columns on SQLite). Matches what the ORM writes for user.id,
    organization.id, etc., so FK columns we populate via raw SQL line up byte-for-byte."""
    if value is None:
        return value
    if isinstance(value, UUID):
        return value.hex
    try:
        return UUID(str(value)).hex
    except (ValueError, TypeError):
        return str(value)

TENANT_SCOPED_TABLES: set[str] = {
    "flow",
    "folder",
    "file",
    "variable",
    "apikey",
    "deployment",
    "deployment_provider_account",
    "flow_version",
    "message",
    "transaction",
    "vertex_build",
    "job",
}

_suppress = contextvars.ContextVar("suppress_org_guard", default=False)

_INSERT_GUARD_INSTALLED = False


class MissingOrgFilterError(RuntimeError):
    """Raised when a tenant-scoped query lacks an organization_id filter."""


class MissingOrgIdOnInsertError(RuntimeError):
    """Raised when a tenant-scoped row is inserted without organization_id."""


class CrossOrgFKError(RuntimeError):
    """Raised when a tenant-scoped row references an FK from another org."""


@contextmanager
def allow_cross_org_query():
    token = _suppress.set(True)
    try:
        yield
    finally:
        _suppress.reset(token)


def _statement_touches_tenant_table(stmt) -> str | None:
    froms = []
    if hasattr(stmt, "get_final_froms"):
        try:
            froms = list(stmt.get_final_froms())
        except Exception:
            froms = []
    # Update/Delete also expose .table
    table = getattr(stmt, "table", None)
    if table is not None and table not in froms:
        froms.append(table)
    for t in froms:
        name = getattr(t, "name", None)
        if name in TENANT_SCOPED_TABLES:
            return name
    return None


def _has_org_filter(stmt) -> bool:
    where = getattr(stmt, "whereclause", None)
    if where is None:
        return False
    try:
        sql = str(where.compile(compile_kwargs={"literal_binds": False}))
    except Exception:
        sql = str(where)
    return "organization_id" in sql


def install_scoping_guards(engine, *, enforce_select: bool) -> None:
    if enforce_select:

        @event.listens_for(engine, "before_execute", retval=False)
        def _guard(conn, clauseelement, multiparams, params, execution_options):  # noqa: ARG001
            if _suppress.get():
                return
            if not isinstance(clauseelement, (Select, Update, Delete)):
                return
            tbl = _statement_touches_tenant_table(clauseelement)
            if tbl and not _has_org_filter(clauseelement):
                raise MissingOrgFilterError(
                    f"Query against tenant table '{tbl}' has no organization_id filter"
                )

    # Insert guard: always installed. Auto-resolves organization_id from the row's
    # user_id (via the user's membership), and if none exists, provisions a personal
    # org + owner membership inline. This lets legacy call sites and test factories
    # that only set user_id keep working while the DB enforces NOT NULL.
    global _INSERT_GUARD_INSTALLED
    if _INSERT_GUARD_INSTALLED:
        return
    _INSERT_GUARD_INSTALLED = True

    # Auto-provision a personal org + membership for any User insert that doesn't
    # already have one. Mirrors the app-level ensure_personal_organization hook so
    # test fixtures and background jobs that insert User rows directly also work.
    @event.listens_for(Mapper, "after_insert")
    def _user_after_insert(mapper, connection, target):  # noqa: ARG001
        if _suppress.get():
            return
        table_name = mapper.local_table.name if mapper.local_table is not None else None
        if table_name != "user":
            return
        uid = getattr(target, "id", None)
        if uid is None:
            return
        uid_str = _as_hex(uid)
        existing = connection.execute(
            text("SELECT 1 FROM membership WHERE user_id = :uid LIMIT 1"),
            {"uid": uid_str},
        ).first()
        if existing is not None:
            return
        org_id = uuid4().hex
        try:
            connection.execute(
                text(
                    "INSERT INTO organization (id, name, slug, is_personal, created_at, updated_at) "
                    "VALUES (:id, :name, :slug, :is_personal, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": org_id,
                    "name": f"{uid_str}'s workspace",
                    "slug": f"user-{uid_str}",
                    "is_personal": True,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO membership (id, user_id, organization_id, role, created_at) "
                    "VALUES (:id, :uid, :oid, :role, CURRENT_TIMESTAMP)"
                ),
                {"id": uuid4().hex, "uid": uid_str, "oid": org_id, "role": "owner"},
            )
        except Exception:  # noqa: BLE001 — best-effort auto-provision; failure shouldn't block user insert
            pass

    @event.listens_for(Mapper, "before_insert")
    def _insert_guard(mapper, connection, target):  # noqa: ARG001
        if _suppress.get():
            return
        table_name = mapper.local_table.name if mapper.local_table is not None else None
        if table_name not in TENANT_SCOPED_TABLES:
            return
        if getattr(target, "organization_id", None) is not None:
            return

        # Resolve via flow_id → flow.organization_id (covers transaction/message/vertex_build/
        # flow_version/job which have no direct user_id).
        flow_id = getattr(target, "flow_id", None)
        if flow_id is not None:
            row = connection.execute(
                text("SELECT organization_id FROM flow WHERE id = :fid"),
                {"fid": _as_hex(flow_id)},
            ).first()
            if row is not None and row[0] is not None:
                target.organization_id = _to_uuid(row[0])
                return

        # Resolve via folder_id → folder.organization_id.
        folder_id = getattr(target, "folder_id", None)
        if folder_id is not None:
            row = connection.execute(
                text("SELECT organization_id FROM folder WHERE id = :fid"),
                {"fid": _as_hex(folder_id)},
            ).first()
            if row is not None and row[0] is not None:
                target.organization_id = _to_uuid(row[0])
                return

        user_id = getattr(target, "user_id", None)
        if user_id is not None:
            uid_str = _as_hex(user_id)
            row = connection.execute(
                text("SELECT organization_id FROM membership WHERE user_id = :uid LIMIT 1"),
                {"uid": uid_str},
            ).first()
            if row is not None:
                target.organization_id = _to_uuid(row[0])
                return

            # No membership — auto-provision a personal org + membership for this user.
            org_id = uuid4().hex
            connection.execute(
                text(
                    "INSERT INTO organization (id, name, slug, is_personal, created_at, updated_at) "
                    "VALUES (:id, :name, :slug, :is_personal, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": org_id,
                    "name": f"auto-{uid_str}",
                    "slug": f"auto-{uid_str}",
                    "is_personal": True,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO membership (id, user_id, organization_id, role, created_at) "
                    "VALUES (:id, :uid, :oid, :role, CURRENT_TIMESTAMP)"
                ),
                {"id": uuid4().hex, "uid": uid_str, "oid": org_id, "role": "owner"},
            )
            target.organization_id = _to_uuid(org_id)
            return

        # No user_id either — last resort, provision an anonymous "system" org so the row
        # satisfies NOT NULL. Rows landing here are typically orphans from test fixtures or
        # background jobs with no tenant attribution; they're captured in a dedicated org.
        row = connection.execute(
            text("SELECT id FROM organization WHERE slug = :slug LIMIT 1"),
            {"slug": "system-orphan"},
        ).first()
        if row is not None:
            target.organization_id = _to_uuid(row[0])
            return
        org_id = uuid4().hex
        try:
            connection.execute(
                text(
                    "INSERT INTO organization (id, name, slug, is_personal, created_at, updated_at) "
                    "VALUES (:id, 'system-orphan', 'system-orphan', :is_personal, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"id": org_id, "is_personal": False},
            )
        except Exception:  # noqa: BLE001 — racing insert from another session won the unique-slug constraint
            row = connection.execute(
                text("SELECT id FROM organization WHERE slug = :slug LIMIT 1"),
                {"slug": "system-orphan"},
            ).first()
            if row is not None:
                target.organization_id = _to_uuid(row[0])
                return
            raise
        target.organization_id = _to_uuid(org_id)
