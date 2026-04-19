# Template Management — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the save-as-template + field-blanking authoring path. Existing starter projects migrate into a new `Template` entity so the product has one template catalog; superuser clicks Share → "Save as Template" on any flow, audits per-field blanking in a save modal, and publishes to the platform catalog.

**Architecture:** New `Template` SQLModel entity replaces the starter-folder convention. One alembic revision performs the destructive migration (creates Template table, copies starter-project Flow rows into Template rows, re-points `TemplateMetadata.flow_id → template_id` and `Flow.based_on_template_flow_id → based_on_template_id`, deletes the Starter Projects folder + its Flow rows). Startup-code switches from folder seeding to Template-table upserter. Frontend gets a new save-modal + retargeted catalog gallery + retargeted admin metadata page.

**Tech Stack:** Python + SQLModel + Alembic + FastAPI on backend; React + TypeScript + Tailwind + Jest on frontend. Follows Plan 5's TDD pattern (failing test → implementation → stage).

---

## Scope notes

**Spec:** `docs/superpowers/specs/2026-04-18-template-management-phase-1-design.md` (committed at `b7cc090108`).

**In scope** (Phase 1):
- New `Template` SQLModel entity (scope + org_id columns present but unused — reserved for Phase 2).
- 5 CRUD endpoints at `/api/v1/templates/*` + soft-delete.
- Save-as-Template modal with field-review panel (per-row blank/keep, password fields auto-blanked with lock icon, Blank-all/Keep-all buttons).
- Catalog gallery retargets to new endpoint.
- Admin metadata endpoints retarget from `{flow_id}` to `{template_id}`.
- Alembic destructive migration of existing starter-project data.
- Frontend type/hook rename: `based_on_template_flow_id → based_on_template_id`.

**Out of scope** (deferred to Phase 2/3):
- Versioning, diff, propagation, cherry-pick, LLM-diff, org-scoped templates, in-place content editing.
- Per-user template-authoring permission flag (superuser-only in Phase 1).

**Commit discipline:** all tasks are stage-only (`git add`, not `git commit`). The human batches commits at plan end. Do NOT run `git commit`.

---

## File Structure

### New backend files

- `src/backend/base/langflow/services/database/models/template/__init__.py` — re-exports
- `src/backend/base/langflow/services/database/models/template/model.py` — SQLModel + Pydantic read/write schemas
- `src/backend/base/langflow/api/v1/templates.py` — user-facing CRUD router (mounted at `/api/v1/templates`)
- `src/backend/base/langflow/alembic/versions/NNNNNNN_template_management_phase_1.py` — single alembic revision (data + schema migration)

### New frontend files

- `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts`
- `src/frontend/src/controllers/API/queries/templates/use-get-template.ts`
- `src/frontend/src/controllers/API/queries/templates/use-create-template.ts`
- `src/frontend/src/controllers/API/queries/templates/use-update-template.ts`
- `src/frontend/src/controllers/API/queries/templates/use-delete-template.ts`
- `src/frontend/src/types/template/index.ts`
- `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/index.tsx` (or a similar location — placed near the Share menu caller)
- `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/field-review-panel.tsx`
- `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/overwrite-confirm.tsx`
- `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`
- `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/field-review-panel.test.tsx`

### Modified backend files

- `src/backend/base/langflow/services/database/models/template_metadata/model.py` — add `template_id` FK
- `src/backend/base/langflow/services/database/models/flow/model.py` — add `based_on_template_id` FK, drop `based_on_template_flow_id` (alembic handles the column; model reflects the new shape)
- `src/backend/base/langflow/api/v1/admin/metadata.py` — retarget template endpoints from `{flow_id}` → `{template_id}`; join on `Template` instead of Folder
- `src/backend/base/langflow/api/v1/admin/__init__.py` — mount (no change expected if admin uses the existing metadata router; verify at Task time)
- `src/backend/base/langflow/api/v1/__init__.py` or `api/router.py` — mount new templates router
- `src/backend/base/langflow/api/v1/starter_projects.py` — retarget to read from `template` table (deprecation compat)
- `src/backend/base/langflow/initial_setup/setup.py` — replace starter-folder seeding with Template upserter; remove `get_or_create_starter_folder`
- `src/backend/base/langflow/api/v1/flows.py` (lines 28, 425, 1027) — retarget starter-folder queries to `template` table
- `src/backend/base/langflow/api/v1/projects.py` (lines 35, 235) — drop `STARTER_FOLDER_NAME` filter (no longer needed)
- `src/backend/base/langflow/services/database/service.py` (lines 30, 319) — drop `STARTER_FOLDER_NAME` exclusion
- `src/backend/base/langflow/services/database/models/flow/starter.py` — retire: remove `is_flow_a_starter_project*` and `list_starter_project_flows`; callers migrate to Template lookups
- `src/backend/base/langflow/services/assistant/tools/template_apply.py` — operate on Template by id; drop `is_flow_a_starter_project_async` check
- `src/backend/base/langflow/services/assistant/flow_template_context.py` — accept `based_on_template_id` instead of `based_on_template_flow_id`; fetch TemplateMetadata by `template_id`
- `src/backend/base/langflow/services/assistant/service.py` (lines 129, 137, 236, 370) — rename param + attr: `based_on_template_flow_id` → `based_on_template_id`
- `src/backend/base/langflow/api/v1/assistant.py` (lines 351, 568) — rename on service init call site

### Modified frontend files

- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx` — retarget to `Template` resource
- `src/frontend/src/modals/templatesModal/index.tsx` — retarget to `useListTemplates` (from `useGetBasicExamplesQuery`)
- `src/frontend/src/modals/templatesModal/components/GetStartedComponent/index.tsx` — adapt to new payload shape if needed
- `src/frontend/src/controllers/API/queries/flows/use-get-basic-examples.ts` — deprecate (keep for backward compat; point at `/api/v1/templates` or leave pointing at `/api/v1/starter-projects/`)
- `src/frontend/src/types/flow/index.ts` — rename `based_on_template_flow_id` → `based_on_template_id`
- `src/frontend/src/hooks/flows/use-add-flow.ts` — rename field
- `src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx` — add "Save as Template" item to Share menu for superusers
- Any other callers of `based_on_template_flow_id` surfaced during the rename task

### Test files to create or update

- Backend: `tests/unit/services/database/test_template_model.py`, `tests/unit/api/v1/test_templates_endpoints.py`, `tests/unit/api/v1/admin/test_metadata_retargeting.py`, `tests/unit/initial_setup/test_template_seeding.py`, `tests/unit/services/assistant/test_template_apply_retargeted.py`
- Frontend: `SaveAsTemplateModal.test.tsx`, `field-review-panel.test.tsx`, `flows-tab.test.tsx` updates, `templatesModal.test.tsx` (if present)

---

## Task 1: Backend — `Template` SQLModel + Pydantic schemas

**Files:**
- Create: `src/backend/base/langflow/services/database/models/template/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/template/model.py`
- Create: `src/backend/tests/unit/services/database/test_template_model.py`

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/services/database/test_template_model.py`:

```python
"""Unit tests for the Template SQLModel."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from langflow.services.database.models.template.model import Template


def test_template_name_is_required(client_fixture):
    # Template with no name must fail. We don't need a DB here — SQLModel
    # validation catches the missing field at construction.
    with pytest.raises(Exception):
        Template(nodes=[], edges=[], created_by=uuid.uuid4(), updated_by=uuid.uuid4())  # type: ignore[call-arg]


def test_template_scope_defaults_to_platform():
    t = Template(
        name="test",
        nodes=[],
        edges=[],
        created_by=uuid.uuid4(),
        updated_by=uuid.uuid4(),
    )
    assert t.scope == "platform"
    assert t.org_id is None


def test_template_scope_platform_requires_null_org_id():
    # Constraint is enforced at DB level via a CHECK constraint; model-level
    # construction does NOT enforce it. We exercise that from an alembic
    # migration test — see test_template_migration.py. This test just
    # documents the expected defaults.
    t = Template(
        name="test",
        scope="platform",
        org_id=None,
        nodes=[],
        edges=[],
        created_by=uuid.uuid4(),
        updated_by=uuid.uuid4(),
    )
    assert t.scope == "platform"
    assert t.org_id is None
```

Note: the `client_fixture` parameter is a convention in this repo's test suite for spinning up a test client with a clean DB. Look at any existing `tests/unit/services/database/test_*.py` for the right fixture name — if it's `db_fixture` or similar, use that. If the test in Step 1 doesn't need a DB (it's pure model construction), drop the fixture param entirely.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/services/database/test_template_model.py -v`
Expected: ImportError — `langflow.services.database.models.template` not found.

- [ ] **Step 3: Create the directory structure**

Create `src/backend/base/langflow/services/database/models/template/__init__.py`:

```python
from langflow.services.database.models.template.model import (
    Template,
    TemplateRead,
    TemplateReadDetail,
    TemplateCreate,
    TemplateUpdate,
)

__all__ = [
    "Template",
    "TemplateRead",
    "TemplateReadDetail",
    "TemplateCreate",
    "TemplateUpdate",
]
```

- [ ] **Step 4: Create the Template model**

Create `src/backend/base/langflow/services/database/models/template/model.py`:

```python
"""Template SQLModel + Pydantic schemas for Phase 1 (save-as-template + blanking).

Phase 1 notes:
- scope is always 'platform'; org_id always NULL. Columns reserved for Phase 2.
- No versioning: every Template row represents the current content. Re-save
  with same name overwrites in place (UPSERT by name at the service layer).
- soft-delete via `deleted_at` nullable column.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import JSON, CheckConstraint, Column, ForeignKey, String, Text, Uuid
from sqlmodel import Field, SQLModel


class Template(SQLModel, table=True):
    """Authored template (platform-scoped in Phase 1)."""

    __tablename__ = "template"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'platform' AND org_id IS NULL) OR "
            "(scope = 'org' AND org_id IS NOT NULL)",
            name="ck_template_scope_org_coherence",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
    )
    description: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )
    icon: str | None = Field(default=None, max_length=64)
    gradient: str | None = Field(default=None, max_length=32)

    scope: str = Field(
        default="platform",
        sa_column=Column(String(16), nullable=False, default="platform"),
        description="Phase 1 is always 'platform'. 'org' reserved for Phase 2.",
    )
    org_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(), ForeignKey("org.id", ondelete="CASCADE"), nullable=True,
        ),
        description="Always NULL in Phase 1. Reserved for Phase 2 org-scoped templates.",
    )

    nodes: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    edges: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))

    created_by: UUID = Field(
        sa_column=Column(
            Uuid(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(nullable=False, default=lambda: datetime.now(timezone.utc)),
    )
    updated_by: UUID = Field(
        sa_column=Column(
            Uuid(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        ),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(nullable=True, default=None),
    )


# ---------------------------- Pydantic schemas ----------------------------


class TemplateRead(BaseModel):
    """Slim catalog listing shape (no nodes/edges)."""

    id: UUID
    name: str
    description: str | None
    icon: str | None
    gradient: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateReadDetail(TemplateRead):
    """Full shape for template detail / clone payload."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class BlankedField(BaseModel):
    node_id: str
    field_name: str


class TemplateCreate(BaseModel):
    source_flow_id: UUID
    name: str = PydanticField(..., max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    blanked_fields: list[BlankedField] = PydanticField(default_factory=list)


class TemplateUpdate(BaseModel):
    """Same shape as Create minus source_flow_id (still re-sourced from a flow)."""

    source_flow_id: UUID
    name: str = PydanticField(..., max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    blanked_fields: list[BlankedField] = PydanticField(default_factory=list)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/services/database/test_template_model.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Stage (do not commit)**

```bash
git add src/backend/base/langflow/services/database/models/template/__init__.py \
        src/backend/base/langflow/services/database/models/template/model.py \
        src/backend/tests/unit/services/database/test_template_model.py
```

---

## Task 2: Backend — Alembic revision (schema + data migration)

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<AUTO>_template_management_phase_1.py`
- Create: `src/backend/tests/unit/alembic/test_template_migration.py`

The alembic revision needs a unique revision ID. Generate with `alembic revision --autogenerate -m 'template management phase 1'` if the convention is autogenerated, OR hand-write the file using a hex hash matching the project's revision filename convention. Inspect an existing recent revision (e.g., `src/backend/base/langflow/alembic/versions/6ec028483162_add_based_on_template_flow_id_to_flow.py`) to confirm style.

- [ ] **Step 1: Generate the revision skeleton**

Run (from repo root): `cd src/backend && uv run alembic revision -m "template management phase 1"`. This creates a stub in `src/backend/base/langflow/alembic/versions/` with a `<hex_id>_template_management_phase_1.py` filename. Note the filename for subsequent steps.

If autogenerate isn't available or fails, hand-write the file with the existing convention. Set `down_revision` to the ID of the most recent alembic revision (inspect `alembic/versions/` for the latest file — `git log -1 --name-only alembic/versions/` may help identify the most recently added revision).

- [ ] **Step 2: Write the failing migration test**

Create `src/backend/tests/unit/alembic/test_template_migration.py`:

```python
"""Alembic migration test — Plan 7 Phase 1.

Verifies the template-management revision:
- Creates the `template` table with expected columns + check constraint.
- Adds `template_id` column to `template_metadata`.
- Adds `based_on_template_id` column to `flow`.
- Copies existing starter-project Flow rows into Template rows.
- Re-points `template_metadata.flow_id` → `template_id` (and drops flow_id).
- Re-points `flow.based_on_template_flow_id` → `based_on_template_id` (and drops old column).
- Deletes the Starter Projects folder + its flow rows.
"""

import uuid
from sqlalchemy import text


def _get_latest_revision_id() -> str:
    """Locate the Plan 7 revision id by scanning alembic/versions/."""
    import pathlib
    versions_dir = pathlib.Path(__file__).resolve().parents[4] / "base" / "langflow" / "alembic" / "versions"
    for f in sorted(versions_dir.glob("*_template_management_phase_1.py"), reverse=True):
        return f.name.split("_", 1)[0]
    raise RuntimeError("Could not find Plan 7 revision file")


def test_migration_creates_template_table(alembic_engine_fixture):
    """After running the revision, the `template` table exists with expected columns."""
    engine = alembic_engine_fixture  # see conftest.py — fixture applies all revisions
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info('template')")).fetchall()}
    expected = {
        "id", "name", "description", "icon", "gradient",
        "scope", "org_id", "nodes", "edges",
        "created_by", "created_at", "updated_by", "updated_at", "deleted_at",
    }
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_migration_adds_template_id_to_template_metadata(alembic_engine_fixture):
    engine = alembic_engine_fixture
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info('template_metadata')")).fetchall()}
    assert "template_id" in cols
    assert "flow_id" not in cols  # dropped in same revision


def test_migration_adds_based_on_template_id_to_flow(alembic_engine_fixture):
    engine = alembic_engine_fixture
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info('flow')")).fetchall()}
    assert "based_on_template_id" in cols
    assert "based_on_template_flow_id" not in cols


def test_migration_copies_starter_flows_to_templates(seeded_alembic_engine_fixture):
    """Pre-seeds 2 starter Flow rows in the Starter Projects folder, then runs migration.

    seeded_alembic_engine_fixture is defined in conftest.py:
      1. Create DB with all revisions EXCEPT the Plan 7 one.
      2. Insert Folder('Starter Projects') + 2 Flow rows in it.
      3. Apply Plan 7 revision.
      4. Return engine.
    """
    engine = seeded_alembic_engine_fixture
    with engine.connect() as conn:
        template_count = conn.execute(text("SELECT count(*) FROM template")).scalar()
        assert template_count == 2, f"Expected 2 migrated templates, got {template_count}"

        # Starter folder + starter flows should be gone.
        folder_count = conn.execute(text("SELECT count(*) FROM folder WHERE name='Starter Projects'")).scalar()
        assert folder_count == 0
```

Note: the fixtures `alembic_engine_fixture` and `seeded_alembic_engine_fixture` don't exist yet in the repo. Either:

(a) Add them to `tests/unit/alembic/conftest.py` (create if missing) following any existing alembic test patterns, OR
(b) If the project has no existing alembic migration tests, simplify by running migrations against an in-memory SQLite via `alembic upgrade head` programmatically (see Alembic's `command.upgrade` API).

For brevity here, assume (a). If conftest work is too large, bundle it into this task.

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/alembic/test_template_migration.py -v`
Expected: FAIL — either the revision file doesn't exist yet, or the fixtures aren't set up.

- [ ] **Step 4: Implement the migration revision**

Edit the generated revision file. Replace the stub contents with:

```python
"""template management phase 1

Revision ID: <AUTO>
Revises: <previous_revision_id>
Create Date: 2026-04-18 ...

"""
from collections.abc import Sequence
from typing import Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "<AUTO>"  # alembic-generated hex
down_revision: Union[str, None] = "<previous_revision>"  # confirmed at Step 1
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create template table
    op.create_table(
        "template",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("gradient", sa.String(length=32), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="platform"),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("org.id", ondelete="CASCADE"), nullable=True),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name", name="uq_template_name"),
        sa.CheckConstraint(
            "(scope = 'platform' AND org_id IS NULL) OR (scope = 'org' AND org_id IS NOT NULL)",
            name="ck_template_scope_org_coherence",
        ),
    )
    op.create_index("ix_template_name", "template", ["name"])

    # 2. Add template_id column to template_metadata
    with op.batch_alter_table("template_metadata") as batch_op:
        batch_op.add_column(
            sa.Column("template_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_template_metadata_template_id",
            "template",
            ["template_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_template_metadata_template_id", ["template_id"],
        )

    # 3. Add based_on_template_id column to flow
    with op.batch_alter_table("flow") as batch_op:
        batch_op.add_column(
            sa.Column("based_on_template_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_flow_based_on_template_id",
            "template",
            ["based_on_template_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 4. Data migration: copy starter flows into template rows
    conn = op.get_bind()
    starter_flows = conn.execute(
        text(
            "SELECT f.id, f.name, f.description, f.icon, f.gradient, f.data, "
            "       f.user_id, f.updated_at "
            "FROM flow f JOIN folder fo ON f.folder_id = fo.id "
            "WHERE fo.name = 'Starter Projects'"
        )
    ).fetchall()

    # Find a fallback user (first superuser) for templates whose creator is NULL.
    fallback_user_id = conn.execute(
        text("SELECT id FROM \"user\" WHERE is_superuser = true ORDER BY create_at LIMIT 1")
    ).scalar()

    flow_to_template: dict[str, str] = {}
    for flow_row in starter_flows:
        flow_id_str = str(flow_row.id)
        new_template_id = str(uuid4())
        data = flow_row.data or {"nodes": [], "edges": []}
        nodes = data.get("nodes") or []
        edges = data.get("edges") or []
        creator = flow_row.user_id or fallback_user_id
        if creator is None:
            # No fallback user exists; skip this flow rather than violate NOT NULL.
            continue

        conn.execute(
            text(
                "INSERT INTO template (id, name, description, icon, gradient, "
                "scope, org_id, nodes, edges, created_by, created_at, updated_by, updated_at) "
                "VALUES (:id, :name, :desc, :icon, :grad, 'platform', NULL, :nodes, :edges, "
                ":creator, :created_at, :creator, :updated_at)"
            ),
            {
                "id": new_template_id,
                "name": flow_row.name,
                "desc": flow_row.description,
                "icon": flow_row.icon,
                "grad": flow_row.gradient,
                "nodes": nodes,
                "edges": edges,
                "creator": str(creator),
                "created_at": flow_row.updated_at,
                "updated_at": flow_row.updated_at,
            },
        )
        flow_to_template[flow_id_str] = new_template_id

    # 5. Re-point template_metadata.flow_id → template_id
    for old_flow_id, new_template_id in flow_to_template.items():
        conn.execute(
            text(
                "UPDATE template_metadata SET template_id = :tid WHERE flow_id = :fid"
            ),
            {"tid": new_template_id, "fid": old_flow_id},
        )

    # 6. Re-point flow.based_on_template_flow_id → based_on_template_id
    for old_flow_id, new_template_id in flow_to_template.items():
        conn.execute(
            text(
                "UPDATE flow SET based_on_template_id = :tid "
                "WHERE based_on_template_flow_id = :fid"
            ),
            {"tid": new_template_id, "fid": old_flow_id},
        )

    # 7. Delete starter Flow rows and the Starter Projects folder
    conn.execute(
        text(
            "DELETE FROM flow WHERE folder_id IN "
            "(SELECT id FROM folder WHERE name = 'Starter Projects')"
        )
    )
    conn.execute(text("DELETE FROM folder WHERE name = 'Starter Projects'"))

    # 8. Drop deprecated columns
    with op.batch_alter_table("template_metadata") as batch_op:
        batch_op.drop_column("flow_id")
    with op.batch_alter_table("flow") as batch_op:
        batch_op.drop_column("based_on_template_flow_id")


def downgrade() -> None:
    """One-way migration. Downgrade re-creates empty columns but does not restore
    deleted starter Flow rows. Per spec: 'no rollback needed — if a reversal
    is ever needed, re-seed from Python graph builders from scratch.'"""
    with op.batch_alter_table("template_metadata") as batch_op:
        batch_op.add_column(sa.Column("flow_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("flow") as batch_op:
        batch_op.add_column(sa.Column("based_on_template_flow_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("flow") as batch_op:
        batch_op.drop_constraint("fk_flow_based_on_template_id", type_="foreignkey")
        batch_op.drop_column("based_on_template_id")
    with op.batch_alter_table("template_metadata") as batch_op:
        batch_op.drop_constraint("uq_template_metadata_template_id", type_="unique")
        batch_op.drop_constraint("fk_template_metadata_template_id", type_="foreignkey")
        batch_op.drop_column("template_id")
    op.drop_index("ix_template_name", "template")
    op.drop_table("template")
```

Replace `<AUTO>` and `<previous_revision>` with the actual values from your generated stub. Inspect the generated file first and only change the body.

- [ ] **Step 5: Run the migration test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/alembic/test_template_migration.py -v`
Expected: 4 PASS.

Also run a full alembic upgrade against a fresh SQLite DB to confirm no regression:

```bash
cd src/backend
LANGFLOW_DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run alembic upgrade head
```

Expected: completes with no errors.

- [ ] **Step 6: Update Flow SQLModel to match the schema**

Edit `src/backend/base/langflow/services/database/models/flow/model.py`. Find the `based_on_template_flow_id` field (line ~52) and replace with:

```python
based_on_template_id: UUID | None = Field(
    default=None,
    sa_column=Column(
        Uuid(),
        ForeignKey("template.id", ondelete="SET NULL"),
        nullable=True,
    ),
    description=(
        "For flows cloned from a template via ADP Assist: the Template's id, "
        "used to resolve TemplateMetadata for conversation context."
    ),
)
```

- [ ] **Step 7: Update TemplateMetadata SQLModel**

Edit `src/backend/base/langflow/services/database/models/template_metadata/model.py`. Replace the `flow_id` field with:

```python
template_id: UUID = Field(
    sa_column=Column(
        Uuid(),
        ForeignKey("template.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    ),
)
```

- [ ] **Step 8: Stage**

```bash
git add src/backend/base/langflow/alembic/versions/*_template_management_phase_1.py \
        src/backend/base/langflow/services/database/models/flow/model.py \
        src/backend/base/langflow/services/database/models/template_metadata/model.py \
        src/backend/tests/unit/alembic/test_template_migration.py
```

---

## Task 3: Backend — Template CRUD router

**Files:**
- Create: `src/backend/base/langflow/api/v1/templates.py`
- Create: `src/backend/tests/unit/api/v1/test_templates_endpoints.py`
- Modify: `src/backend/base/langflow/api/router.py` (or `api/v1/__init__.py`) to mount the new router

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_templates_endpoints.py`:

```python
"""Endpoint tests for /api/v1/templates CRUD."""

import uuid
import pytest


@pytest.mark.asyncio
async def test_post_template_as_superuser_succeeds(client, superuser_headers, sample_flow):
    resp = await client.post(
        "/api/v1/templates",
        json={
            "source_flow_id": str(sample_flow.id),
            "name": "My Template",
            "description": "A test template",
            "blanked_fields": [],
        },
        headers=superuser_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "My Template"
    assert "nodes" in body
    assert "edges" in body


@pytest.mark.asyncio
async def test_post_template_as_regular_user_forbidden(client, user_headers, sample_flow):
    resp = await client.post(
        "/api/v1/templates",
        json={"source_flow_id": str(sample_flow.id), "name": "x"},
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_template_duplicate_name_returns_409(client, superuser_headers, sample_flow):
    body = {"source_flow_id": str(sample_flow.id), "name": "Dup"}
    resp1 = await client.post("/api/v1/templates", json=body, headers=superuser_headers)
    assert resp1.status_code == 201
    resp2 = await client.post("/api/v1/templates", json=body, headers=superuser_headers)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_post_template_blanks_password_fields_unconditionally(
    client, superuser_headers, flow_with_secret_field
):
    """A SecretStrInput field (password=True) must be blanked regardless of blanked_fields[]."""
    resp = await client.post(
        "/api/v1/templates",
        json={
            "source_flow_id": str(flow_with_secret_field.id),
            "name": "secret-free",
            "blanked_fields": [],
        },
        headers=superuser_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    # Find the node whose input was marked password=True; its 'value' must be empty.
    for node in body["nodes"]:
        for field_name, field_cfg in (node.get("data", {}).get("node", {}).get("template", {})).items():
            if field_cfg.get("password") is True:
                assert field_cfg.get("value") in ("", None)


@pytest.mark.asyncio
async def test_put_template_overwrites_content(client, superuser_headers, sample_flow, sample_template):
    resp = await client.put(
        f"/api/v1/templates/{sample_template.id}",
        json={
            "source_flow_id": str(sample_flow.id),
            "name": sample_template.name,
            "description": "new description",
            "blanked_fields": [],
        },
        headers=superuser_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "new description"


@pytest.mark.asyncio
async def test_delete_template_soft_deletes(client, superuser_headers, sample_template):
    resp = await client.delete(
        f"/api/v1/templates/{sample_template.id}",
        headers=superuser_headers,
    )
    assert resp.status_code == 204

    # GET detail returns 404
    get_resp = await client.get(
        f"/api/v1/templates/{sample_template.id}",
        headers=superuser_headers,
    )
    assert get_resp.status_code == 404

    # GET list filters it out
    list_resp = await client.get("/api/v1/templates", headers=superuser_headers)
    ids = [t["id"] for t in list_resp.json()]
    assert str(sample_template.id) not in ids


@pytest.mark.asyncio
async def test_get_list_returns_slim_payload(client, superuser_headers, sample_template):
    resp = await client.get("/api/v1/templates", headers=superuser_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    first = items[0]
    assert "nodes" not in first  # slim list excludes bulk fields
    assert "edges" not in first


@pytest.mark.asyncio
async def test_get_detail_returns_full_payload(client, superuser_headers, sample_template):
    resp = await client.get(
        f"/api/v1/templates/{sample_template.id}",
        headers=superuser_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body
    assert "edges" in body
```

Note: `sample_flow`, `sample_template`, `flow_with_secret_field`, `client`, `superuser_headers`, `user_headers` are fixtures. Inspect existing test files (e.g., `src/backend/tests/unit/api/v1/test_assistant_stream_partial_persistence.py`) for the conftest patterns. `sample_template` can be added to the file's own conftest.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_templates_endpoints.py -v`
Expected: FAIL — `/api/v1/templates` route doesn't exist.

- [ ] **Step 3: Create the templates router**

Create `src/backend/base/langflow/api/v1/templates.py`:

```python
"""User-facing CRUD for Template rows."""

from __future__ import annotations

from datetime import datetime, timezone
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
from langflow.services.database.models.user.model import User

router = APIRouter(tags=["Templates"], prefix="/templates")


def _is_password_input(field_cfg: dict) -> bool:
    """True if a node's input definition marks this field as a password/secret."""
    return bool(field_cfg.get("password"))


def _apply_blanking(
    source_nodes: list[dict],
    blanked_fields: list[dict],
) -> list[dict]:
    """Return a copy of source_nodes with (a) all password=True fields blanked, and
    (b) fields listed in blanked_fields cleared. Non-destructive on the source."""
    blank_set = {(bf["node_id"], bf["field_name"]) for bf in blanked_fields}
    out = []
    for node in source_nodes:
        node_copy = {**node}
        node_id = node_copy.get("id")
        template_fields = (node_copy.get("data", {}).get("node", {}).get("template", {}))
        new_template = {}
        for fname, fcfg in template_fields.items():
            fcfg_copy = {**fcfg}
            if _is_password_input(fcfg_copy) or (node_id, fname) in blank_set:
                fcfg_copy["value"] = ""
            new_template[fname] = fcfg_copy
        # Write back
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


@router.get("", response_model=list[TemplateRead])
async def list_templates(
    *, session: DbSession, _user: User = Depends(get_current_active_user)
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
    # Duplicate-name check (non-deleted only)
    existing = (
        await session.exec(
            select(Template)
            .where(Template.name == body.name)
            .where(Template.deleted_at.is_(None))
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Template name already exists")

    flow = (
        await session.exec(select(Flow).where(Flow.id == body.source_flow_id))
    ).one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Source flow not found")

    source_nodes = (flow.data or {}).get("nodes") or []
    edges = (flow.data or {}).get("edges") or []
    blanked_nodes = _apply_blanking(
        source_nodes,
        [bf.model_dump() for bf in body.blanked_fields],
    )

    now = datetime.now(timezone.utc)
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
        created_at=now,
        updated_by=current_user.id,
        updated_at=now,
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

    # Name-change collision check
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

    flow = (
        await session.exec(select(Flow).where(Flow.id == body.source_flow_id))
    ).one_or_none()
    if flow is None:
        raise HTTPException(status_code=404, detail="Source flow not found")

    source_nodes = (flow.data or {}).get("nodes") or []
    edges = (flow.data or {}).get("edges") or []
    blanked_nodes = _apply_blanking(
        source_nodes,
        [bf.model_dump() for bf in body.blanked_fields],
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
```

- [ ] **Step 4: Mount the router**

Edit `src/backend/base/langflow/api/router.py` (or the equivalent router file — confirm by grepping for `include_router` on the other v1 routers). Add:

```python
from langflow.api.v1.templates import router as templates_router
# ...
router_v1.include_router(templates_router)
```

If the project has a central `api/v1/__init__.py` that aggregates routers, add it there instead. Follow the pattern of existing routers like `assistant_router` or `flows_router`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_templates_endpoints.py -v`
Expected: 8 PASS.

- [ ] **Step 6: Stage**

```bash
git add src/backend/base/langflow/api/v1/templates.py \
        src/backend/base/langflow/api/router.py \
        src/backend/tests/unit/api/v1/test_templates_endpoints.py
```

(Adjust the router file path if it's not at `api/router.py` in your confirm step.)

---

## Task 4: Backend — Retarget admin metadata endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/metadata.py`
- Create/Modify: `src/backend/tests/unit/api/v1/admin/test_metadata_retargeting.py`

The existing `/metadata/templates/{flow_id}` endpoints operate on Flow rows in the "Starter Projects" folder and TemplateMetadata keyed by `flow_id`. After migration both are gone. Retarget to operate on Template rows keyed by `template_id`.

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/admin/test_metadata_retargeting.py`:

```python
"""Admin metadata endpoints retargeted from Flow/Folder → Template."""

import pytest


@pytest.mark.asyncio
async def test_list_templates_joins_template_table(client, superuser_headers, sample_template):
    resp = await client.get("/api/v1/admin/metadata/templates", headers=superuser_headers)
    assert resp.status_code == 200
    items = resp.json()
    ids = [t["template_id"] for t in items]
    assert str(sample_template.id) in ids


@pytest.mark.asyncio
async def test_get_template_metadata_by_template_id(
    client, superuser_headers, sample_template
):
    resp = await client.get(
        f"/api/v1/admin/metadata/templates/{sample_template.id}",
        headers=superuser_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["template_id"] == str(sample_template.id)


@pytest.mark.asyncio
async def test_put_template_metadata_upserts_by_template_id(
    client, superuser_headers, sample_template
):
    resp = await client.put(
        f"/api/v1/admin/metadata/templates/{sample_template.id}",
        json={"agent_usage_notes": "test note", "agent_summary": "test summary"},
        headers=superuser_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_usage_notes"] == "test note"
    assert body["agent_summary"] == "test summary"


@pytest.mark.asyncio
async def test_old_flow_id_path_returns_404(client, superuser_headers):
    """Old /templates/{flow_id} routes no longer exist or return 404."""
    import uuid
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/admin/metadata/templates/{fake_id}",
        headers=superuser_headers,
    )
    # With proper retargeting the route resolves but the id isn't a real Template.
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_metadata_retargeting.py -v`
Expected: 4 FAIL (existing endpoints still key on flow_id).

- [ ] **Step 3: Retarget the admin metadata endpoints**

Edit `src/backend/base/langflow/api/v1/admin/metadata.py`. Find all four template endpoints (list, get, upsert, delete) and retarget:

- Replace `flow_id: UUID` path param with `template_id: UUID`.
- Replace `select(Flow).where(Flow.id == flow_id)` + starter-folder join with `select(Template).where(Template.id == template_id).where(Template.deleted_at.is_(None))`.
- Replace `TemplateMetadata.flow_id == flow_id` with `TemplateMetadata.template_id == template_id`.
- Remove the `is_flow_a_starter_project_async` check (no longer meaningful).

Update the response schema if needed — the existing `TemplateMetadataRead` may need a `template_id` field alongside/instead of `flow_id`. Confirm with a quick read of the current response model.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/admin/test_metadata_retargeting.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/backend/base/langflow/api/v1/admin/metadata.py \
        src/backend/tests/unit/api/v1/admin/test_metadata_retargeting.py
```

---

## Task 5: Backend — Retarget startup seeding

**Files:**
- Modify: `src/backend/base/langflow/initial_setup/setup.py`
- Create: `src/backend/tests/unit/initial_setup/test_template_seeding.py`

Replaces the starter-folder + starter-Flow seeding loop with a Template-table upserter. Idempotent: re-running doesn't duplicate.

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/initial_setup/test_template_seeding.py`:

```python
"""Startup seeds Template rows from Python starter-project graph builders."""

import pytest
from sqlmodel import select
from langflow.initial_setup.setup import create_or_update_starter_templates
from langflow.services.database.models.template.model import Template


@pytest.mark.asyncio
async def test_seeding_creates_template_rows(async_session):
    before = (await async_session.exec(select(Template))).all()
    await create_or_update_starter_templates()
    after = (await async_session.exec(select(Template))).all()
    assert len(after) > len(before)


@pytest.mark.asyncio
async def test_seeding_is_idempotent(async_session):
    await create_or_update_starter_templates()
    count1 = (await async_session.exec(select(Template))).all()
    await create_or_update_starter_templates()
    count2 = (await async_session.exec(select(Template))).all()
    assert len(count1) == len(count2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/initial_setup/test_template_seeding.py -v`
Expected: FAIL — `create_or_update_starter_templates` doesn't exist.

- [ ] **Step 3: Replace the seeding function**

Edit `src/backend/base/langflow/initial_setup/setup.py`. Find `create_or_update_starter_projects` (around line 1105). Rename to `create_or_update_starter_templates` and rewrite:

```python
async def create_or_update_starter_templates(all_types_dict: dict | None = None) -> None:
    """Upsert starter-project graph builders into Template rows.

    Replaces the old 'Starter Projects folder + starter Flow rows' pattern with
    the new Template entity. Idempotent: re-running updates existing rows (by
    name) rather than duplicating.
    """
    if not get_settings_service().settings.create_starter_projects:
        return

    async with session_scope() as session:
        starter_projects = await load_starter_projects()

        # Find a fallback user (first superuser) for created_by/updated_by.
        from langflow.services.database.models.user.model import User
        fallback_user = (
            await session.exec(select(User).where(User.is_superuser.is_(True)))
        ).first()
        if fallback_user is None:
            await logger.awarning(
                "No superuser found; skipping starter template seeding."
            )
            return

        for project_path, project in starter_projects:
            (
                project_name,
                project_description,
                project_is_component,
                _updated_at_datetime,
                project_data,
                project_icon,
                _project_icon_bg_color,
                project_gradient,
                _project_tags,
            ) = get_project_data(project)
            if project_is_component:
                # Component starter projects (if any) are not templates.
                continue

            if all_types_dict is not None:
                project_data = update_projects_components_with_latest_component_versions(
                    project_data.copy(), all_types_dict
                )
                project_data = update_edges_with_latest_component_versions(project_data)

            nodes = project_data.get("nodes") or []
            edges = project_data.get("edges") or []

            existing = (
                await session.exec(
                    select(Template).where(Template.name == project_name)
                )
            ).one_or_none()

            now = datetime.now(timezone.utc)
            if existing is None:
                row = Template(
                    name=project_name,
                    description=project_description,
                    icon=project_icon,
                    gradient=project_gradient,
                    scope="platform",
                    org_id=None,
                    nodes=nodes,
                    edges=edges,
                    created_by=fallback_user.id,
                    created_at=now,
                    updated_by=fallback_user.id,
                    updated_at=now,
                )
                session.add(row)
            else:
                existing.description = project_description
                existing.icon = project_icon
                existing.gradient = project_gradient
                existing.nodes = nodes
                existing.edges = edges
                existing.updated_by = fallback_user.id
                existing.updated_at = now
                session.add(existing)

        await session.commit()
```

Imports needed at top of the file if not already present:

```python
from datetime import datetime, timezone
from sqlmodel import select
from langflow.services.database.models.template.model import Template
```

Then:
- Delete the `get_or_create_starter_folder` function (around line 743).
- Remove imports of `STARTER_FOLDER_NAME` that only that function used (keep imports that Task 6 still needs).
- Update `__main__.py`'s "Step 5: Adding Starter Projects" step to call `create_or_update_starter_templates` instead.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/initial_setup/test_template_seeding.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/backend/base/langflow/initial_setup/setup.py \
        src/backend/base/langflow/__main__.py \
        src/backend/tests/unit/initial_setup/test_template_seeding.py
```

---

## Task 6: Backend — Retarget starter-folder consumers

**Files (modify):**
- `src/backend/base/langflow/api/v1/flows.py` (lines 28, 425, 1027)
- `src/backend/base/langflow/api/v1/projects.py` (lines 35, 235)
- `src/backend/base/langflow/services/database/service.py` (lines 30, 319)
- `src/backend/base/langflow/services/database/models/flow/starter.py` — retire

Every caller of `STARTER_FOLDER_NAME` / `is_flow_a_starter_project*` / `list_starter_project_flows` now queries the `template` table instead.

- [ ] **Step 1: Read each file at the cited line to understand context**

Open each file and locate the reference. Note what the surrounding code is trying to express ("is this flow a template?", "list all templates", "exclude templates from project list").

- [ ] **Step 2: Update `services/database/service.py`**

Line 30 imports `STARTER_FOLDER_NAME`; line 319 uses it to exclude from a query. Both can be deleted now — there's no Starter Projects folder, so no filter needed. Remove the import and the `Folder.name != STARTER_FOLDER_NAME` condition.

- [ ] **Step 3: Update `api/v1/projects.py`**

Line 35 imports `STARTER_FOLDER_NAME`. Line 235 filters projects that are named "Starter Projects". Same treatment — delete the import and the filter condition. Verify the test suite still passes (this just removes a filter that's now moot).

- [ ] **Step 4: Update `api/v1/flows.py`**

Lines 425 and 1027 query for the Starter folder by name. This is usually to find starter flows for UI listing or basic-example serving. Retarget each site:

- If the surrounding code is "serve basic examples / starter projects" → query `select(Template).where(Template.scope == 'platform').where(Template.deleted_at.is_(None))` and return Template rows in the same shape.
- If the surrounding code is "exclude starter flows from normal flow queries" → just remove the filter (there are no Flow rows for starters anymore).

Inspect each call site carefully. Pattern-match against the surrounding function's docstring or name.

- [ ] **Step 5: Retire `services/database/models/flow/starter.py`**

This module's functions (`is_flow_a_starter_project`, `is_flow_a_starter_project_async`, `list_starter_project_flows`) are no longer meaningful. Two options:

(a) Delete the file entirely; callers migrate to Template lookups (covered in later tasks).
(b) Keep the file but stub the functions with deprecation warnings:

```python
async def is_flow_a_starter_project_async(flow: Flow, session: AsyncSession) -> bool:
    """DEPRECATED: starter projects are now Template rows. This always returns False."""
    return False
```

Option (b) is safer — lets callers in task 7/8 keep working while being migrated incrementally. Pick (b) unless the total number of callers is ≤ 3.

- [ ] **Step 6: Run the full backend test suite to confirm nothing broke**

Run: `cd src/backend && uv run pytest tests/unit -x --timeout 120`
Expected: ALL PASS (or the same failing tests as before — no new failures).

- [ ] **Step 7: Stage**

```bash
git add src/backend/base/langflow/services/database/service.py \
        src/backend/base/langflow/api/v1/projects.py \
        src/backend/base/langflow/api/v1/flows.py \
        src/backend/base/langflow/services/database/models/flow/starter.py
```

---

## Task 7: Backend — Retarget `template_apply` assistant tool

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/template_apply.py`
- Create: `src/backend/tests/unit/services/assistant/test_template_apply_retargeted.py`

The existing tool resolves a template flow_id via `is_flow_a_starter_project_async`. Retarget to operate on Template rows by id; write `Flow.based_on_template_id` on the target.

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_template_apply_retargeted.py`:

```python
"""template_apply tool now operates on Template by id."""

import pytest
from langflow.services.assistant.tools.template_apply import apply_template


@pytest.mark.asyncio
async def test_apply_template_sets_based_on_template_id(
    async_session, empty_flow, sample_template
):
    result = await apply_template(
        target_flow_id=str(empty_flow.id),
        template_id=str(sample_template.id),
    )
    assert "error" not in result
    assert result["template_name"] == sample_template.name
    # Refresh the flow; based_on_template_id must match the template
    await async_session.refresh(empty_flow)
    assert empty_flow.based_on_template_id == sample_template.id


@pytest.mark.asyncio
async def test_apply_template_rejects_nonempty_target(
    async_session, populated_flow, sample_template
):
    result = await apply_template(
        target_flow_id=str(populated_flow.id),
        template_id=str(sample_template.id),
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_apply_template_rejects_missing_template(async_session, empty_flow):
    import uuid
    result = await apply_template(
        target_flow_id=str(empty_flow.id),
        template_id=str(uuid.uuid4()),
    )
    assert "error" in result
```

Use existing fixture conventions; define `empty_flow`, `populated_flow`, `sample_template` in a local conftest if needed.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/services/assistant/test_template_apply_retargeted.py -v`
Expected: FAIL — function signature still uses `template_flow_id` + `is_flow_a_starter_project_async`.

- [ ] **Step 3: Rewrite `template_apply.py`**

Replace the body of `src/backend/base/langflow/services/assistant/tools/template_apply.py`:

```python
"""`apply_template` tool: replace a blank flow's content with a Template's content."""

from typing import Any
from uuid import UUID

from sqlmodel import select

from langflow.services.assistant.tools.common import regenerate_flow_ids
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


async def apply_template(
    target_flow_id: str,
    template_id: str,
) -> dict[str, Any]:
    """Replace a blank flow's data with a Template's data. Sets the target's
    based_on_template_id so subsequent assistant messages carry the
    template's agent_usage_notes in the system prompt.

    Returns: {"applied_patch": {...}, "template_name": str}
    Errors: {"error": "..."} when target non-empty, template missing, etc.
    """
    try:
        target_uuid = UUID(target_flow_id)
        template_uuid = UUID(template_id)
    except ValueError:
        return {"error": "Invalid id format."}

    async with session_scope() as session:
        target = (
            await session.exec(select(Flow).where(Flow.id == target_uuid))
        ).one_or_none()
        if target is None:
            return {"error": "Target flow not found."}
        template = (
            await session.exec(
                select(Template)
                .where(Template.id == template_uuid)
                .where(Template.deleted_at.is_(None))
            )
        ).one_or_none()
        if template is None:
            return {"error": "Template not found."}

        current_nodes = (target.data or {}).get("nodes") or []
        if current_nodes:
            return {"error": "Target flow is not empty. Start from a blank flow to apply a template."}

        template_data = {
            "nodes": template.nodes,
            "edges": template.edges,
        }
        new_data = regenerate_flow_ids(template_data)

        target.data = new_data
        target.based_on_template_id = template_uuid
        session.add(target)
        await session.commit()
        await session.refresh(target)

        return {
            "applied_patch": {
                "added_nodes": new_data.get("nodes") or [],
                "added_edges": new_data.get("edges") or [],
                "updated_nodes": [],
                "removed_ids": [],
            },
            "template_name": template.name,
        }
```

- [ ] **Step 4: Update callers of the renamed parameter**

Grep for `template_flow_id=` in the assistant service and rename:

```bash
cd /Users/brycedeneen/dev/langflow
grep -rn "template_flow_id" src/backend/base/langflow/services/assistant/
```

Update any call sites to use `template_id=` as the kwarg name. Also update the assistant tool schema in `services/assistant/tools/registry.py` if `apply_template`'s parameters dict uses `template_flow_id`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/services/assistant/test_template_apply_retargeted.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Stage**

```bash
git add src/backend/base/langflow/services/assistant/tools/template_apply.py \
        src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/tests/unit/services/assistant/test_template_apply_retargeted.py
```

---

## Task 8: Backend — Retarget flow-template-context + assistant service + assistant endpoint

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/flow_template_context.py`
- Modify: `src/backend/base/langflow/services/assistant/service.py` (lines 129, 137, 236, 370)
- Modify: `src/backend/base/langflow/api/v1/assistant.py` (lines 351, 568)

The field is renamed from `based_on_template_flow_id` → `based_on_template_id` everywhere. Plus `flow_template_context.py` queries `TemplateMetadata` by a new FK key (`template_id`).

- [ ] **Step 1: Update `flow_template_context.py`**

Open `src/backend/base/langflow/services/assistant/flow_template_context.py`. Find the function whose signature currently accepts `based_on_template_flow_id`. Rename the parameter and its usages; change the `TemplateMetadata` query to key on `template_id`:

```python
async def fetch_template_usage_notes(
    based_on_template_id: str | None,
) -> str | None:
    """If the current flow is based on a template, fetch that template's agent usage notes."""
    if based_on_template_id is None:
        return None
    async with session_scope() as session:
        row = (
            await session.exec(
                select(TemplateMetadata)
                .where(TemplateMetadata.template_id == UUID(based_on_template_id))
            )
        ).one_or_none()
        return row.agent_usage_notes if row else None
```

Confirm the imports include `TemplateMetadata` and `UUID` / `select`.

- [ ] **Step 2: Update `services/assistant/service.py`**

Find the constructor around line 129 that accepts `based_on_template_flow_id`. Rename the parameter to `based_on_template_id` and rename `self.based_on_template_flow_id = ...` to `self.based_on_template_id = ...`. Update all usages in the class (lines 236, 370 — pass-throughs to the context builder).

- [ ] **Step 3: Update `api/v1/assistant.py`**

Lines 351 and 568 construct AssistantService. Rename the kwarg in both call sites from `based_on_template_flow_id=...` to `based_on_template_id=...`. The source of the value is now `flow.based_on_template_id` (the new column).

- [ ] **Step 4: Grep-verify no stragglers remain**

```bash
grep -rn "based_on_template_flow_id" src/backend/
```

Expected output: no matches (all have been renamed). If any remain, fix them.

- [ ] **Step 5: Run the backend test suite to confirm nothing broke**

Run: `cd src/backend && uv run pytest tests/unit/services/assistant tests/unit/api/v1/test_assistant_stream_partial_persistence.py -v`
Expected: ALL PASS (or no new failures relative to baseline).

- [ ] **Step 6: Stage**

```bash
git add src/backend/base/langflow/services/assistant/flow_template_context.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/base/langflow/api/v1/assistant.py
```

---

## Task 9: Backend — Deprecate `/api/v1/starter-projects/`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/starter_projects.py`

The endpoint stays (frontend's `useGetBasicExamplesQuery` still hits it until Task 12 retargets it) but reads from the `template` table instead of the Python graph-builder dump.

- [ ] **Step 1: Read the current endpoint**

Open `src/backend/base/langflow/api/v1/starter_projects.py`. The endpoint (around line 45) currently calls `get_starter_projects_dump()` from `initial_setup/load.py`.

- [ ] **Step 2: Retarget to read from Template**

Replace the handler body:

```python
@router.get("/", response_model=list[dict], deprecated=True)
async def get_starter_projects(
    *, session: DbSession, _user: User = Depends(get_current_active_user)
) -> list[dict]:
    """DEPRECATED. Reads platform templates from the template table.

    Use /api/v1/templates instead. This endpoint is maintained for backward
    compatibility with older frontend clients; it will be removed in a
    follow-up plan once all callers have migrated.
    """
    stmt = (
        select(Template)
        .where(Template.deleted_at.is_(None))
        .where(Template.scope == "platform")
        .order_by(Template.updated_at.desc())
    )
    rows = (await session.exec(stmt)).all()
    # Return in the same shape as the old Python-dump output:
    # [{ "name": ..., "description": ..., "data": { "nodes": ..., "edges": ... }, ... }]
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "icon": r.icon,
            "gradient": r.gradient,
            "data": {"nodes": r.nodes, "edges": r.edges},
        }
        for r in rows
    ]
```

Imports needed at top: `from langflow.services.database.models.template.model import Template`, `from sqlmodel import select`, DbSession, user auth dep.

- [ ] **Step 3: Add a smoke test (optional — existing tests should cover it)**

If there's an existing `tests/unit/api/v1/test_starter_projects.py`, ensure it still passes with the new implementation. If no test exists, skip — the frontend test in Task 12 exercises the real path.

- [ ] **Step 4: Stage**

```bash
git add src/backend/base/langflow/api/v1/starter_projects.py
```

---

## Task 10: Frontend — Template query hooks

**Files:**
- Create: `src/frontend/src/types/template/index.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-get-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-create-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-update-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-delete-template.ts`

Follow existing hook conventions (inspect `controllers/API/queries/flows/use-get-basic-examples.ts` and `controllers/API/queries/metadata/use-component-metadata.ts` for patterns).

- [ ] **Step 1: Create shared types**

Create `src/frontend/src/types/template/index.ts`:

```typescript
export type TemplateRead = {
  id: string;
  name: string;
  description: string | null;
  icon: string | null;
  gradient: string | null;
  created_at: string;
  updated_at: string;
};

export type TemplateReadDetail = TemplateRead & {
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
};

export type BlankedField = {
  node_id: string;
  field_name: string;
};

export type TemplateCreateBody = {
  source_flow_id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  gradient?: string | null;
  blanked_fields?: BlankedField[];
};

export type TemplateUpdateBody = TemplateCreateBody;
```

- [ ] **Step 2: Create `useListTemplates`**

Create `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts`:

```typescript
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { TemplateRead } from "@/types/template";

export const TEMPLATES_QUERY_KEY = ["templates"];

export function useListTemplates() {
  return useQuery<TemplateRead[]>({
    queryKey: TEMPLATES_QUERY_KEY,
    queryFn: async () => {
      const res = await api.get<TemplateRead[]>("/api/v1/templates");
      return res.data;
    },
    placeholderData: keepPreviousData,
  });
}
```

- [ ] **Step 3: Create `useGetTemplate`**

Create `src/frontend/src/controllers/API/queries/templates/use-get-template.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { TemplateReadDetail } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useGetTemplate(templateId: string | null) {
  return useQuery<TemplateReadDetail>({
    queryKey: [...TEMPLATES_QUERY_KEY, templateId],
    enabled: templateId !== null,
    queryFn: async () => {
      const res = await api.get<TemplateReadDetail>(
        `/api/v1/templates/${templateId}`,
      );
      return res.data;
    },
  });
}
```

- [ ] **Step 4: Create `useCreateTemplate`**

Create `src/frontend/src/controllers/API/queries/templates/use-create-template.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { TemplateCreateBody, TemplateReadDetail } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation<TemplateReadDetail, Error, TemplateCreateBody>({
    mutationFn: async (body) => {
      const res = await api.post<TemplateReadDetail>(
        "/api/v1/templates",
        body,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
```

- [ ] **Step 5: Create `useUpdateTemplate`**

Create `src/frontend/src/controllers/API/queries/templates/use-update-template.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import type { TemplateReadDetail, TemplateUpdateBody } from "@/types/template";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

type Vars = { templateId: string; body: TemplateUpdateBody };

export function useUpdateTemplate() {
  const qc = useQueryClient();
  return useMutation<TemplateReadDetail, Error, Vars>({
    mutationFn: async ({ templateId, body }) => {
      const res = await api.put<TemplateReadDetail>(
        `/api/v1/templates/${templateId}`,
        body,
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
```

- [ ] **Step 6: Create `useDeleteTemplate`**

Create `src/frontend/src/controllers/API/queries/templates/use-delete-template.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { TEMPLATES_QUERY_KEY } from "./use-list-templates";

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (templateId) => {
      await api.delete(`/api/v1/templates/${templateId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TEMPLATES_QUERY_KEY });
    },
  });
}
```

- [ ] **Step 7: Stage**

```bash
git add src/frontend/src/types/template/ \
        src/frontend/src/controllers/API/queries/templates/
```

---

## Task 11: Frontend — Rename `based_on_template_flow_id` → `based_on_template_id`

**Files (modify):**
- `src/frontend/src/types/flow/index.ts`
- `src/frontend/src/hooks/flows/use-add-flow.ts`
- Any other callers (find via grep)

- [ ] **Step 1: Find all callers**

Run: `grep -rn "based_on_template_flow_id" src/frontend/`

Expected: ~3-5 call sites in types + hooks + maybe tests.

- [ ] **Step 2: Rename each occurrence**

For each file:
- Change the field name from `based_on_template_flow_id` to `based_on_template_id`.
- If the type declaration has a comment about the field, update it to say "points at Template.id" instead of another Flow.

- [ ] **Step 3: Run the full frontend test suite**

Run: `cd src/frontend && npx jest --no-coverage`
Expected: ALL PASS (or same baseline failures).

- [ ] **Step 4: Stage**

```bash
git add src/frontend/src/types/flow/ \
        src/frontend/src/hooks/flows/
# Plus any other files the grep surfaced
```

---

## Task 12: Frontend — Retarget `templatesModal` to `useListTemplates`

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/index.tsx`
- Modify: `src/frontend/src/modals/templatesModal/components/GetStartedComponent/index.tsx`

- [ ] **Step 1: Read the current structure**

Inspect `src/frontend/src/modals/templatesModal/index.tsx`. Currently it reads `examples` from the zustand store (populated via `useGetBasicExamplesQuery`).

- [ ] **Step 2: Swap hook**

Replace the `examples` source with `useListTemplates`. The payload shape differs:
- Old: `GraphDumpResponse[]` with `flow.data.nodes`, `flow.data.edges`, etc.
- New: `TemplateRead[]` with slim shape (name, description, icon, gradient, ids).

For the card listing, the slim shape is sufficient. When the user clicks "Create from template", use `useGetTemplate(templateId)` to fetch the full `nodes` + `edges` payload.

- [ ] **Step 3: Adapt `GetStartedComponent`**

Update the `GetStartedComponent` to accept `TemplateRead[]` instead of the old graph-dump shape. The template card display uses name + description + icon + gradient — all present in `TemplateRead`. The only tricky part is the existing knowledge-bases filter at line 31 — keep the `!ENABLE_KNOWLEDGE_BASES && example.name?.includes("Knowledge")` logic but apply it to `TemplateRead.name`.

The "create" action should:

```typescript
const { data: templateDetail } = useGetTemplate(selectedTemplateId);
// ...when user confirms:
await addFlow({
  ...pick from templateDetail (nodes, edges),
  based_on_template_id: templateDetail.id,
});
```

Rely on the existing `addFlow` hook; pass `based_on_template_id` per the rename in Task 11.

- [ ] **Step 4: Manually verify in the browser**

Run the dev server. Open "New Flow" or wherever the templates modal surfaces. Confirm the list renders with the migrated templates and "Create from template" produces a new flow with `based_on_template_id` set (check via React DevTools or the DB).

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/templatesModal/
```

---

## Task 13: Frontend — Save-as-Template modal (field-review panel)

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/field-review-panel.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/field-review-panel.test.tsx`

The field-review panel is the core UX piece. Lists every non-empty Input across all nodes; password fields non-toggleable; Blank/Keep-all buttons at top.

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/field-review-panel.test.tsx`:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FieldReviewPanel } from "../field-review-panel";

// Minimal shape; mirrors how Langflow stores node data.
function nodeWithFields(id: string, template: Record<string, any>) {
  return {
    id,
    data: {
      node: { display_name: id, template },
    },
  };
}

describe("FieldReviewPanel", () => {
  it("renders non-empty fields grouped by node", () => {
    const nodes = [
      nodeWithFields("Slack-1", {
        webhook_url: { value: "https://example.com", password: false },
        channel: { value: "#test", password: false },
      }),
      nodeWithFields("Agent-1", {
        instructions: { value: "Do the thing", password: false },
        token: { value: "secret-xyz", password: true },
      }),
    ];
    render(<FieldReviewPanel nodes={nodes} onBlankedFieldsChange={jest.fn()} />);
    expect(screen.getByText("Slack-1")).toBeInTheDocument();
    expect(screen.getByText("Agent-1")).toBeInTheDocument();
    expect(screen.getByText("webhook_url")).toBeInTheDocument();
    expect(screen.getByText("channel")).toBeInTheDocument();
    expect(screen.getByText("instructions")).toBeInTheDocument();
    expect(screen.getByText("token")).toBeInTheDocument();
  });

  it("renders password fields as non-interactive with lock icon", () => {
    const nodes = [
      nodeWithFields("Agent-1", { token: { value: "x", password: true } }),
    ];
    render(<FieldReviewPanel nodes={nodes} onBlankedFieldsChange={jest.fn()} />);
    expect(screen.queryByRole("checkbox", { name: /token/i })).not.toBeInTheDocument();
    expect(screen.getByTestId("lock-icon-Agent-1-token")).toBeInTheDocument();
  });

  it("Blank all toggles every non-password row to blank", async () => {
    const onChange = jest.fn();
    const user = userEvent.setup();
    const nodes = [
      nodeWithFields("Slack-1", {
        webhook_url: { value: "https://example.com", password: false },
      }),
    ];
    render(<FieldReviewPanel nodes={nodes} onBlankedFieldsChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /blank all/i }));
    const lastCall = onChange.mock.calls.slice(-1)[0][0];
    expect(lastCall).toEqual([{ node_id: "Slack-1", field_name: "webhook_url" }]);
  });

  it("hides empty-valued fields", () => {
    const nodes = [
      nodeWithFields("X-1", { empty_field: { value: "", password: false } }),
    ];
    render(<FieldReviewPanel nodes={nodes} onBlankedFieldsChange={jest.fn()} />);
    expect(screen.queryByText("empty_field")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/field-review-panel.test.tsx --no-coverage`
Expected: FAIL — `../field-review-panel` module not found.

- [ ] **Step 3: Implement `field-review-panel.tsx`**

Create `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/field-review-panel.tsx`:

```tsx
import { useMemo, useState, useEffect } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

type NodeWithFields = {
  id: string;
  data?: {
    node?: {
      display_name?: string;
      template?: Record<string, { value?: unknown; password?: boolean }>;
    };
  };
};

export type BlankedField = { node_id: string; field_name: string };

type Props = {
  nodes: NodeWithFields[];
  onBlankedFieldsChange: (blanked: BlankedField[]) => void;
};

type FieldRow = {
  node_id: string;
  field_name: string;
  node_display_name: string;
  value_preview: string;
  is_password: boolean;
};

function computeRows(nodes: NodeWithFields[]): FieldRow[] {
  const rows: FieldRow[] = [];
  for (const n of nodes) {
    const template = n.data?.node?.template ?? {};
    for (const [field_name, cfg] of Object.entries(template)) {
      const v = cfg?.value;
      // Hide empty fields
      if (v === null || v === undefined || v === "") continue;
      rows.push({
        node_id: n.id,
        field_name,
        node_display_name: n.data?.node?.display_name ?? n.id,
        value_preview:
          typeof v === "string" ? v : JSON.stringify(v).slice(0, 80),
        is_password: Boolean(cfg?.password),
      });
    }
  }
  return rows;
}

export function FieldReviewPanel({ nodes, onBlankedFieldsChange }: Props) {
  const rows = useMemo(() => computeRows(nodes), [nodes]);
  // Password rows are always blanked at submit — not in state.
  const [blanked, setBlanked] = useState<Set<string>>(new Set());

  const keyFor = (node_id: string, field_name: string) =>
    `${node_id}\u0000${field_name}`;

  useEffect(() => {
    const list: BlankedField[] = [];
    for (const row of rows) {
      if (row.is_password) continue;
      if (blanked.has(keyFor(row.node_id, row.field_name))) {
        list.push({ node_id: row.node_id, field_name: row.field_name });
      }
    }
    onBlankedFieldsChange(list);
  }, [rows, blanked, onBlankedFieldsChange]);

  const toggle = (row: FieldRow) => {
    const k = keyFor(row.node_id, row.field_name);
    setBlanked((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  const blankAll = () => {
    const next = new Set<string>();
    for (const row of rows) {
      if (!row.is_password) next.add(keyFor(row.node_id, row.field_name));
    }
    setBlanked(next);
  };
  const keepAll = () => setBlanked(new Set());

  // Group rows by node
  const byNode = rows.reduce<Record<string, FieldRow[]>>((acc, row) => {
    (acc[row.node_id] ??= []).push(row);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded border border-border bg-muted/40 px-2 py-1 text-xs hover:bg-muted"
          onClick={blankAll}
        >
          Blank all
        </button>
        <button
          type="button"
          className="rounded border border-border bg-muted/40 px-2 py-1 text-xs hover:bg-muted"
          onClick={keepAll}
        >
          Keep all
        </button>
      </div>
      {Object.entries(byNode).map(([nodeId, nodeRows]) => (
        <div key={nodeId} className="rounded border border-border p-3">
          <div className="mb-2 text-sm font-medium">
            {nodeRows[0].node_display_name}
          </div>
          <ul className="flex flex-col gap-1">
            {nodeRows.map((row) => (
              <li
                key={row.field_name}
                className="flex items-center justify-between gap-2 text-xs"
              >
                <div className="flex min-w-0 flex-col">
                  <span className="font-mono">{row.field_name}</span>
                  <span className="truncate text-muted-foreground">
                    {row.is_password ? "••••••••••" : row.value_preview}
                  </span>
                </div>
                {row.is_password ? (
                  <span
                    data-testid={`lock-icon-${row.node_id}-${row.field_name}`}
                    className="flex items-center gap-1 text-xs text-muted-foreground"
                    title="Password fields are always blanked in templates."
                  >
                    <ForwardedIconComponent
                      name="Lock"
                      className="h-3 w-3"
                    />
                    always blanked
                  </span>
                ) : (
                  <label className="flex items-center gap-1 text-xs">
                    <input
                      type="checkbox"
                      aria-label={`Blank ${row.field_name}`}
                      checked={blanked.has(
                        keyFor(row.node_id, row.field_name),
                      )}
                      onChange={() => toggle(row)}
                    />
                    blank
                  </label>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/field-review-panel.test.tsx --no-coverage`
Expected: 4 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/field-review-panel.tsx \
        src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/field-review-panel.test.tsx
```

---

## Task 14: Frontend — Save-as-Template modal (container + overwrite flow)

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/index.tsx`
- Create: `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const createMutation = jest.fn().mockResolvedValue({ id: "t1", name: "My Template" });
const updateMutation = jest.fn().mockResolvedValue({ id: "t1", name: "My Template" });

jest.mock("@/controllers/API/queries/templates/use-create-template", () => ({
  __esModule: true,
  useCreateTemplate: () => ({
    mutateAsync: createMutation,
    isPending: false,
    error: null,
  }),
}));
jest.mock("@/controllers/API/queries/templates/use-update-template", () => ({
  __esModule: true,
  useUpdateTemplate: () => ({
    mutateAsync: updateMutation,
    isPending: false,
    error: null,
  }),
}));
jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => ({ data: [{ id: "existing1", name: "Existing" }] }),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

import { SaveAsTemplateModal } from "../index";

describe("SaveAsTemplateModal", () => {
  beforeEach(() => {
    createMutation.mockClear();
    updateMutation.mockClear();
  });

  it("renders metadata fields + field review panel", () => {
    render(
      <SaveAsTemplateModal
        open
        flowId="flow-1"
        flowName="My Flow"
        flowNodes={[]}
        flowEdges={[]}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
  });

  it("submits via useCreateTemplate on save", async () => {
    const user = userEvent.setup();
    render(
      <SaveAsTemplateModal
        open
        flowId="flow-1"
        flowName="My Flow"
        flowNodes={[]}
        flowEdges={[]}
        onClose={jest.fn()}
      />,
    );
    await user.type(screen.getByLabelText(/name/i), "My Template");
    await user.click(screen.getByRole("button", { name: /save as template/i }));
    expect(createMutation).toHaveBeenCalledTimes(1);
    const arg = createMutation.mock.calls[0][0];
    expect(arg.name).toBe("My Template");
    expect(arg.source_flow_id).toBe("flow-1");
  });

  it("shows overwrite confirm on 409, then triggers update on confirm", async () => {
    createMutation.mockRejectedValueOnce({
      response: { status: 409 },
      message: "409",
    });
    const user = userEvent.setup();
    render(
      <SaveAsTemplateModal
        open
        flowId="flow-1"
        flowName="My Flow"
        flowNodes={[]}
        flowEdges={[]}
        onClose={jest.fn()}
      />,
    );
    await user.type(screen.getByLabelText(/name/i), "Existing");
    await user.click(screen.getByRole("button", { name: /save as template/i }));
    expect(
      await screen.findByText(/already exists/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /overwrite/i }));
    expect(updateMutation).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx --no-coverage`
Expected: FAIL — `../index` module not found.

- [ ] **Step 3: Implement the modal container**

Create `src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/index.tsx`:

```tsx
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCreateTemplate } from "@/controllers/API/queries/templates/use-create-template";
import { useUpdateTemplate } from "@/controllers/API/queries/templates/use-update-template";
import { useListTemplates } from "@/controllers/API/queries/templates/use-list-templates";
import { FieldReviewPanel, type BlankedField } from "./field-review-panel";

type Props = {
  open: boolean;
  flowId: string;
  flowName: string;
  flowNodes: Array<Record<string, unknown>>;
  flowEdges: Array<Record<string, unknown>>;
  onClose: () => void;
};

export function SaveAsTemplateModal({
  open,
  flowId,
  flowName,
  flowNodes,
  onClose,
}: Props) {
  const [name, setName] = useState(flowName);
  const [description, setDescription] = useState("");
  const [blanked, setBlanked] = useState<BlankedField[]>([]);
  const [overwriteTarget, setOverwriteTarget] = useState<string | null>(null);

  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const { data: existingTemplates = [] } = useListTemplates();

  const findExistingByName = useCallback(
    (n: string) => existingTemplates.find((t) => t.name === n) ?? null,
    [existingTemplates],
  );

  const handleSave = useCallback(async () => {
    const body = {
      source_flow_id: flowId,
      name,
      description,
      blanked_fields: blanked,
    };
    try {
      await create.mutateAsync(body);
      onClose();
    } catch (err: any) {
      if (err?.response?.status === 409) {
        const existing = findExistingByName(name);
        if (existing) {
          setOverwriteTarget(existing.id);
        }
      } else {
        throw err;
      }
    }
  }, [create, flowId, name, description, blanked, onClose, findExistingByName]);

  const handleOverwrite = useCallback(async () => {
    if (!overwriteTarget) return;
    await update.mutateAsync({
      templateId: overwriteTarget,
      body: {
        source_flow_id: flowId,
        name,
        description,
        blanked_fields: blanked,
      },
    });
    setOverwriteTarget(null);
    onClose();
  }, [update, overwriteTarget, flowId, name, description, blanked, onClose]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Save as Template</DialogTitle>
        </DialogHeader>

        {overwriteTarget === null ? (
          <>
            <div className="flex flex-col gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-sm">Name</span>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-sm">Description</span>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <div>
                <div className="mb-2 text-sm font-medium">Field review</div>
                <FieldReviewPanel
                  nodes={flowNodes as any}
                  onBlankedFieldsChange={setBlanked}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={create.isPending || !name}>
                Save as Template
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="flex flex-col gap-2 text-sm">
              <p className="font-medium">
                A template named <span className="font-mono">"{name}"</span>{" "}
                already exists.
              </p>
              <p className="text-muted-foreground">
                Overwrite it? Clients who cloned the previous version won't be
                automatically notified — they'll continue to see their existing
                flow as-is. Versioning arrives in Phase 2; until then,
                overwriting is destructive to the template's history.
              </p>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setOverwriteTarget(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleOverwrite}
                disabled={update.isPending}
              >
                Overwrite template
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

If your project uses slightly different UI primitives (e.g., the dialog package lives at a different path), adjust imports. Grep for `DialogContent` in `src/frontend/src/` for the canonical import.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx --no-coverage`
Expected: 3 PASS.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/index.tsx \
        src/frontend/src/modals/AssistantPanel/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
```

---

## Task 15: Frontend — Wire "Save as Template" into the Share menu

**Files:**
- Modify: The file that owns the Share dropdown (likely in the flow canvas header, not `AssistantPanel/`)

- [ ] **Step 1: Locate the Share menu**

Run: `grep -rn "API access" src/frontend/src/ | head -20` — the Share dropdown contains "API access / Export / MCP Server / Embed into site / Shareable Playground". Find the file that declares those items.

- [ ] **Step 2: Add "Save as Template" item for superusers**

In that file, add a new menu item between "Export" and "MCP Server":

```tsx
{currentUser?.is_superuser && (
  <DropdownMenuItem onSelect={() => setSaveAsTemplateOpen(true)}>
    <ForwardedIconComponent name="BookTemplate" className="mr-2 h-4 w-4" />
    Save as Template
  </DropdownMenuItem>
)}
```

Declare state for the modal open/close:

```tsx
const [saveAsTemplateOpen, setSaveAsTemplateOpen] = useState(false);
```

And render the modal:

```tsx
<SaveAsTemplateModal
  open={saveAsTemplateOpen}
  flowId={currentFlow.id}
  flowName={currentFlow.name}
  flowNodes={nodes}
  flowEdges={edges}
  onClose={() => setSaveAsTemplateOpen(false)}
/>
```

The `currentUser.is_superuser` check source varies by project convention — grep for `is_superuser` in the frontend to find the canonical access pattern (likely a zustand store selector).

- [ ] **Step 3: Manual verification**

Run dev server. Sign in as a superuser. Open a flow → Share → "Save as Template" appears. Sign out and sign in as a non-superuser. Open same flow → "Save as Template" is not in the menu.

- [ ] **Step 4: Stage**

```bash
git add <the file you modified>
```

---

## Task 16: Frontend — Retarget MetadataPage flows-tab to Template resource

**Files:**
- Modify: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx`
- Modify (possibly): `src/frontend/src/controllers/API/queries/metadata/use-list-template-metadata.ts` (or similar)
- Update tests

- [ ] **Step 1: Read the existing flows-tab**

Open `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx`. It currently reads `row.flow_id` / `row.flow_name` from `useListTemplateMetadata()`. These need to become `row.template_id` / `row.template_name`.

- [ ] **Step 2: Update the metadata query hook**

The existing `useListTemplateMetadata` hits `/api/v1/admin/metadata/templates` — that endpoint is retargeted in Task 4 and now returns rows keyed by `template_id`. Update the hook's TypeScript type to reflect the new shape:

```typescript
export type TemplateMetadataRow = {
  template_id: string;
  template_name: string;
  metadata: {
    agent_usage_notes: string | null;
    agent_summary: string | null;
    updated_by: string;
    updated_at: string;
  } | null;
};
```

Also update `useUpsertTemplateMetadata` and `useDeleteTemplateMetadata` to POST/DELETE at `/api/v1/admin/metadata/templates/{template_id}`.

- [ ] **Step 3: Update flows-tab.tsx**

Replace references:
- `row.flow_id` → `row.template_id`
- `row.flow_name` → `row.template_name`
- Edit dialog initial state builds from `row.metadata` as before.

- [ ] **Step 4: Run the existing tests**

Run: `cd src/frontend && npx jest src/pages/SettingsPage/pages/MetadataPage/__tests__ --no-coverage`

Fix any failing assertions that referenced `flow_id` / `flow_name` — they should now use `template_id` / `template_name`.

- [ ] **Step 5: Stage**

```bash
git add src/frontend/src/pages/SettingsPage/pages/MetadataPage/ \
        src/frontend/src/controllers/API/queries/metadata/
```

---

## Task 17: Cross-suite verification + manual checklist

**Files:** none modified.

- [ ] **Step 1: Full backend suite**

Run: `cd src/backend && uv run pytest tests/unit --timeout 120 -x`
Expected: ALL PASS.

- [ ] **Step 2: Full frontend suite**

Run: `cd src/frontend && npx jest --no-coverage`
Expected: ALL PASS.

- [ ] **Step 3: Alembic upgrade against a fresh dev DB**

```bash
cd src/backend
# Use the project's dev DB URL from your env or a temporary SQLite.
LANGFLOW_DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run alembic upgrade head
```

Expected: clean completion.

- [ ] **Step 4: Alembic upgrade against an existing dev DB with starter-project Flow rows**

Boot the app against a DB that was populated before this plan (so it has Starter Projects + seeded Flow rows). Apply the migration. Inspect:

```sql
SELECT count(*) FROM template;              -- should equal number of starter projects
SELECT count(*) FROM flow WHERE folder_id IN
  (SELECT id FROM folder WHERE name = 'Starter Projects');  -- should be 0
SELECT count(*) FROM folder WHERE name = 'Starter Projects';  -- should be 0
```

- [ ] **Step 5: Manual verification — template catalog**

Boot the app → open "New Flow" → template gallery shows the migrated starter projects. Clone one → new Flow opens, `based_on_template_id` is set (verify via React DevTools).

- [ ] **Step 6: Manual verification — save-as-template**

As superuser, open a flow with a Slack component (has API key + webhook URL). Share → Save as Template. Confirm modal opens with field-review panel showing the webhook_url row (checkbox) + the token row (lock icon). Tick webhook_url. Submit. Toast success. Open the template from the catalog → webhook URL is blank, API key is blank, other fields intact.

- [ ] **Step 7: Manual verification — overwrite flow**

Save a new flow as a template with the SAME NAME. Confirm dialog fires. Click Overwrite. Catalog shows updated content.

- [ ] **Step 8: Manual verification — non-superuser has no Save as Template**

Sign out, sign in as a regular user. Open a flow → Share → "Save as Template" is not in the menu.

- [ ] **Step 9: Manual verification — admin metadata page**

Open Settings → Metadata → Flows tab. List shows Templates (migrated + any new ones). Edit one → saves via the admin metadata endpoint → reload → changes persisted.

- [ ] **Step 10: Manual verification — soft delete**

As superuser, delete a template from the admin metadata page. Catalog gallery no longer shows it. Existing cloned flows continue to load.

- [ ] **Step 11: Report readiness**

If all above steps pass, report: "Plan 7 Phase 1 implementation complete, ready for batched commit."

---

## Open Items

- **Fallback user for migration `created_by`.** If there's no superuser in the DB when the alembic revision runs (unusual in practice — installations always have at least one superuser), the migration logs a warning and skips seeding. Confirm the project's install flow always creates a superuser before seeding templates.
- **`Flow.description` field** — prior Plan 2 followup flagged this may not exist. The Template model has its own `description` column (decoupled); verify `Flow.description` exists before the migration's `SELECT f.description` step, or adjust to handle NULL.
- **Admin metadata response shape** — if `TemplateMetadataRead` currently exposes `flow_id`, update it to expose `template_id` as part of Task 4. Check the pydantic class in `services/database/models/template_metadata/model.py`.
- **`templatesModal` zustand store integration.** The existing modal reads `examples` from a zustand store populated by `useGetBasicExamplesQuery`. Task 12's direct hook call bypasses the store. Verify no other component reads the store's `examples` field; if so, either keep populating it or migrate all readers.
- **Share menu location.** The exact file owning the Share dropdown isn't confirmed in the spec. Task 15 grep finds it.
- **Dialog primitive path.** `@/components/ui/dialog` is the typical shadcn location. Confirm in Task 14 before implementation.
- **Testing fixtures.** `sample_flow`, `sample_template`, `flow_with_secret_field`, `async_session`, etc. are conventional names. Verify which exist in `conftest.py` and either reuse or add as needed at each task's Step 1.
