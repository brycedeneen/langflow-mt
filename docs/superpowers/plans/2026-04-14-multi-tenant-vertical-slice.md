# Multi-Tenant Vertical Slice Implementation Plan

> **Status (2026-04-22):** All 18 tasks landed via the `feat/adp-connector` and `feat/user-detail-and-roles` merges on `platform-multi-tenant`. Verified by running the targeted multi-tenant test suites (93 tests pass). See **Execution Status** section below for per-task notes and design deviations from the original spec.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Langflow from single-tenant to multi-tenant via a foundational vertical slice — `Organization` and `Membership` as first-class entities, every tenant resource carries `organization_id`, all reads/writes scoped per org, existing data migrated into a single Default Organization. UI unchanged (one org per user implicitly).

**Architecture:** Two new SQLModel tables (`organization`, `membership`). Denormalized `organization_id NOT NULL FK` added to every tenant-scoped table. A FastAPI dependency `get_current_organization` resolves the current user's single membership and feeds `organization_id` into every CRUD call. Defense-in-depth via SQLAlchemy `before_insert` (always on) and a dev/test-only `before_execute` guardrail that raises if a tenant query lacks an `organization_id` filter. A single Alembic migration creates the tables, backfills a Default Organization, and stamps every existing tenant row.

**Tech Stack:** Python 3.10+, FastAPI, SQLModel/SQLAlchemy 2.x (async), Alembic, pytest, uv. Spec lives at `docs/superpowers/specs/2026-04-14-multi-tenant-vertical-slice-design.md`.

**Phases:**
1. Schema & scoping primitives (Tasks 1–4)
2. Migration foundation (Tasks 5–7)
3. Signup hook for personal orgs (Task 8)
4. Wire dependency through endpoints (Tasks 9–16)
5. Full integration tests (Tasks 17–18)

**Conventions used throughout this plan:**
- All Python commands use `uv run`. Run from repo root unless noted.
- Test paths use `src/backend/tests/unit/...`.
- Tenant-scoped tables (referenced repeatedly): `flow`, `folder`, `file`, `variable`, `api_key`, `deployment`, `deployment_provider_account`, `flow_version`, `message`, `transaction`, `vertex_build`, `job`. (MCP server config lives on `folder.auth_settings`; folder scoping covers it.)
- "TENANT_TABLES" below is the canonical list — keep in sync if any tasks discover more.

---

## Phase 1: Schema & Scoping Primitives

### Task 1: Create `Organization` SQLModel

**Files:**
- Create: `src/backend/base/langflow/services/database/models/organization/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/organization/model.py`
- Create: `src/backend/tests/unit/services/database/models/organization/__init__.py`
- Test: `src/backend/tests/unit/services/database/models/organization/test_model.py`
- Modify: `src/backend/base/langflow/services/database/models/__init__.py` (register import)

- [ ] **Step 1: Write failing test**

`src/backend/tests/unit/services/database/models/organization/test_model.py`:
```python
import pytest
from uuid import UUID
from sqlmodel import select
from langflow.services.database.models.organization.model import Organization


@pytest.mark.asyncio
async def test_create_organization(async_session):
    org = Organization(name="Acme", slug="acme", is_personal=False)
    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    assert isinstance(org.id, UUID)
    assert org.name == "Acme"
    assert org.slug == "acme"
    assert org.is_personal is False
    assert org.created_at is not None


@pytest.mark.asyncio
async def test_organization_slug_unique(async_session):
    async_session.add(Organization(name="A", slug="dup"))
    await async_session.commit()
    async_session.add(Organization(name="B", slug="dup"))
    with pytest.raises(Exception):
        await async_session.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/database/models/organization/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: ...organization.model`.

- [ ] **Step 3: Implement Organization model**

`src/backend/base/langflow/services/database/models/organization/model.py`:
```python
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "organization"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    name: str = Field(index=True)
    slug: str = Field(index=True, unique=True)
    is_personal: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
```

`src/backend/base/langflow/services/database/models/organization/__init__.py`:
```python
from langflow.services.database.models.organization.model import Organization

__all__ = ["Organization"]
```

`src/backend/tests/unit/services/database/models/organization/__init__.py`: empty file.

- [ ] **Step 4: Register the model so metadata picks it up**

Edit `src/backend/base/langflow/services/database/models/__init__.py` and add `Organization` to its imports/`__all__` alongside the existing models (follow the file's existing alphabetical pattern).

- [ ] **Step 5: Run test, verify pass**

Run: `uv run pytest src/backend/tests/unit/services/database/models/organization/test_model.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/database/models/organization \
        src/backend/base/langflow/services/database/models/__init__.py \
        src/backend/tests/unit/services/database/models/organization
git commit -m "feat(multi-tenant): add Organization model"
```

---

### Task 2: Create `Membership` SQLModel

**Files:**
- Create: `src/backend/base/langflow/services/database/models/membership/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/membership/model.py`
- Create: `src/backend/tests/unit/services/database/models/membership/__init__.py`
- Test: `src/backend/tests/unit/services/database/models/membership/test_model.py`
- Modify: `src/backend/base/langflow/services/database/models/__init__.py`

- [ ] **Step 1: Write failing test**

`src/backend/tests/unit/services/database/models/membership/test_model.py`:
```python
import pytest
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


async def _make_user(session, name="alice"):
    user = User(username=name, password="x", is_active=True)
    session.add(user); await session.commit(); await session.refresh(user)
    return user


async def _make_org(session, slug="acme"):
    org = Organization(name=slug, slug=slug)
    session.add(org); await session.commit(); await session.refresh(org)
    return org


@pytest.mark.asyncio
async def test_create_membership(async_session):
    user = await _make_user(async_session)
    org = await _make_org(async_session)
    m = Membership(user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER)
    async_session.add(m); await async_session.commit(); await async_session.refresh(m)
    assert m.role == MembershipRole.OWNER


@pytest.mark.asyncio
async def test_membership_user_org_unique(async_session):
    user = await _make_user(async_session); org = await _make_org(async_session)
    async_session.add(Membership(user_id=user.id, organization_id=org.id))
    await async_session.commit()
    async_session.add(Membership(user_id=user.id, organization_id=org.id))
    with pytest.raises(Exception):
        await async_session.commit()
```

- [ ] **Step 2: Run, verify FAIL** (`ModuleNotFoundError`)

Run: `uv run pytest src/backend/tests/unit/services/database/models/membership/test_model.py -v`

- [ ] **Step 3: Implement Membership model**

`src/backend/base/langflow/services/database/models/membership/model.py`:
```python
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from langflow.schema.serialize import UUIDstr


class MembershipRole(str, Enum):
    OWNER = "owner"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Membership(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUIDstr = Field(index=True, foreign_key="user.id")
    organization_id: UUIDstr = Field(index=True, foreign_key="organization.id")
    role: MembershipRole = Field(
        default=MembershipRole.OWNER,
        sa_column=Column(SQLEnum(MembershipRole, name="membership_role_enum",
                                 values_callable=lambda e: [m.value for m in e]),
                         nullable=False),
    )
    created_at: datetime = Field(default_factory=_utc_now)
```

`src/backend/base/langflow/services/database/models/membership/__init__.py`:
```python
from langflow.services.database.models.membership.model import Membership, MembershipRole

__all__ = ["Membership", "MembershipRole"]
```

Add `Membership` and `MembershipRole` to `services/database/models/__init__.py`.

- [ ] **Step 4: Run, verify PASS** (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/database/models/membership \
        src/backend/base/langflow/services/database/models/__init__.py \
        src/backend/tests/unit/services/database/models/membership
git commit -m "feat(multi-tenant): add Membership model"
```

---

### Task 3: Scoping module — guardrails and escape hatch

**Files:**
- Create: `src/backend/base/langflow/services/database/scoping.py`
- Test: `src/backend/tests/unit/services/database/test_scoping.py`

The module exports:
- `MissingOrgFilterError(Exception)` — raised when guardrail trips.
- `MissingOrgIdOnInsertError(Exception)` — raised by `before_insert` for missing org_id.
- `CrossOrgFKError(Exception)` — raised when an FK references a row in a different org.
- `TENANT_SCOPED_TABLES: set[str]` — canonical name list (see Conventions above).
- `allow_cross_org_query()` — context manager that suppresses the SELECT/UPDATE/DELETE guardrail in the current asyncio task.
- `install_scoping_guards(engine, *, enforce_select: bool)` — registers SQLAlchemy `before_execute` (only if `enforce_select`) and `before_insert` listeners on the given engine.

- [ ] **Step 1: Write failing tests**

`src/backend/tests/unit/services/database/test_scoping.py`:
```python
import pytest
from sqlmodel import select
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.scoping import (
    MissingOrgFilterError,
    MissingOrgIdOnInsertError,
    allow_cross_org_query,
    install_scoping_guards,
)


@pytest.fixture
def guarded_engine(async_engine):
    install_scoping_guards(async_engine.sync_engine, enforce_select=True)
    return async_engine


@pytest.mark.asyncio
async def test_select_without_org_filter_raises(async_session, guarded_engine):
    with pytest.raises(MissingOrgFilterError):
        await async_session.exec(select(Flow))


@pytest.mark.asyncio
async def test_select_with_org_filter_passes(async_session, guarded_engine, default_org_id):
    await async_session.exec(select(Flow).where(Flow.organization_id == default_org_id))


@pytest.mark.asyncio
async def test_allow_cross_org_query_suppresses(async_session, guarded_engine):
    with allow_cross_org_query():
        await async_session.exec(select(Flow))


@pytest.mark.asyncio
async def test_insert_without_org_id_raises(async_session, guarded_engine, user_id):
    flow = Flow(name="x", user_id=user_id, data={})  # NB: no organization_id
    async_session.add(flow)
    with pytest.raises(MissingOrgIdOnInsertError):
        await async_session.commit()
```

(`async_engine`, `default_org_id`, `user_id` fixtures: add to a local `conftest.py` next to this test file, building on the existing repo `async_session` fixture.)

- [ ] **Step 2: Run, verify FAIL** (`ModuleNotFoundError`)

Run: `uv run pytest src/backend/tests/unit/services/database/test_scoping.py -v`

- [ ] **Step 3: Implement scoping module**

`src/backend/base/langflow/services/database/scoping.py`:
```python
from __future__ import annotations

import contextvars
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.sql import Delete, Select, Update

TENANT_SCOPED_TABLES: set[str] = {
    "flow", "folder", "file", "variable", "api_key", "deployment",
    "deployment_provider_account", "flow_version", "message",
    "transaction", "vertex_build", "job",
}

_suppress = contextvars.ContextVar("suppress_org_guard", default=False)


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
    for table in stmt.get_final_froms() if hasattr(stmt, "get_final_froms") else []:
        name = getattr(table, "name", None)
        if name in TENANT_SCOPED_TABLES:
            return name
    return None


def _has_org_filter(stmt) -> bool:
    sql = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    return "organization_id" in sql


def install_scoping_guards(engine, *, enforce_select: bool) -> None:
    if enforce_select:
        @event.listens_for(engine, "before_execute", retval=False)
        def _guard(conn, clauseelement, multiparams, params, execution_options):
            if _suppress.get():
                return
            if not isinstance(clauseelement, (Select, Update, Delete)):
                return
            tbl = _statement_touches_tenant_table(clauseelement)
            if tbl and not _has_org_filter(clauseelement):
                raise MissingOrgFilterError(
                    f"Query against tenant table '{tbl}' has no organization_id filter"
                )

    @event.listens_for(engine, "before_cursor_execute")
    def _noop(*_a, **_kw):  # placeholder; real insert guard below uses ORM event
        pass

    # Insert guard: ORM-level so it inspects model instances
    from sqlalchemy.orm import Mapper
    from sqlalchemy.orm import mapper as _

    @event.listens_for(Mapper, "before_insert")
    def _insert_guard(mapper, connection, target):
        table_name = mapper.local_table.name if mapper.local_table is not None else None
        if table_name not in TENANT_SCOPED_TABLES:
            return
        if getattr(target, "organization_id", None) is None:
            raise MissingOrgIdOnInsertError(
                f"Insert into '{table_name}' missing organization_id"
            )
```

- [ ] **Step 4: Run, verify PASS** (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/database/scoping.py \
        src/backend/tests/unit/services/database/test_scoping.py \
        src/backend/tests/unit/services/database/conftest.py
git commit -m "feat(multi-tenant): add scoping guardrails (select/insert)"
```

---

### Task 4: `get_current_organization` and `get_current_membership` dependencies

**Files:**
- Create: `src/backend/base/langflow/api/v1/org_helpers.py`
- Modify: `src/backend/base/langflow/api/utils/core.py` (add `CurrentOrg`, `CurrentMembership` aliases)
- Test: `src/backend/tests/unit/api/test_org_helpers.py`

- [ ] **Step 1: Write failing tests**

`src/backend/tests/unit/api/test_org_helpers.py`:
```python
import pytest
from fastapi import HTTPException
from langflow.api.v1.org_helpers import get_current_organization


@pytest.mark.asyncio
async def test_returns_single_membership_org(async_session, user_with_membership):
    user, org = user_with_membership
    result = await get_current_organization(user=user, session=async_session, x_acting_org_id=None)
    assert result.id == org.id


@pytest.mark.asyncio
async def test_no_membership_raises_403(async_session, user_without_membership):
    with pytest.raises(HTTPException) as exc:
        await get_current_organization(user=user_without_membership, session=async_session, x_acting_org_id=None)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_superuser_acting_as_with_header(async_session, superuser, other_org):
    result = await get_current_organization(
        user=superuser, session=async_session, x_acting_org_id=str(other_org.id)
    )
    assert result.id == other_org.id


@pytest.mark.asyncio
async def test_non_superuser_acting_as_rejected(async_session, user_with_membership, other_org):
    user, _ = user_with_membership
    with pytest.raises(HTTPException) as exc:
        await get_current_organization(
            user=user, session=async_session, x_acting_org_id=str(other_org.id)
        )
    assert exc.value.status_code == 403
```

(Add the four fixtures to a `conftest.py` next to this file — they construct rows directly with the existing `async_session`.)

- [ ] **Step 2: Run, verify FAIL** (`ModuleNotFoundError`)

Run: `uv run pytest src/backend/tests/unit/api/test_org_helpers.py -v`

- [ ] **Step 3: Implement dependency module**

`src/backend/base/langflow/api/v1/org_helpers.py`:
```python
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


async def get_current_organization(
    user: User = Depends(CurrentActiveUser),
    session: AsyncSession = Depends(DbSession),
    x_acting_org_id: Annotated[str | None, Header(alias="X-Acting-Org-Id")] = None,
) -> Organization:
    if x_acting_org_id is not None:
        if not user.is_superuser:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "X-Acting-Org-Id requires superuser")
        try:
            org_id = UUID(x_acting_org_id)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid X-Acting-Org-Id") from e
        org = await session.get(Organization, org_id)
        if org is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
        return org

    rows = (await session.exec(select(Membership).where(Membership.user_id == user.id))).all()
    if len(rows) == 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no organization membership")
    if len(rows) > 1:
        # Slice invariant: one membership per user. If violated, fail loudly.
        raise HTTPException(status.HTTP_409_CONFLICT, "User has multiple memberships (unsupported in this slice)")
    org = await session.get(Organization, rows[0].organization_id)
    assert org is not None  # FK guarantees this
    return org


async def get_current_membership(
    user: User = Depends(CurrentActiveUser),
    session: AsyncSession = Depends(DbSession),
) -> Membership:
    row = (await session.exec(select(Membership).where(Membership.user_id == user.id))).first()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no organization membership")
    return row
```

Add to `src/backend/base/langflow/api/utils/core.py` (after the existing `CurrentActiveUser` definition):
```python
from langflow.services.database.models.membership.model import Membership  # noqa: E402
from langflow.services.database.models.organization.model import Organization  # noqa: E402
from langflow.api.v1.org_helpers import get_current_organization, get_current_membership  # noqa: E402

CurrentOrg = Annotated[Organization, Depends(get_current_organization)]
CurrentMembership = Annotated[Membership, Depends(get_current_membership)]
```

- [ ] **Step 4: Run, verify PASS** (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/org_helpers.py \
        src/backend/base/langflow/api/utils/core.py \
        src/backend/tests/unit/api/test_org_helpers.py \
        src/backend/tests/unit/api/conftest.py
git commit -m "feat(multi-tenant): add CurrentOrg / CurrentMembership dependencies"
```

---

## Phase 2: Migration Foundation

### Task 5: Add `organization_id` columns to all tenant-scoped models

This task only changes the SQLModel definitions (so future code & migration can reference the column). The migration to actually add the columns to the DB is in Task 6.

**Files:** for each table in TENANT_TABLES, modify the model file under `src/backend/base/langflow/services/database/models/<table>/model.py`. Concrete list:
- `flow/model.py`
- `folder/model.py`
- `file/model.py`
- `variable/model.py`
- `api_key/model.py`
- `deployment/model.py`
- `deployment_provider_account/model.py`
- `flow_version/model.py`
- `message/model.py`
- `transactions/model.py` (table name `transaction`)
- `vertex_builds/model.py` (table name `vertex_build`)
- `jobs/model.py` (table name `job`)

**Test:** `src/backend/tests/unit/services/database/test_org_columns.py`

- [ ] **Step 1: Write failing test**

```python
import pytest
from sqlalchemy import inspect
from langflow.services.database.scoping import TENANT_SCOPED_TABLES


@pytest.mark.asyncio
async def test_every_tenant_table_has_org_id(async_engine):
    async with async_engine.begin() as conn:
        def _check(sync_conn):
            insp = inspect(sync_conn)
            missing = []
            for table in TENANT_SCOPED_TABLES:
                cols = {c["name"] for c in insp.get_columns(table)}
                if "organization_id" not in cols:
                    missing.append(table)
            return missing
        missing = await conn.run_sync(_check)
    assert missing == [], f"Missing organization_id on: {missing}"
```

- [ ] **Step 2: Run, verify FAIL** (every table missing column)

Run: `uv run pytest src/backend/tests/unit/services/database/test_org_columns.py -v`

- [ ] **Step 3: Add `organization_id` field to each tenant model**

In each `<table>/model.py`'s primary table class (the one with `table=True`), add:
```python
organization_id: UUIDstr = Field(index=True, foreign_key="organization.id", nullable=False)
```

Place it adjacent to existing FK fields (e.g., near `user_id`). Import `UUIDstr` if not already present (`from langflow.schema.serialize import UUIDstr`).

For each of the 12 tables, locate the `class Foo(FooBase, table=True):` (or equivalent) and insert the field. Update any `*Create` schemas to either accept `organization_id` from internal callers or compute it server-side; `*Read` schemas should expose it.

Also update test factories: any test that constructs one of these models without `organization_id` will now fail — search and add `organization_id=<some_org.id>` (a follow-up step in Task 6 will provide a `default_org` fixture for the broad test suite).

- [ ] **Step 4: Run, verify PASS**

Run: `uv run pytest src/backend/tests/unit/services/database/test_org_columns.py -v`
Expected: PASS.

Then run a broader smoke check:
Run: `uv run pytest src/backend/tests/unit/services/database -x -q`
Expected: only failures should be from constructs missing `organization_id`. Fix those by adding the field where models are instantiated in tests.

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/database/models \
        src/backend/tests/unit/services/database/test_org_columns.py
git commit -m "feat(multi-tenant): add organization_id FK to all tenant tables"
```

---

### Task 6: Alembic migration — create org/membership, backfill, NOT NULL

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<timestamp>_multi_tenant_foundation.py` (generated)
- Test: `src/backend/tests/unit/services/database/test_migration_multi_tenant.py`

- [ ] **Step 1: Generate the migration scaffold**

Run: `cd src/backend/base/langflow && uv run alembic revision -m "multi_tenant_foundation"`
Note the generated filename — refer to it as `<rev>_multi_tenant_foundation.py` below.

- [ ] **Step 2: Write failing migration test**

`src/backend/tests/unit/services/database/test_migration_multi_tenant.py`:
```python
import pytest
from sqlalchemy import inspect, text
from langflow.services.database.scoping import TENANT_SCOPED_TABLES


@pytest.mark.asyncio
async def test_default_org_created_and_backfilled(migrated_engine_with_legacy_data):
    """Engine fixture: applies migration to a DB pre-loaded with one user and one flow
    (created with organization_id NULL via raw SQL before the column became NOT NULL)."""
    eng = migrated_engine_with_legacy_data
    async with eng.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM organization WHERE slug='default'"))).all()
        assert len(rows) == 1
        default_org_id = rows[0][0]

        memberships = (await conn.execute(text("SELECT user_id FROM membership"))).all()
        assert len(memberships) >= 1

        for table in TENANT_SCOPED_TABLES:
            res = (await conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE organization_id IS NULL"))).scalar()
            assert res == 0, f"{table} has NULL organization_id rows after migration"


@pytest.mark.asyncio
async def test_migration_round_trip(alembic_config):
    """upgrade head → downgrade -1 → upgrade head must succeed without error."""
    from alembic import command
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "-1")
    command.upgrade(alembic_config, "head")
```

- [ ] **Step 3: Run, verify FAIL** (migration is a stub)

Run: `uv run pytest src/backend/tests/unit/services/database/test_migration_multi_tenant.py -v`

- [ ] **Step 4: Implement the migration**

Replace the body of `<rev>_multi_tenant_foundation.py`:
```python
from uuid import uuid4
import sqlalchemy as sa
from alembic import op

# revision identifiers, auto-set by alembic
revision = "<rev>"
down_revision = "<previous>"  # Alembic fills this; verify it points at the latest existing head.
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "flow", "folder", "file", "variable", "api_key", "deployment",
    "deployment_provider_account", "flow_version", "message",
    "transaction", "vertex_build", "job",
]


def upgrade() -> None:
    # 1. organization
    op.create_table(
        "organization",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organization_slug", "organization", ["slug"], unique=True)
    op.create_index("ix_organization_name", "organization", ["name"])

    # 2. membership
    op.create_table(
        "membership",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    op.create_index("ix_membership_user_id", "membership", ["user_id"])
    op.create_index("ix_membership_organization_id", "membership", ["organization_id"])

    # 3. Insert default org
    bind = op.get_bind()
    default_org_id = uuid4()
    bind.execute(
        sa.text(
            "INSERT INTO organization (id, name, slug, is_personal) "
            "VALUES (:id, 'Default Organization', 'default', false)"
        ),
        {"id": default_org_id},
    )

    # 4. Backfill memberships (one per existing user)
    bind.execute(
        sa.text(
            'INSERT INTO membership (id, user_id, organization_id, role) '
            'SELECT :prefix || u.id, u.id, :org_id, :role FROM "user" u'
        ),
        # Note: SQLite-friendly id derivation; if your dialect rejects this, switch to
        # iterating user rows in Python and inserting one-by-one with uuid4() each.
        {"prefix": "00000000-0000-0000-0000-", "org_id": default_org_id, "role": "owner"},
    )

    # 5. Add organization_id columns (nullable first), backfill, then NOT NULL
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET organization_id = :org_id"), {"org_id": default_org_id})
        with op.batch_alter_table(table) as batch:
            batch.alter_column("organization_id", nullable=False)
            batch.create_foreign_key(f"fk_{table}_organization", "organization", ["organization_id"], ["id"])
            batch.create_index(f"ix_{table}_organization_id", ["organization_id"])

    # 6. Verify
    for table in TENANT_TABLES:
        nulls = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE organization_id IS NULL")
        ).scalar()
        if nulls:
            raise RuntimeError(f"Backfill failed: {table} has {nulls} NULL organization_id rows")


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_organization_id")
            batch.drop_constraint(f"fk_{table}_organization", type_="foreignkey")
            batch.drop_column("organization_id")
    op.drop_index("ix_membership_organization_id", "membership")
    op.drop_index("ix_membership_user_id", "membership")
    op.drop_table("membership")
    op.drop_index("ix_organization_name", "organization")
    op.drop_index("ix_organization_slug", "organization")
    op.drop_table("organization")
```

Note on the `uuid4`-via-string trick in Step 4: it's a SQLite-friendly hack to avoid per-row Python iteration. If your dialect (Postgres) rejects the prefix string, replace that block with a Python loop:
```python
for (uid,) in bind.execute(sa.text('SELECT id FROM "user"')).all():
    bind.execute(
        sa.text("INSERT INTO membership (id, user_id, organization_id, role) "
                "VALUES (:id, :uid, :org, 'owner')"),
        {"id": uuid4(), "uid": uid, "org": default_org_id},
    )
```

- [ ] **Step 5: Run, verify PASS** (both tests pass)

Run: `uv run pytest src/backend/tests/unit/services/database/test_migration_multi_tenant.py -v`

- [ ] **Step 6: Run the full unit suite — fix any newly-broken tests**

Run: `make unit_tests async=false`
Expected: tests that previously constructed tenant models without `organization_id` may still need fixture updates. Add a session-scoped `default_org` fixture in `src/backend/tests/conftest.py` and update factories.

- [ ] **Step 7: Commit**

```bash
git add src/backend/base/langflow/alembic/versions/<rev>_multi_tenant_foundation.py \
        src/backend/tests/unit/services/database/test_migration_multi_tenant.py \
        src/backend/tests/conftest.py
git commit -m "feat(multi-tenant): alembic migration creates org+membership and backfills tenant tables"
```

---

### Task 7: Wire scoping guards into the database service at app startup

**Files:**
- Modify: `src/backend/base/langflow/services/database/service.py` (call `install_scoping_guards` after engine creation)
- Test: `src/backend/tests/unit/services/database/test_scoping_installed.py`

- [ ] **Step 1: Find current engine creation**

Run: `grep -n "create_async_engine\|self.engine" src/backend/base/langflow/services/database/service.py | head`

- [ ] **Step 2: Write failing test**

```python
import os
import pytest
from sqlmodel import select
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.scoping import MissingOrgFilterError


@pytest.mark.asyncio
async def test_guard_active_in_dev(monkeypatch, app_with_dev_env, async_session):
    monkeypatch.setenv("LANGFLOW_ENV", "dev")
    with pytest.raises(MissingOrgFilterError):
        await async_session.exec(select(Flow))


@pytest.mark.asyncio
async def test_guard_inactive_in_prod(monkeypatch, app_with_prod_env, async_session, default_org_id):
    monkeypatch.setenv("LANGFLOW_ENV", "prod")
    # Should not raise — but insert guard still runs
    await async_session.exec(select(Flow).where(Flow.organization_id == default_org_id))
```

- [ ] **Step 3: Run, verify FAIL**

- [ ] **Step 4: Implement install in `service.py`**

After the engine is created, add:
```python
from langflow.services.database.scoping import install_scoping_guards

enforce_select = os.getenv("LANGFLOW_ENV", "prod").lower() in {"dev", "test"}
install_scoping_guards(self.engine.sync_engine, enforce_select=enforce_select)
```
(Adapt the attribute name to whatever the engine is stored as.)

- [ ] **Step 5: Run, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/database/service.py \
        src/backend/tests/unit/services/database/test_scoping_installed.py
git commit -m "feat(multi-tenant): install scoping guards on db service startup"
```

---

## Phase 3: Personal Org on Signup

### Task 8: Auto-create personal Organization + Membership on user creation

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/user/crud.py` (or wherever `create_user` lives — verify with `grep`)
- Modify: CLI superuser creation path (`src/backend/base/langflow/main.py` or `cli.py` — `grep -rn "create_super_user"` to find it)
- Test: `src/backend/tests/unit/services/database/models/user/test_create_user_personal_org.py`

- [ ] **Step 1: Locate user creation paths**

Run: `grep -rn "def create_user\|create_super_user" src/backend/base/langflow`

- [ ] **Step 2: Write failing test**

```python
import pytest
from sqlmodel import select
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.crud import create_user
from langflow.services.database.models.user.model import UserCreate


@pytest.mark.asyncio
async def test_create_user_creates_personal_org(async_session):
    user = await create_user(async_session, UserCreate(username="bob", password="x"))
    rows = (await async_session.exec(select(Membership).where(Membership.user_id == user.id))).all()
    assert len(rows) == 1
    assert rows[0].role == MembershipRole.OWNER
    org = await async_session.get(Organization, rows[0].organization_id)
    assert org.is_personal is True
    assert org.name == "bob's workspace"
```

- [ ] **Step 3: Run, verify FAIL**

- [ ] **Step 4: Implement personal-org creation**

In the user-creation function (after the User row commits), add:
```python
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization

org = Organization(name=f"{user.username}'s workspace", slug=f"user-{user.id}", is_personal=True)
session.add(org); await session.flush()
session.add(Membership(user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER))
await session.commit()
```

Apply the same to the CLI superuser path.

- [ ] **Step 5: Run, verify PASS**

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/database/models/user/crud.py \
        <cli/superuser file> \
        src/backend/tests/unit/services/database/models/user/test_create_user_personal_org.py
git commit -m "feat(multi-tenant): auto-create personal org + owner membership on user creation"
```

---

## Phase 4: Wire Dependency Through Endpoints

### Task 9: Cross-org isolation test fixtures

**Files:**
- Create: `src/backend/tests/unit/api/multi_tenant_fixtures.py`
- Modify: `src/backend/tests/conftest.py` (re-export the fixtures)

- [ ] **Step 1: Write the fixtures (no test yet — they're consumed by Tasks 10–16)**

`src/backend/tests/unit/api/multi_tenant_fixtures.py`:
```python
import pytest
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


@pytest.fixture
async def two_orgs(async_session):
    org_a = Organization(name="A", slug="org-a")
    org_b = Organization(name="B", slug="org-b")
    async_session.add(org_a); async_session.add(org_b)
    await async_session.commit()
    user_a = User(username="user-a", password="x", is_active=True)
    user_b = User(username="user-b", password="x", is_active=True)
    async_session.add(user_a); async_session.add(user_b)
    await async_session.commit()
    async_session.add(Membership(user_id=user_a.id, organization_id=org_a.id, role=MembershipRole.OWNER))
    async_session.add(Membership(user_id=user_b.id, organization_id=org_b.id, role=MembershipRole.OWNER))
    await async_session.commit()
    return {"user_a": user_a, "org_a": org_a, "user_b": user_b, "org_b": org_b}


@pytest.fixture
async def auth_client_factory(client):
    """Returns a callable: auth_as(user) -> AsyncClient with auth headers set for that user."""
    def _make(user):
        # Reuse repo's existing test login helper. If none, fabricate a JWT via the auth service.
        from langflow.services.deps import get_settings_service
        from langflow.services.auth.utils import create_token_for_user
        token = create_token_for_user(user, get_settings_service().auth_settings)
        client.headers.update({"Authorization": f"Bearer {token}"})
        return client
    return _make
```

(The exact JWT-creation helper may differ — `grep -rn "create_token\|create_user_token" src/backend/base/langflow/services/auth | head` to confirm and substitute.)

- [ ] **Step 2: Re-export from conftest**

In `src/backend/tests/conftest.py`, add: `from .unit.api.multi_tenant_fixtures import *  # noqa: F401,F403`

- [ ] **Step 3: Commit (no tests change yet)**

```bash
git add src/backend/tests/unit/api/multi_tenant_fixtures.py src/backend/tests/conftest.py
git commit -m "test(multi-tenant): add two-org isolation fixtures"
```

---

### Task 10: Enforce org scoping on Flow endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py`
- Test: `src/backend/tests/unit/api/test_flows_org_isolation.py`

- [ ] **Step 1: Write failing isolation tests**

```python
import pytest
from uuid import uuid4
from langflow.services.database.models.flow.model import Flow


@pytest.mark.asyncio
async def test_get_flow_cross_org_returns_404(two_orgs, auth_client_factory, async_session):
    flow_b = Flow(name="b-flow", user_id=two_orgs["user_b"].id,
                  organization_id=two_orgs["org_b"].id, data={})
    async_session.add(flow_b); await async_session.commit()
    client = auth_client_factory(two_orgs["user_a"])
    resp = await client.get(f"/api/v1/flows/{flow_b.id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_flows_returns_only_own_org(two_orgs, auth_client_factory, async_session):
    async_session.add(Flow(name="a", user_id=two_orgs["user_a"].id,
                           organization_id=two_orgs["org_a"].id, data={}))
    async_session.add(Flow(name="b", user_id=two_orgs["user_b"].id,
                           organization_id=two_orgs["org_b"].id, data={}))
    await async_session.commit()
    client = auth_client_factory(two_orgs["user_a"])
    resp = await client.get("/api/v1/flows/")
    assert resp.status_code == 200
    names = [f["name"] for f in resp.json()]
    assert "a" in names and "b" not in names


@pytest.mark.asyncio
async def test_delete_flow_cross_org_returns_404(two_orgs, auth_client_factory, async_session):
    flow_b = Flow(name="x", user_id=two_orgs["user_b"].id,
                  organization_id=two_orgs["org_b"].id, data={})
    async_session.add(flow_b); await async_session.commit()
    client = auth_client_factory(two_orgs["user_a"])
    resp = await client.delete(f"/api/v1/flows/{flow_b.id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run, verify FAIL** (current code doesn't filter by org)

- [ ] **Step 3: Update each route**

In `flows.py`, for every route handler that touches Flow:
1. Add `org: CurrentOrg` to the parameter list (import from `langflow.api.utils.core`).
2. Add `Flow.organization_id == org.id` to every `select(Flow).where(...)` query.
3. On create, set `flow.organization_id = org.id` from the dependency before commit.

Example pattern for `read_flow`:
```python
async def read_flow(
    flow_id: UUID,
    user: CurrentActiveUser,
    org: CurrentOrg,
    session: DbSession,
):
    flow = await session.scalar(
        select(Flow).where(Flow.id == flow_id, Flow.organization_id == org.id)
    )
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow
```

Repeat for `create_flow`, `update_flow`, `delete_flow`, `read_flows` (list), and any flow-by-name lookup.

- [ ] **Step 4: Run, verify PASS**

Run: `uv run pytest src/backend/tests/unit/api/test_flows_org_isolation.py -v`
Then run the existing flow tests: `uv run pytest src/backend/tests/unit/api/test_endpoints.py -k flow -v` and fix any breakage from missing fixtures.

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py \
        src/backend/tests/unit/api/test_flows_org_isolation.py
git commit -m "feat(multi-tenant): scope Flow endpoints by organization"
```

---

### Tasks 11–15: Repeat the Task 10 pattern for each remaining resource

Each task follows the *exact* shape of Task 10:
1. Write failing isolation test (`test_<resource>_org_isolation.py`) covering: cross-org GET → 404, LIST returns only own-org rows, cross-org DELETE → 404.
2. Run, verify FAIL.
3. Add `org: CurrentOrg` to route handlers; add `Model.organization_id == org.id` to every query; set `organization_id` on create.
4. Run, verify PASS.
5. Commit with message `feat(multi-tenant): scope <Resource> endpoints by organization`.

| Task | Route file | Test file | Model |
|------|-----------|-----------|-------|
| 11 | `api/v1/folders.py` and `api/v1/projects.py` | `test_folders_org_isolation.py` | Folder |
| 12 | `api/v1/files.py` and `api/v2/files.py` | `test_files_org_isolation.py` | File |
| 13 | `api/v1/variable.py` | `test_variables_org_isolation.py` | Variable |
| 14 | `api/v1/api_key.py` | `test_api_keys_org_isolation.py` | ApiKey |
| 15 | `api/v1/deployments.py` | `test_deployments_org_isolation.py` | Deployment, DeploymentProviderAccount |

For each task, before writing the test, run `grep -n "select(<Model>)" src/backend/base/langflow/api` to enumerate every query that needs an `organization_id` clause. If any query joins another tenant table, add the FK validator check (Task 3's `CrossOrgFKError`) — but for the slice, the SELECT guardrail will catch missed filters in CI.

---

### Task 16: MCP endpoint isolation

**Files:**
- Modify: `src/backend/base/langflow/api/v1/mcp.py`
- Modify: `src/backend/base/langflow/api/v1/mcp_projects.py`
- Modify: `src/backend/base/langflow/api/v2/mcp.py`
- Test: `src/backend/tests/unit/api/test_mcp_org_isolation.py`

- [ ] **Step 1: Write failing isolation tests**

```python
import pytest
from uuid import uuid4
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder


@pytest.mark.asyncio
async def test_global_mcp_only_exposes_own_org_flows(two_orgs, auth_client_factory, async_session):
    async_session.add(Flow(name="visible", user_id=two_orgs["user_a"].id,
                           organization_id=two_orgs["org_a"].id, data={}, mcp_enabled=True))
    async_session.add(Flow(name="hidden", user_id=two_orgs["user_b"].id,
                           organization_id=two_orgs["org_b"].id, data={}, mcp_enabled=True))
    await async_session.commit()
    client = auth_client_factory(two_orgs["user_a"])
    resp = await client.get("/api/v1/mcp/sse")  # adapt to actual endpoint
    body = resp.text
    assert "visible" in body
    assert "hidden" not in body


@pytest.mark.asyncio
async def test_per_project_mcp_cross_org_returns_404(two_orgs, auth_client_factory, async_session):
    folder_b = Folder(name="proj-b", user_id=two_orgs["user_b"].id,
                      organization_id=two_orgs["org_b"].id)
    async_session.add(folder_b); await async_session.commit()
    client = auth_client_factory(two_orgs["user_a"])
    resp = await client.get(f"/api/v1/mcp/{folder_b.id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Wire org dep into MCP routes**

For `handle_global_*` handlers in `mcp.py`: add `org: CurrentOrg`; pass `org.id` into the Flow lookup that builds the tool list.

For `mcp_projects.py`'s `verify_project_auth`: add an `organization_id` check — if the resolved Folder's `organization_id != org.id`, return 404.

For `api/v2/mcp.py`: same pattern — add `org: CurrentOrg` and filter every Flow/Folder query by `organization_id`.

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/mcp.py \
        src/backend/base/langflow/api/v1/mcp_projects.py \
        src/backend/base/langflow/api/v2/mcp.py \
        src/backend/tests/unit/api/test_mcp_org_isolation.py
git commit -m "feat(multi-tenant): scope MCP global and per-project endpoints by organization"
```

---

## Phase 5: Final Integration

### Task 17: Mechanical cross-org coverage matrix

**Files:**
- Test: `src/backend/tests/unit/api/test_cross_org_matrix.py`

A single parametrized test that asserts `404` for every `(method, path-template)` pair touching a tenant resource cross-org. Adding a new tenant route means adding one row.

- [ ] **Step 1: Write the parametrized test**

```python
import pytest

ENDPOINTS = [
    ("GET",    "/api/v1/flows/{flow_id}",                "flow_id_b"),
    ("DELETE", "/api/v1/flows/{flow_id}",                "flow_id_b"),
    ("GET",    "/api/v1/folders/{folder_id}",            "folder_id_b"),
    ("DELETE", "/api/v1/folders/{folder_id}",            "folder_id_b"),
    ("GET",    "/api/v1/files/{file_id}",                "file_id_b"),
    ("DELETE", "/api/v1/files/{file_id}",                "file_id_b"),
    ("GET",    "/api/v1/variables/{variable_id}",        "variable_id_b"),
    ("DELETE", "/api/v1/variables/{variable_id}",        "variable_id_b"),
    ("DELETE", "/api/v1/api_key/{api_key_id}",           "api_key_id_b"),
    ("GET",    "/api/v1/deployments/{deployment_id}",    "deployment_id_b"),
    ("DELETE", "/api/v1/deployments/{deployment_id}",    "deployment_id_b"),
    ("GET",    "/api/v1/mcp/{folder_id}",                "folder_id_b"),
]


@pytest.mark.parametrize("method,template,id_key", ENDPOINTS)
@pytest.mark.asyncio
async def test_cross_org_returns_404(method, template, id_key,
                                      two_orgs_with_resources, auth_client_factory):
    client = auth_client_factory(two_orgs_with_resources["user_a"])
    path = template.format(**{template.split("{")[1].rstrip("}"): two_orgs_with_resources[id_key]})
    resp = await client.request(method, path)
    assert resp.status_code == 404, f"{method} {path} returned {resp.status_code}"
```

The fixture `two_orgs_with_resources` extends `two_orgs` by also creating one of every tenant resource in `org_b`, returning each id as `<resource>_id_b`.

- [ ] **Step 2: Run, verify PASS** (every row should already pass after Tasks 10–16; failures here mean a route was missed)

Run: `uv run pytest src/backend/tests/unit/api/test_cross_org_matrix.py -v`

- [ ] **Step 3: Commit**

```bash
git add src/backend/tests/unit/api/test_cross_org_matrix.py \
        src/backend/tests/unit/api/multi_tenant_fixtures.py
git commit -m "test(multi-tenant): parametrized cross-org isolation matrix"
```

---

### Task 18: Final smoke — full unit suite + migration round-trip

- [ ] **Step 1: Run full unit suite**

Run: `make unit_tests async=false`
Expected: all green. Fix any factory-construction failures by adding `organization_id=<default_org.id>`.

- [ ] **Step 2: Verify migration round-trip on a fresh DB**

```bash
cd src/backend/base/langflow
rm -f /tmp/langflow_test.db
LANGFLOW_DATABASE_URL=sqlite:////tmp/langflow_test.db uv run alembic upgrade head
LANGFLOW_DATABASE_URL=sqlite:////tmp/langflow_test.db uv run alembic downgrade -1
LANGFLOW_DATABASE_URL=sqlite:////tmp/langflow_test.db uv run alembic upgrade head
```
Expected: each command exits 0 with no errors.

- [ ] **Step 3: Manual smoke — boot the app**

Run: `make backend`
Expected: server starts; `tail -f logs/...` shows no `MissingOrgFilterError` or `MissingOrgIdOnInsertError`.

Hit a few endpoints with `curl` after creating a fresh user — the user should land in their personal org and see only their own resources.

- [ ] **Step 4: Commit any final fixture cleanups**

```bash
git add -u
git commit -m "test(multi-tenant): final fixture and factory cleanups for org-scoped models"
```

---

## Self-Review Notes

- Spec coverage walked: data model (T1–T2, T5), auth/scoping deps (T4), signup hook (T8), query enforcement guards (T3, T7), migration (T6), MCP isolation (T16), cross-org isolation tests (T9–T17), migration round-trip (T6, T18). All sections of the spec have at least one task.
- `default_org` and `two_orgs` fixtures are defined in earlier tasks before later tasks consume them.
- The plan deliberately keeps Phase 4 tasks symmetric (Task 10 is the template; 11–15 reference it explicitly rather than re-listing every step). Engineers reading them out of order will see the cross-reference up top.
- Open question for executor: Task 6 Step 4's SQLite-friendly `id`-prefix trick is fragile on Postgres. If the engineer is on Postgres, they should use the Python-loop alternative shown in the same step.

---

## Execution Status (2026-04-22)

All 18 tasks landed on `platform-multi-tenant` ahead of this plan being executed, via the
`feat/adp-connector` merge (multi-tenant foundation) and the `feat/user-detail-and-roles`
merge (5-tier role model). Verified by running:

```
uv run pytest \
  src/backend/tests/unit/services/database/ \
  src/backend/tests/unit/api/test_org_helpers.py \
  src/backend/tests/unit/api/test_cross_org_matrix.py \
  src/backend/tests/unit/api/test_flows_org_isolation.py \
  src/backend/tests/unit/api/v1/test_memberships.py \
  src/backend/tests/unit/api/v1/test_org_helpers_multi_membership.py \
  src/backend/tests/unit/api/v1/admin/
```
→ **93 passed**.

| Task | Status | Deviation from plan |
|------|--------|---------------------|
| 1 — Organization model | Done | Extended with `runs_max_concurrent`, `runs_priority_tier` columns |
| 2 — Membership model | Done | `MembershipRole` has 5 values (OWNER/ADMIN/MEMBER/OPERATOR/VIEWER), not just OWNER |
| 3 — Scoping module | Done, **design changed** | `before_insert` auto-resolves `organization_id` via flow_id → folder_id → user_id lookup chain and auto-provisions personal orgs; `MissingOrgIdOnInsertError` is defined but rarely raised. `TENANT_SCOPED_TABLES` uses `apikey` (actual table name), not `api_key` |
| 4 — org_helpers dependency | Done at `api/utils/org_helpers.py` (plan said `api/v1/`) | Relaxed single-membership assertion to "prefer personal, else earliest-created" to support the role/admin work |
| 5 — `organization_id` on tenant tables | Done on 13 tables (12 planned + `flow_run`) | |
| 6 — Alembic migration | `6d926936ec2d_multi_tenant_foundation.py` + follow-up `26b3d04efba1_organization_runs_limits.py` | |
| 7 — Install guards at startup | `services/database/service.py` wires `install_scoping_guards` | |
| 8 — Personal org on signup | Via scoping's `after_insert` User hook + explicit `test_personal_org.py` coverage | |
| 9 — Two-org fixtures | Used throughout isolation test suites | |
| 10–15 — Endpoint scoping | `flows.py`, `variable.py`, `api_key.py`, `projects.py`, `files.py` (v2) all call `get_current_organization` | |
| 16 — MCP isolation | `api/v1/mcp.py`, `mcp_projects.py`, `api/v2/mcp.py` all scope by org | |
| 17 — Cross-org matrix | `test_cross_org_matrix.py` | |
| 18 — Final smoke | Targeted suite green | |

**Extras landed beyond plan scope:** `api/v1/admin/orgs.py` admin endpoint; membership/role-change test coverage (`test_memberships.py`, `test_role_changes.py`, `test_org_helpers_multi_membership.py`).

### Known gap (deferred)

**Cross-org FK validator is not wired.** `CrossOrgFKError` is defined in `scoping.py` but no `before_insert` / `before_update` listener uses it. The auto-resolve logic covers the case where `organization_id` is missing (it derives it from `folder_id`/`flow_id`), but if a caller supplies BOTH `organization_id=X` and `folder_id=Y` where `folder.organization_id == Z`, the DB layer won't catch the inconsistency. Mitigation today: every route's folder/flow lookup filters by current org, so cross-org FK stitching requires bypassing the API layer. Worth adding the defense-in-depth validator as a follow-up.
