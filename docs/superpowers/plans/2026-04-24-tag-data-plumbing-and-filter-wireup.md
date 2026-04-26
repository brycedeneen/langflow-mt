# Tag Data Plumbing and Filter Wire-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User-specific commit discipline:** This user has a standing rule — pause and ask before every `git commit`. The commit commands below are the exact command to run *after* the user approves. Stage explicit paths only (no `git add -A` / `.`).

**Goal:** Surface assigned tags on flow and template read shapes so the UI wired in Sprint-2-Part-B (Tasks 7–10) stops being a no-op — chips render on rows, edit panels initialize with current tags, and filter chips actually filter.

**Architecture:** Add `Flow.tags` / `Template.tags` SQLModel relationships via the existing M2M tables. Eager-load through `selectinload` in every list endpoint that returns Flow or Template. Add `tags: list[TagRead]` to `FlowRead` / `FlowHeader` / `TemplateRead` Pydantic shapes, which automatically propagates through the folders endpoint (already uses `FlowRead`). Frontend consumers read the new field and wire filter state through the existing query hooks. An optional AND-combinator is added as a new `tag_match` query param (default `any`, backwards-compatible).

**Tech Stack:** Python 3.11, FastAPI, SQLModel (async), pytest-asyncio, React + TypeScript, react-query v5 (`isPending`), Jest.

**Depends on:** Sprint-2-Part-B (commits `83b744ee16` → `8f0953440d`) — tag tables, SQLModels, CRUD/assign/filter APIs, frontend hooks and components all shipped. Tag data is being written but not yet read on Flow/Template read paths.

**Out of scope:** Adding a UI toggle to switch OR/AND filter modes (only the backend param lands — any future toggle is a trivial follow-up). Per-org tag vocabularies. Free-hex color input.

---

## File Structure

**Modified (backend):**
- `src/backend/base/langflow/services/database/models/flow/model.py` — add `Flow.tags` relationship + add `tags: list[TagRead]` to `FlowRead` and `FlowHeader`.
- `src/backend/base/langflow/services/database/models/template/model.py` — add `Template.tags` relationship + add `tags: list[TagRead]` to `TemplateRead`.
- `src/backend/base/langflow/services/database/models/tag/model.py` — add `Tag.flows` and `Tag.templates` back-populated relationships.
- `src/backend/base/langflow/api/v1/flows.py` — add `selectinload(Flow.tags)` to `read_flows` and any other flow-returning route in this module; optional `tag_match` param on `read_flows`.
- `src/backend/base/langflow/api/v1/templates.py` — add `selectinload(Template.tags)` alongside every existing `selectinload(Template.categories)` call; optional `tag_match` param on `list_templates`.
- `src/backend/base/langflow/api/v1/folders.py` — ensure the folder GET endpoint's flow-list build uses `selectinload(Flow.tags)` when serializing through `FlowRead`.

**New (backend tests):**
- `src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py`
- `src/backend/tests/unit/api/v1/test_template_read_includes_tags.py`
- `src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py` (optional — Task 7 only)

**Modified (frontend):**
- `src/frontend/src/types/flow/index.ts` — add `tags?: TagRead[]` to `FlowType`.
- `src/frontend/src/types/template/index.ts` — add `tags?: TagRead[]` to `TemplateRead`.
- `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts` — accept `tag_id: string[]` param; pass as repeating query string.
- `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx` — remove the "start empty" TODO; initialize `selectedTagIds` from `template.tags ?? []`.
- `src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx` — initialize from `currentSavedFlow.tags ?? []`.
- `src/frontend/src/pages/MainPage/pages/homePage/index.tsx` — filter `folderData.flows.items` by `selectedTagIds` (client-side).
- `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx` — thread `selectedTagIds` into `useListTemplates`.
- `src/frontend/src/pages/MainPage/components/list/index.tsx` — no code change; chips now render because `flow.tags` is populated. Update the inline TODO comment.
- `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx` — no code change; chips now render because `template.tags` is populated. Update the inline TODO comment.

---

## Task 1: Add M2M relationships on Flow / Template / Tag

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py`
- Modify: `src/backend/base/langflow/services/database/models/template/model.py`
- Modify: `src/backend/base/langflow/services/database/models/tag/model.py`

**Context:** Task 2 of Sprint-2-Part-B created `Tag`, `FlowTag`, `TemplateTag` but did not add relationship objects on `Flow` or `Template`. The sibling pattern at `template/model.py:106` shows the exact shape: `categories: list["Category"] = Relationship(back_populates="templates", link_model=TemplateCategory)`. Mirror that.

- [ ] **Step 1: Add `Flow.tags` relationship**

Edit `src/backend/base/langflow/services/database/models/flow/model.py`. Near the existing `user: "User" = Relationship(...)` / `folder: Optional["Folder"] = Relationship(...)` lines (around line 216-221), add:

```python
    tags: list["Tag"] = Relationship(back_populates="flows", link_model=FlowTag)
```

Add the import at the top of the file (near other model imports):

```python
from langflow.services.database.models.tag.model import FlowTag, Tag
```

- [ ] **Step 2: Add `Template.tags` relationship**

Edit `src/backend/base/langflow/services/database/models/template/model.py`. Directly after the existing `categories: list["Category"]` relationship (around line 106-108), add:

```python
    tags: list["Tag"] = Relationship(back_populates="templates", link_model=TemplateTag)
```

Add the import at the top of the file:

```python
from langflow.services.database.models.tag.model import Tag, TemplateTag
```

- [ ] **Step 3: Add back-populated relationships on Tag**

Edit `src/backend/base/langflow/services/database/models/tag/model.py`. After the existing `Tag` SQLModel class body, add two relationship fields:

```python
    flows: list["Flow"] = Relationship(back_populates="tags", link_model=FlowTag)
    templates: list["Template"] = Relationship(back_populates="tags", link_model=TemplateTag)
```

The `Flow` and `Template` forward references only need to resolve at class-registration time. Since `tag/model.py` is imported before `flow/model.py` and `template/model.py` in most call paths, add TYPE_CHECKING imports at the top:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.template.model import Template
```

- [ ] **Step 4: Verify imports resolve at startup**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run python -c "from langflow.services.database.models.flow.model import Flow; from langflow.services.database.models.template.model import Template; from langflow.services.database.models.tag.model import Tag; print('Flow.tags:', Flow.tags); print('Template.tags:', Template.tags); print('Tag.flows:', Tag.flows); print('Tag.templates:', Tag.templates)"
```
Expected: four lines printing the SQLModel RelationshipInfo objects. No ImportError, no circular-import warnings.

- [ ] **Step 5: Run the existing tag model tests to confirm no regression**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/services/database/models/test_tag_models.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Stage explicit paths + pause for commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/backend/base/langflow/services/database/models/flow/model.py && \
git add src/backend/base/langflow/services/database/models/template/model.py && \
git add src/backend/base/langflow/services/database/models/tag/model.py && \
git status --short
```

Proposed commit message:
```
feat(db): add Flow.tags + Template.tags M2M relationships

Adds forward-and-back SQLModel relationships for the flow_tag and
template_tag M2M tables shipped in a73dd31cf140. Flow.tags /
Template.tags allow eager-loading tags in read endpoints via
selectinload; Tag.flows / Tag.templates are included for symmetry.
Existing 4 tag-model tests remain green.
```

STOP. Ask the user before running the commit.

---

## Task 2: Add `tags: list[TagRead]` to FlowRead / FlowHeader / TemplateRead + eager-load in list endpoints

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py` — `FlowRead` and `FlowHeader` pydantic shapes.
- Modify: `src/backend/base/langflow/services/database/models/template/model.py` — `TemplateRead` pydantic shape.
- Modify: `src/backend/base/langflow/api/v1/flows.py` — add `selectinload(Flow.tags)` to `read_flows`.
- Modify: `src/backend/base/langflow/api/v1/templates.py` — add `selectinload(Template.tags)` to every existing `selectinload(Template.categories)` call.
- Modify: `src/backend/base/langflow/api/v1/folders.py` — ensure the folder-with-flows path eager-loads tags.
- Create: `src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py`
- Create: `src/backend/tests/unit/api/v1/test_template_read_includes_tags.py`

**Context:** `FlowRead` / `FlowHeader` at `flow/model.py:247-271` currently declare `tags: list[str] | None = Field(None, ...)` — a legacy Pydantic-only field that was intentionally left in place during Sprint-2-Part-B Task 2. That field needs to be replaced with the new `list[TagRead]` shape so consumers can render chips. Templates has `categories: list[CategoryRead]` at `template/model.py:123` as the exact pattern to mirror.

**Folders endpoint** at `api/v1/folders.py:34` uses `FolderWithPaginatedFlows | FolderReadWithFlows` which both serialize flows through `FlowRead` (confirmed at `folders.py:9`). Updating `FlowRead.tags` automatically propagates there — but the folder handler must also eager-load tags in its flow subquery.

- [ ] **Step 1: Write the failing flow read test**

Create `src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py`:

```python
"""Tests that GET /api/v1/flows/ returns flows with populated tags field."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_flow_read_includes_tags_after_assignment(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    # Seed two tags via admin CRUD.
    t1 = (await client.post("api/v1/admin/tags", json={"name": "ft2_alpha", "color": "blue"}, headers=admin_headers)).json()
    t2 = (await client.post("api/v1/admin/tags", json={"name": "ft2_beta", "color": "green"}, headers=admin_headers)).json()

    # Regular user creates a flow and assigns the two tags.
    flow = (await client.post(
        "api/v1/flows/",
        json={"name": "ft2_flow", "description": "t2", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )).json()
    assign_resp = await client.put(
        f"api/v1/flows/{flow['id']}/tags",
        json={"tag_ids": [t1["id"], t2["id"]]},
        headers=logged_in_headers,
    )
    assert assign_resp.status_code == status.HTTP_200_OK

    # GET /api/v1/flows/ should return the flow with both tags populated.
    resp = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    # Response is a raw list when get_all=True (default).
    mine = [f for f in body if f["id"] == flow["id"]]
    assert len(mine) == 1
    returned_tags = mine[0].get("tags") or []
    returned_ids = {t["id"] for t in returned_tags}
    assert returned_ids == {t1["id"], t2["id"]}
    # Each tag carries the full TagRead shape.
    sample = returned_tags[0]
    assert set(sample.keys()) >= {"id", "name", "color"}


@pytest.mark.asyncio
async def test_flow_read_tags_empty_list_when_unassigned(
    client: AsyncClient, logged_in_headers: dict
) -> None:
    flow = (await client.post(
        "api/v1/flows/",
        json={"name": "ft2_notags", "description": "", "data": {"nodes": [], "edges": []}},
        headers=logged_in_headers,
    )).json()

    resp = await client.get("api/v1/flows/", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    mine = [f for f in resp.json() if f["id"] == flow["id"]]
    assert len(mine) == 1
    assert mine[0].get("tags") == []
```

- [ ] **Step 2: Run — expect failure (field isn't populated / is `None` / is the legacy string list)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py -v
```
Expected: both tests FAIL — the first asserts on `{t1["id"], t2["id"]}` but `tags` is `None` or `[]`; the second passes OR fails depending on whether the Pydantic default is `None` vs `[]`.

- [ ] **Step 3: Update FlowRead / FlowHeader pydantic shape**

Edit `src/backend/base/langflow/services/database/models/flow/model.py`.

Near the top of the file (model.py imports block), add:

```python
from langflow.services.database.models.tag.schema import TagRead
```

Find `FlowRead` at line 247 and replace the legacy `tags: list[str] | None = Field(None, description="The tags of the flow")` line with:

```python
    tags: list[TagRead] = Field(
        default_factory=list,
        description="Tags assigned to this flow via flow_tag",
    )
```

Find `FlowHeader` at line 268 and make the identical replacement.

- [ ] **Step 4: Update TemplateRead pydantic shape**

Edit `src/backend/base/langflow/services/database/models/template/model.py`.

Add `TagRead` to the imports at the top:
```python
from langflow.services.database.models.tag.schema import TagRead
```

Find `TemplateRead` at line 114 and add, after the existing `categories: list[CategoryRead]` line:

```python
    tags: list[TagRead] = Field(
        default_factory=list,
        description="Tags assigned to this template via template_tag",
    )
```

- [ ] **Step 5: Add `selectinload(Flow.tags)` to `read_flows`**

Edit `src/backend/base/langflow/api/v1/flows.py`.

Find the `read_flows` handler (line 428). Near the initial `stmt = select(Flow).where(...)` construction (around lines 478-492), add a `.options(selectinload(Flow.tags))` call. The cleanest place is right after the `select(Flow)` is created but before the conditional `.where(...)` chain:

```python
    # Add `.options(selectinload(Flow.tags))` so the tags relationship is
    # eager-loaded and can be serialized into FlowRead without N+1 queries.
    stmt = select(Flow).options(selectinload(Flow.tags)).where(...)
```

Ensure `selectinload` and `Flow.tags` are importable at the top of the file:

```python
from sqlalchemy.orm import selectinload

from langflow.services.database.models.flow.model import Flow
# Flow.tags is auto-resolved via the relationship added in Task 1 — no separate import needed.
```

If there are other handlers in `flows.py` that return `FlowRead` or `FlowHeader` and currently do NOT eager-load tags (grep `select(Flow)` inside this file), add the same `.options(selectinload(Flow.tags))` to each. A handler that returns a single flow (e.g. `read_flow(flow_id)`) should also eager-load if its response is `FlowRead`.

- [ ] **Step 6: Add `selectinload(Template.tags)` everywhere `Template.categories` is eager-loaded**

Edit `src/backend/base/langflow/api/v1/templates.py`.

Grep for every `.options(selectinload(Template.categories))` call (there are 10, based on prior recon: lines 175, 240, 344, 352, 426, 539, 557, 572, 590, 605). Extend each to also load tags:

```python
.options(
    selectinload(Template.categories),
    selectinload(Template.tags),
)
```

(The single-argument form `.options(selectinload(Template.categories))` can be converted to the multi-argument form, OR each can be chained — either works. Pick the form that produces the smallest diff.)

- [ ] **Step 7: Verify folder endpoint eager-loads tags**

Open `src/backend/base/langflow/api/v1/folders.py`.

Find the handler that returns `FolderWithPaginatedFlows | FolderReadWithFlows` (around line 34). Locate where the folder's flows are queried — look for `select(Flow)` or equivalent. Add `.options(selectinload(Flow.tags))` to that query so the folder response also serializes tags. If the handler delegates to a helper in `flow/starter.py` or similar, update the helper.

If the folder handler serializes flows via a raw SELECT without going through the ORM, ensure the flow-in-folder serialization result has access to each flow's tags (easiest: use the same `select(Flow).options(...).where(Flow.folder_id == ...)` pattern as `read_flows`).

- [ ] **Step 8: Run the tests — expect PASS**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py -v
```
Expected: 2 passed.

- [ ] **Step 9: Write the failing template read test**

Create `src/backend/tests/unit/api/v1/test_template_read_includes_tags.py`:

```python
"""Tests that GET /api/v1/templates returns templates with populated tags field."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


async def _create_template_with_source_flow(
    client: AsyncClient, admin_headers: dict, name: str
) -> dict:
    """Create a platform-scoped template via the API. Returns JSON."""
    # Seed a source flow via raw SQLModel session (API create requires one).
    async with session_scope() as session:
        flow = Flow(
            id=uuid4(),
            name=f"{name}-source",
            data={"nodes": [], "edges": []},
            user_id=None,
            organization_id=None,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        source_id = flow.id

    resp = await client.post(
        "api/v1/templates/",
        json={"name": name, "scope": "platform", "source_flow_id": str(source_id)},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    return resp.json()


async def _cleanup_template(admin_headers: dict, template_id: str, client: AsyncClient) -> None:
    await client.delete(f"api/v1/templates/{template_id}", headers=admin_headers)


@pytest.mark.asyncio
async def test_template_list_includes_tags_after_assignment(
    client: AsyncClient, admin_headers: dict
) -> None:
    t1 = (await client.post("api/v1/admin/tags", json={"name": "tt2_x", "color": "teal"}, headers=admin_headers)).json()
    t2 = (await client.post("api/v1/admin/tags", json={"name": "tt2_y", "color": "pink"}, headers=admin_headers)).json()

    tmpl = await _create_template_with_source_flow(client, admin_headers, "tt2_tmpl")
    try:
        await client.put(
            f"api/v1/templates/{tmpl['id']}/tags",
            json={"tag_ids": [t1["id"], t2["id"]]},
            headers=admin_headers,
        )
        resp = await client.get("api/v1/templates", headers=admin_headers)
        assert resp.status_code == status.HTTP_200_OK
        mine = [x for x in resp.json() if x["id"] == tmpl["id"]]
        assert len(mine) == 1
        returned_ids = {t["id"] for t in mine[0].get("tags", [])}
        assert returned_ids == {t1["id"], t2["id"]}
    finally:
        await _cleanup_template(admin_headers, tmpl["id"], client)


@pytest.mark.asyncio
async def test_template_list_tags_empty_when_unassigned(
    client: AsyncClient, admin_headers: dict
) -> None:
    tmpl = await _create_template_with_source_flow(client, admin_headers, "tt2_bare")
    try:
        resp = await client.get("api/v1/templates", headers=admin_headers)
        assert resp.status_code == status.HTTP_200_OK
        mine = [x for x in resp.json() if x["id"] == tmpl["id"]]
        assert len(mine) == 1
        assert mine[0].get("tags") == []
    finally:
        await _cleanup_template(admin_headers, tmpl["id"], client)
```

- [ ] **Step 10: Run the template test — expect PASS**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_template_read_includes_tags.py -v
```
Expected: 2 passed.

- [ ] **Step 11: Regression sweep**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest \
  src/backend/tests/unit/api/v1/test_flows.py \
  src/backend/tests/unit/api/v1/test_flow_tag_assignment.py \
  src/backend/tests/unit/api/v1/test_flow_tag_filter.py \
  src/backend/tests/unit/api/v1/test_template_tag_assignment.py \
  src/backend/tests/unit/api/v1/test_template_tag_filter.py \
  src/backend/tests/unit/api/v1/test_tags_public.py \
  src/backend/tests/unit/api/v1/admin/test_tags_admin.py \
  src/backend/tests/unit/services/database/models/test_tag_models.py \
  -v --tb=short
```
Expected: all pass. If a test now sees a `tags: []` where it previously saw no `tags` key at all, update the test ONLY if it was asserting the *absence* of the field (unlikely).

- [ ] **Step 12: Stage + pause**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/backend/base/langflow/services/database/models/flow/model.py \
        src/backend/base/langflow/services/database/models/template/model.py \
        src/backend/base/langflow/api/v1/flows.py \
        src/backend/base/langflow/api/v1/templates.py \
        src/backend/base/langflow/api/v1/folders.py \
        src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py \
        src/backend/tests/unit/api/v1/test_template_read_includes_tags.py && \
git status --short
```

Proposed commit message:
```
feat(api): return tags: list[TagRead] on FlowRead / FlowHeader / TemplateRead

Extends the read shapes with a fully-populated tags field, eagerly
loaded via selectinload in read_flows, list_templates, and every other
handler that serializes through these response models. Folder endpoint
inherits the change (it already serializes flows via FlowRead).

Replaces the legacy Pydantic-only `tags: list[str] | None` fields on
FlowRead and FlowHeader — the legacy field was a remnant of the
dropped flow.tags JSON column and never carried real data.

Covered by 4 new integration tests. Regression sweep across 8 tag and
flow/template test files is green.
```

STOP. Ask the user before running the commit.

---

## Task 3: Update frontend types

**Files:**
- Modify: `src/frontend/src/types/flow/index.ts` — update `FlowType` tags field from legacy shape to `TagRead[]`.
- Modify: `src/frontend/src/types/template/index.ts` — add `tags: TagRead[]` to `TemplateRead`.

**Context:** The frontend already imports `TagRead` from `@/types/tag` (shipped in Task 7 of Sprint-2-Part-B). The legacy `FlowType.tags?: string[]` field is what the Task 10 defensive `coerceTagList` guards against — once replaced with the proper `TagRead[]`, the guard passes through real data.

- [ ] **Step 1: Update FlowType**

Edit `src/frontend/src/types/flow/index.ts`. Find the existing `tags?: string[]` field on `FlowType` (Task 10 recon noted it's at line 29 approximately) and replace with:

```typescript
import type { TagRead } from "@/types/tag";

// ...

export type FlowType = {
  // ... existing fields ...
  tags?: TagRead[]; // populated by GET /api/v1/flows/ and folder listings (see backend commit).
};
```

Search for other references to `FlowType.tags` or code that treats `tags` as a `string[]`:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
  grep -rn '\.tags' src/frontend/src --include='*.ts' --include='*.tsx' | \
  grep -vE 'TagRead|TagWrite|TagChip|TagPicker|TagFilterChips|tags-tab|TAG_COLOR|types/tag' | \
  head -30
```

For each callsite, verify it treats `tags` as `TagRead[]` (objects) and not as `string[]`. If any callsite uses `flow.tags[0]` expecting a string, update it.

- [ ] **Step 2: Update TemplateRead**

Edit `src/frontend/src/types/template/index.ts`. Find the `TemplateRead` (or `type Template = {...}`) type and add:

```typescript
import type { TagRead } from "@/types/tag";

// ...
// Inside TemplateRead / Template type:
  tags?: TagRead[];
```

If `TemplateRead` lives in a different file (the Task 7 recon noted it's at `@/types/template/index.ts`), follow the existing file.

- [ ] **Step 3: Type-check**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && \
  npx tsc --noEmit 2>&1 | grep -iE 'types/flow|types/template|\.tags' | head -30
```
Expected: no errors in your changes.

If type errors appear in files you didn't write (e.g. downstream consumers expecting a `string[]`), pause and report — that means a caller was relying on the old shape. Patch the call site minimally (the most likely fix: cast via `coerceTagList` from `@/types/tag/runtime-validate`) or, if it's the Task 10 `coerceTagList` guard itself, verify it already handles the new shape (it should — the guard accepts anything shaped like `TagRead`).

- [ ] **Step 4: Stage + pause**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/frontend/src/types/flow/index.ts \
        src/frontend/src/types/template/index.ts && \
git status --short
```

Proposed commit message:
```
feat(ui): FlowType.tags + TemplateRead.tags use TagRead shape

Replaces the legacy FlowType.tags: string[] with TagRead[] matching the
new backend serialization. Adds TemplateRead.tags so the edit panel,
card rows, and filter wiring can consume real data.
```

STOP. Ask the user before committing.

---

## Task 4: Initialize TagPicker with current tags on edit surfaces

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx` — initialize `selectedTagIds` from `template.tags`.
- Modify: `src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx` — initialize from `currentSavedFlow.tags`.

**Context:** Task 9 of Sprint-2-Part-B intentionally initialized both edit surfaces with an empty `selectedTagIds` array and a TODO comment explaining the data gap. Now that Task 2 of this plan populates `tags` on both read shapes, we can remove the TODOs and use the real data. The existing `selectedTagIds.length > 0` safety gate is no longer needed for these surfaces because the user always sees the current state before saving.

- [ ] **Step 1: Initialize TemplateEditPanel from `template.tags`**

Edit `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx`.

Replace the existing `selectedTagIds` useState initializer (currently `useState<string[]>([])` with the TODO comment above it) with:

```typescript
// template.tags is now populated by TemplateRead (see follow-up plan
// 2026-04-24, Task 2). Mirror the pattern used for selectedCategoryIds.
const [selectedTagIds, setSelectedTagIds] = useState<string[]>(
  template.tags?.map((t) => t.id) ?? [],
);
```

Delete the old TODO comment above this block.

Because the edit surface now reflects current state, you can also remove the `selectedTagIds.length > 0` safety gate on the tag-assign mutation chained in the update `onSuccess`. Change:

```typescript
if (selectedTagIds.length > 0) {
  assignTemplateTags.mutate({...});
}
```

to always call the mutation unconditionally:

```typescript
assignTemplateTags.mutate({ templateId: template.id, tagIds: selectedTagIds });
```

This means "save with an empty tag picker" now correctly clears tags on the server. Update the inline comment.

- [ ] **Step 2: Initialize flow toolbar from `currentSavedFlow.tags`**

Edit `src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx`.

Replace the `FlowTagsButton`'s `useState<string[]>([])` initializer (with its TODO) with:

```typescript
// currentSavedFlow.tags is populated by FlowRead (see follow-up plan
// 2026-04-24, Task 2). If the toolbar is invoked before the saved flow
// is available, start empty.
const [selectedTagIds, setSelectedTagIds] = useState<string[]>(
  currentSavedFlow?.tags?.map((t) => t.id) ?? [],
);
```

Confirm `currentSavedFlow` is already the read source used by the button. If it isn't (e.g. the button uses `currentFlow` from `useFlowStore` which doesn't carry tags), switch to `useFlowsManagerStore((s) => s.currentFlow)` — the same source recon identified in Task 9.

Additionally, because the button fires `useAssignFlowTags.mutate` on every chip toggle, re-sync local state when the underlying flow's tags change (e.g., another tab assigned tags):

```typescript
useEffect(() => {
  setSelectedTagIds(currentSavedFlow?.tags?.map((t) => t.id) ?? []);
}, [currentSavedFlow?.tags]);
```

- [ ] **Step 3: Manual/Jest check**

The existing Task 8 / Task 9 unit tests may have asserted "empty selection" behavior. Run:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && \
  npx jest src/modals/templatesModal src/components/core/flowToolbarComponent src/components/common/TagPicker 2>&1 | tail -30
```
Expected: all pass. If a test mocked `template.tags = []` to verify the empty init, that assertion is still correct — this change makes the init pass-through, not empty-fallback.

If the flow-toolbar has no test, that's fine — the button was added in Task 9 without one.

- [ ] **Step 4: Stage + pause**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx \
        src/frontend/src/components/core/flowToolbarComponent/components/flow-toolbar-options.tsx && \
git status --short
```

Proposed commit message:
```
fix(ui): initialize tag picker with current tags on edit surfaces

TemplateEditPanel and the flow toolbar's Tag button now read
template.tags / currentSavedFlow.tags (populated by the previous
commit) to seed selectedTagIds. This unblocks the Task 9 safety gates
added in 36fa40db11 — the user now sees the current tag state before
saving, so an empty save correctly clears tags rather than silently
preserving them. Removes the `selectedTagIds.length > 0` safety check
on TemplateEditPanel's chained assign mutation.
```

STOP. Ask before committing.

---

## Task 5: Wire flow list filter (client-side)

**Files:**
- Modify: `src/frontend/src/pages/MainPage/pages/homePage/index.tsx`
- Modify: `src/frontend/src/pages/MainPage/components/list/index.tsx` — refresh the TODO / comment (no behavior change).

**Context:** The flow list on the HomePage is driven by `useGetFolderQuery` which hits `GET /api/v1/folders/{id}` (not `/flows`). The folders response already includes `flow.tags` after Task 2. Rather than plumbing a new `tag_id` query param through the folder endpoint, filter client-side: intersect each flow's `tags[].id` set with `selectedTagIds`. The response set is paginated but small (typical page is ≤50 flows), so client-side filtering is fine.

- [ ] **Step 1: Wire the filter in HomePage**

Edit `src/frontend/src/pages/MainPage/pages/homePage/index.tsx`.

Find the existing rendering of `ListComponent` with `selectedTagIds` as an unused prop. Change the passed `flowItems` (or whatever the list prop is called) to a filtered copy:

```typescript
const allFlowItems = folderData?.flows?.items ?? [];
const visibleFlowItems =
  selectedTagIds.length === 0
    ? allFlowItems
    : allFlowItems.filter((f) =>
        f.tags?.some((t) => selectedTagIds.includes(t.id)),
      );
// ... pass visibleFlowItems into ListComponent ...
```

Also compute `availableTags` to filter to "tags in use by visible flows" only (per the original plan's vision), so the filter row hides unused tags:

```typescript
const tagsInUse = React.useMemo(() => {
  const inUse = new Set<string>();
  allFlowItems.forEach((f) => f.tags?.forEach((t) => inUse.add(t.id)));
  return allTags.filter((t) => inUse.has(t.id));
}, [allFlowItems, allTags]);
```

Pass `tagsInUse` (not `allTags`) to `TagFilterChips`' `availableTags` prop.

**Edge case:** if `selectedTagIds` contains an id that's no longer in `tagsInUse` (e.g. user deselected the last flow with that tag), keep the id in the selection — the user may want to re-select other flows without losing their filter state. Only drop when they explicitly uncheck.

- [ ] **Step 2: Update the list-component TODO**

Edit `src/frontend/src/pages/MainPage/components/list/index.tsx`. The previous TODO said "Filter flows by tag_id once FlowHeader/FlowRead exposes the new flow_tag-backed tag list." Replace with a one-liner reflecting the current state:

```typescript
// flow.tags is populated by FlowRead (follow-up commit), consumed by
// HomePage for client-side filtering; chips render per-row below.
```

No behavior change in this file — the `coerceTagList` guard already passes through real data.

- [ ] **Step 3: Manual smoke**

The worktree likely doesn't run the full frontend dev server, but verify the unit tests for TagFilterChips + ListComponent still pass:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && \
  npx jest src/components/common/TagFilterChips src/pages/MainPage/components/list 2>&1 | tail -20
```
Expected: pass.

- [ ] **Step 4: Stage + pause**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/frontend/src/pages/MainPage/pages/homePage/index.tsx \
        src/frontend/src/pages/MainPage/components/list/index.tsx && \
git status --short
```

Proposed commit message:
```
feat(ui): wire TagFilterChips to actual flow list filtering

HomePage now filters the folder-response flow list client-side by
intersecting each flow's tags with selectedTagIds. The filter chip row
is populated only with tags actually assigned to visible flows
(tagsInUse), so the row auto-hides when the vocabulary doesn't intersect
the user's workspace.
```

STOP.

---

## Task 6: Wire template list filter (server-side)

**Files:**
- Modify: `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts` — add `tag_id: string[]` param.
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx` — pass selectedTagIds through.
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx` — update TODO comment (no behavior change).

**Context:** Unlike the flow list, the templates modal hits `GET /api/v1/templates` directly via `useListTemplates` — which already accepts `tag_id` from Task 6 of Sprint-2-Part-B. We just plumb the new param through the hook and pass `selectedTagIds` down.

- [ ] **Step 1: Extend useListTemplates**

Edit `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts`.

Add `tag_id` to the params type:

```typescript
export type ListTemplatesParams = {
  category?: string;
  scope?: "platform" | "org" | "all";
  created_by_me?: boolean;
  include_archived?: boolean;
  tag_id?: string[];
};
```

Add the query-string serialization in the `fn`:

```typescript
if (params?.tag_id && params.tag_id.length > 0) {
  for (const id of params.tag_id) {
    searchParams.append("tag_id", id);
  }
}
```

- [ ] **Step 2: Thread selectedTagIds into useListTemplates**

Edit `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx`.

Find where `useListTemplates` is called. Add `tag_id: selectedTagIds` to the params object:

```typescript
const { data: templates = [], isPending } = useListTemplates({
  category: currentTab,
  // ... existing params ...
  tag_id: selectedTagIds, // empty array is ignored by the hook's serializer
});
```

Remove the TODO that said "state is held but not threaded" — it's threaded now.

- [ ] **Step 3: Compute tagsInUse for the filter chip row**

Same pattern as HomePage. Before rendering `<TagFilterChips>`, compute:

```typescript
const tagsInUse = React.useMemo(() => {
  const inUse = new Set<string>();
  templates.forEach((t) => t.tags?.forEach((tag) => inUse.add(tag.id)));
  return allTags.filter((t) => inUse.has(t.id));
}, [templates, allTags]);
```

Pass `tagsInUse` (not `allTags`) to `TagFilterChips`.

**Note on server-side filtering + tagsInUse:** server-side filtering returns only matching templates, so `tagsInUse` computed from the filtered list will collapse to just the selected tags after a filter is applied. To keep the full vocabulary visible while a filter is active, fetch twice — once unfiltered (for the chip row), once filtered (for the grid). Implement this with two hook calls:

```typescript
const { data: allTemplates = [] } = useListTemplates({
  category: currentTab,
  // ... existing params WITHOUT tag_id ...
});
const { data: filteredTemplates = [] } = useListTemplates({
  category: currentTab,
  // ... existing params ...
  tag_id: selectedTagIds,
});
const templates = selectedTagIds.length === 0 ? allTemplates : filteredTemplates;
const tagsInUse = React.useMemo(() => { /* ... computed from allTemplates */ }, [allTemplates, allTags]);
```

Or, simpler: keep a single query and just use `allTags` unfiltered on the chip row (users see the full vocabulary always). Pick whichever is cleaner in the actual file.

- [ ] **Step 4: Update TemplateCardComponent TODO**

Edit `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx`. Replace the TODO with a one-liner:

```typescript
// template.tags is populated by TemplateRead (follow-up commit).
```

No behavior change.

- [ ] **Step 5: Run tests**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1/src/frontend && \
  npx jest src/modals/templatesModal src/controllers/API/queries/templates src/components/common/TagFilterChips 2>&1 | tail -20
```
Expected: pass. If the existing `useListTemplates` test doesn't cover the new `tag_id` param path, add one assertion in the test file (mock `searchParams.append` tracking, assert it's called twice for two tag ids).

- [ ] **Step 6: Stage + pause**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/frontend/src/controllers/API/queries/templates/use-list-templates.ts \
        src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx \
        src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx && \
git status --short
```

Proposed commit message:
```
feat(ui): wire TagFilterChips to template list filtering

useListTemplates accepts a repeatable tag_id param; the templates
modal threads selectedTagIds through so the grid filter is handled
server-side by GET /api/v1/templates?tag_id=... (OR semantics).
```

STOP.

---

## Task 7: (Optional) Backend AND-combinator for tag_id filter

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` — add `tag_match: Literal["any", "all"] = "any"` query param on `read_flows`.
- Modify: `src/backend/base/langflow/api/v1/templates.py` — same on `list_templates`.
- Create: `src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py`

**Context:** This was explicitly deferred in the Sprint-2-Part-B spec (AND semantics → P1.5). Include or skip at your discretion. If included, it is backend-only — no UI toggle ships with this plan. The default remains `tag_match="any"` (OR) for full backwards compatibility.

SQL pattern for AND semantics:

```sql
SELECT flow.* FROM flow WHERE flow.id IN (
  SELECT flow_id FROM flow_tag
  WHERE tag_id = ANY(:tag_ids)
  GROUP BY flow_id
  HAVING COUNT(DISTINCT tag_id) = :n
)
```

SQLAlchemy version:

```python
from sqlalchemy import func
from sqlalchemy.sql import select as sa_select

if tag_id and tag_match == "all":
    n = len(set(tag_id))
    subq = (
        sa_select(FlowTag.flow_id)
        .where(col(FlowTag.tag_id).in_(tag_id))
        .group_by(FlowTag.flow_id)
        .having(func.count(func.distinct(FlowTag.tag_id)) == n)
    )
    stmt = stmt.where(col(Flow.id).in_(subq))
elif tag_id:
    # existing OR path
    stmt = (
        stmt.join(FlowTag, FlowTag.flow_id == Flow.id)
        .where(col(FlowTag.tag_id).in_(tag_id))
        .distinct()
    )
```

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py`:

```python
"""Tests for tag_match=all on GET /api/v1/flows."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient


async def _mkflow(client: AsyncClient, headers: dict, name: str) -> dict:
    resp = await client.post(
        "api/v1/flows/",
        json={"name": name, "description": "and", "data": {"nodes": [], "edges": []}},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


async def _mktag(client: AsyncClient, admin_headers: dict, name: str, color: str = "blue") -> dict:
    resp = await client.post(
        "api/v1/admin/tags", json={"name": name, "color": color}, headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


@pytest.mark.asyncio
async def test_flow_list_and_combinator_returns_only_all_match(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    t1 = await _mktag(client, admin_headers, "ta1")
    t2 = await _mktag(client, admin_headers, "ta2", "green")

    f1 = await _mkflow(client, logged_in_headers, "tandf1")  # t1 only
    f2 = await _mkflow(client, logged_in_headers, "tandf2")  # t1 AND t2
    f3 = await _mkflow(client, logged_in_headers, "tandf3")  # t2 only

    await client.put(f"api/v1/flows/{f1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f2['id']}/tags", json={"tag_ids": [t1["id"], t2["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f3['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=logged_in_headers)

    # AND: only f2 has both t1 AND t2.
    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}&tag_id={t2['id']}&tag_match=all",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = {x["id"] for x in resp.json()}
    assert f2["id"] in ids
    assert f1["id"] not in ids
    assert f3["id"] not in ids


@pytest.mark.asyncio
async def test_flow_list_default_is_or_semantics(
    client: AsyncClient, admin_headers: dict, logged_in_headers: dict
) -> None:
    t1 = await _mktag(client, admin_headers, "tor1")
    t2 = await _mktag(client, admin_headers, "tor2", "red")

    f1 = await _mkflow(client, logged_in_headers, "torf1")
    f2 = await _mkflow(client, logged_in_headers, "torf2")
    await client.put(f"api/v1/flows/{f1['id']}/tags", json={"tag_ids": [t1["id"]]}, headers=logged_in_headers)
    await client.put(f"api/v1/flows/{f2['id']}/tags", json={"tag_ids": [t2["id"]]}, headers=logged_in_headers)

    # No tag_match param → default OR: both f1 and f2 appear.
    resp = await client.get(
        f"api/v1/flows/?tag_id={t1['id']}&tag_id={t2['id']}",
        headers=logged_in_headers,
    )
    ids = {x["id"] for x in resp.json()}
    assert f1["id"] in ids
    assert f2["id"] in ids
```

- [ ] **Step 2: Run — expect first test to fail (tag_match param ignored, falls through to OR)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
  uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py -v
```
Expected: `test_flow_list_and_combinator_returns_only_all_match` FAILS (f1 and/or f3 are returned when only f2 should be). `test_flow_list_default_is_or_semantics` PASSES.

- [ ] **Step 3: Add tag_match param + AND branch to read_flows**

Edit `src/backend/base/langflow/api/v1/flows.py`.

Add `tag_match` to the `read_flows` signature:

```python
from typing import Literal

# ...

async def read_flows(
    # ... existing params ...
    tag_id: Annotated[list[UUID] | None, Query()] = None,
    tag_match: Annotated[Literal["any", "all"], Query()] = "any",
):
```

Replace the existing `if tag_id:` branch with the conditional described in the Context block above:

```python
if tag_id:
    if tag_match == "all":
        from sqlalchemy import func
        n = len(set(tag_id))
        subq = (
            select(FlowTag.flow_id)
            .where(col(FlowTag.tag_id).in_(tag_id))
            .group_by(FlowTag.flow_id)
            .having(func.count(func.distinct(FlowTag.tag_id)) == n)
        )
        stmt = stmt.where(col(Flow.id).in_(subq))
    else:
        stmt = (
            stmt.join(FlowTag, FlowTag.flow_id == Flow.id)
            .where(col(FlowTag.tag_id).in_(tag_id))
            .distinct()
        )
```

Ensure `func` is imported (`from sqlalchemy import func`).

- [ ] **Step 4: Mirror in `list_templates`**

Edit `src/backend/base/langflow/api/v1/templates.py`. Same shape — add `tag_match` param, swap the `if tag_id:` branch to the same `any`/`all` conditional using `TemplateTag` + `Template`.

- [ ] **Step 5: Run the tests — expect PASS**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
  uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py \
                src/backend/tests/unit/api/v1/test_flow_tag_filter.py \
                src/backend/tests/unit/api/v1/test_template_tag_filter.py \
                -v
```
Expected: all pass (the OR path tests from Sprint-2-Part-B Task 6 must still pass unchanged).

- [ ] **Step 6: Stage + pause**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && \
git add src/backend/base/langflow/api/v1/flows.py \
        src/backend/base/langflow/api/v1/templates.py \
        src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py && \
git status --short
```

Proposed commit message:
```
feat(api): add tag_match=any|all param for AND-combinator filtering

New optional query param on GET /api/v1/flows and GET /api/v1/templates.
Default remains "any" (OR semantics; backwards compatible). Setting
tag_match=all returns only rows that have every one of the listed tag
ids (AND semantics), via a GROUP BY ... HAVING COUNT(DISTINCT) subquery.

Addresses the P1.5 follow-up from the Sprint-2-Part-B tagging design.
No frontend toggle ships with this — the UI default stays OR.
```

STOP.

---

## Verification After All Tasks

- [ ] `cd src/backend/base/langflow && uv run alembic upgrade head` — clean.
- [ ] `uv run pytest src/backend/tests/unit/services/database/models/test_tag_models.py -v` — 4 passed.
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_flow_read_includes_tags.py src/backend/tests/unit/api/v1/test_template_read_includes_tags.py -v` — 4 passed.
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter.py src/backend/tests/unit/api/v1/test_template_tag_filter.py -v` — still passes (OR path untouched).
- [ ] (If Task 7 ran) `uv run pytest src/backend/tests/unit/api/v1/test_flow_tag_filter_and_combinator.py -v` — 2 passed.
- [ ] Full tag regression: `uv run pytest src/backend/tests/unit/api/v1/admin/test_tags_admin.py src/backend/tests/unit/api/v1/test_tags_public.py src/backend/tests/unit/api/v1/test_flow_tag_assignment.py src/backend/tests/unit/api/v1/test_template_tag_assignment.py -v` — all green.
- [ ] Frontend: `cd src/frontend && npx jest src/components/common/TagChip src/components/common/TagPicker src/components/common/TagFilterChips src/pages/SettingsPage/pages/MetadataPage src/controllers/API/queries/tags` — all green.
- [ ] Manual smoke (if a dev server is up): create 3 tags, assign 2 to a flow, reload the HomePage, confirm chips render and the filter row shows only tags-in-use. Repeat for templates modal.
- [ ] `git log --oneline p1/batch-1 | head -8` — commits land in task order, with the standing "Co-Authored-By: Claude …" trailer on each.

---

## Self-Review Notes

- **Spec coverage:** All three follow-up goals covered. Item 1 (read shapes + eager-load) → Tasks 1-2. Item 2 (AND combinator, P1.5) → optional Task 7. Item 3 (filter wire-up) → Tasks 5-6, which depend on Task 3's frontend type update, which depends on Task 2's backend shape.
- **Type consistency:** `TagRead` is imported everywhere as the same shape. `selectedTagIds` is `string[]` at every mount site. `tag_id` query param is `list[UUID]` on the backend and `string[]` on the frontend — matched serialization via `searchParams.append`.
- **Placeholders:** None. Every step has concrete code or an exact command.
- **Dependencies:** Task 3 depends on Task 2 (backend shape must ship first so TS types match what the server returns). Tasks 4-6 depend on Task 3. Task 7 is independent (backend-only, doesn't need Task 3).
- **Skippable:** Task 7 is optional per the spec deferral. Skipping it leaves OR semantics as the only available filter mode.
- **Risk:** Task 2's eager-load change touches 10+ `selectinload(Template.categories)` sites in `templates.py`. Missing one means tag-less responses in that handler. Mitigation: the test at Step 10 only covers the list endpoint; if a single-template GET regresses, it won't be caught until surfaced by the UI. Worth a grep-audit during review: `grep -n 'select(Template)' src/backend/base/langflow/api/v1/templates.py | wc -l` should equal the number of `.options(selectinload(Template.tags))` calls.
- **Client-side vs server-side filter asymmetry** (Task 5 vs Task 6): intentional. HomePage consumes folder responses (not `/flows` directly) so adding server-side tag filtering would require threading `tag_id` through `GET /folders/{id}`. That's a bigger change than the client-side filter for the typical page size (<50 flows).
