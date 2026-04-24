# Template Categories Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** ✅ Fully shipped. The individual `- [ ]` boxes below were never flipped during implementation; ground truth is the git log + code. Full category test sweep green on 2026-04-24 — 34 passed across `test_categories.py`, `test_category.py`, `test_category_migration.py`, `test_templates_patch.py`, `test_templates_create_with_categories.py`. See the shipped spec amendments in `docs/superpowers/specs/2026-04-21-template-categories-rework-design.md` §7 for deltas (11 seed categories not 8, FU-7 `/memberships/me` added, `ck_template_scope_org_coherence` rewrite dropped as SQLite-hostile no-op, `ix_template_active` dropped). Flaky fixture in `test_templates_create_with_categories.py::test_org_member_creates_org_template_with_categories` repaired 2026-04-24 — `source_flow` now scoped to `sample_org` so non-admin callers can load it.

**Shipped commits (chronological):** `79865ccc48` (schema migration) · `b4e51662c2` (migration ordering fix) · `af0c6f83c0` (CRUD API) · `f35510b59b` (no-op scope-constraint rewrite removed) · `1b496aa8b8` (POST /templates scope/org_id/category_ids) · plus FU-7 memberships endpoint and migration `cc6f6cca0ead` (partial-index cleanup) + `7c8e4f1a2d9b` (cascade + updated_by alignment).

**Goal:** Replace hardcoded template categories with an admin-managed, DB-backed taxonomy; migrate all starter-project JSON files into the `Template` table; enable org-scoped templates; add archive + hard-delete actions.

**Architecture:** A new `Category` model (platform-global) and `template_category` M2M join. `Template.scope` unfreezes to allow `org`-scoped rows. An Alembic data migration seeds 8 categories from today's tag vocabulary and inserts one `Template` row per starter JSON, then deletes the shadow starter `Flow` rows. The frontend replaces its hardcoded `Category[]` constant with a `GET /api/v1/categories` fetch and adds inline admin affordances (category CRUD popover; template edit side-panel; archive / delete; "Show archived" toggle; categories chip picker in the Save-as-Template dialog).

**Tech Stack:** Python 3.11, FastAPI, SQLModel, Alembic, pytest, React 18, TypeScript, @tanstack/react-query v5, Zustand v5, Jest, Tailwind v4.

**Related spec:** `docs/superpowers/specs/2026-04-21-template-categories-rework-design.md`

---

## File Structure

### Backend

Create:
- `src/backend/base/langflow/alembic/versions/<rev>_category_and_template_rework.py` — schema + data migration in one revision.
- `src/backend/base/langflow/services/database/models/category/__init__.py`
- `src/backend/base/langflow/services/database/models/category/model.py` — `Category`, `TemplateCategory`, `CategoryCreate`, `CategoryUpdate`, `CategoryRead`.
- `src/backend/base/langflow/api/v1/categories.py` — router at prefix `/categories`.
- `src/backend/tests/unit/api/v1/test_categories.py`
- `src/backend/tests/unit/services/database/models/test_category.py`
- `src/backend/tests/unit/alembic/test_category_migration.py`
- `src/backend/tests/unit/api/v1/test_template_archive.py`

Modify:
- `src/backend/base/langflow/services/database/models/template/model.py` — add `archived_at`, nullable `created_by`, scope constraint rewrite, `categories` relationship, update Pydantic schemas.
- `src/backend/base/langflow/services/database/models/template/__init__.py` — export updated classes.
- `src/backend/base/langflow/services/database/models/__init__.py` — export `Category`, `TemplateCategory`.
- `src/backend/base/langflow/api/v1/templates.py` — extend list/create/update/delete handlers; add archive/unarchive endpoints; category replacement logic.
- `src/backend/base/langflow/api/v1/__init__.py` (or the router registry) — register `categories_router`.
- `src/backend/base/langflow/api/v1/flows.py` (flow creation POST) — 422 guard when `based_on_template_id` points to archived template.
- `src/backend/base/langflow/initial_setup/setup.py` — remove starter loader helpers (`load_starter_projects`, `create_or_update_starter_projects`, `create_new_project`, `get_or_create_starter_folder`) and their call sites.
- `src/backend/tests/unit/test_webhook.py` and any other test that relies on starter-project Flow rows — update to create their own fixtures.

Delete:
- `src/backend/base/langflow/initial_setup/starter_projects/*.json` (all ~20+ files) — copies live inside the Alembic revision as bundled fixtures.

### Frontend

Create:
- `src/frontend/src/controllers/API/queries/categories/use-list-categories.ts`
- `src/frontend/src/controllers/API/queries/categories/use-create-category.ts`
- `src/frontend/src/controllers/API/queries/categories/use-update-category.ts`
- `src/frontend/src/controllers/API/queries/categories/use-delete-category.ts`
- `src/frontend/src/controllers/API/queries/categories/index.ts`
- `src/frontend/src/controllers/API/queries/templates/use-archive-template.ts`
- `src/frontend/src/controllers/API/queries/templates/use-unarchive-template.ts`
- `src/frontend/src/controllers/API/queries/templates/use-hard-delete-template.ts`
- `src/frontend/src/modals/templatesModal/components/CategoryEditPopover/index.tsx`
- `src/frontend/src/modals/templatesModal/components/TemplateCardAdminMenu/index.tsx`
- `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx`
- `src/frontend/src/modals/templatesModal/components/CategoryChipPicker/index.tsx` (reused by the Save-as-Template dialog)
- `src/frontend/src/hooks/use-is-platform-admin.ts`
- `src/frontend/tests/unit/CategoryEditPopover.test.tsx`
- `src/frontend/tests/unit/TemplateCardAdminMenu.test.tsx`
- `src/frontend/tests/unit/TemplateEditPanel.test.tsx`

Modify:
- `src/frontend/src/modals/templatesModal/index.tsx` — remove hardcoded `Category[]` (lines 100-134); fetch via `useListCategories`; render admin controls.
- `src/frontend/src/modals/templatesModal/components/navComponent/index.tsx` — hover `…` menu per category; "+ New category" row.
- `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx` — swap `example.tags?.includes(currentTab)` client filter for a server-side query param; add "Show archived" toggle; dim archived cards; render `TemplateCardAdminMenu`.
- `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx` — expose `…` menu slot.
- `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` — insert `CategoryChipPicker`; add conditional scope selector.
- `src/frontend/src/types/api/index.ts` — add `Category` type; extend `Template` with `categories`, `scope`, `org_id`, `archived_at`.

---

## Phase A — Backend Data Model

### Task A1: Add Alembic schema migration

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<rev>_category_and_template_rework.py`

Use `alembic revision -m "category and template rework"` to get the `<rev>` prefix. Place the file into the branch's normal revision chain by setting `down_revision` to the current head.

- [ ] **Step 1: Write the schema migration**

```python
"""category and template rework

Revision ID: <rev>
Revises: <prev>
Create Date: 2026-04-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "<rev>"
down_revision: str | None = "<prev>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. category table
    op.create_table(
        "category",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_category_name_lower",
        "category",
        [sa.text("LOWER(name)")],
        unique=True,
    )

    # 2. template_category join
    op.create_table(
        "template_category",
        sa.Column("template_id", sa.Uuid(), sa.ForeignKey("template.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_template_category_category_id", "template_category", ["category_id"])

    # 3. template.archived_at + partial index
    op.add_column("template", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_template_active",
        "template",
        ["id"],
        postgresql_where=sa.text("archived_at IS NULL"),
        sqlite_where=sa.text("archived_at IS NULL"),
    )

    # 4. template.created_by nullable
    with op.batch_alter_table("template") as batch:
        batch.alter_column("created_by", existing_type=sa.Uuid(), nullable=True)

    # 5. drop old name uniqueness, add per-scope uniqueness
    with op.batch_alter_table("template") as batch:
        batch.drop_constraint("uq_template_name", type_="unique")
    op.create_index(
        "uq_template_name_per_scope",
        "template",
        [
            sa.text("COALESCE(org_id, '00000000-0000-0000-0000-000000000000')"),
            sa.text("LOWER(name)"),
        ],
        unique=True,
    )

    # 6. rewrite scope coherence constraint
    with op.batch_alter_table("template") as batch:
        batch.drop_constraint("ck_template_scope_org_coherence", type_="check")
        batch.create_check_constraint(
            "ck_template_scope_org_coherence",
            "(scope = 'platform' AND org_id IS NULL) OR (scope = 'org' AND org_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("template") as batch:
        batch.drop_constraint("ck_template_scope_org_coherence", type_="check")
        batch.create_check_constraint(
            "ck_template_scope_org_coherence",
            "scope = 'platform' AND org_id IS NULL",
        )

    op.drop_index("uq_template_name_per_scope", table_name="template")
    op.create_unique_constraint("uq_template_name", "template", ["name"])

    with op.batch_alter_table("template") as batch:
        batch.alter_column("created_by", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_template_active", table_name="template")
    op.drop_column("template", "archived_at")

    op.drop_index("ix_template_category_category_id", table_name="template_category")
    op.drop_table("template_category")

    op.drop_index("uq_category_name_lower", table_name="category")
    op.drop_table("category")
```

- [ ] **Step 2: Run migration upgrade against a fresh SQLite DB**

Run: `uv run alembic -c src/backend/base/langflow/alembic.ini upgrade head`
Expected: no errors; `alembic current` shows the new revision.

- [ ] **Step 3: Run migration downgrade to confirm reversibility**

Run: `uv run alembic -c src/backend/base/langflow/alembic.ini downgrade -1`
Expected: no errors; schema returns to the prior revision.

- [ ] **Step 4: Re-run upgrade and commit**

Run: `uv run alembic -c src/backend/base/langflow/alembic.ini upgrade head`

```bash
git add src/backend/base/langflow/alembic/versions/<rev>_category_and_template_rework.py
git commit -m "feat(db): schema migration for categories and template rework"
```

### Task A2: Create `Category` SQLModel and Pydantic schemas

**Files:**
- Create: `src/backend/base/langflow/services/database/models/category/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/category/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_category.py`

- [ ] **Step 1: Write the failing model test**

```python
# src/backend/tests/unit/services/database/models/test_category.py
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from langflow.services.database.models.category.model import Category


def test_category_insert_and_read(session: Session) -> None:
    cat = Category(
        id=uuid4(),
        name="RAG",
        icon="database",
        color="indigo",
        description="Retrieval-augmented generation templates",
        created_by=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(cat)
    session.commit()

    loaded = session.exec(select(Category).where(Category.name == "RAG")).one()
    assert loaded.icon == "database"
    assert loaded.color == "indigo"
    assert loaded.created_by is None


def test_category_name_is_case_insensitive_unique(session: Session) -> None:
    session.add(Category(
        id=uuid4(), name="RAG", icon="database", color="indigo",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    session.commit()

    session.add(Category(
        id=uuid4(), name="rag", icon="database", color="indigo",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    with pytest.raises(Exception):  # IntegrityError (driver-specific subclass)
        session.commit()
```

- [ ] **Step 2: Run test, confirm ImportError**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_category.py -v`
Expected: FAIL with `ModuleNotFoundError: category`

- [ ] **Step 3: Implement the model**

```python
# src/backend/base/langflow/services/database/models/category/model.py
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, Relationship, SQLModel


class TemplateCategory(SQLModel, table=True):
    __tablename__ = "template_category"

    template_id: UUID = Field(
        foreign_key="template.id",
        primary_key=True,
        sa_column_kwargs={"ondelete": "CASCADE"},
    )
    category_id: UUID = Field(
        foreign_key="category.id",
        primary_key=True,
        sa_column_kwargs={"ondelete": "CASCADE"},
    )


class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=64, nullable=False)
    icon: str = Field(max_length=64, nullable=False)
    color: str = Field(max_length=16, nullable=False)
    description: str | None = Field(default=None, max_length=256)
    created_by: UUID | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )

    templates: list["Template"] = Relationship(  # noqa: F821
        back_populates="categories", link_model=TemplateCategory
    )


class CategoryCreate(BaseModel):
    name: str = PydanticField(min_length=1, max_length=64)
    icon: str = PydanticField(min_length=1, max_length=64)
    color: str = PydanticField(min_length=1, max_length=16)
    description: str | None = PydanticField(default=None, max_length=256)


class CategoryUpdate(BaseModel):
    name: str | None = PydanticField(default=None, min_length=1, max_length=64)
    icon: str | None = PydanticField(default=None, min_length=1, max_length=64)
    color: str | None = PydanticField(default=None, min_length=1, max_length=16)
    description: str | None = PydanticField(default=None, max_length=256)


class CategoryRead(BaseModel):
    id: UUID
    name: str
    icon: str
    color: str
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

```python
# src/backend/base/langflow/services/database/models/category/__init__.py
from langflow.services.database.models.category.model import (
    Category,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    TemplateCategory,
)

__all__ = [
    "Category",
    "CategoryCreate",
    "CategoryRead",
    "CategoryUpdate",
    "TemplateCategory",
]
```

- [ ] **Step 4: Re-run tests — pass**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_category.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Register the model in the models package**

Edit `src/backend/base/langflow/services/database/models/__init__.py` — add:

```python
from langflow.services.database.models.category import Category, TemplateCategory
```

to both the imports and the `__all__` list (follow the existing style there).

- [ ] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/database/models/category/ \
        src/backend/base/langflow/services/database/models/__init__.py \
        src/backend/tests/unit/services/database/models/test_category.py
git commit -m "feat(db): add Category model and TemplateCategory join"
```

### Task A3: Extend the `Template` model

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/template/model.py`
- Modify: `src/backend/base/langflow/services/database/models/template/__init__.py`
- Test: `src/backend/tests/unit/services/database/models/test_template_extensions.py` (new)

- [ ] **Step 1: Write failing tests for archived_at, scope loosening, and categories relation**

```python
# src/backend/tests/unit/services/database/models/test_template_extensions.py
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel import Session

from langflow.services.database.models.category.model import Category
from langflow.services.database.models.template.model import Template


def test_template_defaults_archived_at_to_none(session: Session) -> None:
    t = Template(
        id=uuid4(), name="Seed", description=None, icon="bot", gradient="1",
        scope="platform", org_id=None, nodes={}, edges={},
        created_by=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.add(t)
    session.commit()
    assert t.archived_at is None


def test_template_accepts_org_scope_with_org_id(session: Session, org_id) -> None:
    t = Template(
        id=uuid4(), name="Org Seed", description=None, icon="bot", gradient="1",
        scope="org", org_id=org_id, nodes={}, edges={},
        created_by=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.add(t)
    session.commit()
    assert t.scope == "org"
    assert t.org_id == org_id


def test_template_rejects_org_scope_without_org_id(session: Session) -> None:
    t = Template(
        id=uuid4(), name="Bad", description=None, icon="bot", gradient="1",
        scope="org", org_id=None, nodes={}, edges={},
        created_by=None,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.add(t)
    with pytest.raises(Exception):
        session.commit()


def test_template_categories_many_to_many(session: Session) -> None:
    cat = Category(
        id=uuid4(), name="Agents", icon="bot", color="rose",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    t = Template(
        id=uuid4(), name="Agent Starter", description=None, icon="bot", gradient="1",
        scope="platform", org_id=None, nodes={}, edges={},
        created_by=None, categories=[cat],
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.add_all([cat, t])
    session.commit()
    session.refresh(t)
    assert [c.name for c in t.categories] == ["Agents"]
```

(`session` and `org_id` fixtures are assumed from `conftest.py`; if a per-test Organization fixture doesn't exist, wrap inserts to create one via the existing `Organization` model — see `src/backend/tests/conftest.py` for patterns.)

- [ ] **Step 2: Run tests — confirm failure**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_template_extensions.py -v`
Expected: all fail (`archived_at` attribute missing, scope constraint still frozen).

- [ ] **Step 3: Edit `template/model.py` — add `archived_at`, loosen `created_by`, add relationship**

Locate the `Template(SQLModel, table=True)` class. Apply these edits:

```python
# add near other field declarations
archived_at: datetime | None = Field(default=None)

# change created_by from non-null UUID to nullable
created_by: UUID | None = Field(default=None, foreign_key="user.id")

# add relationship (requires import of TemplateCategory from the join table)
from langflow.services.database.models.category.model import TemplateCategory  # top of file
# inside Template class:
categories: list["Category"] = Relationship(  # noqa: F821 — forward ref
    back_populates="templates", link_model=TemplateCategory
)
```

Also update the `__table_args__` check constraint value to:

```python
CheckConstraint(
    "(scope = 'platform' AND org_id IS NULL) OR (scope = 'org' AND org_id IS NOT NULL)",
    name="ck_template_scope_org_coherence",
),
```

Remove any Phase-1 comment/assertion that pins scope to `"platform"`.

Update Pydantic schemas in the same file:
- `TemplateCreate`: add `scope: Literal["platform", "org"] = "platform"`, `org_id: UUID | None = None`, `category_ids: list[UUID] = []`.
- `TemplateUpdate`: add `category_ids: list[UUID] | None = None` (None = leave unchanged; `[]` = clear all tags).
- `TemplateRead` / `TemplateReadDetail`: add `archived_at: datetime | None`, `categories: list[CategoryRead]`.

- [ ] **Step 4: Run tests — pass**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_template_extensions.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/database/models/template/ \
        src/backend/tests/unit/services/database/models/test_template_extensions.py
git commit -m "feat(db): extend Template with archived_at, org scope, categories relation"
```

---

## Phase B — Backend API: Categories

### Fixtures prelude (shared by B and C tasks)

Several tests below reference fixtures like `seed_categories`, `platform_admin_headers`, `seed_own_org_template`, etc. Before starting the first API test, extend `src/backend/tests/conftest.py` (or create a narrower `src/backend/tests/unit/api/v1/conftest.py`) with:

- `platform_admin_headers`: creates a user with `is_platform_admin=True`, returns auth headers (pattern off the existing `logged_in_headers` fixture).
- `other_user_headers`: second logged-in regular user, for "different-user forbidden" tests.
- `seed_categories`: inserts three `Category` rows with names chosen to test alpha sort (e.g., "Banana", "apple", "Cherry").
- `seed_category_with_one_template`: inserts one category + one template tagged with it; yields `(category_id, template_id)`.
- `seed_platform_template`, `seed_archived_platform_template`, `seed_own_org_template`, `seed_own_archived_org_template`: single-row factories following the existing template test-fixture style. See `src/backend/tests/unit/api/v1/` for existing template fixtures to mirror.

Treat these as part of the TDD for each task where first referenced — write the fixture when the test first needs it.

### Task B1: Read endpoints (`GET /categories`, `GET /categories/{id}`)

**Files:**
- Create: `src/backend/base/langflow/api/v1/categories.py`
- Test: `src/backend/tests/unit/api/v1/test_categories.py`

- [ ] **Step 1: Write failing list and get tests**

```python
# src/backend/tests/unit/api/v1/test_categories.py
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_categories_returns_alpha_sorted(
    client: AsyncClient, logged_in_headers: dict, seed_categories
) -> None:
    res = await client.get("/api/v1/categories/", headers=logged_in_headers)
    assert res.status_code == 200
    names = [c["name"] for c in res.json()]
    assert names == sorted(names, key=str.lower)


@pytest.mark.asyncio
async def test_get_category_by_id(
    client: AsyncClient, logged_in_headers: dict, seed_categories
) -> None:
    any_id = seed_categories[0].id
    res = await client.get(f"/api/v1/categories/{any_id}", headers=logged_in_headers)
    assert res.status_code == 200
    assert res.json()["id"] == str(any_id)


@pytest.mark.asyncio
async def test_get_category_404(client: AsyncClient, logged_in_headers: dict) -> None:
    res = await client.get(f"/api/v1/categories/{uuid4()}", headers=logged_in_headers)
    assert res.status_code == 404
```

(`seed_categories` and `logged_in_headers` fixtures: add to the test file or `conftest.py`. Seed fixture inserts 3 categories with out-of-order names.)

- [ ] **Step 2: Run, confirm 404s or ImportError**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_categories.py -v`
Expected: FAIL (router not registered).

- [ ] **Step 3: Create the router with read endpoints**

```python
# src/backend/base/langflow/api/v1/categories.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.database.models.category.model import Category, CategoryRead

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=list[CategoryRead])
async def list_categories(
    _user: CurrentActiveUser,
    session: DbSession,
) -> list[Category]:
    stmt = select(Category).order_by(Category.name)
    return list((await session.exec(stmt)).all())


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: UUID,
    _user: CurrentActiveUser,
    session: DbSession,
) -> Category:
    obj = await session.get(Category, category_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    return obj
```

Register the router: edit wherever `templates_router` is included in `src/backend/base/langflow/api/v1/__init__.py` and add `from .categories import router as categories_router` + `router.include_router(categories_router)`.

- [ ] **Step 4: Run tests — pass**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_categories.py -v`
Expected: the three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/categories.py \
        src/backend/base/langflow/api/v1/__init__.py \
        src/backend/tests/unit/api/v1/test_categories.py
git commit -m "feat(api): GET /categories list and get"
```

### Task B2: Write endpoints (`POST`, `PATCH`, `DELETE`)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/categories.py`
- Modify: `src/backend/tests/unit/api/v1/test_categories.py`

- [ ] **Step 1: Write failing tests for create/patch/delete + platform-admin gate**

```python
@pytest.mark.asyncio
async def test_create_category_requires_platform_admin(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    res = await client.post(
        "/api/v1/categories/",
        headers=logged_in_headers,  # regular user
        json={"name": "NewCat", "icon": "bot", "color": "slate"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_category_as_admin(
    client: AsyncClient, platform_admin_headers: dict
) -> None:
    res = await client.post(
        "/api/v1/categories/",
        headers=platform_admin_headers,
        json={"name": "NewCat", "icon": "bot", "color": "slate"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "NewCat"


@pytest.mark.asyncio
async def test_create_category_duplicate_name_conflict(
    client: AsyncClient, platform_admin_headers: dict
) -> None:
    body = {"name": "Dup", "icon": "bot", "color": "slate"}
    await client.post("/api/v1/categories/", headers=platform_admin_headers, json=body)
    res = await client.post(
        "/api/v1/categories/",
        headers=platform_admin_headers,
        json={**body, "name": "dup"},  # different case, same lower()
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_patch_category(
    client: AsyncClient, platform_admin_headers: dict, seed_categories
) -> None:
    cid = seed_categories[0].id
    res = await client.patch(
        f"/api/v1/categories/{cid}",
        headers=platform_admin_headers,
        json={"color": "amber"},
    )
    assert res.status_code == 200
    assert res.json()["color"] == "amber"


@pytest.mark.asyncio
async def test_delete_category_cascades_links(
    client: AsyncClient,
    platform_admin_headers: dict,
    seed_category_with_one_template,
) -> None:
    cid, tid = seed_category_with_one_template
    res = await client.delete(f"/api/v1/categories/{cid}", headers=platform_admin_headers)
    assert res.status_code == 204
    # template survives
    t = await client.get(f"/api/v1/templates/{tid}", headers=platform_admin_headers)
    assert t.status_code == 200
    # template has no categories
    assert t.json().get("categories") == []
```

- [ ] **Step 2: Run — expect failures**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_categories.py -v`

- [ ] **Step 3: Implement the write endpoints**

Append to `categories.py`:

```python
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from langflow.api.utils.core import PlatformAdmin
from langflow.services.database.models.category.model import (
    CategoryCreate,
    CategoryUpdate,
)


@router.post(
    "/",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    payload: CategoryCreate,
    admin: PlatformAdmin,
    session: DbSession,
) -> Category:
    obj = Category(
        name=payload.name,
        icon=payload.icon,
        color=payload.color,
        description=payload.description,
        created_by=admin.id,
    )
    session.add(obj)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category name already exists")
    await session.refresh(obj)
    return obj


@router.patch("/{category_id}", response_model=CategoryRead)
async def patch_category(
    category_id: UUID,
    payload: CategoryUpdate,
    _admin: PlatformAdmin,
    session: DbSession,
) -> Category:
    obj = await session.get(Category, category_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(obj, key, value)
    obj.updated_at = datetime.now(timezone.utc)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Category name already exists")
    await session.refresh(obj)
    return obj


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    _admin: PlatformAdmin,
    session: DbSession,
) -> None:
    obj = await session.get(Category, category_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    await session.delete(obj)
    await session.commit()
```

- [ ] **Step 4: Run tests — pass**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_categories.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/categories.py \
        src/backend/tests/unit/api/v1/test_categories.py
git commit -m "feat(api): POST/PATCH/DELETE /categories with platform-admin gate"
```

---

## Phase C — Backend API: Template Extensions

### Task C1: Permission helper `user_can_edit_template`

**Files:**
- Create: `src/backend/base/langflow/api/v1/_template_permissions.py`
- Test: `src/backend/tests/unit/api/v1/test_template_permissions.py`

- [ ] **Step 1: Test**

```python
# src/backend/tests/unit/api/v1/test_template_permissions.py
from uuid import uuid4

from langflow.api.v1._template_permissions import user_can_edit_template


def _make_user(*, id=None, is_platform_admin=False, org_admin_of=None):
    class _U:
        def __init__(self):
            self.id = id or uuid4()
            self.is_platform_admin = is_platform_admin
            self._org_admin_of = set(org_admin_of or [])

        def is_org_admin(self, org_id):
            return org_id in self._org_admin_of
    return _U()


def _make_template(*, scope="platform", org_id=None, created_by=None):
    class _T:
        pass
    t = _T()
    t.scope = scope
    t.org_id = org_id
    t.created_by = created_by
    return t


def test_platform_admin_can_edit_any() -> None:
    u = _make_user(is_platform_admin=True)
    assert user_can_edit_template(u, _make_template()) is True
    assert user_can_edit_template(u, _make_template(scope="org", org_id=uuid4())) is True


def test_non_admin_cannot_edit_platform() -> None:
    u = _make_user()
    assert user_can_edit_template(u, _make_template()) is False


def test_org_admin_can_edit_own_org_template() -> None:
    org = uuid4()
    u = _make_user(org_admin_of=[org])
    assert user_can_edit_template(u, _make_template(scope="org", org_id=org)) is True


def test_creator_can_edit_own_org_template() -> None:
    uid = uuid4()
    org = uuid4()
    u = _make_user(id=uid)
    t = _make_template(scope="org", org_id=org, created_by=uid)
    assert user_can_edit_template(u, t) is True


def test_other_member_cannot_edit() -> None:
    org = uuid4()
    u = _make_user()  # not admin, not creator
    t = _make_template(scope="org", org_id=org, created_by=uuid4())
    assert user_can_edit_template(u, t) is False
```

- [ ] **Step 2: Run — fail (module missing)**

- [ ] **Step 3: Implement**

```python
# src/backend/base/langflow/api/v1/_template_permissions.py
from __future__ import annotations


def user_can_edit_template(user, template) -> bool:
    if getattr(user, "is_platform_admin", False):
        return True
    if template.scope == "platform":
        return False
    # org-scoped
    if template.org_id is None:
        return False
    if hasattr(user, "is_org_admin") and user.is_org_admin(template.org_id):
        return True
    return template.created_by == user.id
```

If the `User` class does not yet have `is_org_admin`, add it as a SQLModel-level `@property` that checks the `Membership` table. See `src/backend/base/langflow/services/database/models/membership/model.py` and pattern the helper there or in `api/utils/core.py`. The function here tolerates its absence (returns False) so tests and initial callers work.

- [ ] **Step 4: Run tests — pass. Commit.**

```bash
git add src/backend/base/langflow/api/v1/_template_permissions.py \
        src/backend/tests/unit/api/v1/test_template_permissions.py
git commit -m "feat(api): user_can_edit_template permission helper"
```

### Task C2: Extend `GET /templates` with `category`, `scope`, `include_archived`, `created_by_me`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/templates.py`
- Test: `src/backend/tests/unit/api/v1/test_templates_list.py` (new)

- [ ] **Step 1: Write tests**

```python
# tests cover:
# - default list excludes archived
# - ?category=RAG returns only templates tagged RAG
# - ?scope=platform excludes org templates
# - ?created_by_me=true returns only user-created rows
# - non-admin passing ?include_archived=true without ?created_by_me=true -> 403
# - non-admin ?created_by_me=true&include_archived=true returns own archived
# - admin ?include_archived=true returns archived across scopes

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_excludes_archived_by_default(
    client: AsyncClient, logged_in_headers: dict, seed_one_archived_platform_template
) -> None:
    res = await client.get("/api/v1/templates/", headers=logged_in_headers)
    ids = [t["id"] for t in res.json()]
    assert str(seed_one_archived_platform_template.id) not in ids


# … (full tests for each case above; follow the same shape) …
```

Flesh out each scenario following the list. Use existing fixtures where they exist; add minimal new ones for org-scoped templates and archived templates.

- [ ] **Step 2: Run — fail. Implement.**

In `templates.py`, update the `list_templates` handler signature to:

```python
from typing import Literal

@router.get("/", response_model=list[TemplateRead])
async def list_templates(
    session: DbSession,
    user: CurrentActiveUser,
    category: str | None = None,
    scope: Literal["platform", "org", "all"] = "all",
    created_by_me: bool = False,
    include_archived: bool = False,
) -> list[Template]:
    if include_archived and not user.is_platform_admin and not created_by_me:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="include_archived requires admin or created_by_me")

    stmt = select(Template)
    if not include_archived:
        stmt = stmt.where(Template.archived_at.is_(None))
    if scope != "all":
        stmt = stmt.where(Template.scope == scope)
    if created_by_me:
        stmt = stmt.where(Template.created_by == user.id)
    if category is not None:
        stmt = (
            stmt.join(TemplateCategory, TemplateCategory.template_id == Template.id)
                .join(Category, Category.id == TemplateCategory.category_id)
                .where(func.lower(Category.name) == category.lower())
        )
    stmt = stmt.order_by(Template.name)
    return list((await session.exec(stmt)).unique().all())
```

Add required imports (`TemplateCategory`, `Category`, `func`, `Literal`) at top.

- [ ] **Step 3: Run tests — pass. Commit.**

```bash
git add src/backend/base/langflow/api/v1/templates.py \
        src/backend/tests/unit/api/v1/test_templates_list.py
git commit -m "feat(api): GET /templates query params (category, scope, created_by_me, include_archived)"
```

### Task C3: Extend `POST /templates` with `scope`, `org_id`, `category_ids`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/templates.py`
- Test: `src/backend/tests/unit/api/v1/test_templates_create.py` (new)

- [ ] **Step 1: Write tests**

Cover:
- Platform admin can create `scope=platform`.
- Non-admin creating `scope=platform` → 403.
- Org member can create `scope=org` with their `org_id` → 201; backend rejects an `org_id` the user is not a member of → 403.
- `category_ids` referencing unknown ids → 422.
- Successful create persists `template_category` links.

- [ ] **Step 2: Run — fail. Implement.**

Update `create_template` to:
- Reject `scope="platform"` unless `user.is_platform_admin`.
- Reject `scope="org"` if `org_id` is not in the user's memberships (query `Membership`).
- Insert `Template`, then bulk-insert `TemplateCategory` rows for each `category_id`. If any id is missing, raise 422.

Code snippet for the category-ids lookup:

```python
if payload.category_ids:
    stmt = select(Category.id).where(Category.id.in_(payload.category_ids))
    found = {row for row in (await session.exec(stmt)).all()}
    missing = set(payload.category_ids) - found
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown category_ids: {sorted(str(m) for m in missing)}",
        )
    session.add_all(
        TemplateCategory(template_id=template.id, category_id=cid)
        for cid in payload.category_ids
    )
```

- [ ] **Step 3: Run — pass. Commit.**

```bash
git add src/backend/base/langflow/api/v1/templates.py \
        src/backend/tests/unit/api/v1/test_templates_create.py
git commit -m "feat(api): POST /templates accepts scope, org_id, category_ids"
```

### Task C4: Extend `PATCH /templates` with `category_ids` (full-replace)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/templates.py`
- Test: `src/backend/tests/unit/api/v1/test_templates_update.py` (new)

- [ ] **Step 1: Write tests covering:**
- Non-editor (per `user_can_edit_template`) → 403.
- `category_ids=[]` clears all tags.
- `category_ids=[a, b]` replaces tag set (previous tags removed, new tags added).
- `category_ids=None` (key omitted from payload) leaves tags untouched.
- Unknown category id → 422.

- [ ] **Step 2: Fail. Implement.**

Update `update_template` to:
- Use `user_can_edit_template` for the 403 gate.
- When `payload.category_ids is not None`:
  - Validate all ids exist (reuse the lookup from C3).
  - Delete all existing `TemplateCategory` rows for this template: `await session.exec(delete(TemplateCategory).where(TemplateCategory.template_id == t.id))`.
  - Insert new rows.

- [ ] **Step 3: Pass. Commit.**

```bash
git commit -m "feat(api): PATCH /templates replaces category_ids atomically"
```

### Task C5: Add `POST /templates/{id}/archive` and `/unarchive`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/templates.py`
- Test: `src/backend/tests/unit/api/v1/test_template_archive.py` (new)

- [ ] **Step 1: Tests**

```python
@pytest.mark.asyncio
async def test_archive_sets_archived_at(
    client: AsyncClient, logged_in_headers: dict, seed_own_org_template
) -> None:
    tid = seed_own_org_template.id
    r = await client.post(f"/api/v1/templates/{tid}/archive", headers=logged_in_headers)
    assert r.status_code == 200
    r2 = await client.get(f"/api/v1/templates/{tid}", headers=logged_in_headers)
    assert r2.json()["archived_at"] is not None


@pytest.mark.asyncio
async def test_archive_idempotent(client, logged_in_headers, seed_own_org_template):
    tid = seed_own_org_template.id
    await client.post(f"/api/v1/templates/{tid}/archive", headers=logged_in_headers)
    r = await client.post(f"/api/v1/templates/{tid}/archive", headers=logged_in_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_unarchive_clears_archived_at(client, logged_in_headers, seed_own_archived_org_template):
    tid = seed_own_archived_org_template.id
    r = await client.post(f"/api/v1/templates/{tid}/unarchive", headers=logged_in_headers)
    assert r.status_code == 200
    r2 = await client.get(f"/api/v1/templates/{tid}", headers=logged_in_headers)
    assert r2.json()["archived_at"] is None


@pytest.mark.asyncio
async def test_archive_rejects_non_editor(client, other_user_headers, seed_platform_template):
    tid = seed_platform_template.id
    r = await client.post(f"/api/v1/templates/{tid}/archive", headers=other_user_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run — fail. Implement.**

```python
@router.post("/{template_id}/archive", response_model=TemplateRead)
async def archive_template(
    template_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> Template:
    t = await session.get(Template, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
    if not user_can_edit_template(user, t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if t.archived_at is None:
        t.archived_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(t)
    return t


@router.post("/{template_id}/unarchive", response_model=TemplateRead)
async def unarchive_template(
    template_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> Template:
    t = await session.get(Template, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
    if not user_can_edit_template(user, t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if t.archived_at is not None:
        t.archived_at = None
        await session.commit()
        await session.refresh(t)
    return t
```

- [ ] **Step 3: Pass. Commit.**

```bash
git commit -m "feat(api): archive and unarchive endpoints on /templates/{id}"
```

### Task C6: Replace soft-delete with hard-delete + 409 guard

**Files:**
- Modify: `src/backend/base/langflow/api/v1/templates.py`
- Test: `src/backend/tests/unit/api/v1/test_templates_delete.py` (new)

- [ ] **Step 1: Tests**

Cover:
- Delete succeeds (204) when no Flow references the template.
- Delete returns 409 with body `{"referencing_flow_ids": [...]}` when at least one Flow has `based_on_template_flow_id == template.id`.
- Non-editor → 403.

- [ ] **Step 2: Fail. Rewrite `soft_delete_template` into `delete_template`.**

```python
from langflow.services.database.models.flow.model import Flow


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> Response:
    t = await session.get(Template, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Template not found")
    if not user_can_edit_template(user, t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")

    stmt = select(Flow.id).where(Flow.based_on_template_flow_id == template_id)
    referencing = [str(fid) for fid in (await session.exec(stmt)).all()]
    if referencing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"referencing_flow_ids": referencing},
        )

    await session.delete(t)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 3: Pass. Commit.**

```bash
git commit -m "feat(api): hard DELETE /templates/{id} with 409 guard on active flows"
```

### Task C7: Flow-creation 422 guard when template is archived

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (or wherever `POST /flows` lives — `endpoints.py` if the explore identified that route there)
- Test: `src/backend/tests/unit/test_flows_archived_template.py` (new)

- [ ] **Step 1: Test**

```python
@pytest.mark.asyncio
async def test_create_flow_from_archived_template_returns_422(
    client: AsyncClient, logged_in_headers: dict, seed_archived_platform_template
) -> None:
    r = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={"name": "x", "based_on_template_id": str(seed_archived_platform_template.id)},
    )
    assert r.status_code == 422
    assert "archived" in r.json().get("detail", "").lower()
```

- [ ] **Step 2: Fail. Implement.**

Near the top of the POST `/flows` handler (before the `flow = Flow(...)` construction), insert:

```python
if payload.based_on_template_id is not None:
    t = await session.get(Template, payload.based_on_template_id)
    if t is not None and t.archived_at is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template is archived",
        )
```

- [ ] **Step 3: Pass. Commit.**

```bash
git commit -m "feat(api): reject flow creation when based_on template is archived"
```

---

## Phase D — Data Migration & Starter JSON Removal

### Task D1: Bundle starter JSON files inside the Alembic revision

**Files:**
- Modify: `src/backend/base/langflow/alembic/versions/<rev>_category_and_template_rework.py`

The revision needs the JSON content even after the source files are deleted. Create a sibling package directory for this revision holding the fixtures.

- [ ] **Step 1: Copy every starter JSON to a revision-local fixtures folder**

```bash
mkdir -p src/backend/base/langflow/alembic/versions/<rev>_fixtures
cp src/backend/base/langflow/initial_setup/starter_projects/*.json \
   src/backend/base/langflow/alembic/versions/<rev>_fixtures/
```

- [ ] **Step 2: Commit the fixture snapshot**

```bash
git add src/backend/base/langflow/alembic/versions/<rev>_fixtures/
git commit -m "chore(migration): snapshot starter JSON fixtures for data migration"
```

### Task D2: Data-migration seed + JSON import

**Files:**
- Modify: `src/backend/base/langflow/alembic/versions/<rev>_category_and_template_rework.py`
- Test: `src/backend/tests/unit/alembic/test_category_migration.py` (new)

- [ ] **Step 1: Write the migration test**

```python
# src/backend/tests/unit/alembic/test_category_migration.py
from alembic import command
from alembic.config import Config
from sqlmodel import Session, select

from langflow.services.database.models.category.model import Category
from langflow.services.database.models.template.model import Template


def test_category_migration_seeds_eight_categories(alembic_config: Config, db_session: Session) -> None:
    command.upgrade(alembic_config, "head")
    names = sorted(n for n, in db_session.exec(select(Category.name)).all())
    assert names == [
        "Agents", "Assistants", "Classification", "Coding",
        "Content Generation", "Prompting", "Q&A", "RAG",
    ]


def test_category_migration_imports_all_starter_json(alembic_config, db_session):
    command.upgrade(alembic_config, "head")
    templates = db_session.exec(select(Template).where(Template.scope == "platform")).all()
    # every JSON fixture produced a Template row
    import pathlib
    repo_root = pathlib.Path(__file__).resolve().parents[4]  # src/backend/tests/unit/alembic/test_*.py → repo root
    fixture_dir = repo_root / "src/backend/base/langflow/alembic/versions" / f"{revision}_fixtures"
    expected = {p.stem for p in fixture_dir.glob("*.json")}
    assert {t.name for t in templates} >= expected


def test_category_migration_tags_each_template(alembic_config, db_session):
    command.upgrade(alembic_config, "head")
    t = db_session.exec(select(Template).where(Template.name == "Basic Prompting")).one()
    assert {c.name for c in t.categories} == {"Prompting"}
```

- [ ] **Step 2: Run — fail**

- [ ] **Step 3: Append `upgrade()` with data steps**

In the same revision file, extend `upgrade()` after the schema changes with:

```python
import json
import pathlib
import uuid
from datetime import datetime, timezone

FIXTURE_DIR = pathlib.Path(__file__).parent / f"{revision}_fixtures"

_CATEGORY_SEEDS: list[dict[str, str]] = [
    {"name": "Assistants",         "from_tag": "assistants",         "icon": "users-round",    "color": "slate"},
    {"name": "Classification",     "from_tag": "classification",     "icon": "tag",            "color": "amber"},
    {"name": "Coding",             "from_tag": "coding",             "icon": "code",           "color": "violet"},
    {"name": "Content Generation", "from_tag": "content-generation", "icon": "book-open",      "color": "emerald"},
    {"name": "Q&A",                "from_tag": "q-a",                "icon": "help-circle",    "color": "sky"},
    {"name": "Prompting",          "from_tag": "chatbots",           "icon": "message-square", "color": "fuchsia"},
    {"name": "RAG",                "from_tag": "rag",                "icon": "database",       "color": "indigo"},
    {"name": "Agents",             "from_tag": "agents",             "icon": "bot",            "color": "rose"},
]


def _data_upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # Seed categories (idempotent).
    tag_to_category_id: dict[str, uuid.UUID] = {}
    for seed in _CATEGORY_SEEDS:
        existing = conn.execute(
            sa.text("SELECT id FROM category WHERE LOWER(name) = LOWER(:name)"),
            {"name": seed["name"]},
        ).first()
        if existing:
            tag_to_category_id[seed["from_tag"]] = existing[0]
            continue
        new_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO category (id, name, icon, color, created_at, updated_at) "
                "VALUES (:id, :n, :i, :c, :ts, :ts)"
            ),
            {"id": new_id, "n": seed["name"], "i": seed["icon"], "c": seed["color"], "ts": now},
        )
        tag_to_category_id[seed["from_tag"]] = new_id

    # Seed templates from fixtures (idempotent by lower(name)).
    for json_path in sorted(FIXTURE_DIR.glob("*.json")):
        data = json.loads(json_path.read_text())
        name = data["name"]
        existing = conn.execute(
            sa.text(
                "SELECT id FROM template WHERE LOWER(name) = LOWER(:name) AND scope = 'platform' AND org_id IS NULL"
            ),
            {"name": name},
        ).first()
        if existing:
            continue
        tid = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO template (id, name, description, icon, gradient, scope, org_id, nodes, edges, "
                "created_by, created_at, updated_at) "
                "VALUES (:id, :n, :d, :icon, :g, 'platform', NULL, :nodes, :edges, NULL, :ts, :ts)"
            ),
            {
                "id": tid,
                "n": name,
                "d": data.get("description"),
                "icon": data.get("icon") or "bot",
                "g": data.get("gradient") or "1",
                "nodes": json.dumps(data.get("data", {}).get("nodes", [])),
                "edges": json.dumps(data.get("data", {}).get("edges", [])),
                "ts": now,
            },
        )
        for tag in data.get("tags", []):
            if tag not in tag_to_category_id:
                raise RuntimeError(
                    f"Starter JSON {json_path.name} uses unknown tag {tag!r}; "
                    f"add it to _CATEGORY_SEEDS in this revision."
                )
            conn.execute(
                sa.text(
                    "INSERT INTO template_category (template_id, category_id) VALUES (:t, :c)"
                ),
                {"t": tid, "c": tag_to_category_id[tag]},
            )


def upgrade() -> None:
    # … existing schema steps from Task A1 …
    _data_upgrade()
```

- [ ] **Step 4: Run tests — pass. Commit.**

```bash
git commit -m "feat(migration): seed categories and import starter JSON into Template"
```

### Task D3: Delete the shadow starter Flow rows

**Files:**
- Modify: `src/backend/base/langflow/alembic/versions/<rev>_category_and_template_rework.py`
- Modify: `src/backend/tests/unit/alembic/test_category_migration.py`

- [ ] **Step 1: Add a test asserting starter Flow rows are gone after upgrade**

```python
def test_old_starter_flow_rows_are_deleted(alembic_config, db_session):
    # Before upgrade: insert a Flow row simulating a legacy starter (folder_id = starter folder).
    starter_folder_id = db_session.exec(
        sa.text("SELECT id FROM folder WHERE name = 'Starter Projects'")
    ).scalar()
    from langflow.services.database.models.flow.model import Flow
    dummy = Flow(id=uuid4(), name="Legacy Starter", folder_id=starter_folder_id, data={}, user_id=None)
    db_session.add(dummy); db_session.commit()

    command.upgrade(alembic_config, "head")

    remaining = db_session.exec(
        sa.text("SELECT COUNT(*) FROM flow WHERE folder_id = :f"),
        {"f": starter_folder_id},
    ).scalar()
    assert remaining == 0
```

Seed pattern assumes the starter folder exists pre-migration. If the upgrade runs against a schema where that folder does not exist yet, guard the deletion with a folder-existence check.

- [ ] **Step 2: Fail. Extend `_data_upgrade()`**

```python
# At the end of _data_upgrade():
conn.execute(
    sa.text(
        "DELETE FROM flow WHERE folder_id IN "
        "(SELECT id FROM folder WHERE name = :n)"
    ),
    {"n": "Starter Projects"},  # match STARTER_FOLDER_NAME exactly
)
conn.execute(
    sa.text("DELETE FROM folder WHERE name = :n"),
    {"n": "Starter Projects"},
)
```

Verify the folder name matches `STARTER_FOLDER_NAME` in `setup.py:41` *before* committing; use that constant's value literally.

- [ ] **Step 3: Pass. Commit.**

```bash
git commit -m "feat(migration): drop shadow starter Flow rows after importing templates"
```

### Task D4: Remove the runtime starter loader + delete JSON source files

**Files:**
- Modify: `src/backend/base/langflow/initial_setup/setup.py`
- Delete: `src/backend/base/langflow/initial_setup/starter_projects/*.json`
- Modify: any caller importing the removed helpers (check with `rg "load_starter_projects|create_or_update_starter_projects|get_or_create_starter_folder" src/`)

- [ ] **Step 1: Confirm no callers remain outside setup.py itself**

Run: `rg -n "load_starter_projects|create_or_update_starter_projects|get_or_create_starter_folder"`

Expected output: references only in `setup.py` + anywhere these are scheduled (e.g., startup hooks). Update those call sites to remove the invocations.

- [ ] **Step 2: Delete the loader helpers from `setup.py`**

Locate and remove: `load_starter_projects` (~line 557), `create_or_update_starter_projects` (~line 1110), `create_new_project` (~line 702), `get_or_create_starter_folder` (~line 748), and any module-level `STARTER_FOLDER_NAME` constant and associated imports that become unused.

Grep for the removed function names in the whole repo one more time after deletion to confirm no dangling callers:

Run: `rg -n "load_starter_projects|create_or_update_starter_projects|create_new_project|get_or_create_starter_folder"`

Expected: only occurrences are in the Alembic revision fixture folder path string (`"<rev>_fixtures"` doesn't match these) and tests we're about to update.

- [ ] **Step 3: Delete the JSON source files**

```bash
git rm src/backend/base/langflow/initial_setup/starter_projects/*.json
```

- [ ] **Step 4: Update `src/backend/tests/unit/test_webhook.py` and other tests that depend on the starter loader**

Use `rg "starter_projects" src/backend/tests/`. For each failing test, replace dependence on the loader with an explicit fixture that creates a `Template` row directly. Pattern:

```python
template = Template(
    id=uuid4(), name="Test Template", description="…", icon="bot", gradient="1",
    scope="platform", org_id=None, nodes={}, edges={},
    created_by=None, created_at=…, updated_at=…,
)
session.add(template)
await session.commit()
```

- [ ] **Step 5: Run the full backend test suite**

Run: `uv run pytest src/backend/tests/ -x`
Expected: green, or only failures clearly introduced by test-fixture edits; iterate until green.

- [ ] **Step 6: Commit**

```bash
git commit -m "chore: remove runtime starter loader and JSON fixtures (now DB-resident)"
```

---

## Phase E — Frontend: Categories API & Hardcoded Removal

### Task E1: Add category query hooks

**Files:**
- Create: `src/frontend/src/controllers/API/queries/categories/{use-list-categories,use-create-category,use-update-category,use-delete-category}.ts`
- Create: `src/frontend/src/controllers/API/queries/categories/index.ts`
- Modify: `src/frontend/src/types/api/index.ts` (new `Category` type)

- [ ] **Step 1: Add the `Category` type**

```ts
// src/frontend/src/types/api/index.ts — append
export type Category = {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};
```

Extend the existing `Template` type with:

```ts
categories: Category[];
archived_at: string | null;
scope: "platform" | "org";
org_id: string | null;
```

- [ ] **Step 2: Write the list-categories hook**

```ts
// src/frontend/src/controllers/API/queries/categories/use-list-categories.ts
import { useQueryFunctionType } from "@/types/api";
import { UseRequestProcessor } from "../services/request-processor";
import { Category } from "@/types/api";

export const CATEGORIES_QUERY_KEY = ["categories"] as const;

export const useListCategories: useQueryFunctionType<undefined, Category[]> = (
  options,
) => {
  const { query } = UseRequestProcessor();
  return query(
    CATEGORIES_QUERY_KEY,
    async () => {
      const res = await fetch("/api/v1/categories/");
      if (!res.ok) throw new Error("Failed to list categories");
      return (await res.json()) as Category[];
    },
    options,
  );
};
```

Repeat the pattern for `useCreateCategory`, `useUpdateCategory`, `useDeleteCategory`, each invalidating `CATEGORIES_QUERY_KEY` on success. Match the exact call shape of the existing template hooks (they use `UseRequestProcessor().mutate` — see `use-create-template.ts`).

Re-export from `index.ts`:

```ts
export { useListCategories, CATEGORIES_QUERY_KEY } from "./use-list-categories";
export { useCreateCategory } from "./use-create-category";
export { useUpdateCategory } from "./use-update-category";
export { useDeleteCategory } from "./use-delete-category";
```

- [ ] **Step 3: Snapshot / smoke test that the hook compiles**

Run: `npm --prefix src/frontend run typecheck`
Expected: no new TS errors.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/controllers/API/queries/categories/ \
        src/frontend/src/types/api/index.ts
git commit -m "feat(frontend): category query hooks"
```

### Task E2: Replace hardcoded `Category[]` in the templates modal

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/index.tsx`

- [ ] **Step 1: Delete the hardcoded array (current lines ~100-134)**

Remove the `const categories: Category[] = [ … "Use Cases" … "Methodology" … ]` constant entirely. Remove its accompanying type definition if no longer used by `navComponent`.

- [ ] **Step 2: Fetch categories via the hook**

Near the top of the component body:

```tsx
const { data: apiCategories = [], isPending: isLoadingCategories } = useListCategories();
```

Construct the sidebar input from `apiCategories`, plus fixed permanent rows ("Get started", "All templates", "Saved Templates") prepended. Alpha-sort by `name` (server already does, but sort defensively).

- [ ] **Step 3: Pass the sidebar input into `<Nav />` and `<TemplateContentComponent />`**

Update `<Nav categories={…} />` to accept the new shape (a flat list after the 3 permanent rows). If `navComponent` today expects grouped `{title, items}` sections, refactor its prop type inline in this step to a flat `items: Category[]` — further admin affordances on the nav are added in Task F3.

- [ ] **Step 4: Typecheck and lint**

Run: `npm --prefix src/frontend run typecheck && npm --prefix src/frontend run lint`

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(frontend): templates modal pulls categories from API"
```

### Task E3: Switch `TemplateContentComponent` filter to server-side `?category=`

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx`
- Modify: the template list hook (`use-list-templates.ts`) to accept a `category` query param.

- [ ] **Step 1: Extend `useListTemplates` to pass optional query params**

Current signature likely takes no args. Change to accept `{ category?: string; scope?: "platform"|"org"|"all"; created_by_me?: boolean; include_archived?: boolean }`. Encode into the request URL.

- [ ] **Step 2: In `TemplateContentComponent`, remove the client-side tag filter**

Delete: `example.tags?.includes(currentTab ?? "")`. Instead, call `useListTemplates({ category: currentTab === "all-templates" ? undefined : currentTab, created_by_me: currentTab === "saved-templates" ? true : undefined })`.

- [ ] **Step 3: Verify UI**

Start the frontend dev server and the backend:

Run (split terminals or `run_in_background`):
- Backend: `uv run langflow run --backend-only`
- Frontend: `npm --prefix src/frontend start`

Open the templates modal, click several categories, confirm the grid narrows correctly. Switch to "Saved Templates", confirm it only shows user-created rows.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(frontend): use server-side category filter in templates modal"
```

---

## Phase F — Frontend Admin UX: Category CRUD

### Task F1: `useIsPlatformAdmin` hook + admin-gate rendering

**Files:**
- Create: `src/frontend/src/hooks/use-is-platform-admin.ts`

- [ ] **Step 1: Implement the hook**

```ts
// src/frontend/src/hooks/use-is-platform-admin.ts
import useAuthStore from "@/stores/authStore";

export function useIsPlatformAdmin(): boolean {
  return useAuthStore((s) => !!s.userData?.is_platform_admin);
}
```

- [ ] **Step 2: Use it in the templates modal**

In `templatesModal/index.tsx`, read `const isAdmin = useIsPlatformAdmin();` and pass as a prop to `navComponent` and `TemplateContentComponent`.

- [ ] **Step 3: Commit**

```bash
git add src/frontend/src/hooks/use-is-platform-admin.ts src/frontend/src/modals/templatesModal/index.tsx
git commit -m "feat(frontend): useIsPlatformAdmin hook and gate propagation"
```

### Task F2: `CategoryEditPopover` with icon + color picker

**Files:**
- Create: `src/frontend/src/modals/templatesModal/components/CategoryEditPopover/index.tsx`
- Test: `src/frontend/tests/unit/CategoryEditPopover.test.tsx`

- [ ] **Step 1: Write failing component test (Jest + React Testing Library)**

Test that:
- Rendering in "create" mode shows empty fields.
- Rendering in "edit" mode shows the passed category's values.
- Submitting calls the passed `onSubmit` with the form state.
- The icon picker dropdown contains items from `LUCIDE_ICON_NAMES`.
- The color picker renders 8 swatches.

- [ ] **Step 2: Fail. Implement component**

Use Radix `Popover` wrapper (`components/ui/popover.tsx`), an input for `name`, a shadcn `Select` (or existing `select-custom.tsx`) for `icon` whose options are sourced from `LUCIDE_ICON_NAMES` in `SaveAsTemplateModal/iconPicker/lucideIconNames.ts`. Color picker is a horizontal row of 8 `button` pills (one per palette key: slate/amber/violet/emerald/sky/fuchsia/indigo/rose) with an outline on the selected one. Submit button calls `onSubmit(formState)`.

- [ ] **Step 3: Pass. Commit.**

```bash
git commit -m "feat(frontend): CategoryEditPopover with icon + color picker"
```

### Task F3: Wire category hover menu and "+ New category"

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/components/navComponent/index.tsx`

- [ ] **Step 1: When `isAdmin`, render a `...` button per category row**

Use the `dropdown-menu.tsx` primitive. Menu items:
- **Edit** → opens `CategoryEditPopover` anchored to the row in edit mode.
- **Delete** → opens a confirm dialog (`components/ui/dialog.tsx`) with the copy from §5.1 of the spec; on confirm, call `useDeleteCategory().mutate(id)`.

- [ ] **Step 2: Add "+ New category" row under the category list when `isAdmin`**

Clicking opens `CategoryEditPopover` in create mode. On submit, call `useCreateCategory().mutate(form)`.

- [ ] **Step 3: Invalidate list query on successful mutations** — reuse `CATEGORIES_QUERY_KEY` invalidation (already wired in Task E1 hooks).

- [ ] **Step 4: Smoke test in browser (dev server)**

Confirm: as admin, hover reveals `...`; Edit updates the row live; Delete removes the row; "+ New category" adds a new row alpha-sorted.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(frontend): inline category CRUD in templates modal sidebar"
```

---

## Phase G — Frontend Admin UX: Per-Template Actions

### Task G1: Archive / unarchive / hard-delete hooks

**Files:**
- Create: `src/frontend/src/controllers/API/queries/templates/use-archive-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-unarchive-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-hard-delete-template.ts`

- [ ] **Step 1: Implement the three mutations**

Each follows the pattern of existing template mutation hooks (`use-update-template.ts`). On success, invalidate the templates query key. For `useHardDeleteTemplate`, on 409 response return the parsed body (`{ referencing_flow_ids }`) so the UI can surface the list.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(frontend): template archive, unarchive, hard-delete hooks"
```

### Task G2: `TemplateCardAdminMenu` and `TemplateEditPanel`

**Files:**
- Create: `src/frontend/src/modals/templatesModal/components/TemplateCardAdminMenu/index.tsx`
- Create: `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx`
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx`
- Test: `src/frontend/tests/unit/TemplateCardAdminMenu.test.tsx`

- [ ] **Step 1: Write the failing card-menu test**

Assert that when `canEdit=true`, the `...` button is rendered and the dropdown shows Edit / Archive / Delete (or Unarchive if the template is already archived).

- [ ] **Step 2: Fail. Implement `TemplateCardAdminMenu`**

Props:
```ts
type Props = {
  template: Template;
  canEdit: boolean;
  onEdit(): void;
  onArchiveToggle(): void;
  onDelete(): void;
};
```

Render nothing when `!canEdit`. Otherwise render a `dropdown-menu` anchored to a `...` button positioned absolutely in the top-right of the card.

- [ ] **Step 3: Implement `TemplateEditPanel`**

A right-side slide-in panel (can be a stacked `Dialog` or a custom Framer-Motion slide; fall back to `Dialog` if the codebase doesn't already include a side-panel primitive). Fields: name, description, icon (reuse `IconPickerField`), gradient (reuse `GradientPickerField`), categories (reuse `CategoryChipPicker` — built in Task H1). Save calls `useUpdateTemplate().mutate(...)` including `category_ids` from the chip picker.

- [ ] **Step 4: Wire `TemplateCardAdminMenu` into `TemplateCardComponent`**

In `TemplateCardComponent`, compute `canEdit` from: platform admin OR (template scope is 'org' AND (org admin OR template.created_by === userData.id)). Pass through to the menu component. On **Edit**, open `TemplateEditPanel`. On **Archive**/**Unarchive**, call the appropriate mutation. On **Delete**, open a confirm dialog; on 409 response show the referencing flow ids.

- [ ] **Step 5: Smoke test in browser**

Verify: card shows `...` for admin; Edit opens the side-panel; saving updates the card; Archive hides the card immediately (unless "Show archived" is on); Delete shows confirmation and removes or 409s.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(frontend): per-template admin menu and edit panel"
```

### Task G3: "Show archived" toggle

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx`

- [ ] **Step 1: Add a toggle near the section title when admin OR on Saved Templates tab**

```tsx
const [showArchived, setShowArchived] = useState(false);
const canSeeArchived =
  isAdmin || currentTab === "saved-templates";
{canSeeArchived && (
  <Switch checked={showArchived} onCheckedChange={setShowArchived}>
    Show archived
  </Switch>
)}
```

- [ ] **Step 2: Pass `include_archived` into `useListTemplates`**

When `showArchived && canSeeArchived`, include `include_archived: true` and (if non-admin) `created_by_me: true`.

- [ ] **Step 3: Render archived cards at 50% opacity with an "Archived" pill; disable Start Building**

In `TemplateCardComponent`, check `template.archived_at !== null` and apply a conditional className (`opacity-50`) plus a pill. Disable the Start Building button (or Start Building equivalent) with a `title` tooltip from §5.3 of the spec.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(frontend): Show archived toggle with dimmed cards and disabled build"
```

---

## Phase H — Frontend: Save-as-Template Extensions

### Task H1: `CategoryChipPicker` component

**Files:**
- Create: `src/frontend/src/modals/templatesModal/components/CategoryChipPicker/index.tsx`

- [ ] **Step 1: Implement**

Props:
```ts
type Props = {
  selectedIds: string[];
  onChange(ids: string[]): void;
};
```

Behavior: Fetches categories via `useListCategories`. Renders a search input + a list of category chips — selected chips have a filled appearance; clicking toggles. Exports selected ids upward via `onChange`.

Since there's no pre-existing chip-input in the codebase (confirmed in the frontend explore), build it from `Input` + `Badge` (`components/ui/badge.tsx` if present; else a simple pill div).

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(frontend): CategoryChipPicker component"
```

### Task H2: Integrate chip picker + scope selector into `SaveAsTemplateModal`

**Files:**
- Modify: `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`
- Modify: `src/frontend/src/controllers/API/queries/templates/use-create-template.ts` (accept `category_ids`, `scope`, `org_id`)

- [ ] **Step 1: Add category picker to the form**

Under the existing `description` field, insert `<CategoryChipPicker selectedIds={categoryIds} onChange={setCategoryIds} />`. Pass `categoryIds` into the mutation body.

- [ ] **Step 2: Add scope selector conditionally**

```tsx
const isPlatformAdmin = useIsPlatformAdmin();
const orgMemberships = useOrganizationMemberships(); // new or existing hook; fetch from /api/v1/memberships/me

const showScopeSelector = isPlatformAdmin && orgMemberships.length > 0;

{showScopeSelector && (
  <RadioGroup value={scope} onValueChange={setScope}>
    <RadioGroupItem value="platform">Platform</RadioGroupItem>
    {orgMemberships.map(m => (
      <RadioGroupItem key={m.org_id} value={`org:${m.org_id}`}>
        Org: {m.org_name}
      </RadioGroupItem>
    ))}
  </RadioGroup>
)}
```

Defaults:
- If the logged-in user is a platform admin not in any org → `scope = "platform"`, no selector.
- If the user is a platform admin in an org → selector is shown; default to `"platform"`.
- If the user is an org admin / member (not platform admin) → `scope = "org"`, `org_id = their org`, no selector. If exactly zero memberships → Save disabled with tooltip.

If `useOrganizationMemberships` does not exist yet, add a minimal hook that calls `GET /api/v1/memberships/me` (check whether the backend has it — if not, add that lookup now; it's needed by the frontend here).

- [ ] **Step 3: Wire `scope` and `org_id` into the create-template mutation**

The create payload should include `scope`, `org_id` (null when platform), and `category_ids`.

- [ ] **Step 4: Smoke test**

As a regular org member: verify Save produces an org-scoped template, visible to another member of the same org. As a platform admin: verify the selector appears and creating a platform-scoped template shows up for all orgs.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(frontend): Save-as-Template — categories chip picker and scope selector"
```

---

## Phase I — Verification & Polish

### Task I1: Full test suite

- [ ] **Step 1: Backend**

Run: `uv run pytest src/backend/tests/ -x`

Expected: all green. Fix flakes immediately.

- [ ] **Step 2: Frontend unit**

Run: `npm --prefix src/frontend test -- --watchAll=false`

Expected: all green.

- [ ] **Step 3: Type + lint**

Run: `npm --prefix src/frontend run typecheck && npm --prefix src/frontend run lint`

Expected: no errors.

### Task I2: Manual UX pass

- [ ] **Step 1: Start both servers**

- Backend: `uv run langflow run --backend-only` (background)
- Frontend: `npm --prefix src/frontend start` (background)

- [ ] **Step 2: Check a regular user's flow**

Log in as a non-admin member of an org. Open the templates modal. Confirm:
- Category sidebar populated from the seeded list (alpha-sorted).
- Clicking a category narrows the grid.
- Saved Templates shows only your own saves.
- Save-as-Template picks up the categories chip picker; no scope selector.
- You can archive your own template; it disappears from the grid.
- Toggle "Show archived" on Saved Templates; the archived row reappears with a pill; Unarchive works.

- [ ] **Step 3: Check a platform admin's flow**

Log in as a platform admin. Confirm:
- Category sidebar has `...` menus; edit renames live; delete removes row; + New category appears in alpha position.
- Template cards have `...` menus; Edit opens side-panel with categories chip; Save persists.
- "Show archived" toggle is visible everywhere; archived cards dim.
- Delete blocks with 409 when flows reference the template; succeeds otherwise.

- [ ] **Step 4: Commit any fixes**

```bash
git commit -m "fix(frontend/backend): polish from manual UX pass"
```

### Task I3: Push & (optional) internal PR

`platform-multi-tenant` is the effective main for this fork (per the user's repo convention). Work lands directly on it — there is no upstream PR to `langflow-ai/langflow` planned.

- [ ] **Step 1: Push the branch**

```bash
git push
```

- [ ] **Step 2 (optional): Open an internal PR for review**

Only if the user requests it. Title: `Rework template categories (DB-backed, admin-managed, org-scoped templates)`.

Summary bullets:
- Migrates all starter JSON into DB-backed `Template` rows via Alembic.
- Adds `Category` model + platform-admin CRUD; alpha-sorted flat sidebar.
- Unfreezes `Template.scope`/`org_id`; enables org-scoped templates + Save-as-Template scope selector.
- Adds archive/unarchive + hard-delete with 409 guard on referencing flows.
- Flow creation is blocked (422) when the source template is archived.

Rollback note: reversing requires re-adding the starter JSON source files from git history.

---

## Execution Notes

- **Frequent commits**: one per task-end at minimum; commits inside a task are fine when a step naturally concludes (e.g., test passing).
- **TDD is rigid for this plan**: each backend task writes the failing test first; frontend component tasks follow the same pattern using Jest.
- **Commits with the user's approval only**: per the active repo convention (`MEMORY.md`), always pause and ask before running `git commit`, even though this plan specifies commit points. The commit commands in each task are the payload to run when the user approves.
