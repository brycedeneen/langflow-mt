# Tagging for Flows and Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User-specific commit discipline:** This user has a standing rule — pause and ask before every `git commit`. The commit commands below are the exact command to run *after* the user approves. Stage explicit paths only (no `git add -A` / `.`).

**Goal:** Platform-admin-curated global tag vocabulary that members can assign to flows and templates. Includes admin CRUD, public list, assign endpoints, filter by tag, admin UI tab, chip picker UX, and filter chip row.

**Architecture:** Three new tables (`tag`, `flow_tag`, `template_tag`). `tag` is platform-global and gated by `User.is_platform_admin` for mutations. M2M tables cascade on flow/template delete. The unused `Flow.tags: list[str]` JSON column is dropped in the same migration. A fixed 10-color palette lives as a named enum on both backend and frontend — colors are names (`slate`, `red`, …), not hex, so the design can evolve without touching the API.

**Tech Stack:** Python 3.11, FastAPI, SQLModel (async), Alembic, pytest-asyncio, React + TypeScript, react-query v5 (`isPending` — the fork uses v5), Jest (not Vitest), Tailwind v4 (CSS-first, `@reference` for applies).

**Spec:** `docs/superpowers/specs/2026-04-23-assistant-org-isolation-and-tagging-design.md` (Part B).

**Out of scope (explicit, per spec B.2):** AND-combinator filter, per-org tag vocabularies, free-hex color input, tag usage counts, auto-tagging, migration of the unused `Flow.tags` data (no rows to migrate).

---

## File Structure

**New (backend):**
- `src/backend/base/langflow/alembic/versions/<hash>_add_tag_tables.py` — migration (hash generated in Task 1).
- `src/backend/base/langflow/services/database/models/tag/__init__.py`
- `src/backend/base/langflow/services/database/models/tag/model.py` — `Tag`, `FlowTag`, `TemplateTag`, `TagColor` enum.
- `src/backend/base/langflow/services/database/models/tag/schema.py` — Pydantic read/write schemas.
- `src/backend/base/langflow/api/v1/admin/tags.py` — admin CRUD router (platform-admin gated).
- `src/backend/base/langflow/api/v1/tags.py` — public list router.
- `src/backend/tests/unit/services/database/models/test_tag_models.py` — model tests.
- `src/backend/tests/unit/api/v1/test_tag_admin.py`
- `src/backend/tests/unit/api/v1/test_tags_public.py`
- `src/backend/tests/unit/api/v1/test_flow_tag_assignment.py`
- `src/backend/tests/unit/api/v1/test_template_tag_assignment.py`
- `src/backend/tests/unit/api/v1/test_flow_tag_filter.py`
- `src/backend/tests/unit/api/v1/test_template_tag_filter.py`

**Modified (backend):**
- `src/backend/base/langflow/services/database/models/flow/model.py` — drop the `tags: list[str] | None` field (line 65) and back-reference the `FlowTag` relationship.
- `src/backend/base/langflow/services/database/models/template/model.py` — back-reference `TemplateTag`.
- `src/backend/base/langflow/services/database/models/__init__.py` — export `Tag`, `FlowTag`, `TemplateTag`.
- `src/backend/base/langflow/api/v1/flows.py` — `read_flows()` accept `tag_id: list[UUID] | None`; add `PUT /api/v1/flows/{id}/tags`.
- `src/backend/base/langflow/api/v1/templates.py` — same pair: filter + assign.
- `src/backend/base/langflow/api/router.py` — include both new routers.

**New (frontend):**
- `src/frontend/src/types/api/tag.ts` — TS types for `Tag`, `TagColor`, `TagWrite`.
- `src/frontend/src/controllers/API/queries/tags/use-tags.ts` — `useGetTags`, `useAssignFlowTags`, `useAssignTemplateTags`.
- `src/frontend/src/controllers/API/queries/tags/use-tag-admin.ts` — admin CRUD hooks.
- `src/frontend/src/components/common/TagChip/index.tsx` — presentational chip.
- `src/frontend/src/components/common/TagPicker/index.tsx` — multi-select combobox.
- `src/frontend/src/components/common/TagFilterChips/index.tsx` — toggle-filter row.
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/tags-tab.tsx` — admin tab.
- `src/frontend/src/components/common/TagChip/__tests__/TagChip.test.tsx`
- `src/frontend/src/components/common/TagPicker/__tests__/TagPicker.test.tsx`
- `src/frontend/src/components/common/TagFilterChips/__tests__/TagFilterChips.test.tsx`

**Modified (frontend):**
- `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx` — add third tab.
- `src/frontend/src/pages/FlowPage/components/flowHeaderComponent/...` — the exact file is discovered in Task 10; it is the header bar that displays the flow name + actions.
- `src/frontend/src/modals/saveAsTemplateModal/...` — add tag picker below category picker.
- `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarItemsList.tsx` — render chip row per flow; filter row above list.
- `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx` — render chips on card.
- `src/frontend/src/modals/templatesModal/index.tsx` — filter row above category grid.

---

## Task 1: Alembic migration (tag + flow_tag + template_tag; drop flow.tags)

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<hash>_add_tag_tables.py`

**Context:** Our migration pattern (per `2026-04-22-audit-log` and `2026-04-18-metadata-infrastructure`) is hand-written alembic with both upgrade and downgrade. Migration head is discoverable via `uv run alembic heads`.

- [ ] **Step 1: Find the current migration head**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run alembic -c src/backend/base/langflow/alembic.ini heads
```
Expected: single hash output, e.g. `2998418b3bc5 (head)` or the most recent audit-log migration. Record this hash — it will be the `down_revision`.

- [ ] **Step 2: Generate a skeleton migration**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run alembic -c src/backend/base/langflow/alembic.ini revision -m "add_tag_tables"
```
Expected: creates `src/backend/base/langflow/alembic/versions/<new_hash>_add_tag_tables.py` with empty `upgrade()` / `downgrade()` stubs. Record `<new_hash>`.

- [ ] **Step 3: Replace the migration body**

Open the newly created file. Replace its body with:

```python
"""add tag tables

Revision ID: <new_hash>
Revises: <down_revision_from_step_1>
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "<new_hash>"
down_revision = "<down_revision>"
branch_labels = None
depends_on = None


TAG_COLOR_VALUES = (
    "slate",
    "red",
    "orange",
    "amber",
    "green",
    "teal",
    "sky",
    "blue",
    "violet",
    "pink",
)


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Case-insensitive uniqueness on name.
    op.create_index(
        "uq_tag_name_lower",
        "tag",
        [sa.text("lower(name)")],
        unique=True,
    )
    # CHECK constraint: color must be in palette.
    op.create_check_constraint(
        "ck_tag_color_palette",
        "tag",
        sa.text(
            "color IN ("
            + ", ".join(f"'{c}'" for c in TAG_COLOR_VALUES)
            + ")"
        ),
    )

    op.create_table(
        "flow_tag",
        sa.Column(
            "flow_id",
            sa.Uuid(),
            sa.ForeignKey("flow.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("tag.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_flow_tag_tag_id", "flow_tag", ["tag_id"])

    op.create_table(
        "template_tag",
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("template.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("tag.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_template_tag_tag_id", "template_tag", ["tag_id"])

    # Drop the unused Flow.tags JSON column (spec B.2 / B.3 — never had rows).
    with op.batch_alter_table("flow") as batch:
        batch.drop_column("tags")


def downgrade() -> None:
    with op.batch_alter_table("flow") as batch:
        batch.add_column(
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )
    op.drop_index("ix_template_tag_tag_id", table_name="template_tag")
    op.drop_table("template_tag")
    op.drop_index("ix_flow_tag_tag_id", table_name="flow_tag")
    op.drop_table("flow_tag")
    op.drop_constraint("ck_tag_color_palette", "tag", type_="check")
    op.drop_index("uq_tag_name_lower", table_name="tag")
    op.drop_table("tag")
```

Replace the two `<new_hash>` / `<down_revision>` placeholders literally.

- [ ] **Step 4: Verify upgrade + downgrade round-trip**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run alembic -c src/backend/base/langflow/alembic.ini upgrade head
uv run alembic -c src/backend/base/langflow/alembic.ini downgrade -1
uv run alembic -c src/backend/base/langflow/alembic.ini upgrade head
```
Expected: all three commands succeed. Inspect schema with `\d tag`, `\d flow_tag`, `\d template_tag` if on Postgres, or `.schema tag` on SQLite, and confirm columns + indexes + constraint are present after final upgrade.

- [ ] **Step 5: Pause before commit**

Proposed commit message:
```
feat(db): tag + flow_tag + template_tag tables; drop unused flow.tags

Adds the three tables for the platform-global tag vocabulary (Part B of
the Sprint 2 design). Case-insensitive UNIQUE on tag.name via functional
index. CHECK constraint ensures color is from the fixed 10-value palette.
M2M tables cascade on flow/template delete. The Flow.tags JSON column
(present but never used) is dropped in the same migration.
```

---

## Task 2: SQLModel definitions + unit tests

**Files:**
- Create: `src/backend/base/langflow/services/database/models/tag/__init__.py`
- Create: `src/backend/base/langflow/services/database/models/tag/model.py`
- Create: `src/backend/base/langflow/services/database/models/tag/schema.py`
- Modify: `src/backend/base/langflow/services/database/models/__init__.py`
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py`
- Modify: `src/backend/base/langflow/services/database/models/template/model.py`
- Create: `src/backend/tests/unit/services/database/models/test_tag_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `src/backend/tests/unit/services/database/models/test_tag_models.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.database.models.tag.model import (
    FlowTag,
    Tag,
    TagColor,
    TemplateTag,
)


@pytest.mark.asyncio
async def test_tag_requires_palette_color(session) -> None:
    tag = Tag(name="finance", color="not-a-color")
    session.add(tag)
    with pytest.raises(Exception):  # IntegrityError or CheckConstraint fail
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_tag_name_case_insensitive_unique(session) -> None:
    session.add(Tag(name="Finance", color=TagColor.BLUE.value))
    await session.commit()
    session.add(Tag(name="finance", color=TagColor.RED.value))
    with pytest.raises(Exception):
        await session.commit()
    await session.rollback()


@pytest.mark.asyncio
async def test_flow_tag_cascades_on_flow_delete(session, make_flow) -> None:
    tag = Tag(name="hr", color=TagColor.GREEN.value)
    flow = await make_flow()
    session.add(tag)
    await session.commit()
    session.add(FlowTag(flow_id=flow.id, tag_id=tag.id))
    await session.commit()

    await session.delete(flow)
    await session.commit()

    remaining = (await session.exec(select(FlowTag).where(FlowTag.tag_id == tag.id))).all()
    assert remaining == []


def test_tag_color_enum_lists_ten_values() -> None:
    assert len(TagColor) == 10
    assert {c.value for c in TagColor} == {
        "slate", "red", "orange", "amber", "green",
        "teal", "sky", "blue", "violet", "pink",
    }
```

- [ ] **Step 2: Run the test — confirm it fails at import**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/services/database/models/test_tag_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'langflow.services.database.models.tag.model'`.

- [ ] **Step 3: Write the minimal model**

Create `src/backend/base/langflow/services/database/models/tag/__init__.py`:

```python
from langflow.services.database.models.tag.model import (
    FlowTag,
    Tag,
    TagColor,
    TemplateTag,
)
from langflow.services.database.models.tag.schema import (
    TagRead,
    TagWrite,
)

__all__ = ["FlowTag", "Tag", "TagColor", "TemplateTag", "TagRead", "TagWrite"]
```

Create `src/backend/base/langflow/services/database/models/tag/model.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Text, text
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class TagColor(str, Enum):
    SLATE = "slate"
    RED = "red"
    ORANGE = "orange"
    AMBER = "amber"
    GREEN = "green"
    TEAL = "teal"
    SKY = "sky"
    BLUE = "blue"
    VIOLET = "violet"
    PINK = "pink"


_PALETTE = tuple(c.value for c in TagColor)
_COLOR_CHECK_CLAUSE = "color IN (" + ", ".join(f"'{c}'" for c in _PALETTE) + ")"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "tag"
    __table_args__ = (
        Index("uq_tag_name_lower", text("lower(name)"), unique=True),
        CheckConstraint(_COLOR_CHECK_CLAUSE, name="ck_tag_color_palette"),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=64)
    color: str = Field(max_length=32)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class FlowTag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_tag"
    __table_args__ = (Index("ix_flow_tag_tag_id", "tag_id"),)

    flow_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("flow.id", ondelete="CASCADE"), primary_key=True)
    )
    tag_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    )


class TemplateTag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "template_tag"
    __table_args__ = (Index("ix_template_tag_tag_id", "tag_id"),)

    template_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("template.id", ondelete="CASCADE"), primary_key=True)
    )
    tag_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    )
```

Create `src/backend/base/langflow/services/database/models/tag/schema.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from langflow.services.database.models.tag.model import TagColor

TagName = Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)]


class TagWrite(BaseModel):
    name: TagName
    color: TagColor
    description: str | None = Field(default=None, max_length=1024)


class TagRead(BaseModel):
    id: UUID
    name: str
    color: TagColor
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Re-export from the models package**

Edit `src/backend/base/langflow/services/database/models/__init__.py`. Find the block of imports / `__all__` — add:

```python
from langflow.services.database.models.tag import FlowTag, Tag, TagColor, TemplateTag  # noqa: F401
```

If the file uses an `__all__` list, append `"FlowTag"`, `"Tag"`, `"TagColor"`, `"TemplateTag"` to it.

- [ ] **Step 5: Drop Flow.tags + add back-reference**

Edit `src/backend/base/langflow/services/database/models/flow/model.py`. Find line 65 (`tags: list[str] | None = None`) and **delete that single line**. Do not change any other line.

- [ ] **Step 6: Run the model tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/services/database/models/test_tag_models.py -v
```
Expected: 4 tests PASS.

If `make_flow` fixture doesn't exist in conftest, search for an existing one:
```bash
grep -rn 'def make_flow\|make_flow =\|@pytest.*fixture' src/backend/tests/conftest.py src/backend/tests/unit/conftest.py 2>&1 | head -10
```
If absent, inline the flow creation in the test using `Flow(...)` directly.

- [ ] **Step 7: Pause before commit**

Proposed commit message:
```
feat(db): SQLModel definitions for Tag + FlowTag + TemplateTag

Adds Tag, FlowTag, TemplateTag SQLModel tables with a TagColor enum
matching the palette CHECK constraint from the migration. Drops the
unused Flow.tags JSON field. Re-exports new models from the database
models package. Covered by 4 model-level unit tests (palette check,
case-insensitive unique, cascade on flow delete, enum length).
```

---

## Task 3: Admin CRUD router (PlatformAdmin gated)

**Files:**
- Create: `src/backend/base/langflow/api/v1/admin/tags.py`
- Modify: `src/backend/base/langflow/api/router.py`
- Create: `src/backend/tests/unit/api/v1/test_tag_admin.py`

**Context:** Mirror the pattern at `src/backend/base/langflow/api/v1/admin/metadata.py` (line 1-309). Existing `PlatformAdmin` dependency is at `src/backend/base/langflow/api/utils/core.py:94`.

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_tag_admin.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.fixture
async def platform_admin_user(session):
    from langflow.services.database.models.user.model import User
    user = User(username="platform_admin", password="x", is_active=True, is_platform_admin=True)
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
async def regular_member(session):
    from langflow.services.database.models.user.model import User
    user = User(username="member", password="x", is_active=True, is_platform_admin=False)
    session.add(user)
    await session.commit()
    return user


@pytest.mark.asyncio
async def test_regular_user_cannot_create_tag(client: AsyncClient, regular_member) -> None:
    resp = await client.post(
        "/api/v1/admin/tags",
        json={"name": "finance", "color": "blue"},
        headers={"Authorization": f"Bearer test-{regular_member.id}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_creates_and_reads_tag(client: AsyncClient, platform_admin_user) -> None:
    resp = await client.post(
        "/api/v1/admin/tags",
        json={"name": "finance", "color": "blue", "description": "cost center"},
        headers={"Authorization": f"Bearer test-{platform_admin_user.id}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "finance"
    assert body["color"] == "blue"
    tag_id = body["id"]

    r2 = await client.get(f"/api/v1/admin/tags/{tag_id}", headers={"Authorization": f"Bearer test-{platform_admin_user.id}"})
    assert r2.status_code == 200
    assert r2.json()["description"] == "cost center"


@pytest.mark.asyncio
async def test_create_duplicate_name_case_insensitive_returns_409(
    client: AsyncClient, platform_admin_user
) -> None:
    hdr = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    await client.post("/api/v1/admin/tags", json={"name": "HR", "color": "green"}, headers=hdr)
    resp = await client.post("/api/v1/admin/tags", json={"name": "hr", "color": "red"}, headers=hdr)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_invalid_color_returns_422(client: AsyncClient, platform_admin_user) -> None:
    resp = await client.post(
        "/api/v1/admin/tags",
        json={"name": "bad", "color": "purple"},
        headers={"Authorization": f"Bearer test-{platform_admin_user.id}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_updates_tag(client: AsyncClient, platform_admin_user) -> None:
    hdr = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    created = (await client.post("/api/v1/admin/tags", json={"name": "ops", "color": "slate"}, headers=hdr)).json()
    resp = await client.put(f"/api/v1/admin/tags/{created['id']}", json={"color": "red"}, headers=hdr)
    assert resp.status_code == 200
    assert resp.json()["color"] == "red"


@pytest.mark.asyncio
async def test_delete_cascades_associations(client: AsyncClient, platform_admin_user) -> None:
    # Will be exercised more fully in Task 5; smoke test here.
    hdr = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    created = (await client.post("/api/v1/admin/tags", json={"name": "temp", "color": "amber"}, headers=hdr)).json()
    resp = await client.delete(f"/api/v1/admin/tags/{created['id']}", headers=hdr)
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/v1/admin/tags/{created['id']}", headers=hdr)
    assert resp2.status_code == 404
```

- [ ] **Step 2: Run tests — expect module-import failure**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_tag_admin.py -v
```
Expected: import or routing failures — the router isn't registered yet.

- [ ] **Step 3: Write the admin router**

Create `src/backend/base/langflow/api/v1/admin/tags.py`:

```python
"""Admin CRUD for the platform-global tag vocabulary.

Gated by :class:`PlatformAdmin` (User.is_platform_admin). Any authenticated
user can list tags via GET /api/v1/tags (see api/v1/tags.py); only platform
admins can mutate the vocabulary.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.api.utils.core import PlatformAdmin
from langflow.services.database.models.tag.model import Tag
from langflow.services.database.models.tag.schema import TagRead, TagWrite
from lfx.services.deps import session_scope

router = APIRouter(prefix="/admin/tags", tags=["admin:tags"])


@router.get("", response_model=list[TagRead])
async def list_tags(_actor: PlatformAdmin) -> list[TagRead]:
    async with session_scope() as session:
        rows = (await session.exec(select(Tag).order_by(Tag.name))).all()
        return [TagRead.model_validate(r) for r in rows]


@router.get("/{tag_id}", response_model=TagRead)
async def get_tag(tag_id: UUID, _actor: PlatformAdmin) -> TagRead:
    async with session_scope() as session:
        tag = await session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="tag not found")
        return TagRead.model_validate(tag)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
async def create_tag(payload: TagWrite, actor: PlatformAdmin) -> TagRead:
    async with session_scope() as session:
        tag = Tag(
            name=payload.name,
            color=payload.color.value,
            description=payload.description,
            created_by=actor.id,
        )
        session.add(tag)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            if "uq_tag_name_lower" in str(exc.orig):
                raise HTTPException(status_code=409, detail="tag name already exists") from exc
            raise
        await session.refresh(tag)
        return TagRead.model_validate(tag)


@router.put("/{tag_id}", response_model=TagRead)
async def update_tag(tag_id: UUID, payload: TagWrite, _actor: PlatformAdmin) -> TagRead:
    # Note: TagWrite validates all fields; send the full desired state.
    async with session_scope() as session:
        tag = await session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="tag not found")
        tag.name = payload.name
        tag.color = payload.color.value
        tag.description = payload.description
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            if "uq_tag_name_lower" in str(exc.orig):
                raise HTTPException(status_code=409, detail="tag name already exists") from exc
            raise
        await session.refresh(tag)
        return TagRead.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: UUID, _actor: PlatformAdmin) -> None:
    async with session_scope() as session:
        tag = await session.get(Tag, tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="tag not found")
        await session.delete(tag)  # FK CASCADE removes flow_tag / template_tag rows.
        await session.commit()
```

- [ ] **Step 4: Mount the router**

Edit `src/backend/base/langflow/api/router.py`. Find where other `admin/*` routers are included (search for `admin/metadata` or `include_router`) and add the tags admin router in the same block:

```python
from langflow.api.v1.admin import tags as admin_tags

router.include_router(admin_tags.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_tag_admin.py -v
```
Expected: 7 tests PASS. If a test fails with a 401 (not 403), the auth fixture isn't wired; inspect `src/backend/tests/unit/api/v1/test_tag_admin.py` headers and align with whatever auth helper the existing `test_metadata_admin.py` uses.

- [ ] **Step 6: Pause before commit**

Proposed commit message:
```
feat(api): platform-admin CRUD for tag vocabulary

Adds /api/v1/admin/tags [GET/POST/GET-id/PUT/DELETE] gated by
User.is_platform_admin. Case-insensitive unique on name → 409 on conflict.
Invalid color → 422. Covered by 7 tests including role enforcement.
Mirrors the admin/metadata.py pattern.
```

---

## Task 4: Public list endpoint

**Files:**
- Create: `src/backend/base/langflow/api/v1/tags.py`
- Modify: `src/backend/base/langflow/api/router.py`
- Create: `src/backend/tests/unit/api/v1/test_tags_public.py`

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_tags_public.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_any_authenticated_user_lists_tags(client: AsyncClient, regular_member, platform_admin_user) -> None:
    hdr_admin = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    for name, color in [("a", "blue"), ("b", "red"), ("c", "green")]:
        await client.post("/api/v1/admin/tags", json={"name": name, "color": color}, headers=hdr_admin)

    resp = await client.get("/api/v1/tags", headers={"Authorization": f"Bearer test-{regular_member.id}"})
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert set(names) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/tags")
    assert resp.status_code == 401
```

The fixtures `regular_member` and `platform_admin_user` come from the conftest-appropriate location (copy from `test_tag_admin.py` into a shared conftest if both files need them).

- [ ] **Step 2: Run — expect 404 route-not-found**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_tags_public.py -v
```
Expected: FAIL with 404 because the route isn't mounted.

- [ ] **Step 3: Implement the endpoint**

Create `src/backend/base/langflow/api/v1/tags.py`:

```python
from __future__ import annotations

from fastapi import APIRouter
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser
from langflow.services.database.models.tag.model import Tag
from langflow.services.database.models.tag.schema import TagRead
from lfx.services.deps import session_scope_readonly

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagRead])
async def list_tags(_user: CurrentActiveUser) -> list[TagRead]:
    async with session_scope_readonly() as session:
        rows = (await session.exec(select(Tag).order_by(Tag.name))).all()
        return [TagRead.model_validate(r) for r in rows]
```

- [ ] **Step 4: Mount the router**

Edit `src/backend/base/langflow/api/router.py` — add after existing v1 includes:

```python
from langflow.api.v1 import tags as tags_v1

router.include_router(tags_v1.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_tags_public.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 6: Pause before commit**

Proposed commit message:
```
feat(api): public read-only list of tags

Adds GET /api/v1/tags for any authenticated user. Returns the full
platform-global tag vocabulary ordered by name. Uses session_scope_readonly
since this is a read path.
```

---

## Task 5: Flow and Template assign endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py`
- Modify: `src/backend/base/langflow/api/v1/templates.py`
- Create: `src/backend/tests/unit/api/v1/test_flow_tag_assignment.py`
- Create: `src/backend/tests/unit/api/v1/test_template_tag_assignment.py`

**Context:** PUT-replaces-set semantics per spec B.4. The request body is `{"tag_ids": [uuid, ...]}`. Server validates every id exists; unknown → 422. Delete all existing M2M rows then insert the new set, in one transaction.

- [ ] **Step 1: Write the failing flow-assignment test**

Create `src/backend/tests/unit/api/v1/test_flow_tag_assignment.py`:

```python
import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_assign_tags_replaces_existing(client: AsyncClient, platform_admin_user, make_flow_in_my_org) -> None:
    hdr = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    flow = await make_flow_in_my_org()
    t1 = (await client.post("/api/v1/admin/tags", json={"name": "t1", "color": "red"}, headers=hdr)).json()
    t2 = (await client.post("/api/v1/admin/tags", json={"name": "t2", "color": "blue"}, headers=hdr)).json()
    t3 = (await client.post("/api/v1/admin/tags", json={"name": "t3", "color": "green"}, headers=hdr)).json()

    r1 = await client.put(f"/api/v1/flows/{flow.id}/tags", json={"tag_ids": [t1["id"], t2["id"]]}, headers=hdr)
    assert r1.status_code == 200
    assert {x["id"] for x in r1.json()["tags"]} == {t1["id"], t2["id"]}

    r2 = await client.put(f"/api/v1/flows/{flow.id}/tags", json={"tag_ids": [t3["id"]]}, headers=hdr)
    assert r2.status_code == 200
    assert {x["id"] for x in r2.json()["tags"]} == {t3["id"]}


@pytest.mark.asyncio
async def test_assign_unknown_tag_returns_422(client: AsyncClient, platform_admin_user, make_flow_in_my_org) -> None:
    hdr = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    flow = await make_flow_in_my_org()
    resp = await client.put(f"/api/v1/flows/{flow.id}/tags", json={"tag_ids": [str(uuid4())]}, headers=hdr)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assign_without_edit_permission_returns_403(client: AsyncClient, regular_member, foreign_flow) -> None:
    # foreign_flow is owned by someone else; regular_member cannot edit it.
    resp = await client.put(
        f"/api/v1/flows/{foreign_flow.id}/tags",
        json={"tag_ids": []},
        headers={"Authorization": f"Bearer test-{regular_member.id}"},
    )
    assert resp.status_code in (403, 404)  # either is acceptable — matches existing edit-permission behavior
```

Mirror these in `test_template_tag_assignment.py` with `make_template_in_my_org` and `template_id` in the URL.

- [ ] **Step 2: Run — confirm module/route failure**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_assignment.py src/backend/tests/unit/api/v1/test_template_tag_assignment.py -v
```
Expected: 404 route-not-found on the PUT.

- [ ] **Step 3: Add the flow assign endpoint**

Open `src/backend/base/langflow/api/v1/flows.py`. Append a new route (keeping it near the other flow-by-id routes):

```python
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlmodel import select

from langflow.services.database.models.tag.model import FlowTag, Tag
from langflow.services.database.models.tag.schema import TagRead


class _FlowTagAssignBody(BaseModel):
    tag_ids: list[UUID]


class _FlowWithTagsRead(BaseModel):
    id: UUID
    tags: list[TagRead]


@router.put("/{flow_id}/tags", response_model=_FlowWithTagsRead)
async def assign_flow_tags(
    flow_id: UUID,
    body: _FlowTagAssignBody,
    current_user: CurrentActiveUser,
) -> _FlowWithTagsRead:
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow is None or flow.organization_id != current_user.active_org_id:
            raise HTTPException(status_code=404, detail="flow not found")
        # Reuse existing edit-permission helper.
        if not user_can_edit_flow(current_user, flow):
            raise HTTPException(status_code=403, detail="cannot edit this flow")

        # Validate every tag exists.
        if body.tag_ids:
            existing = (
                await session.exec(select(Tag).where(Tag.id.in_(body.tag_ids)))
            ).all()
            if len(existing) != len(set(body.tag_ids)):
                raise HTTPException(status_code=422, detail="one or more tag_ids do not exist")
        else:
            existing = []

        await session.exec(sa_delete(FlowTag).where(FlowTag.flow_id == flow_id))
        for tid in body.tag_ids:
            session.add(FlowTag(flow_id=flow_id, tag_id=tid))
        await session.commit()

        return _FlowWithTagsRead(
            id=flow.id,
            tags=[TagRead.model_validate(t) for t in existing],
        )
```

**Helpers to verify exist or add imports for:** `Flow`, `CurrentActiveUser`, `user_can_edit_flow`, `HTTPException`. If `user_can_edit_flow` doesn't exist, grep for the equivalent check used elsewhere in `flows.py` and mirror it inline.

- [ ] **Step 4: Add the template assign endpoint**

Same structure in `src/backend/base/langflow/api/v1/templates.py`. Use `Template`, `TemplateTag`, `user_can_edit_template` (existing at per the spec B.7).

- [ ] **Step 5: Run tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_assignment.py src/backend/tests/unit/api/v1/test_template_tag_assignment.py -v
```
Expected: all PASS.

- [ ] **Step 6: Pause before commit**

Proposed commit message:
```
feat(api): PUT /flows/{id}/tags and /templates/{id}/tags

Assign tags to flows and templates with PUT-replaces-set semantics.
Validates every tag_id exists → 422 on unknown. Gated by existing
edit-permission helpers; 404 for cross-org flow access (matches the
assistant isolation contract from the Part A plan).
```

---

## Task 6: Filter flows + templates by tag_id

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` — extend `read_flows()`.
- Modify: `src/backend/base/langflow/api/v1/templates.py` — extend template list endpoint.
- Create: `src/backend/tests/unit/api/v1/test_flow_tag_filter.py`
- Create: `src/backend/tests/unit/api/v1/test_template_tag_filter.py`

- [ ] **Step 1: Write the failing filter test (flows)**

Create `src/backend/tests/unit/api/v1/test_flow_tag_filter.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_flow_list_filters_by_single_tag(client: AsyncClient, platform_admin_user, make_flow_in_my_org) -> None:
    hdr = {"Authorization": f"Bearer test-{platform_admin_user.id}"}
    t1 = (await client.post("/api/v1/admin/tags", json={"name": "x", "color": "red"}, headers=hdr)).json()
    t2 = (await client.post("/api/v1/admin/tags", json={"name": "y", "color": "blue"}, headers=hdr)).json()

    f1 = await make_flow_in_my_org(name="a")
    f2 = await make_flow_in_my_org(name="b")
    f3 = await make_flow_in_my_org(name="c")

    await client.put(f"/api/v1/flows/{f1.id}/tags", json={"tag_ids": [t1["id"]]}, headers=hdr)
    await client.put(f"/api/v1/flows/{f2.id}/tags", json={"tag_ids": [t2["id"]]}, headers=hdr)
    await client.put(f"/api/v1/flows/{f3.id}/tags", json={"tag_ids": [t1["id"], t2["id"]]}, headers=hdr)

    # Single tag: OR semantics → 2 flows with t1
    resp = await client.get(f"/api/v1/flows?tag_id={t1['id']}", headers=hdr)
    assert resp.status_code == 200
    ids = {f["id"] for f in resp.json()["items"]}
    assert ids == {str(f1.id), str(f3.id)}

    # Two tags: OR semantics → all 3 flows
    resp = await client.get(
        f"/api/v1/flows?tag_id={t1['id']}&tag_id={t2['id']}",
        headers=hdr,
    )
    ids = {f["id"] for f in resp.json()["items"]}
    assert ids == {str(f1.id), str(f2.id), str(f3.id)}
```

Mirror in `test_template_tag_filter.py`.

- [ ] **Step 2: Run — expect filter to be ignored (all flows returned)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter.py -v
```
Expected: FAIL because the filter param is unknown and ignored.

- [ ] **Step 3: Wire the filter into `read_flows()`**

Locate `read_flows()` in `src/backend/base/langflow/api/v1/flows.py`. Add the `tag_id` query parameter and extend the query:

```python
from fastapi import Query


async def read_flows(
    # ... existing params ...
    tag_id: list[UUID] | None = Query(default=None),
) -> ...:
    # ... existing filter setup ...
    stmt = select(Flow).where(Flow.organization_id == current_user.active_org_id)
    if folder_id is not None:
        stmt = stmt.where(Flow.folder_id == folder_id)
    if tag_id:
        stmt = (
            stmt.join(FlowTag, FlowTag.flow_id == Flow.id)
            .where(FlowTag.tag_id.in_(tag_id))
            .distinct()
        )
    # ... existing pagination / return logic ...
```

Make sure `FlowTag` is imported at the top of the file.

- [ ] **Step 4: Wire the template filter**

Same pattern in `templates.py`, using `TemplateTag`.

- [ ] **Step 5: Run tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter.py src/backend/tests/unit/api/v1/test_template_tag_filter.py -v
```
Expected: all PASS.

- [ ] **Step 6: Pause before commit**

Proposed commit message:
```
feat(api): filter flows + templates by tag_id (OR semantics)

Adds tag_id query param (repeatable) to GET /api/v1/flows and GET
/api/v1/templates. Multiple tag_id values combine with OR — returns any
flow/template that has at least one of the listed tags. AND semantics
deferred to P1.5.
```

---

## Task 7: React-query hooks for tags

**Files:**
- Create: `src/frontend/src/types/api/tag.ts`
- Create: `src/frontend/src/controllers/API/queries/tags/use-tags.ts`
- Create: `src/frontend/src/controllers/API/queries/tags/use-tag-admin.ts`

**Context:** Fork uses react-query v5 — use `isPending`, not `isLoading`. Jest (not Vitest).

- [ ] **Step 1: Write the TS types**

Create `src/frontend/src/types/api/tag.ts`:

```typescript
export const TAG_COLORS = [
  "slate",
  "red",
  "orange",
  "amber",
  "green",
  "teal",
  "sky",
  "blue",
  "violet",
  "pink",
] as const;

export type TagColor = typeof TAG_COLORS[number];

export interface TagRead {
  id: string;
  name: string;
  color: TagColor;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface TagWrite {
  name: string;
  color: TagColor;
  description?: string | null;
}
```

- [ ] **Step 2: Write the public-read hook**

Create `src/frontend/src/controllers/API/queries/tags/use-tags.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api-client"; // adjust import to match fork's actual http client
import type { TagRead } from "@/types/api/tag";

export const TAG_LIST_KEY = ["tags"] as const;

export function useGetTags() {
  return useQuery({
    queryKey: TAG_LIST_KEY,
    queryFn: async () => (await apiClient.get<TagRead[]>("/api/v1/tags")).data,
  });
}

export function useAssignFlowTags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ flowId, tagIds }: { flowId: string; tagIds: string[] }) =>
      (await apiClient.put(`/api/v1/flows/${flowId}/tags`, { tag_ids: tagIds })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["flows"] }),
  });
}

export function useAssignTemplateTags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ templateId, tagIds }: { templateId: string; tagIds: string[] }) =>
      (await apiClient.put(`/api/v1/templates/${templateId}/tags`, { tag_ids: tagIds })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });
}
```

**Implementer note:** Inspect an existing hooks file in `src/frontend/src/controllers/API/queries/` and copy its exact `apiClient` import path + error handling pattern. Do not guess.

- [ ] **Step 3: Write the admin CRUD hooks**

Create `src/frontend/src/controllers/API/queries/tags/use-tag-admin.ts` with `useListTagsAdmin`, `useCreateTag`, `useUpdateTag`, `useDeleteTag`. Follow the same pattern as existing admin/metadata hooks in the fork (search for `useCreateTemplateMetadata` or similar as a template).

- [ ] **Step 4: Pause before commit**

Proposed commit message:
```
feat(ui): react-query hooks + TS types for tag vocabulary

TagRead / TagWrite / TAG_COLORS in types/api/tag.ts. useGetTags +
useAssignFlowTags + useAssignTemplateTags for regular-user surfaces.
useListTagsAdmin/Create/Update/Delete for platform-admin CRUD. Uses
react-query v5 isPending (fork convention).
```

---

## Task 8: Admin tab UI (Settings > Metadata > Tags)

**Files:**
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/tags-tab.tsx`
- Modify: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx` — add the third tab.
- Create: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/tags-tab.test.tsx`

**Context:** Clone the structure of `flows-tab.tsx` / `components-tab.tsx`. Visible only when `currentUser.is_platform_admin === true`.

- [ ] **Step 1: Write the failing test**

Create the test file using the testing utilities already in use (`@testing-library/react`, the project's custom `renderWithProviders`):

```tsx
import { render, screen, waitFor } from "@/test/renderWithProviders";
import TagsTab from "../tags-tab";

describe("TagsTab", () => {
  it("renders the tag list for a platform admin", async () => {
    // Mock useGetTagsAdmin to return two tags.
    render(<TagsTab currentUser={{ is_platform_admin: true } as any} />);
    await waitFor(() => expect(screen.getByText("finance")).toBeInTheDocument());
    expect(screen.getByText("engineering")).toBeInTheDocument();
  });

  it("hides create button for non-platform-admins", () => {
    render(<TagsTab currentUser={{ is_platform_admin: false } as any} />);
    expect(screen.queryByRole("button", { name: /new tag/i })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement the component**

Create `src/frontend/src/pages/SettingsPage/pages/MetadataPage/tags-tab.tsx` by copying `flows-tab.tsx` and adapting fields to Tag shape. Render a table with columns Name / Color swatch / Description / Created-at / Actions. Row action buttons open an edit drawer that reuses the existing drawer component. Include a "New tag" button visible only to platform admins.

- [ ] **Step 3: Wire the tab in the metadata index**

Edit `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx`. Find the existing `<Tabs>` or tab-list declaration and add a third tab:

```tsx
<Tab label="Tags" value="tags">
  <TagsTab currentUser={currentUser} />
</Tab>
```

If the metadata page uses a router-based tab model rather than in-place tabs, mirror whatever the two existing tabs do.

- [ ] **Step 4: Run the Jest test**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && npx jest src/pages/SettingsPage/pages/MetadataPage/__tests__/tags-tab.test.tsx
```
Expected: both tests PASS.

- [ ] **Step 5: Pause before commit**

Proposed commit message:
```
feat(ui): Settings > Metadata > Tags admin tab

Third tab alongside Flows and Components. Platform-admin-only create/edit/
delete (New tag button hidden otherwise). Color swatch column uses the
10-value palette. Clones the flows-tab structure for consistency.
```

---

## Task 9: TagChip + TagPicker components

**Files:**
- Create: `src/frontend/src/components/common/TagChip/index.tsx`
- Create: `src/frontend/src/components/common/TagChip/__tests__/TagChip.test.tsx`
- Create: `src/frontend/src/components/common/TagPicker/index.tsx`
- Create: `src/frontend/src/components/common/TagPicker/__tests__/TagPicker.test.tsx`
- Modify: the flow header file (discovered in sub-step below).
- Modify: `src/frontend/src/modals/saveAsTemplateModal/...` — add picker below category picker.

- [ ] **Step 1: Identify the flow header file**

Run:
```bash
grep -rn 'flow.name\|FlowHeader\|<h1.*flow\|PageHeader.*flow' src/frontend/src/pages/FlowPage/components/ 2>&1 | head -10
```
Record the file + line where the flow name is rendered in the editor header.

- [ ] **Step 2: Write TagChip test**

Create `src/frontend/src/components/common/TagChip/__tests__/TagChip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import TagChip from "../index";
import type { TagRead } from "@/types/api/tag";

const mkTag = (overrides: Partial<TagRead> = {}): TagRead => ({
  id: "t1",
  name: "finance",
  color: "blue",
  description: null,
  created_by: null,
  created_at: "",
  updated_at: "",
  ...overrides,
});

describe("TagChip", () => {
  it("renders the tag name and a swatch matching the palette color", () => {
    render(<TagChip tag={mkTag({ color: "red" })} />);
    const chip = screen.getByText("finance").closest("span");
    expect(chip).toHaveClass("bg-red-500");
  });
});
```

- [ ] **Step 3: Implement TagChip**

Create `src/frontend/src/components/common/TagChip/index.tsx`:

```tsx
import type { TagRead } from "@/types/api/tag";

const COLOR_BG_MAP = {
  slate: "bg-slate-500",
  red: "bg-red-500",
  orange: "bg-orange-500",
  amber: "bg-amber-500",
  green: "bg-green-500",
  teal: "bg-teal-500",
  sky: "bg-sky-500",
  blue: "bg-blue-500",
  violet: "bg-violet-500",
  pink: "bg-pink-500",
} as const;

interface TagChipProps {
  tag: TagRead;
  onRemove?: (id: string) => void;
  className?: string;
}

export default function TagChip({ tag, onRemove, className }: TagChipProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs text-white ${COLOR_BG_MAP[tag.color]} ${className ?? ""}`}
      title={tag.description ?? tag.name}
    >
      {tag.name}
      {onRemove && (
        <button
          type="button"
          aria-label={`remove ${tag.name}`}
          onClick={() => onRemove(tag.id)}
          className="text-white/80 hover:text-white"
        >
          ×
        </button>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Write TagPicker test + implementation**

TagPicker test asserts the combobox shows available tags, selecting one calls `onChange` with an updated array, selected tags render as chips.

TagPicker implementation is a multi-select combobox. Reuse the fork's existing multi-select component if one exists (search for `MultiSelect` in `src/frontend/src/components/ui/`). If not, build a minimal one using the `ComboBox` primitive.

- [ ] **Step 5: Mount the TagPicker at the three spec B.6 sites**

**Site 1 — flow header:** File from Step 1. Add a `<TagPicker value={flow.tags ?? []} onChange={...} />` near the flow-name heading. On change, call `useAssignFlowTags`.

**Site 2 — save-as-template modal:** `src/frontend/src/modals/saveAsTemplateModal/...`. Add picker below the category picker. Store selection in modal state; on submit, include `tag_ids` in the payload to create-template, or call `useAssignTemplateTags` after create.

**Site 3 — template edit drawer:** If a template edit drawer exists, add the picker there. If not (templates may only be edited through save-as-template), skip this site — no regression.

- [ ] **Step 6: Run frontend tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && npx jest src/components/common/TagChip src/components/common/TagPicker
```
Expected: all PASS.

- [ ] **Step 7: Pause before commit**

Proposed commit message:
```
feat(ui): TagChip + TagPicker components and 3 mount points

TagChip renders a pill from the 10-value palette. TagPicker is a
multi-select combobox. Mounted at (1) flow header, (2) save-as-template
modal, (3) template edit drawer (if present; skipped otherwise). Colors
map to Tailwind tokens; no free-hex input per spec B.5.
```

---

## Task 10: TagFilterChips + wire into flow sidebar + templates modal

**Files:**
- Create: `src/frontend/src/components/common/TagFilterChips/index.tsx`
- Create: `src/frontend/src/components/common/TagFilterChips/__tests__/TagFilterChips.test.tsx`
- Modify: `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarItemsList.tsx` — add the filter row above the tree.
- Modify: `src/frontend/src/modals/templatesModal/index.tsx` — add the filter row above the category grid.
- Modify: flow listing card and template card to render up to N chips with `+M` badge overflow.

- [ ] **Step 1: Write TagFilterChips test**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import TagFilterChips from "../index";

it("toggles a chip on click", () => {
  const onChange = jest.fn();
  render(<TagFilterChips availableTags={[mkTag(), mkTag({ id: "t2", name: "hr", color: "green" })]} selected={[]} onChange={onChange} />);
  fireEvent.click(screen.getByText("finance"));
  expect(onChange).toHaveBeenCalledWith(["t1"]);
});
```

- [ ] **Step 2: Implement TagFilterChips**

```tsx
import type { TagRead } from "@/types/api/tag";
import TagChip from "@/components/common/TagChip";

interface Props {
  availableTags: TagRead[];
  selected: string[];
  onChange: (ids: string[]) => void;
}

export default function TagFilterChips({ availableTags, selected, onChange }: Props) {
  if (availableTags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 pb-2">
      {availableTags.map((t) => {
        const active = selected.includes(t.id);
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(active ? selected.filter((x) => x !== t.id) : [...selected, t.id])}
            className={active ? "opacity-100" : "opacity-50"}
          >
            <TagChip tag={t} />
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Wire in the flow sidebar**

`src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarItemsList.tsx` — above the tree render, add:

```tsx
const { data: tags = [] } = useGetTags();
const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
const visibleTags = tags.filter((t) => flows.some((f) => f.tags?.some((ft) => ft.id === t.id)));

// ...
<TagFilterChips availableTags={visibleTags} selected={selectedTagIds} onChange={setSelectedTagIds} />
// ...
const filteredFlows = selectedTagIds.length === 0 ? flows : flows.filter((f) => f.tags?.some((ft) => selectedTagIds.includes(ft.id)));
```

- [ ] **Step 4: Wire in the templates modal**

Same pattern in `src/frontend/src/modals/templatesModal/index.tsx` above the category grid.

- [ ] **Step 5: Render chips on cards**

- Flow sidebar item — show up to 2 chips with `+N` badge if more.
- Template card (`TemplateCardComponent/index.tsx`) — show up to 3 chips with `+N` badge.

Truncation is display-only; hovering the `+N` shows a tooltip with the full set.

- [ ] **Step 6: Run tests**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && npx jest src/components/common/TagFilterChips
```

- [ ] **Step 7: Pause before commit**

Proposed commit message:
```
feat(ui): tag filter chip row + chip display on flow/template cards

TagFilterChips above the flow sidebar tree + templates modal grid.
Click-to-toggle; hidden when no tag is in use. Flow sidebar items show
up to 2 chips (+N overflow badge), template cards show up to 3.
Filter uses client-side state today; server-side tag_id param wire-up
is covered by Task 7 hooks.
```

---

## Verification After All Tasks

- [ ] `uv run alembic -c src/backend/base/langflow/alembic.ini upgrade head` — clean.
- [ ] `uv run pytest src/backend/tests/unit/services/database/models/test_tag_models.py -v` — PASS (4 tests).
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_tag_admin.py -v` — PASS (7 tests).
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_tags_public.py -v` — PASS (2 tests).
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_assignment.py src/backend/tests/unit/api/v1/test_template_tag_assignment.py -v` — PASS.
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter.py src/backend/tests/unit/api/v1/test_template_tag_filter.py -v` — PASS.
- [ ] `cd src/frontend && npx jest src/components/common/TagChip src/components/common/TagPicker src/components/common/TagFilterChips src/pages/SettingsPage/pages/MetadataPage` — PASS.
- [ ] Manual smoke: log in as a platform admin, create 3 tags, assign to a flow, reload flow list, confirm chips and filter work. Repeat for a template.
- [ ] `git log --oneline p1/batch-1 | head -15` — commits land in the order Task 1 → Task 10.

---

## Self-Review Notes

- **Spec coverage:** B.3 (schema) → Task 1+2. B.4 (API) → Tasks 3-6. B.5 (color palette) → Task 1 (CHECK constraint), Task 2 (TagColor enum), Task 7 (TS constant), Task 9 (Tailwind mapping). B.6 (UI) → Tasks 8-10. B.7 (role enforcement) → Task 3 (PlatformAdmin gate), Task 5 (edit-permission gate). B.8 (deliverables) — all 5 commits represented by Tasks 1, 3-4, 5, 8-9, 10.
- **Placeholders:** Task 7 Step 2 notes "adjust import to match fork's actual http client" and Task 9 Step 1 tells the implementer to discover the flow header file via grep. Both are unavoidable: the exact paths depend on current-state of the fork's frontend, which I chose not to hard-code to avoid drift. Each is bounded to a single grep + substitution.
- **Type consistency:** `Tag`, `FlowTag`, `TemplateTag`, `TagColor`, `TagRead`, `TagWrite` used consistently across backend. TS equivalents `TagColor`, `TagRead`, `TagWrite` in frontend. `TAG_COLORS` is the sole source of truth for palette membership on the frontend.
- **Scope match:** Part B is self-contained in this plan. Part A has its own plan file.
