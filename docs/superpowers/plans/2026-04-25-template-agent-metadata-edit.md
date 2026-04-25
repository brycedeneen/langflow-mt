# Template Agent Metadata Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `agent_summary` and `agent_usage_notes` to the `Template` model, surface them in the existing `TemplateEditPanel`, rewire the assistant's template-context plumbing to read from `Template` (replacing dead `Flow`/`TemplateMetadata` lookups), and remove the now-defunct Settings → Flows tab.

**Architecture:** One Alembic migration adds two text columns to `template`, adds `flow.based_on_template_id` (FK → template.id), drops `flow.based_on_template_flow_id`, drops the `template_metadata` table, and one-time-backfills agent fields from `*.metadata.json` files. Backend/frontend code rename the Flow→Template pointer and rewire the assistant's four touch points (`flow_template_context`, `metadata_lookup`, `template_apply`, `mcp_server`) to query the `Template` table directly. The `TemplateEditPanel` gains two textareas; the dead Settings sub-tab is deleted.

**Tech Stack:** Python 3.11, SQLModel, Alembic, FastAPI, Pydantic, React, TypeScript, Jest, react-query v5.

**Spec reference:** `docs/superpowers/specs/2026-04-25-template-agent-metadata-edit-design.md`

---

## Conventions

- **TDD:** every feature task is "write failing test → run it → implement → run it → commit." For pure deletions/refactors that are covered by existing tests, the failing test step is a green test that demonstrates the expected behavior post-change (or `pytest -k …` of the existing test).
- **Commits:** stage explicit paths only — never `git add -A`/`.`/`-a` (subagent landmine per project memory). Commit messages use the conventional `feat:`, `refactor:`, `chore:`, `test:`, `fix:` prefixes seen in recent history.
- **Permission to commit:** the user has a standing rule to be asked before any `git commit`. Each task's commit step instructs the executor to **pause and request explicit approval from the user** before running `git commit`. Do not bypass.
- **Backend tests** run with `uv run pytest <path>` from the langflow root.
- **Frontend tests** use Jest (NOT Vitest, per project memory): `cd src/frontend && npm test -- <pattern>`.
- **Test isolation for `src/lfx`:** not relevant to this plan (no lfx changes).

---

## Task 1: Alembic migration — schema + backfill

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<new_rev>_template_agent_metadata.py`
- Test: `src/backend/tests/unit/services/database/test_template_agent_metadata_migration.py`

- [ ] **Step 1: Generate the empty revision file**

```bash
cd /Users/brycedeneen/dev/langflow/src/backend/base/langflow && uv run alembic revision -m "template agent metadata + based_on_template_id"
```

This creates `alembic/versions/<rev>_template_agent_metadata_based_on_.py` with `down_revision = "e1f42ac1d7a9"` (current head). Note the generated revision id; subsequent steps refer to it as `<NEW_REV>`.

- [ ] **Step 2: Write the failing migration smoke test**

Create `src/backend/tests/unit/services/database/test_template_agent_metadata_migration.py`:

```python
"""Smoke test: the new revision adds template agent columns, swaps the
flow→template FK, and drops the legacy template_metadata table.
"""
from __future__ import annotations

import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def alembic_cfg(tmp_path):
    cfg = Config("/Users/brycedeneen/dev/langflow/src/backend/base/langflow/alembic.ini")
    db_url = f"sqlite:///{tmp_path / 'mig.db'}"
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option(
        "script_location",
        "/Users/brycedeneen/dev/langflow/src/backend/base/langflow/alembic",
    )
    return cfg, db_url


def _columns(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _tables(engine):
    return set(inspect(engine).get_table_names())


def test_upgrade_then_downgrade_round_trip(alembic_cfg):
    cfg, db_url = alembic_cfg
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)

    tcols = _columns(engine, "template")
    assert "agent_summary" in tcols
    assert "agent_usage_notes" in tcols

    fcols = _columns(engine, "flow")
    assert "based_on_template_id" in fcols
    assert "based_on_template_flow_id" not in fcols

    assert "template_metadata" not in _tables(engine)

    # Downgrade one step
    command.downgrade(cfg, "-1")
    engine.dispose()
    engine = create_engine(db_url)

    tcols = _columns(engine, "template")
    assert "agent_summary" not in tcols
    assert "agent_usage_notes" not in tcols
    fcols = _columns(engine, "flow")
    assert "based_on_template_id" not in fcols
    assert "based_on_template_flow_id" in fcols
    assert "template_metadata" in _tables(engine)


def test_backfill_populates_template_agent_fields(alembic_cfg, monkeypatch):
    """Upgrade against a DB pre-seeded with a Template row whose name matches
    a *.metadata.json fixture; assert backfill copies agent_summary/notes."""
    cfg, db_url = alembic_cfg
    # Step to the migration just before ours
    command.upgrade(cfg, "e1f42ac1d7a9")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO template (id, name, scope, org_id, nodes, edges, "
            "created_at, updated_at) "
            "VALUES ('11111111-1111-1111-1111-111111111111', "
            "'ADP Worker Sync to SFTP', 'platform', NULL, '[]', '[]', "
            "'2026-04-25', '2026-04-25')"
        ))
    engine.dispose()
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT agent_summary, agent_usage_notes FROM template "
            "WHERE name = 'ADP Worker Sync to SFTP'"
        )).first()
    assert row is not None
    # JSON fixture has at least one of these set
    assert row[0] is not None or row[1] is not None
```

- [ ] **Step 3: Run the test — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/database/test_template_agent_metadata_migration.py -v`
Expected: FAIL — both assertions fire (columns missing, table still present).

- [ ] **Step 4: Implement the migration**

Replace the body of the new revision file with:

```python
"""template agent metadata + based_on_template_id

Revision ID: <NEW_REV>
Revises: e1f42ac1d7a9
Create Date: 2026-04-25
"""
from __future__ import annotations

import json
import pathlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "<NEW_REV>"
down_revision: str | None = "e1f42ac1d7a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STARTER_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parents[3]
    / "initial_setup"
    / "starter_projects"
)


def _backfill_template_agent_fields(conn) -> None:
    """For each *.metadata.json sibling fixture, populate the matching
    Template row's agent_summary / agent_usage_notes (only when the row
    exists and the target column is currently NULL)."""
    if not STARTER_FIXTURE_DIR.is_dir():
        return
    for path in sorted(STARTER_FIXTURE_DIR.glob("*.metadata.json")):
        template_name = path.name[: -len(".metadata.json")]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        agent_summary = payload.get("agent_summary")
        agent_usage_notes = payload.get("agent_usage_notes")
        if agent_summary is None and agent_usage_notes is None:
            continue
        conn.execute(
            sa.text(
                "UPDATE template SET "
                "agent_summary = COALESCE(agent_summary, :s), "
                "agent_usage_notes = COALESCE(agent_usage_notes, :n) "
                "WHERE LOWER(name) = LOWER(:name)"
            ),
            {"s": agent_summary, "n": agent_usage_notes, "name": template_name},
        )


def upgrade() -> None:
    # 1. Add agent fields to template
    op.add_column("template", sa.Column("agent_summary", sa.Text(), nullable=True))
    op.add_column("template", sa.Column("agent_usage_notes", sa.Text(), nullable=True))

    # 2. Backfill from *.metadata.json fixtures
    _backfill_template_agent_fields(op.get_bind())

    # 3. Add the new flow.based_on_template_id column + FK
    op.add_column(
        "flow",
        sa.Column(
            "based_on_template_id",
            sa.Uuid(),
            sa.ForeignKey("template.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 4. Drop the obsolete flow.based_on_template_flow_id (FK first on backends that need it)
    with op.batch_alter_table("flow") as batch:
        batch.drop_column("based_on_template_flow_id")

    # 5. Drop the orphaned template_metadata table
    op.drop_table("template_metadata")


def downgrade() -> None:
    # Recreate template_metadata (empty — no data restore)
    op.create_table(
        "template_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("flow_id", sa.Uuid(),
                  sa.ForeignKey("flow.id", ondelete="CASCADE"),
                  nullable=False, unique=True, index=True),
        sa.Column("agent_usage_notes", sa.Text(), nullable=True),
        sa.Column("agent_summary", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Uuid(),
                  sa.ForeignKey("user.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Recreate flow.based_on_template_flow_id (FK back to flow.id)
    op.add_column(
        "flow",
        sa.Column(
            "based_on_template_flow_id",
            sa.Uuid(),
            sa.ForeignKey("flow.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    with op.batch_alter_table("flow") as batch:
        batch.drop_column("based_on_template_id")

    op.drop_column("template", "agent_usage_notes")
    op.drop_column("template", "agent_summary")
```

Replace `<NEW_REV>` with the revision id Alembic generated in Step 1 (also visible as the file name prefix and as the value of `revision:`).

- [ ] **Step 5: Run the migration test — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/database/test_template_agent_metadata_migration.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit (PAUSE for user approval)**

Pause and ask the user: *"Migration scaffolding + smoke tests pass. OK to commit?"* On approval:

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/alembic/versions/<NEW_REV>_*.py \
        src/backend/tests/unit/services/database/test_template_agent_metadata_migration.py
git commit -m "feat(template): alembic migration adds agent fields + based_on_template_id, drops template_metadata"
```

---

## Task 2: SQLModel updates — Template + Flow

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/template/model.py:27-109`
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py:52-63`
- Modify: `src/backend/base/langflow/api/v1/assistant.py:405,623` (column rename — passes the value through)
- Modify: `src/backend/base/langflow/services/assistant/service.py:245,254,368,502` (rename ctor param + attr — keeps behavior aligned with the renamed Flow column)
- Modify: `src/backend/base/langflow/services/assistant/tools/template_apply.py:60` (the one assignment to `target.based_on_template_flow_id`)
- Modify: `src/backend/base/langflow/api/v1/templates.py:582` (delete-guard column ref)
- Modify: `src/backend/base/langflow/api/v1/flows.py:409-410` (archive-guard column ref)
- Test: `src/backend/tests/unit/services/database/test_template_model.py` (add cases)

**Note on scope creep:** `service.py` and `template_apply.py` get *full* rewrites in Tasks 5 and 6. This task only touches the **column reference** in those files — keep the change minimal (one or two lines per file). Logic refactoring stays in the later tasks.

**Note on TemplateMetadata deletion ordering:** the `TemplateMetadata` SQLModel + its directory + its `__init__.py` registration are intentionally **not** removed in this task. They're still imported by `assistant/tools/metadata_lookup.py` (cleaned in Task 4), `api/v1/admin/metadata.py` (cleaned in Task 7), and `initial_setup/setup.py` (cleaned in Task 7). Deleting the model now would break import-time loading for every intervening commit. Removal happens in Task 7's final step after the last consumer is gone.

- [ ] **Step 1: Write the failing model test**

Append to `src/backend/tests/unit/services/database/test_template_model.py` (create the file if missing — base it on the project's standard async-session pattern in nearby tests):

```python
import pytest
from langflow.services.database.models.template.model import Template


@pytest.mark.asyncio
async def test_template_persists_agent_fields(async_session, organization_factory):
    org = await organization_factory()
    t = Template(
        name="Tpl with notes",
        nodes=[], edges=[],
        scope="org", org_id=org.id,
        agent_summary="short",
        agent_usage_notes="long\nmultiline",
    )
    async_session.add(t)
    await async_session.commit()
    await async_session.refresh(t)
    assert t.agent_summary == "short"
    assert t.agent_usage_notes == "long\nmultiline"


@pytest.mark.asyncio
async def test_flow_based_on_template_id_nullable(async_session, flow_factory):
    f = await flow_factory()
    assert f.based_on_template_id is None
```

(Use whatever `async_session` / `organization_factory` / `flow_factory` fixtures the surrounding test files use; if a similar test file already exists at this path, append rather than overwrite.)

- [ ] **Step 2: Run the test — expect ImportError or AttributeError**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/database/test_template_model.py -v`
Expected: FAIL — `Template` has no `agent_summary` attribute / `Flow` has no `based_on_template_id`.

- [ ] **Step 3: Add fields to `Template` model**

In `src/backend/base/langflow/services/database/models/template/model.py`, after the `gradient` field (around line 56), insert:

```python
    agent_summary: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )
    agent_usage_notes: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )
```

- [ ] **Step 4: Replace the Flow pointer column**

In `src/backend/base/langflow/services/database/models/flow/model.py`, replace lines 52-63 (the `based_on_template_flow_id` block) with:

```python
    based_on_template_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(),
            ForeignKey("template.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description=(
            "For flows cloned from a template: the source template's id, used to "
            "resolve the template's agent metadata for assistant context."
        ),
    )
```

- [ ] **Step 4a: Update column references in api/v1/templates.py**

In `src/backend/base/langflow/api/v1/templates.py` line 582, replace:

```python
            select(Flow.id).where(Flow.based_on_template_flow_id == template_id)
```

with:

```python
            select(Flow.id).where(Flow.based_on_template_id == template_id)
```

- [ ] **Step 4b: Update column references in api/v1/flows.py**

In `src/backend/base/langflow/api/v1/flows.py` lines 409-410, replace:

```python
    if flow.based_on_template_flow_id is not None:
        t = await session.get(Template, flow.based_on_template_flow_id)
```

with:

```python
    if flow.based_on_template_id is not None:
        t = await session.get(Template, flow.based_on_template_id)
```

- [ ] **Step 4c: Update column references in api/v1/assistant.py**

In `src/backend/base/langflow/api/v1/assistant.py` at lines 405 and 623, replace each:

```python
            based_on_template_flow_id=flow.based_on_template_flow_id,
```

with:

```python
            based_on_template_id=flow.based_on_template_id,
```

- [ ] **Step 4d: Update the AssistantService ctor + attr names in service.py**

In `src/backend/base/langflow/services/assistant/service.py`:
- Line 245: change `based_on_template_flow_id: UUID | None = None,` → `based_on_template_id: UUID | None = None,`
- Line 254: change `self.based_on_template_flow_id = based_on_template_flow_id` → `self.based_on_template_id = based_on_template_id`
- Lines 368 and 502 (call sites of `build_flow_template_context`): change `self.based_on_template_flow_id` → `self.based_on_template_id`

(Don't touch the body of `build_flow_template_context` or any of the assistant logic — that's Task 5.)

- [ ] **Step 4e: Update the one column write in template_apply.py**

In `src/backend/base/langflow/services/assistant/tools/template_apply.py` line 60, replace:

```python
        target.based_on_template_flow_id = template_uuid
```

with:

```python
        target.based_on_template_id = template_uuid
```

(The full file rewrite in Task 6 supersedes this; the one-line change here keeps the codebase consistent with the column rename.)

- [ ] **Step 5: Run the model test — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/database/test_template_model.py -v`
Expected: PASS.

- [ ] **Step 6: Quick import sanity sweep**

Run: `cd /Users/brycedeneen/dev/langflow && uv run python -c "import langflow.services.database.models; import langflow.api.v1.templates"`
Expected: success (the rename of `flow.based_on_template_flow_id` to `based_on_template_id` will surface as an `AttributeError` at any call site that still references the old name — that's expected, fix in the dependent task that owns the call site).

- [ ] **Step 7: Commit (PAUSE for user approval)**

Pause and ask user. On approval:

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/services/database/models/template/model.py \
        src/backend/base/langflow/services/database/models/flow/model.py \
        src/backend/base/langflow/api/v1/templates.py \
        src/backend/base/langflow/api/v1/flows.py \
        src/backend/base/langflow/api/v1/assistant.py \
        src/backend/base/langflow/services/assistant/service.py \
        src/backend/base/langflow/services/assistant/tools/template_apply.py \
        src/backend/tests/unit/services/database/test_template_model.py
git commit -m "feat(template): add agent fields; rename flow pointer to based_on_template_id"
```

---

## Task 3: API — Template Pydantic schemas + PATCH handler with proper clearing semantics

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/template/model.py` (TemplateRead, TemplatePatch, TemplateReadDetail)
- Modify: `src/backend/base/langflow/api/v1/templates.py:424-490`
- Test: `src/backend/tests/unit/api/v1/test_templates_patch.py` (extend existing or add)

- [ ] **Step 1: Find the existing PATCH test file**

```bash
grep -rln "patch_template\|PATCH /templates" /Users/brycedeneen/dev/langflow/src/backend/tests/ 2>/dev/null | head -3
```

The file most likely is `src/backend/tests/unit/api/v1/test_templates.py` or `…/test_templates_patch.py`. If neither exists, create `src/backend/tests/unit/api/v1/test_templates_patch.py` with the auth/client fixtures cribbed from a sibling file (e.g. `test_flows.py`).

- [ ] **Step 2: Write failing tests for new fields**

Append:

```python
@pytest.mark.asyncio
async def test_patch_template_sets_agent_fields(client, platform_admin_token, seed_template):
    tpl = await seed_template()
    res = await client.patch(
        f"/api/v1/templates/{tpl.id}",
        json={"agent_summary": "summary", "agent_usage_notes": "notes"},
        headers={"Authorization": f"Bearer {platform_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["agent_summary"] == "summary"
    assert body["agent_usage_notes"] == "notes"


@pytest.mark.asyncio
async def test_patch_template_null_clears_agent_fields(client, platform_admin_token, seed_template):
    tpl = await seed_template(agent_summary="x", agent_usage_notes="y")
    res = await client.patch(
        f"/api/v1/templates/{tpl.id}",
        json={"agent_summary": None, "agent_usage_notes": None},
        headers={"Authorization": f"Bearer {platform_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["agent_summary"] is None
    assert body["agent_usage_notes"] is None


@pytest.mark.asyncio
async def test_patch_template_omitted_field_is_no_op(client, platform_admin_token, seed_template):
    tpl = await seed_template(agent_summary="keep me", agent_usage_notes=None)
    res = await client.patch(
        f"/api/v1/templates/{tpl.id}",
        json={"description": "new desc"},
        headers={"Authorization": f"Bearer {platform_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["agent_summary"] == "keep me"


@pytest.mark.asyncio
async def test_patch_template_non_admin_forbidden(client, member_token, seed_template):
    tpl = await seed_template()
    res = await client.patch(
        f"/api/v1/templates/{tpl.id}",
        json={"agent_summary": "x"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 403
```

If the surrounding fixtures (`seed_template`, `platform_admin_token`, `member_token`) don't exist, add them as conftest helpers, mirroring patterns in nearby tests. **Do not** invent fixtures wholesale — read 2-3 sibling test files first and reuse their idioms.

- [ ] **Step 3: Run tests — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/api/v1/test_templates_patch.py -v`
Expected: FAIL on the first new test — schema doesn't accept the field, or response doesn't include it.

- [ ] **Step 4: Update the Pydantic schemas**

In `src/backend/base/langflow/services/database/models/template/model.py`:

Replace the `TemplateRead` class (lines 114-127) with:

```python
class TemplateRead(BaseModel):
    """Slim catalog listing shape (no nodes/edges)."""

    id: UUID
    name: str
    description: str | None
    icon: str | None
    gradient: str | None
    archived_at: datetime | None
    categories: list[CategoryRead]
    created_at: datetime
    updated_at: datetime
    agent_summary: str | None = None
    agent_usage_notes: str | None = None

    model_config = {"from_attributes": True}
```

Replace the `TemplatePatch` class (lines 168-181) with:

```python
class TemplatePatch(BaseModel):
    """Partial update body for PATCH /templates/{id}.

    Field semantics — driven by ``model_fields_set``:
    - field absent from request body  -> leave current value untouched
    - field present and set to ``null`` -> clear the column
    - field present and set to a value -> overwrite

    For ``category_ids``: an empty list clears tags; the field key being
    absent leaves tags unchanged (mirrors the column-level rule).
    """

    name: str | None = PydanticField(default=None, max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    category_ids: list[UUID] | None = None
    agent_summary: str | None = None
    agent_usage_notes: str | None = None
```

(`TemplateReadDetail` inherits from `TemplateRead` so it picks up the new fields automatically.)

- [ ] **Step 5: Update the PATCH handler to use `model_fields_set`**

In `src/backend/base/langflow/api/v1/templates.py`, replace lines 446-477 (the partial-update block) with:

```python
    set_fields = body.model_fields_set

    if "name" in set_fields and body.name is not None and body.name != row.name:
        existing = (
            await session.exec(
                select(Template)
                .where(Template.name == body.name)
                .where(Template.deleted_at.is_(None))
            )
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Template name already exists",
            )
        row.name = body.name
    elif "name" in set_fields and body.name is None:
        # Disallow clearing the name (NOT NULL).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name cannot be null",
        )

    if "description" in set_fields:
        row.description = body.description
    if "icon" in set_fields:
        row.icon = body.icon
    if "gradient" in set_fields:
        row.gradient = body.gradient
    if "agent_summary" in set_fields:
        row.agent_summary = body.agent_summary
    if "agent_usage_notes" in set_fields:
        row.agent_usage_notes = body.agent_usage_notes

    if "category_ids" in set_fields and body.category_ids is not None:
        await _validate_category_ids(session, body.category_ids)
        existing_links = (
            await session.exec(
                select(TemplateCategory).where(TemplateCategory.template_id == template_id)
            )
        ).all()
        for link in existing_links:
            await session.delete(link)
        for cat_id in body.category_ids:
            session.add(TemplateCategory(template_id=row.id, category_id=cat_id))
```

Leave the `row.updated_by = current_user.id` and `row.updated_at = datetime.now(timezone.utc)` lines and the commit/reload block below it untouched.

- [ ] **Step 6: Run the PATCH tests — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/api/v1/test_templates_patch.py -v`
Expected: PASS (all four new tests + any existing ones).

- [ ] **Step 7: Run the broader templates test suite as a regression guard**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/api/v1/ -k templates -v`
Expected: PASS (with possibly some failures from Task 4+ work — note them; if any failure references `agent_summary`/`agent_usage_notes`/PATCH semantics, fix here).

- [ ] **Step 8: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/services/database/models/template/model.py \
        src/backend/base/langflow/api/v1/templates.py \
        src/backend/tests/unit/api/v1/test_templates_patch.py
git commit -m "feat(templates): expose agent_summary/agent_usage_notes via PATCH; switch to model_fields_set semantics"
```

---

## Task 4: Rewire assistant — `metadata_lookup.py`

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/metadata_lookup.py`
- Test: `src/backend/tests/unit/services/assistant/tools/test_metadata_lookup.py` (rewrite the template-related tests)

- [ ] **Step 1: Locate or create the test file**

```bash
ls /Users/brycedeneen/dev/langflow/src/backend/tests/unit/services/assistant/tools/ 2>/dev/null
```

If a test file for `metadata_lookup` already exists there, edit in place. Otherwise create `test_metadata_lookup.py` and import the helpers under test.

- [ ] **Step 2: Write failing tests for the new template lookups**

Use `template_factory` if one exists in the suite; if not, instantiate `Template` rows directly via the provided async session fixture. Add:

```python
import pytest
from langflow.services.assistant.tools.metadata_lookup import (
    fetch_template_summaries,
    fetch_template_usage_notes,
)


@pytest.mark.asyncio
async def test_fetch_template_summaries_excludes_null_summary(async_session):
    # Two templates: one with summary, one without
    from langflow.services.database.models.template.model import Template
    a = Template(name="A", nodes=[], edges=[], scope="platform",
                 agent_summary="alpha summary")
    b = Template(name="B", nodes=[], edges=[], scope="platform",
                 agent_summary=None)
    async_session.add_all([a, b])
    await async_session.commit()

    rows = await fetch_template_summaries()
    keyed = {r["template_name"]: r for r in rows}
    assert "A" in keyed
    assert "B" not in keyed
    assert keyed["A"]["agent_summary"] == "alpha summary"
    assert keyed["A"]["template_id"] == str(a.id)


@pytest.mark.asyncio
async def test_fetch_template_usage_notes_returns_notes(async_session):
    from langflow.services.database.models.template.model import Template
    t = Template(name="T", nodes=[], edges=[], scope="platform",
                 agent_usage_notes="how to use")
    async_session.add(t)
    await async_session.commit()

    out = await fetch_template_usage_notes(str(t.id))
    assert out == {
        "template_id": str(t.id),
        "template_name": "T",
        "agent_usage_notes": "how to use",
    }


@pytest.mark.asyncio
async def test_fetch_template_usage_notes_unknown_returns_none():
    out = await fetch_template_usage_notes("00000000-0000-0000-0000-000000000000")
    assert out is None


@pytest.mark.asyncio
async def test_fetch_template_usage_notes_malformed_returns_none():
    out = await fetch_template_usage_notes("not-a-uuid")
    assert out is None
```

Delete (or comment-and-rewrite) any existing tests in this file that import `TemplateMetadata` — those are obsolete.

- [ ] **Step 3: Run tests — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/tools/test_metadata_lookup.py -v`
Expected: FAIL — old function returns `flow_id`/`flow_name` keys, or imports break because `TemplateMetadata` was deleted in Task 2.

- [ ] **Step 4: Rewrite `metadata_lookup.py` template helpers**

Replace the entire file content of `src/backend/base/langflow/services/assistant/tools/metadata_lookup.py` with:

```python
"""Shared metadata lookup helpers for assistant tools and system prompt injection."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import select

from langflow.services.database.models import ComponentMetadata
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


async def fetch_component_summaries(names: list[str]) -> dict[str, str | None]:
    """Return {component_name: agent_summary} for the given names (absent → None)."""
    if not names:
        return {}
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(ComponentMetadata).where(ComponentMetadata.component_name.in_(names))
            )
        ).all()
    return {r.component_name: r.agent_summary for r in rows}


async def fetch_component_usage_notes(component_name: str) -> str | None:
    """Return agent_usage_notes for a single component, or None when absent."""
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == component_name
                )
            )
        ).one_or_none()
    return row.agent_usage_notes if row else None


async def fetch_template_summaries() -> list[dict]:
    """Return rows with (template_id, template_name, agent_summary) for prompt injection.

    Only includes templates whose ``agent_summary`` is non-null and that are
    neither archived nor soft-deleted. Sorted by template name.
    """
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(Template)
                .where(Template.agent_summary.is_not(None))
                .where(Template.deleted_at.is_(None))
                .where(Template.archived_at.is_(None))
            )
        ).all()
    out = [
        {
            "template_id": str(t.id),
            "template_name": t.name,
            "agent_summary": t.agent_summary,
        }
        for t in rows
    ]
    out.sort(key=lambda r: r["template_name"])
    return out


async def fetch_template_usage_notes(template_id: str) -> dict | None:
    """Return {template_id, template_name, agent_usage_notes} for a single template.

    Returns None when ``template_id`` is malformed or the template doesn't exist.
    Returns ``agent_usage_notes=None`` when the template exists but has no notes.
    """
    try:
        parsed = UUID(template_id)
    except ValueError:
        return None
    async with session_scope() as session:
        t = (
            await session.exec(select(Template).where(Template.id == parsed))
        ).one_or_none()
    if t is None:
        return None
    return {
        "template_id": str(t.id),
        "template_name": t.name,
        "agent_usage_notes": t.agent_usage_notes,
    }
```

- [ ] **Step 5: Run tests — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/tools/test_metadata_lookup.py -v`
Expected: PASS.

- [ ] **Step 6: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/services/assistant/tools/metadata_lookup.py \
        src/backend/tests/unit/services/assistant/tools/test_metadata_lookup.py
git commit -m "refactor(assistant): query Template directly for agent metadata"
```

---

## Task 5: Rewire assistant — `flow_template_context.py` + caller in `service.py`

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/flow_template_context.py`
- Test: `src/backend/tests/unit/services/assistant/test_flow_template_context.py`

**Note:** the `service.py` ctor param rename and the `api/v1/assistant.py` call-site updates were folded into Task 2 (steps 4c-4d) so the column rename and its consumers all land in one commit. This task is now solely about rewriting the template-context lookup logic.

- [ ] **Step 1: Write failing test**

Create `src/backend/tests/unit/services/assistant/test_flow_template_context.py`:

```python
import pytest
from uuid import uuid4
from langflow.services.assistant.flow_template_context import build_flow_template_context


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_none():
    assert await build_flow_template_context(None) == ""


@pytest.mark.asyncio
async def test_returns_empty_for_unknown_template():
    assert await build_flow_template_context(uuid4()) == ""


@pytest.mark.asyncio
async def test_returns_block_for_template_with_notes(async_session):
    from langflow.services.database.models.template.model import Template
    t = Template(name="My Tpl", nodes=[], edges=[], scope="platform",
                 agent_usage_notes="Use carefully")
    async_session.add(t)
    await async_session.commit()
    block = await build_flow_template_context(t.id)
    assert "My Tpl" in block
    assert "Use carefully" in block


@pytest.mark.asyncio
async def test_returns_empty_for_template_without_notes(async_session):
    from langflow.services.database.models.template.model import Template
    t = Template(name="Notes-less", nodes=[], edges=[], scope="platform")
    async_session.add(t)
    await async_session.commit()
    assert await build_flow_template_context(t.id) == ""
```

- [ ] **Step 2: Run tests — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/test_flow_template_context.py -v`
Expected: FAIL — current code keys off `flow_id`, won't find a Template by uuid.

- [ ] **Step 3: Update `flow_template_context.py`**

Replace the whole file body with:

```python
"""Per-message helper that injects the source-template notes into the system prompt."""

from __future__ import annotations

from uuid import UUID

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def build_flow_template_context(
    based_on_template_id: UUID | None,
) -> str:
    """Return a markdown block describing the flow's source template, or "".

    The block is inserted between ``{canvas_summary}`` and ``{available_templates}``
    in SYSTEM_PROMPT_TEMPLATE. It gives the LLM the template's admin-authored
    ``agent_usage_notes`` so it can customize the flow with the user intelligently.

    Returns "" when:
      - based_on_template_id is None (ordinary user flow), or
      - the pointer references a template that no longer exists, or
      - the template has no agent_usage_notes set.
    """
    if based_on_template_id is None:
        return ""
    notes = await fetch_template_usage_notes(str(based_on_template_id))
    if notes is None or notes.get("agent_usage_notes") is None:
        return ""
    return (
        "## Current Flow Template\n\n"
        f'This flow was created from the "{notes["template_name"]}" template.\n'
        f"{notes['agent_usage_notes']}\n\n"
    )
```

- [ ] **Step 4: Run the new test — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/test_flow_template_context.py -v`
Expected: PASS.

- [ ] **Step 5: Run broader assistant tests as regression**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/ src/backend/tests/unit/api/v1/test_assistant.py -v`
Expected: PASS or only failures rooted in the still-pending `template_apply` rewrite (Task 6).

- [ ] **Step 6: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/services/assistant/flow_template_context.py \
        src/backend/tests/unit/services/assistant/test_flow_template_context.py
git commit -m "refactor(assistant): build_flow_template_context keys off Template, not Flow"
```

---

## Task 6: Rewire `template_apply.py` + tool registry + MCP server

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/tools/template_apply.py`
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py:64-89` (apply_template tool def) + lines defining `get_template_instructions`
- Modify: `src/backend/base/langflow/services/assistant/tools/template_metadata.py`
- Modify: `src/backend/base/langflow/services/assistant/mcp_server.py:82-98,143-149`
- Test: `src/backend/tests/unit/services/assistant/tools/test_template_apply.py`

**Note:** the column-name updates in `api/v1/templates.py:582` and `api/v1/flows.py:409-410` were folded into Task 2 (steps 4a-4b). This task only handles the assistant tool rewrites + MCP server.

- [ ] **Step 1: Write failing test for `apply_template`**

Create `src/backend/tests/unit/services/assistant/tools/test_template_apply.py`:

```python
import pytest
from langflow.services.assistant.tools.template_apply import apply_template


@pytest.mark.asyncio
async def test_apply_template_copies_nodes_and_sets_pointer(async_session, flow_factory):
    from langflow.services.database.models.template.model import Template
    template = Template(
        name="Source Tpl", scope="platform",
        nodes=[{"id": "n1"}], edges=[],
    )
    async_session.add(template)
    target = await flow_factory(data={"nodes": [], "edges": []})
    await async_session.commit()

    out = await apply_template(str(target.id), str(template.id))
    assert "applied_patch" in out
    assert out["template_name"] == "Source Tpl"

    # Pointer set on target
    await async_session.refresh(target)
    assert target.based_on_template_id == template.id


@pytest.mark.asyncio
async def test_apply_template_rejects_non_empty_target(async_session, flow_factory):
    from langflow.services.database.models.template.model import Template
    t = Template(name="X", scope="platform", nodes=[{"id": "a"}], edges=[])
    async_session.add(t)
    target = await flow_factory(data={"nodes": [{"id": "existing"}], "edges": []})
    await async_session.commit()
    out = await apply_template(str(target.id), str(t.id))
    assert "error" in out


@pytest.mark.asyncio
async def test_apply_template_rejects_archived_template(async_session, flow_factory):
    from datetime import datetime, timezone
    from langflow.services.database.models.template.model import Template
    t = Template(name="Y", scope="platform", nodes=[], edges=[],
                 archived_at=datetime.now(timezone.utc))
    async_session.add(t)
    target = await flow_factory(data={"nodes": [], "edges": []})
    await async_session.commit()
    out = await apply_template(str(target.id), str(t.id))
    assert "error" in out


@pytest.mark.asyncio
async def test_apply_template_unknown_returns_error(flow_factory):
    target = await flow_factory(data={"nodes": [], "edges": []})
    out = await apply_template(str(target.id), "00000000-0000-0000-0000-000000000000")
    assert "error" in out
```

- [ ] **Step 2: Run — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/tools/test_template_apply.py -v`
Expected: FAIL — current code looks up Template arg as a Flow.

- [ ] **Step 3: Rewrite `template_apply.py`**

Replace the entire file content of `src/backend/base/langflow/services/assistant/tools/template_apply.py` with:

```python
"""Tool: apply_template — atomically load a template's nodes+edges into a flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import select

from langflow.services.assistant.tools._id_regen import regenerate_flow_ids
from langflow.services.database.models import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


async def apply_template(
    target_flow_id: str,
    template_id: str,
) -> dict[str, Any]:
    """Replace a blank flow's data with a template's data. Sets the target's
    ``based_on_template_id`` so subsequent assistant messages carry the
    template's ``agent_usage_notes`` in the system prompt.

    Returns: {"applied_patch": {"added_nodes": [...], "added_edges": [...],
              "updated_nodes": [], "removed_ids": []}, "template_name": str}
    Errors:  {"error": "..."} when target is non-empty, the template is
    archived/deleted, or either record is missing.
    """
    try:
        target_uuid = UUID(target_flow_id)
        template_uuid = UUID(template_id)
    except ValueError:
        return {"error": "Invalid id format."}

    async with session_scope() as session:
        target = (await session.exec(select(Flow).where(Flow.id == target_uuid))).one_or_none()
        if target is None:
            return {"error": "Target flow not found."}

        template = (
            await session.exec(select(Template).where(Template.id == template_uuid))
        ).one_or_none()
        if template is None:
            return {"error": "Template not found."}
        if template.archived_at is not None or template.deleted_at is not None:
            return {"error": "Template is archived or deleted."}

        current_nodes = (target.data or {}).get("nodes") or []
        if current_nodes:
            return {
                "error": (
                    "Target flow is not empty. Start from a blank flow to apply a template."
                )
            }

        template_data = {"nodes": template.nodes, "edges": template.edges}
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

- [ ] **Step 4: Update `tools/template_metadata.py`**

Replace the file body with:

```python
"""Tool: get_template_instructions — on-demand fetch of a template's usage notes."""

from __future__ import annotations

from typing import Any

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def get_template_instructions(template_id: str) -> dict[str, Any] | None:
    """Return the admin-authored usage notes for a template.

    Returns None when the template doesn't exist or the id is malformed.
    Otherwise returns ``{template_id, template_name, agent_usage_notes}``.
    The ``agent_usage_notes`` field is None when no notes have been authored.
    """
    return await fetch_template_usage_notes(template_id)
```

- [ ] **Step 5: Update `tools/registry.py`**

In `src/backend/base/langflow/services/assistant/tools/registry.py`:
- The `get_template_instructions` parameter (likely lines 50-62 area, the `flow_id` param block): change `flow_id` to `template_id`. Update the description to say "the template's id" rather than "the template's flow."
- The `apply_template` parameters block (lines 75-87): rename `template_flow_id` → `template_id`. Update its `description` to "UUID of the template (from the Available Templates list)." Description string of the tool itself should drop "starter-project" wording.

- [ ] **Step 6: Update `mcp_server.py`**

In `src/backend/base/langflow/services/assistant/mcp_server.py`:

Replace lines 82-98 (the `get_template_instructions` Tool block) with:

```python
        types.Tool(
            name="get_template_instructions",
            description=(
                "Fetch the admin-authored usage notes for a template, "
                "keyed by template_id. Returns {template_id, template_name, agent_usage_notes}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "template_id": {
                        "type": "string",
                        "description": "UUID of the template.",
                    },
                },
                "required": ["template_id"],
            },
        ),
```

Replace lines 143-149 (the dispatch branch) with:

```python
    elif name == "get_template_instructions":
        template_id = arguments.get("template_id")
        if not template_id:
            return [types.TextContent(type="text", text=json.dumps({"error": "template_id is required"}))]
        result = await get_template_instructions(template_id=template_id)
        if result is None:
            result = {"error": f"Template '{template_id}' not found"}
```

- [ ] **Step 7: Run the apply_template test — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/services/assistant/tools/test_template_apply.py -v`
Expected: PASS.

- [ ] **Step 8: Run a broader regression sweep**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest \
  src/backend/tests/unit/services/assistant/ \
  src/backend/tests/unit/api/v1/test_assistant.py \
  src/backend/tests/unit/api/v1/test_flows.py \
  src/backend/tests/unit/api/v1/test_templates_patch.py -v
```
Expected: PASS. If any test still references `based_on_template_flow_id` or `TemplateMetadata`, fix it (these are stale references the column rename invalidated).

- [ ] **Step 9: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/services/assistant/tools/template_apply.py \
        src/backend/base/langflow/services/assistant/tools/template_metadata.py \
        src/backend/base/langflow/services/assistant/tools/registry.py \
        src/backend/base/langflow/services/assistant/mcp_server.py \
        src/backend/tests/unit/services/assistant/tools/test_template_apply.py
git commit -m "refactor(assistant): apply_template + MCP tools key off template_id"
```

---

## Task 7: Delete legacy admin metadata endpoint + startup seeder

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/metadata.py` (delete template-section routes + helpers)
- Modify: `src/backend/base/langflow/main.py:34,207` (drop seeder import + call)
- Modify: `src/backend/base/langflow/initial_setup/setup.py:52,1018-1109` (drop import + function)
- Modify: `src/backend/base/langflow/services/database/models/__init__.py:25,64` (drop `TemplateMetadata` import + `__all__` entry)
- Delete: `src/backend/base/langflow/services/database/models/template_metadata/` (entire dir — only safe to delete after the three consumers above are gone)
- Test: `src/backend/tests/unit/api/v1/test_admin_metadata.py` (drop template-tab test cases)

- [ ] **Step 1: Find existing test coverage for the admin metadata routes**

```bash
grep -rln "metadata/templates\|list_template_metadata" /Users/brycedeneen/dev/langflow/src/backend/tests/ 2>/dev/null | head
```

Note any test functions that hit `/api/v1/admin/metadata/templates*`. Those will need to be deleted in Step 4.

- [ ] **Step 2: Write a failing test that asserts the routes are gone**

Append (or create) `src/backend/tests/unit/api/v1/test_admin_metadata.py` with:

```python
@pytest.mark.asyncio
async def test_admin_metadata_templates_routes_removed(client, super_admin_token):
    headers = {"Authorization": f"Bearer {super_admin_token}"}
    res = await client.get("/api/v1/admin/metadata/templates", headers=headers)
    assert res.status_code == 404
```

- [ ] **Step 3: Run — expect failure (route still 200/empty)**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/api/v1/test_admin_metadata.py::test_admin_metadata_templates_routes_removed -v`
Expected: FAIL — route still exists.

- [ ] **Step 4: Delete the template section of `admin/metadata.py`**

In `src/backend/base/langflow/api/v1/admin/metadata.py`:

Remove:
- The imports `Flow`, `Folder`, `TemplateMetadata` from the `from langflow.services.database.models import …` block (keep `ComponentMetadata`, `User`).
- The whole `from langflow.services.database.models.flow.starter import (…)` line.
- The whole `from langflow.services.database.models.template_metadata import (…)` line.
- The `_template_row_read` helper (lines ~41-59).
- The four `@router.get/put/delete` decorated functions for `/templates*` (lines ~62-166).

Keep the components-metadata section intact. The router still has prefix `/metadata`. Update the module docstring to drop "template metadata" mention.

- [ ] **Step 5: Delete the startup seeder**

In `src/backend/base/langflow/initial_setup/setup.py`:
- Remove the import `from langflow.services.database.models.template_metadata.model import TemplateMetadata` (line 52).
- Delete the entire `async def create_or_update_template_metadata(...)` function (lines ~1018-1109).

In `src/backend/base/langflow/main.py`:
- Remove the import `create_or_update_template_metadata` from the multi-line import block at line ~34.
- Remove the `await create_or_update_template_metadata()` call at line ~207.

- [ ] **Step 6: Drop test cases that reference removed routes**

Open any test file flagged in Step 1 and delete tests that exercise `GET/PUT/DELETE /admin/metadata/templates*` (or the `useUpsertTemplateMetadata` flow). Keep the new `test_admin_metadata_templates_routes_removed`.

Likewise in `src/backend/tests/unit/initial_setup/`, search for `create_or_update_template_metadata` and delete the relevant test if any.

- [ ] **Step 7: Drop the TemplateMetadata model now that no consumer remains**

Edit `src/backend/base/langflow/services/database/models/__init__.py`:
- Remove the line `from .template_metadata import TemplateMetadata`
- Remove `"TemplateMetadata",` from the `__all__` list

Then delete the directory:

```bash
rm -rf /Users/brycedeneen/dev/langflow/src/backend/base/langflow/services/database/models/template_metadata
```

- [ ] **Step 8: Run targeted tests — expect pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest \
  src/backend/tests/unit/api/v1/test_admin_metadata.py \
  src/backend/tests/unit/initial_setup/ -v
```
Expected: PASS. Then run the full backend smoke as a guardrail:
```bash
cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/ -x
```
Expected: PASS. If a stale `TemplateMetadata` import surfaces (e.g., a missed test fixture) the executor must remove that reference here — by this point in the plan the model is genuinely gone.

- [ ] **Step 9: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/backend/base/langflow/api/v1/admin/metadata.py \
        src/backend/base/langflow/main.py \
        src/backend/base/langflow/initial_setup/setup.py \
        src/backend/base/langflow/services/database/models/__init__.py \
        src/backend/base/langflow/services/database/models/template_metadata \
        src/backend/tests/unit/api/v1/test_admin_metadata.py
git commit -m "chore(admin): remove legacy template_metadata routes, startup seeder, and SQLModel"
```

---

## Task 8: Frontend types + edit panel UI

**Files:**
- Modify: `src/frontend/src/types/template/index.ts`
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx`
- Test: `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/__tests__/TemplateEditPanel.test.tsx` (create or extend)

- [ ] **Step 1: Locate or stub the existing test**

```bash
find /Users/brycedeneen/dev/langflow/src/frontend/src/modals/templatesModal -name "*.test.tsx" 2>/dev/null
```

If none exists, create `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/__tests__/TemplateEditPanel.test.tsx`. Reuse a render+mock-mutation pattern from a sibling component test (e.g. one that already mocks `useUpdateTemplate`).

- [ ] **Step 2: Write a failing component test**

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TemplateEditPanel from "../index";

const mockMutate = jest.fn();
jest.mock("@/controllers/API/queries/templates/use-update-template", () => ({
  useUpdateTemplate: () => ({ mutate: mockMutate, isPending: false }),
}));

const baseTemplate = {
  id: "tpl-1",
  name: "Tpl",
  description: "desc",
  icon: "FileText",
  gradient: "0",
  archived_at: null,
  scope: "platform" as const,
  org_id: null,
  created_by: null,
  created_at: "2026-04-25",
  updated_at: "2026-04-25",
  categories: [],
  agent_summary: "old summary",
  agent_usage_notes: "old notes",
};

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("TemplateEditPanel agent fields", () => {
  beforeEach(() => mockMutate.mockReset());

  it("renders agent_summary + agent_usage_notes inputs", () => {
    renderWithClient(
      <TemplateEditPanel template={baseTemplate} open={true} onOpenChange={() => {}} />,
    );
    expect(screen.getByLabelText(/agent summary/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/agent usage notes/i)).toBeInTheDocument();
  });

  it("includes agent fields in the PATCH body on save", async () => {
    renderWithClient(
      <TemplateEditPanel template={baseTemplate} open={true} onOpenChange={() => {}} />,
    );
    fireEvent.change(screen.getByLabelText(/agent summary/i), {
      target: { value: "new summary" },
    });
    fireEvent.change(screen.getByLabelText(/agent usage notes/i), {
      target: { value: "new notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(mockMutate).toHaveBeenCalled());
    const [vars] = mockMutate.mock.calls[0];
    expect(vars.body.agent_summary).toBe("new summary");
    expect(vars.body.agent_usage_notes).toBe("new notes");
  });

  it("sends null when fields are cleared", async () => {
    renderWithClient(
      <TemplateEditPanel template={baseTemplate} open={true} onOpenChange={() => {}} />,
    );
    fireEvent.change(screen.getByLabelText(/agent summary/i), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(mockMutate).toHaveBeenCalled());
    const [vars] = mockMutate.mock.calls[0];
    expect(vars.body.agent_summary).toBeNull();
  });
});
```

- [ ] **Step 3: Run — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- TemplateEditPanel`
Expected: FAIL — labels not present, mutate not called with new fields.

- [ ] **Step 4: Update the TS types**

Edit `src/frontend/src/types/template/index.ts`:

In `TemplateRead`, after `categories: Category[];` add:

```typescript
  agent_summary: string | null;
  agent_usage_notes: string | null;
```

In `TemplatePatchBody`, after the `category_ids?` line add:

```typescript
  agent_summary?: string | null;
  agent_usage_notes?: string | null;
```

- [ ] **Step 5: Update `TemplateEditPanel` to render + send the fields**

Edit `src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx`:

Add the `Textarea` import (use whatever the codebase exports; if no `Textarea` primitive exists, fall back to `<textarea>` styled like other multi-line fields nearby):

```tsx
import { Textarea } from "@/components/ui/textarea";
```

After the existing `useState` for `selectedCategoryIds`, add:

```tsx
const [agentSummary, setAgentSummary] = useState(template.agent_summary ?? "");
const [agentUsageNotes, setAgentUsageNotes] = useState(template.agent_usage_notes ?? "");
```

In the `useEffect` reset block, after `setSelectedCategoryIds(...)`, add:

```tsx
setAgentSummary(template.agent_summary ?? "");
setAgentUsageNotes(template.agent_usage_notes ?? "");
```

Replace the body assembly inside `handleSave` so the PATCH body explicitly includes the agent fields with empty-string → `null` normalization:

```tsx
  const handleSave = () => {
    updateTemplate(
      {
        templateId: template.id,
        body: {
          name: name.trim() || template.name,
          description: description.trim() || null,
          icon,
          gradient,
          category_ids: selectedCategoryIds,
          agent_summary: agentSummary.trim() === "" ? null : agentSummary,
          agent_usage_notes: agentUsageNotes.trim() === "" ? null : agentUsageNotes,
        },
      },
      ...
    );
  };
```

In the JSX form body, after the Categories block, add two new field groups:

```tsx
{/* Agent Summary */}
<div className="flex flex-col gap-1.5">
  <Label htmlFor="tpl-edit-agent-summary">Agent summary</Label>
  <Textarea
    id="tpl-edit-agent-summary"
    rows={2}
    value={agentSummary}
    onChange={(e) => setAgentSummary(e.target.value)}
    placeholder="Short description the assistant uses to match this template to user requests."
  />
</div>

{/* Agent Usage Notes */}
<div className="flex flex-col gap-1.5">
  <Label htmlFor="tpl-edit-agent-usage-notes">Agent usage notes</Label>
  <Textarea
    id="tpl-edit-agent-usage-notes"
    rows={6}
    value={agentUsageNotes}
    onChange={(e) => setAgentUsageNotes(e.target.value)}
    placeholder="Guidance the assistant injects when a user works with a flow created from this template."
    className="resize-y"
  />
</div>
```

If `@/components/ui/textarea` doesn't exist, replace `<Textarea …>` with `<textarea …>` and copy class names from a sibling multi-line input (search the repo for `textarea` for an example).

- [ ] **Step 6: Run the test — expect pass**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- TemplateEditPanel`
Expected: PASS.

- [ ] **Step 7: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/frontend/src/types/template/index.ts \
        src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx \
        src/frontend/src/modals/templatesModal/components/TemplateEditPanel/__tests__/TemplateEditPanel.test.tsx
git commit -m "feat(templates-ui): edit panel exposes agent_summary + agent_usage_notes"
```

---

## Task 9: Remove Settings → Flows tab + dead frontend hooks

**Files:**
- Modify: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx`
- Delete: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx`
- Delete: `src/frontend/src/controllers/API/queries/metadata/use-template-metadata.ts`
- Modify: `src/frontend/src/controllers/API/queries/metadata/index.ts` (drop `use-template-metadata` export)
- Modify: `src/frontend/src/types/metadata/index.ts` (drop `TemplateMetadata*` types)
- Modify: `src/frontend/src/controllers/API/helpers/constants.ts:48` (drop `METADATA_TEMPLATES`)
- Test: `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/components-tab.test.tsx` may need adjustments if it asserts the tab strip; otherwise no new test required.

- [ ] **Step 1: Find frontend tests that assert the Flows tab presence**

```bash
grep -rn "Flows\|FlowsTab\|flows-tab" /Users/brycedeneen/dev/langflow/src/frontend/src/pages/SettingsPage/ 2>/dev/null | head
```

If a test asserts the tab list contains "Flows", update it in this task (plan presents the assertion change inline once the file is identified).

- [ ] **Step 2: Write/update the failing test**

If `src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__/index.test.tsx` doesn't exist, create it:

```tsx
import { render, screen } from "@testing-library/react";
import MetadataPage from "../index";

jest.mock("../components-tab", () => ({ ComponentsTab: () => <div>components-tab</div> }));

describe("MetadataPage", () => {
  it("renders only the Components tab", () => {
    render(<MetadataPage />);
    expect(screen.queryByRole("tab", { name: /flows/i })).toBeNull();
    expect(screen.getByText("components-tab")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run — expect failure**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- pages/SettingsPage/pages/MetadataPage`
Expected: FAIL — Flows tab still rendered.

- [ ] **Step 4: Simplify `MetadataPage/index.tsx` to a single section**

Replace the entire file content of `src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx` with:

```tsx
import { ComponentsTab } from "./components-tab";

export default function MetadataPage() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">Component Management</h1>
      <ComponentsTab />
    </div>
  );
}
```

- [ ] **Step 5: Delete dead files**

```bash
rm /Users/brycedeneen/dev/langflow/src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx
rm /Users/brycedeneen/dev/langflow/src/frontend/src/controllers/API/queries/metadata/use-template-metadata.ts
```

- [ ] **Step 6: Update `metadata/index.ts` exports**

Edit `src/frontend/src/controllers/API/queries/metadata/index.ts`:
Remove `export * from "./use-template-metadata";` so only the components-metadata export remains.

- [ ] **Step 7: Trim `types/metadata/index.ts`**

Open `src/frontend/src/types/metadata/index.ts`. Remove the three template-keyed types (`TemplateMetadataRead`, `TemplateMetadataRow`, `TemplateMetadataWrite`). Replace the `ComponentMetadataRead = TemplateMetadataRead` alias with the explicit shape:

```typescript
export type ComponentMetadataRead = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
  updated_by: string;
  updated_at: string;
};

export type ComponentMetadataRow = {
  component_name: string;
  display_name: string | null;
  category: string | null;
  icon: string | null;
  is_orphan: boolean;
  metadata: ComponentMetadataRead | null;
};

export type ComponentMetadataWrite = {
  agent_usage_notes: string | null;
  agent_summary: string | null;
};
```

- [ ] **Step 8: Drop the `METADATA_TEMPLATES` URL constant**

Edit `src/frontend/src/controllers/API/helpers/constants.ts`. Remove the line:

```typescript
  METADATA_TEMPLATES: `admin/metadata/templates`,
```

If the `METADATA_COMPONENTS` constant lives below it, leave it alone.

- [ ] **Step 9: Run frontend tests — expect pass**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && \
  npm test -- pages/SettingsPage/pages/MetadataPage \
  controllers/API/queries/metadata \
  types/metadata
```
Expected: PASS.

- [ ] **Step 10: Run a build to surface stale TS imports**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm run build 2>&1 | tail -40`
Expected: build succeeds. If any file still imports `useListTemplateMetadata`, `TemplateMetadataRow`, etc., delete the import and any consumer code in this task — it's dead.

- [ ] **Step 11: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add src/frontend/src/pages/SettingsPage/pages/MetadataPage/index.tsx \
        src/frontend/src/pages/SettingsPage/pages/MetadataPage/flows-tab.tsx \
        src/frontend/src/pages/SettingsPage/pages/MetadataPage/__tests__ \
        src/frontend/src/controllers/API/queries/metadata \
        src/frontend/src/types/metadata/index.ts \
        src/frontend/src/controllers/API/helpers/constants.ts
git commit -m "chore(settings-ui): remove dead Flows tab + template_metadata hooks"
```

(Note: `git add <dir>` includes deletions automatically. If the `__tests__` directory only contains the new test, the path shown is fine.)

---

## Task 10: End-to-end verification + spec sign-off

**Files:** none (manual + smoke tests)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/ -x`
Expected: PASS. Investigate and fix any failure that traces back to this PR's column rename, deleted symbols, or schema change. Do **not** mark this step complete on a green-with-skips run unless all skips are pre-existing.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm test -- --watchAll=false`
Expected: PASS.

- [ ] **Step 3: Frontend build sanity**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm run build`
Expected: success.

- [ ] **Step 4: Manual UI verification (per CLAUDE.md "test the UI" rule)**

Spin up the app:
```bash
cd /Users/brycedeneen/dev/langflow && make backend &
cd /Users/brycedeneen/dev/langflow/src/frontend && npm run dev
```

Check, in a browser:
1. Log in as platform admin → open the templates modal → click `⋯` on a card → click **Edit** → confirm "Agent summary" and "Agent usage notes" textareas appear → fill both → Save → reopen the panel → values persist.
2. Open Settings → confirm "Flows" tab is gone, "Components" still works.
3. Create a flow from a template that has `agent_usage_notes` set → open ADP Assist → send any message → in the dev tools network tab, inspect the request to `/api/v1/assistant/...` and confirm the system prompt includes a `## Current Flow Template` block referencing the template name.

If any of (1)–(3) fails, file what failed and which task introduced the regression. Fix in-place if narrow.

- [ ] **Step 5: Update the spec status field**

Open `docs/superpowers/specs/2026-04-25-template-agent-metadata-edit-design.md`. Change `**Status:** Spec — pending implementation plan` to `**Status:** Implemented`.

- [ ] **Step 6: Commit (PAUSE for user approval)**

```bash
cd /Users/brycedeneen/dev/langflow
git add docs/superpowers/specs/2026-04-25-template-agent-metadata-edit-design.md \
        docs/superpowers/plans/2026-04-25-template-agent-metadata-edit.md
git commit -m "docs: mark template-agent-metadata spec as implemented"
```

(Plan doc is included so post-merge readers see the version that was actually executed.)

---

## Plan self-review notes

- **Spec coverage:** Section 1 (data model) → Tasks 1+2. Section 2 (migration) → Task 1. Section 3 (API) → Task 3 + Task 7. Section 4 (assistant rewiring) → Tasks 4+5+6. Section 5 (frontend) → Tasks 8+9. Section 6 (component boundaries) → checked across all tasks. Section 7 (error handling) → covered by Task 3 model_fields_set logic and Task 6 archived/deleted guards. Testing section → mapped onto every task's failing-test step + Task 10 manual.
- **Placeholder scan:** no TBDs or "implement later." `<NEW_REV>` placeholder in Task 1 is explicitly described as the alembic-generated id.
- **Type/symbol consistency:**
  - Field names `agent_summary` / `agent_usage_notes` used identically backend ↔ frontend ↔ tests.
  - Column rename `based_on_template_flow_id` → `based_on_template_id` applied in **Task 2** at every call site in one commit (model + templates.py + flows.py + assistant.py + service.py + template_apply.py one-line write). Tasks 5 and 6 then refactor the *logic* in those files without re-touching the column name.
  - Lookup function rename `flow_id` → `template_id` applied in Task 4 (`fetch_template_summaries`/`fetch_template_usage_notes` return shape), Task 6 (`get_template_instructions` arg + MCP tool def + dispatch).
- **Boundaries:** Each task produces a green-tree commit. The deletion of the `TemplateMetadata` model is deferred to Task 7 step 7 — it cannot be removed until `metadata_lookup.py` (Task 4), `admin/metadata.py` (Task 7 steps 1-4), and `initial_setup/setup.py` (Task 7 step 5) all stop importing it. Task 2 explicitly notes this and only modifies the model files it owns. The migration in Task 1 *does* drop the SQL table, but the orphaned Python class is harmless until startup-time queries run (the seeder, removed in Task 7); none of the intervening test suites trigger startup or query `template_metadata`.
