# ADP Assist Full-Screen Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit discipline:** The project owner batches commits to the **end** of the plan. Every task ends with "Pause for commit" meaning **stage with `git add`, do not run `git commit`**. Controller proposes one batched commit message for user approval at plan completion.

**Goal:** Make the fullscreen assistant proactive (speaks first on empty conversations) and context-aware (knows which template the current flow was cloned from). Adds a greeting endpoint, a `Flow.based_on_template_flow_id` pointer, an `apply_template` tool, and system-prompt extensions for opinionated narration.

**Architecture:** New `POST /api/v1/assistant/flows/{flow_id}/greet` endpoint triggers a one-shot LLM greeting that gets persisted like any other assistant message. A new nullable UUID column on `Flow` points back to the source template; it's read per message by a small helper that injects the template's `agent_usage_notes` into the system prompt. A new `apply_template` assistant tool atomically loads a template's nodes/edges into a blank flow and sets the pointer. Four new `## Guidelines` bullets steer the LLM toward opinionated narration, non-technical vocabulary, and a conversational test-mode hand-off.

**Tech Stack:** Python 3.11+, SQLModel, Alembic, FastAPI, Pydantic v2; React 18, @tanstack/react-query, Zustand, TypeScript; pytest + pytest-asyncio, Jest + @testing-library/react.

---

## Spec reference

Authoritative design: `docs/superpowers/specs/2026-04-18-assist-fullscreen-experience-design.md`. Decisions locked in that spec:

- Proactive greeting = new non-streaming endpoint + persisted `AssistantMessage`.
- Template link = `Flow.based_on_template_flow_id: UUID | null` with `ON DELETE SET NULL`.
- Apply template = bulk tool, atomic, errors if target flow is non-empty.
- "Opinionated" = prompt engineering only (4 new bullets).
- Test-mode transition = conversational only ("click the Test button"), zero new tools or SSE events.

---

## File Structure

### New files — backend

- `src/backend/base/langflow/alembic/versions/<rev>_add_based_on_template_flow_id.py`
- `src/backend/base/langflow/services/assistant/flow_template_context.py` — new helper that builds the per-message template-context block
- `src/backend/base/langflow/services/assistant/tools/template_apply.py` — `apply_template` tool implementation
- `src/backend/base/langflow/services/assistant/tools/_id_regen.py` — minimal node/edge id regenerator (no equivalent exists backend-side)
- `src/backend/tests/unit/services/database/models/test_flow_based_on_template.py`
- `src/backend/tests/unit/api/v1/test_assistant_greet_endpoint.py`
- `src/backend/tests/unit/services/assistant/tools/test_apply_template.py`
- `src/backend/tests/unit/services/assistant/tools/test_id_regen.py`
- `src/backend/tests/unit/services/assistant/test_flow_template_context.py`
- `src/backend/tests/unit/services/assistant/test_greeting_guidelines_in_prompt.py`

### Modified files — backend

- `src/backend/base/langflow/services/database/models/flow/model.py` — add `based_on_template_flow_id` column to `FlowBase`
- `src/backend/base/langflow/services/assistant/service.py` — (a) prompt-template updates (placeholder + 4 bullets), (b) per-message `build_flow_template_context` call, (c) `CATALOG_DISPATCH` registration
- `src/backend/base/langflow/services/assistant/tools/registry.py` — append `apply_template` to `CATALOG_TOOLS`
- `src/backend/base/langflow/api/v1/assistant.py` — add the greet endpoint handler + request/response models

### New files — frontend

- `src/frontend/src/controllers/API/queries/assistant/use-greet-conversation.ts`

### Modified files — frontend

- `src/frontend/src/types/flow/index.ts` — add `based_on_template_flow_id?: string | null` to `FlowType`
- `src/frontend/src/hooks/flows/use-add-flow.ts` — set `based_on_template_flow_id` when cloning a template
- `src/frontend/src/controllers/API/queries/flows/use-post-add-flow.ts` — extend `IPostAddFlow` + POST body
- `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-conversation.ts` — auto-fire greet on fullscreen + empty

### Jest tests — new

- `src/frontend/src/controllers/API/queries/assistant/__tests__/use-greet-conversation.test.ts`
- `src/frontend/src/modals/AssistantPanel/hooks/__tests__/greet-on-fullscreen.test.tsx`

---

## Design notes

### The `__greet__` sentinel

The greet endpoint passes a synthetic user message with content `"__greet__"` to the LLM. The system prompt (via guideline bullet #1 in Task 6) tells the LLM that this token means "open the conversation." The sentinel is **not** persisted — only the LLM's reply is written to `assistant_message`. If a real user happens to type `"__greet__"` via the normal `/messages` path, the LLM will treat it as a greeting trigger, which is harmless.

### Idempotent greet

The endpoint's 409-guard looks at persisted messages, not ephemeral state. Two tabs racing to greet the same empty conversation end up with exactly one persisted greeting; the loser's 409 is caught by the frontend and the list reconverges via re-fetch.

### `apply_template` empties check

The tool refuses to overwrite a non-empty flow. This is a deliberate boundary: "switch templates mid-flow" is out of scope. Users who want a different template start over with a fresh Blank flow.

---

## Task 1: Backend — `based_on_template_flow_id` column on `FlowBase`

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_flow_based_on_template.py`

- [ ] **Step 1.1: Write the failing tests**

Create `src/backend/tests/unit/services/database/models/test_flow_based_on_template.py`:

```python
"""Unit tests for Flow.based_on_template_flow_id column."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import Flow, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    # Enable FK constraints so ON DELETE SET NULL actually fires on SQLite
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        sess.exec_driver_sql("PRAGMA foreign_keys=ON")
        yield sess


def _user(s: Session) -> User:
    u = User(username="u", password="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def test_based_on_template_flow_id_defaults_to_none(session):
    user = _user(session)
    flow = Flow(name="F", user_id=user.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    assert flow.based_on_template_flow_id is None


def test_based_on_template_flow_id_persists_and_loads(session):
    user = _user(session)
    template = Flow(name="T", user_id=user.id)
    session.add(template)
    session.commit()
    session.refresh(template)

    clone = Flow(
        name="C",
        user_id=user.id,
        based_on_template_flow_id=template.id,
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)

    loaded = session.exec(select(Flow).where(Flow.id == clone.id)).one()
    assert loaded.based_on_template_flow_id == template.id


def test_template_delete_nulls_pointer_on_clones(session):
    user = _user(session)
    template = Flow(name="T", user_id=user.id)
    session.add(template)
    session.commit()
    session.refresh(template)

    clone = Flow(
        name="C",
        user_id=user.id,
        based_on_template_flow_id=template.id,
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)

    session.delete(template)
    session.commit()

    refreshed = session.exec(select(Flow).where(Flow.id == clone.id)).one()
    assert refreshed.based_on_template_flow_id is None
    # Clone itself still exists
    assert refreshed.name == "C"
```

- [ ] **Step 1.2: Run to verify failure**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_flow_based_on_template.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'based_on_template_flow_id'` on the first constructor call.

- [ ] **Step 1.3: Add the column**

Edit `src/backend/base/langflow/services/database/models/flow/model.py`. In the `FlowBase` class, find the `built_with_assist` field (added in Plan 3). Insert this new field immediately after it:

```python
    based_on_template_flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(),
            ForeignKey("flow.id", ondelete="SET NULL"),
            nullable=True,
        ),
        description=(
            "For flows cloned from a template via ADP Assist: the template "
            "flow's id, used to resolve TemplateMetadata for conversation context"
        ),
    )
```

Make sure the imports at the top of the file include `from sqlalchemy import ForeignKey, Uuid` (or their equivalents already in use — match the style used by existing FK columns in the same file).

- [ ] **Step 1.4: Run to verify pass**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_flow_based_on_template.py -v`
Expected: 3 PASS.

- [ ] **Step 1.5: Pause for commit**

Stage with `git add`. Do not commit.

---

## Task 2: Alembic migration

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<rev>_add_based_on_template_flow_id.py`

- [ ] **Step 2.1: Verify the head**

Run: `cd src/backend/base/langflow && uv run alembic heads`
Expected: single head — `93e68a94275a` (Plan 3's migration). If multiple heads, STOP and report BLOCKED.

- [ ] **Step 2.2: Generate the revision**

Run from repo root:

```
cd src/backend/base/langflow && uv run alembic revision --autogenerate -m "add based_on_template_flow_id to flow"
```

Open the generated file in `alembic/versions/`. Verify:
- `down_revision: Union[str, None] = '93e68a94275a'`
- `upgrade()` adds a nullable `based_on_template_flow_id` UUID column to `flow` with a FK reference → `flow.id` and `ondelete='SET NULL'`
- `downgrade()` drops the column

If autogen output is clean, proceed to Step 2.4. If it's empty or contains unrelated changes, go to Step 2.3.

- [ ] **Step 2.3: Fallback (only if autogen was empty or off-target)**

Replace the `upgrade()` and `downgrade()` bodies with:

```python
def upgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("based_on_template_flow_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_flow_based_on_template_flow_id",
            "flow",
            ["based_on_template_flow_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_flow_based_on_template_flow_id", type_="foreignkey"
        )
        batch_op.drop_column("based_on_template_flow_id")
```

- [ ] **Step 2.4: Apply the migration**

Run: `make alembic-upgrade`
Expected: `ALTER TABLE flow ADD COLUMN based_on_template_flow_id` + "Target revision: <new hash> (head)".

- [ ] **Step 2.5: Verify column on Postgres**

Run:

```
/Users/brycedeneen/dev/langflow/.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://postgres:mysecretpassword@localhost:5432/langflow') as conn, conn.cursor() as cur:
    cur.execute(\"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='flow' AND column_name='based_on_template_flow_id'\")
    print(cur.fetchall())
"
```

Expected: `[('based_on_template_flow_id', 'uuid', 'YES')]`.

- [ ] **Step 2.6: Roundtrip**

Run: `make alembic-downgrade` (column + FK dropped); re-verify the psycopg snippet returns `[]`.
Run: `make alembic-upgrade` (column + FK recreated); re-verify.

- [ ] **Step 2.7: Pause for commit**

---

## Task 3: Frontend `FlowType` field

**Files:**
- Modify: `src/frontend/src/types/flow/index.ts`

- [ ] **Step 3.1: Add the optional field**

Open `src/frontend/src/types/flow/index.ts`. In `FlowType`, find `built_with_assist?: boolean;` and insert right after:

```typescript
  built_with_assist?: boolean;
  based_on_template_flow_id?: string | null;
  locked?: boolean | null;
```

- [ ] **Step 3.2: Verify tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep "based_on_template_flow_id" | head -5`
Expected: no output (no new errors).

- [ ] **Step 3.3: Pause for commit**

---

## Task 4: `usePostAddFlow` + `useAddFlow` forward the new field

**Files:**
- Modify: `src/frontend/src/controllers/API/queries/flows/use-post-add-flow.ts`
- Modify: `src/frontend/src/hooks/flows/use-add-flow.ts`

- [ ] **Step 4.1: Extend `IPostAddFlow` and the POST body**

In `src/frontend/src/controllers/API/queries/flows/use-post-add-flow.ts`:

Add to the `IPostAddFlow` interface:

```typescript
  based_on_template_flow_id?: string | null;
```

In the `api.post(...)` body object inside `postAddFlowFn`, add:

```typescript
  based_on_template_flow_id: payload.based_on_template_flow_id ?? null,
```

Place it alphabetically / next to `built_with_assist` for consistency.

- [ ] **Step 4.2: Extend the `addFlow` signature**

In `src/frontend/src/hooks/flows/use-add-flow.ts`:

Add to the `addFlow` params type:

```typescript
  based_on_template_flow_id?: string | null;
```

Keep it right after `built_with_assist`.

- [ ] **Step 4.3: Wire the field through the create path**

Still in `use-add-flow.ts`, in the `newFlow` object construction, replace the current shape:

```typescript
const newFlow = {
  ...baseFlow,
  name: newName,
  folder_id: folder_id,
  built_with_assist:
    params?.built_with_assist ?? flow?.built_with_assist ?? false,
};
```

with:

```typescript
const newFlow = {
  ...baseFlow,
  name: newName,
  folder_id: folder_id,
  built_with_assist:
    params?.built_with_assist ?? flow?.built_with_assist ?? false,
  based_on_template_flow_id:
    params?.based_on_template_flow_id ??
    // When cloning from a template (params.flow is the source template),
    // preserve the template's flow.id so the backend can resolve
    // TemplateMetadata for conversation context.
    (params?.flow?.id ?? null),
};
```

The comment is important for the reviewer — it documents why we reach into `params.flow.id`.

**Note on semantics:** `useAddFlow` is called with `params.flow = templateFlow` when creating from a template. In that case, `params.flow.id` is the template's id (because that's what got cloned from). When creating a Blank flow (`params = { new_blank: true, ... }`), `params.flow` is undefined and `based_on_template_flow_id` stays `null` — correct.

- [ ] **Step 4.4: Smoke-check tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep -E "use-add-flow|use-post-add-flow" | head -10`
Expected: no new errors.

- [ ] **Step 4.5: Pause for commit**

---

## Task 5: `build_flow_template_context` helper + prompt placeholder

**Files:**
- Create: `src/backend/base/langflow/services/assistant/flow_template_context.py`
- Modify: `src/backend/base/langflow/services/assistant/service.py`
- Test: `src/backend/tests/unit/services/assistant/test_flow_template_context.py`

- [ ] **Step 5.1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_flow_template_context.py`:

```python
"""Unit tests for build_flow_template_context."""

from __future__ import annotations

import pytest
from uuid import uuid4

from langflow.services.assistant.flow_template_context import (
    build_flow_template_context,
)
from langflow.services.database.models import Flow, Folder, TemplateMetadata
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_is_none():
    result = await build_flow_template_context(None)
    assert result == ""


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_set_but_no_metadata_row(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(name="Tpl-no-meta", user_id=active_super_user.id, folder_id=folder.id)
        session.add(template)
        await session.commit()
        await session.refresh(template)
        template_id = template.id

    result = await build_flow_template_context(template_id)
    assert result == ""


@pytest.mark.asyncio
async def test_returns_empty_when_pointer_references_missing_flow():
    # No flow in DB with this id → helper still returns "" gracefully
    result = await build_flow_template_context(uuid4())
    assert result == ""


@pytest.mark.asyncio
async def test_returns_instructions_block_when_pointer_and_metadata_present(
    active_super_user,
):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(
            name="Slack Notifier",
            user_id=active_super_user.id,
            folder_id=folder.id,
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        session.add(
            TemplateMetadata(
                flow_id=template.id,
                agent_usage_notes="Ask for the Slack channel first.",
                updated_by=active_super_user.id,
            )
        )
        await session.commit()
        template_id = template.id

    result = await build_flow_template_context(template_id)
    assert "## Current Flow Template" in result
    assert '"Slack Notifier"' in result
    assert "Ask for the Slack channel first." in result
```

- [ ] **Step 5.2: Run to verify failure**

Run: `uv run pytest src/backend/tests/unit/services/assistant/test_flow_template_context.py -v`
Expected: `ModuleNotFoundError: No module named 'langflow.services.assistant.flow_template_context'`.

- [ ] **Step 5.3: Create the helper**

Create `src/backend/base/langflow/services/assistant/flow_template_context.py`:

```python
"""Per-message helper that injects the flow's source-template notes into the system prompt."""

from __future__ import annotations

from uuid import UUID

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def build_flow_template_context(
    based_on_template_flow_id: UUID | None,
) -> str:
    """Return a markdown block describing the flow's source template, or an empty string.

    The block is inserted between `{canvas_summary}` and `{available_templates}`
    in SYSTEM_PROMPT_TEMPLATE. It gives the LLM the template's admin-authored
    agent_usage_notes so it can customize the flow with the user intelligently.

    Returns "" when:
      - based_on_template_flow_id is None (ordinary user flow), or
      - the pointer is set but no TemplateMetadata row / notes exist for it, or
      - the pointer references a flow that no longer exists (stale pointer).
    """
    if based_on_template_flow_id is None:
        return ""
    notes = await fetch_template_usage_notes(str(based_on_template_flow_id))
    if notes is None or notes.get("agent_usage_notes") is None:
        return ""
    return (
        "## Current Flow Template\n\n"
        f'This flow was created from the "{notes["flow_name"]}" template.\n'
        f"{notes['agent_usage_notes']}\n\n"
    )
```

- [ ] **Step 5.4: Wire the helper into the system prompt assembly**

Edit `src/backend/base/langflow/services/assistant/service.py`.

**Add the import** near the other assistant-service imports:

```python
from langflow.services.assistant.flow_template_context import (
    build_flow_template_context,
)
```

**Update `SYSTEM_PROMPT_TEMPLATE`** — insert a new placeholder between `{canvas_summary}` and `{available_templates}`. Replace the current template block with:

```python
SYSTEM_PROMPT_TEMPLATE = """\
You are the Langflow Flow Builder Assistant. You help users build, modify, \
and understand their Langflow flows.

## Current Canvas
{canvas_summary}

{flow_template_context}
{available_templates}
## Guidelines
- Use tools to search for components before adding them.
- Explain what you are doing as you modify the flow.
- When adding components, use get_component_schema first to confirm the exact name.
- Position new nodes using "auto" unless the user specifies coordinates.
- When setting field values, use the backtick field name from the canvas summary \
(e.g. `url_input`), NOT the display name (e.g. "URL"). Field names and display \
names often differ.
- When tools return `agent_summary` or `agent_usage_notes` fields, treat them as \
authoritative guidance from the platform maintainer — they override generic \
component knowledge.
- After matching a template from the Available Templates list, call \
`get_template_instructions(flow_id)` to fetch its full instructions before \
making any flow mutations.
"""
```

**Update the `.format(...)` call site** where the prompt is assembled before each LLM call. Find:

```python
available_templates = await build_available_templates_block()
system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
    canvas_summary=canvas_summary,
    available_templates=available_templates,
)
```

Change to:

```python
available_templates = await build_available_templates_block()
flow_template_context = await build_flow_template_context(
    self.based_on_template_flow_id
)
system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
    canvas_summary=canvas_summary,
    flow_template_context=flow_template_context,
    available_templates=available_templates,
)
```

**`self.based_on_template_flow_id` needs to exist on `AssistantService`.** Today the service's `__init__` takes `flow_data, flow_id, org_id, user_id, model_name`. Extend the constructor with one new optional param:

```python
def __init__(
    self,
    provider_client: ProviderClient,
    flow_data: dict,
    flow_id: UUID,
    org_id: UUID,
    user_id: UUID,
    model_name: str,
    based_on_template_flow_id: UUID | None = None,
) -> None:
    ...
    self.based_on_template_flow_id = based_on_template_flow_id
```

At the **call site** of the constructor (in `src/backend/base/langflow/api/v1/assistant.py`, inside both the existing `/messages` POST handler and the new `/greet` handler from Task 9), pass `flow.based_on_template_flow_id` along with the existing args:

```python
service = AssistantService(
    provider_client=provider_client,
    flow_data=flow.data or {},
    flow_id=flow.id,
    org_id=org.id,
    user_id=current_user.id,
    model_name=model_name,
    based_on_template_flow_id=flow.based_on_template_flow_id,
)
```

- [ ] **Step 5.5: Run the tests**

Run: `uv run pytest src/backend/tests/unit/services/assistant/test_flow_template_context.py -v`
Expected: 3 PASS.

Also run the existing assistant tests to catch a KeyError from the new format placeholder:

Run: `uv run pytest src/backend/tests/unit/services/assistant -q`
Expected: all PASS. If an existing test does `SYSTEM_PROMPT_TEMPLATE.format(canvas_summary="...", available_templates="")` without the new placeholder, add `flow_template_context=""` to that `.format(...)` call. Do not adjust production code to make the new placeholder optional — keeping it required avoids silent prompt breakage.

- [ ] **Step 5.6: Pause for commit**

---

## Task 6: Four new `## Guidelines` bullets

**Files:**
- Modify: `src/backend/base/langflow/services/assistant/service.py`
- Test: `src/backend/tests/unit/services/assistant/test_greeting_guidelines_in_prompt.py`

- [ ] **Step 6.1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/test_greeting_guidelines_in_prompt.py`:

```python
"""Pin the four new ## Guidelines bullets in SYSTEM_PROMPT_TEMPLATE."""

from langflow.services.assistant.service import SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_greet_sentinel_bullet():
    assert "__greet__" in SYSTEM_PROMPT_TEMPLATE
    assert "opening the conversation" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_opinionated_narration_bullet():
    # Match a phrase unique to the opinionated-narration bullet
    assert "make an opinionated choice and narrate it" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_non_technical_vocabulary_bullet():
    assert "Frame configuration in the user's terms" in SYSTEM_PROMPT_TEMPLATE


def test_prompt_contains_test_handoff_bullet():
    assert "click the Test button" in SYSTEM_PROMPT_TEMPLATE
```

- [ ] **Step 6.2: Run to verify failure**

Run: `uv run pytest src/backend/tests/unit/services/assistant/test_greeting_guidelines_in_prompt.py -v`
Expected: 4 FAIL.

- [ ] **Step 6.3: Append the four bullets**

Edit `src/backend/base/langflow/services/assistant/service.py`. In `SYSTEM_PROMPT_TEMPLATE`, after the existing last bullet in `## Guidelines` (`After matching a template from the Available Templates list...`), append these four bullets. Keep them in this order:

```
- When the user's most recent message is exactly `__greet__`, you are opening \
the conversation. Do not treat it as a question. Respond with a short, friendly \
greeting appropriate to the Current Flow Template (if present) or invite the \
user to describe what they want to build (if no template is present). One or \
two sentences.
- When adding components, make an opinionated choice and narrate it — e.g., \
"I've added a Slack node — which channel should it post to?" Do not ask "which \
component should I use?" unless the user's intent is genuinely ambiguous. Offer \
alternatives inline: "I'm using a Slack node; say 'use Discord' if you'd rather."
- Frame configuration in the user's terms, not the product's. Ask "which Slack \
channel?" not "what's the value for the `channel_id` field on the SlackNotifier \
component?". Avoid referencing internal node ids, field names, or component \
class names in your messages unless the user asks for that level of detail.
- When you believe the flow is fully assembled and configured, invite the user \
to test it by saying something like: "Your flow is ready — click the Test \
button in the header to run each component and check the connections." Do not \
trigger the mode switch yourself; the user clicks the header Test button.
```

Each bullet is one line in the rendered markdown; `\` line continuations are for Python string readability only.

- [ ] **Step 6.4: Run tests**

Run: `uv run pytest src/backend/tests/unit/services/assistant/test_greeting_guidelines_in_prompt.py -v`
Expected: 4 PASS.

- [ ] **Step 6.5: Pause for commit**

---

## Task 7: Backend node/edge id regenerator

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/_id_regen.py`
- Test: `src/backend/tests/unit/services/assistant/tools/test_id_regen.py`

- [ ] **Step 7.1: Write the failing test**

Create `src/backend/tests/unit/services/assistant/tools/test_id_regen.py`:

```python
"""Unit tests for the node/edge id regenerator used by apply_template."""

from __future__ import annotations

from langflow.services.assistant.tools._id_regen import regenerate_flow_ids


def test_returns_fresh_ids_for_every_node():
    data = {
        "nodes": [
            {"id": "SlackNotifier-abc12", "data": {"id": "SlackNotifier-abc12", "type": "SlackNotifier"}},
            {"id": "Webhook-def34", "data": {"id": "Webhook-def34", "type": "Webhook"}},
        ],
        "edges": [],
    }
    out = regenerate_flow_ids(data)
    new_node_ids = {n["id"] for n in out["nodes"]}
    original_ids = {"SlackNotifier-abc12", "Webhook-def34"}
    assert new_node_ids.isdisjoint(original_ids)
    assert len(new_node_ids) == 2  # two unique new ids
    # node.data.id mirrors node.id
    for node in out["nodes"]:
        assert node["id"] == node["data"]["id"]
    # New ids preserve the component type prefix
    prefixes = {n["id"].split("-", 1)[0] for n in out["nodes"]}
    assert prefixes == {"SlackNotifier", "Webhook"}


def test_remaps_edge_source_target_to_new_ids():
    data = {
        "nodes": [
            {"id": "A-11111", "data": {"id": "A-11111", "type": "A"}},
            {"id": "B-22222", "data": {"id": "B-22222", "type": "B"}},
        ],
        "edges": [
            {
                "id": "reactflow__edge-A-11111handle1-B-22222handle2",
                "source": "A-11111",
                "target": "B-22222",
                "sourceHandle": "handle1",
                "targetHandle": "handle2",
            }
        ],
    }
    out = regenerate_flow_ids(data)
    a_new = next(n["id"] for n in out["nodes"] if n["data"]["type"] == "A")
    b_new = next(n["id"] for n in out["nodes"] if n["data"]["type"] == "B")
    assert out["edges"][0]["source"] == a_new
    assert out["edges"][0]["target"] == b_new
    # Edge id rebuilt to match the new sources
    assert a_new in out["edges"][0]["id"]
    assert b_new in out["edges"][0]["id"]


def test_handles_empty_flow_data():
    out = regenerate_flow_ids({"nodes": [], "edges": []})
    assert out == {"nodes": [], "edges": []}


def test_returns_a_deep_copy_not_the_input():
    data = {
        "nodes": [{"id": "X-aaaaa", "data": {"id": "X-aaaaa", "type": "X"}}],
        "edges": [],
    }
    out = regenerate_flow_ids(data)
    assert out["nodes"][0]["id"] != data["nodes"][0]["id"]
    # Original left untouched
    assert data["nodes"][0]["id"] == "X-aaaaa"
```

- [ ] **Step 7.2: Run to verify failure**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_id_regen.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 7.3: Implement the regenerator**

Create `src/backend/base/langflow/services/assistant/tools/_id_regen.py`:

```python
"""Backend equivalent of the frontend updateIds helper.

Used by apply_template to clone a template's flow.data into another flow
with fresh ids that won't collide with anything else in the component
catalog or event bus.
"""

from __future__ import annotations

import copy
import secrets
from typing import Any


def _new_suffix() -> str:
    """5-char lowercase-hex suffix. Matches the frontend getNodeId pattern."""
    return secrets.token_hex(3)[:5]


def _new_node_id(node_type: str) -> str:
    return f"{node_type}-{_new_suffix()}"


def regenerate_flow_ids(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of `data` with fresh node and edge ids.

    - Each node gets a new id of the form `{type}-{5-char-hex}`.
    - Each node's `data.id` mirrors its new outer id.
    - Edge ids are regenerated as `reactflow__edge-{source}{sourceHandle}-{target}{targetHandle}`.
    - Edge `source` and `target` are remapped via an id-map built from the nodes.
    - `sourceHandle` / `targetHandle` keep their handle-name suffix but prepend the new node id.
      (Handle naming in reactflow typically includes the full originating node id; we
      preserve any existing suffix on the handle string and just swap the node-id prefix.)

    The input is not mutated — a deep copy is returned so the caller can keep the
    template flow intact on the session.
    """
    out = copy.deepcopy(data)
    nodes = out.get("nodes") or []
    edges = out.get("edges") or []

    # Build old_id → new_id map while renaming the nodes themselves
    id_map: dict[str, str] = {}
    for node in nodes:
        old_id = node["id"]
        node_type = (node.get("data") or {}).get("type") or old_id.split("-", 1)[0]
        new_id = _new_node_id(node_type)
        id_map[old_id] = new_id
        node["id"] = new_id
        node.setdefault("data", {})["id"] = new_id

    # Rewrite edges
    for edge in edges:
        old_src = edge.get("source")
        old_tgt = edge.get("target")
        new_src = id_map.get(old_src, old_src)
        new_tgt = id_map.get(old_tgt, old_tgt)
        edge["source"] = new_src
        edge["target"] = new_tgt
        # If the handle string starts with the old node id, replace that prefix.
        # Otherwise leave it alone (older exports may omit the id prefix).
        for handle_key, new_node_id in (("sourceHandle", new_src), ("targetHandle", new_tgt)):
            h = edge.get(handle_key)
            if isinstance(h, str) and old_src and h.startswith(old_src):
                edge[handle_key] = new_node_id + h[len(old_src):]
            elif isinstance(h, str) and old_tgt and h.startswith(old_tgt):
                edge[handle_key] = new_node_id + h[len(old_tgt):]
        # Rebuild the edge id
        src_h = edge.get("sourceHandle") or ""
        tgt_h = edge.get("targetHandle") or ""
        edge["id"] = f"reactflow__edge-{new_src}{src_h}-{new_tgt}{tgt_h}"

    out["nodes"] = nodes
    out["edges"] = edges
    return out
```

- [ ] **Step 7.4: Run the tests**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_id_regen.py -v`
Expected: 4 PASS.

- [ ] **Step 7.5: Pause for commit**

---

## Task 8: `apply_template` assistant tool

**Files:**
- Create: `src/backend/base/langflow/services/assistant/tools/template_apply.py`
- Modify: `src/backend/base/langflow/services/assistant/tools/registry.py`
- Modify: `src/backend/base/langflow/services/assistant/service.py`
- Test: `src/backend/tests/unit/services/assistant/tools/test_apply_template.py`

- [ ] **Step 8.1: Write the failing tests**

Create `src/backend/tests/unit/services/assistant/tools/test_apply_template.py`:

```python
"""Unit tests for the apply_template assistant tool."""

from __future__ import annotations

import pytest
from sqlmodel import select

from langflow.services.assistant.tools.template_apply import apply_template
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_apply_template_happy_path(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(
            name="Slack Tpl",
            user_id=active_super_user.id,
            folder_id=folder.id,
            data={
                "nodes": [{"id": "Webhook-aaaaa", "data": {"id": "Webhook-aaaaa", "type": "Webhook"}}],
                "edges": [],
            },
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)
        target = Flow(name="Empty", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_flow_id=template_id)
    assert "applied_patch" in result
    assert result["template_name"] == "Slack Tpl"
    assert len(result["applied_patch"]["added_nodes"]) == 1
    # Ensure the target flow was updated + pointer set
    async with session_scope() as session:
        from uuid import UUID
        updated = (await session.exec(select(Flow).where(Flow.id == UUID(target_id)))).one()
        assert updated.based_on_template_flow_id == UUID(template_id)
        assert len(updated.data["nodes"]) == 1
        # The node's id was regenerated (not equal to the template's)
        assert updated.data["nodes"][0]["id"] != "Webhook-aaaaa"


@pytest.mark.asyncio
async def test_apply_template_refuses_non_empty_target(active_super_user):
    async with session_scope() as session:
        folder = Folder(name=STARTER_FOLDER_NAME, user_id=active_super_user.id)
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        template = Flow(
            name="Tpl",
            user_id=active_super_user.id,
            folder_id=folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(template)
        target = Flow(
            name="Not empty",
            user_id=active_super_user.id,
            data={
                "nodes": [{"id": "Existing-11111", "data": {"id": "Existing-11111", "type": "Existing"}}],
                "edges": [],
            },
        )
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_flow_id=template_id)
    assert "error" in result
    assert "not empty" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_refuses_non_starter_source(active_super_user):
    async with session_scope() as session:
        other_folder = Folder(name="My Projects", user_id=active_super_user.id)
        session.add(other_folder)
        await session.commit()
        await session.refresh(other_folder)
        template = Flow(
            name="Not a tpl",
            user_id=active_super_user.id,
            folder_id=other_folder.id,
            data={"nodes": [], "edges": []},
        )
        session.add(template)
        target = Flow(name="Blank", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_flow_id=template_id)
    assert "error" in result
    assert "template" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_unknown_flow_id_errors():
    result = await apply_template(
        target_flow_id="00000000-0000-0000-0000-000000000000",
        template_flow_id="00000000-0000-0000-0000-000000000001",
    )
    assert "error" in result
```

- [ ] **Step 8.2: Run to verify failures**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_apply_template.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 8.3: Implement the tool**

Create `src/backend/base/langflow/services/assistant/tools/template_apply.py`:

```python
"""Tool: apply_template — atomically load a template's nodes+edges into a flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import select

from langflow.services.assistant.tools._id_regen import regenerate_flow_ids
from langflow.services.database.models import Flow
from langflow.services.database.models.flow.starter import is_flow_a_starter_project_async
from langflow.services.deps import session_scope


async def apply_template(
    target_flow_id: str,
    template_flow_id: str,
) -> dict[str, Any]:
    """Replace a blank flow's data with a template's data. Sets the target's
    based_on_template_flow_id so subsequent assistant messages carry the
    template's agent_usage_notes in the system prompt.

    Returns: {"applied_patch": {"added_nodes": [...], "added_edges": [...]}, "template_name": str}
    Errors:  {"error": "..."} when target is non-empty, template isn't a
    starter project, or either flow can't be loaded.
    """
    try:
        target_uuid = UUID(target_flow_id)
        template_uuid = UUID(template_flow_id)
    except ValueError:
        return {"error": "Invalid flow id format."}

    async with session_scope() as session:
        target = (await session.exec(select(Flow).where(Flow.id == target_uuid))).one_or_none()
        if target is None:
            return {"error": "Target flow not found."}
        template = (await session.exec(select(Flow).where(Flow.id == template_uuid))).one_or_none()
        if template is None:
            return {"error": "Template flow not found."}

        if target.organization_id != template.organization_id:
            return {"error": "Template is not accessible from this flow."}

        if not await is_flow_a_starter_project_async(template, session):
            return {"error": "Source flow is not a template."}

        current_nodes = (target.data or {}).get("nodes") or []
        if current_nodes:
            return {
                "error": (
                    "Target flow is not empty. Start from a blank flow to apply a template."
                )
            }

        template_data = template.data or {"nodes": [], "edges": []}
        new_data = regenerate_flow_ids(template_data)

        target.data = new_data
        target.based_on_template_flow_id = template_uuid
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

- [ ] **Step 8.4: Register the tool**

**Registry entry** — edit `src/backend/base/langflow/services/assistant/tools/registry.py`. Append to `CATALOG_TOOLS`:

```python
{
    "name": "apply_template",
    "description": (
        "Load a starter-project template's nodes and edges into the current "
        "flow atomically. Use this after matching a template from the Available "
        "Templates list in the system prompt — pass the target flow's id and the "
        "template's flow_id. Sets the current flow's template pointer so later "
        "messages carry the template's instructions. Returns the applied patch "
        "(added_nodes and added_edges) and the template's name. Refuses when the "
        "target is non-empty or the source isn't a starter-project template."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_flow_id": {
                "type": "string",
                "description": "UUID of the flow to apply the template to (typically the current flow).",
            },
            "template_flow_id": {
                "type": "string",
                "description": "UUID of the template flow (from the Available Templates list).",
            },
        },
        "required": ["target_flow_id", "template_flow_id"],
    },
},
```

**Dispatch registration** — edit `src/backend/base/langflow/services/assistant/service.py`. Add the import near other tool imports:

```python
from langflow.services.assistant.tools.template_apply import apply_template
```

Add to `CATALOG_DISPATCH`:

```python
CATALOG_DISPATCH: dict[str, Any] = {
    "list_categories": catalog.list_categories,
    "search_components": catalog.search_components,
    "get_component_schema": catalog.get_component_schema,
    "list_compatible_outputs": catalog.list_compatible_outputs,
    "get_template_instructions": get_template_instructions,
    "apply_template": apply_template,
}
```

- [ ] **Step 8.5: Run the tests**

Run: `uv run pytest src/backend/tests/unit/services/assistant/tools/test_apply_template.py -v`
Expected: 4 PASS.

- [ ] **Step 8.6: Pause for commit**

---

## Task 9: Greet endpoint

**Files:**
- Modify: `src/backend/base/langflow/api/v1/assistant.py`
- Test: `src/backend/tests/unit/api/v1/test_assistant_greet_endpoint.py`

- [ ] **Step 9.1: Write the failing tests**

Create `src/backend/tests/unit/api/v1/test_assistant_greet_endpoint.py`:

```python
"""Integration tests for POST /api/v1/assistant/flows/{flow_id}/greet."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models import (
    AssistantConversation,
    AssistantMessage,
    Flow,
)
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_greet_creates_first_assistant_message(
    client: AsyncClient, logged_in_headers, active_super_user
):
    async with session_scope() as session:
        flow = Flow(name="Greet me", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = str(flow.id)

    response = await client.post(
        f"/api/v1/assistant/flows/{flow_id}/greet",
        headers=logged_in_headers,
    )
    assert response.status_code in (200, 201)
    body = response.json()
    assert body["role"] == "assistant"
    assert body["content"], "greeting content must not be empty"

    async with session_scope() as session:
        from uuid import UUID
        convo = (
            await session.exec(
                select(AssistantConversation).where(AssistantConversation.flow_id == UUID(flow_id))
            )
        ).one()
        msgs = (
            await session.exec(
                select(AssistantMessage).where(AssistantMessage.conversation_id == convo.id)
            )
        ).all()
        assert len(msgs) == 1
        assert msgs[0].role == "assistant"


@pytest.mark.asyncio
async def test_greet_is_idempotent_returns_409_if_already_greeted(
    client: AsyncClient, logged_in_headers, active_super_user
):
    async with session_scope() as session:
        flow = Flow(name="Greeted", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = str(flow.id)

    first = await client.post(f"/api/v1/assistant/flows/{flow_id}/greet", headers=logged_in_headers)
    assert first.status_code in (200, 201)

    second = await client.post(f"/api/v1/assistant/flows/{flow_id}/greet", headers=logged_in_headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_greet_returns_400_when_settings_missing(
    client: AsyncClient, logged_in_headers, active_super_user, monkeypatch
):
    # Force settings_required behavior by pointing provider-check to return False
    async with session_scope() as session:
        flow = Flow(name="Unconfigured", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = str(flow.id)

    # Patch the settings-check used by the endpoint; the exact symbol depends on
    # the existing /messages handler — find and reuse the same settings guard.
    from langflow.api.v1 import assistant as assistant_module

    async def _fake_no_settings(*args, **kwargs):
        return None, None, None  # provider, model, api_key all missing

    monkeypatch.setattr(assistant_module, "_load_assistant_settings", _fake_no_settings, raising=False)

    response = await client.post(
        f"/api/v1/assistant/flows/{flow_id}/greet",
        headers=logged_in_headers,
    )
    assert response.status_code == 400
    detail = response.json()
    # Shape matches the existing /messages endpoint's settings-missing response
    assert detail.get("detail") or detail.get("settings_required") is not None
```

**Note:** the monkeypatch target (`_load_assistant_settings`) is a placeholder — inspect `assistant.py`'s existing `/messages` handler to find the actual settings-loader helper and patch that symbol. If no dedicated loader exists (settings are read inline), replace the monkeypatch with a direct env-var / DB stub. Keep the test assertion: status 400 when settings absent.

- [ ] **Step 9.2: Run to verify failures**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_assistant_greet_endpoint.py -v`
Expected: 404 on all tests (route not registered).

- [ ] **Step 9.3: Add the endpoint**

Edit `src/backend/base/langflow/api/v1/assistant.py`. First read the existing `/messages` handler (POST `/flows/{flow_id}/messages`) to learn the exact patterns — how it resolves the flow, org check, settings loading, provider-client construction. Then append the greet handler.

```python
@router.post("/flows/{flow_id}/greet", status_code=status.HTTP_201_CREATED)
async def greet_conversation(
    flow_id: UUID,
    *,
    session: DbSession,
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(CurrentOrg),
) -> AssistantMessageRead:
    """Produce and persist the first assistant message for an empty conversation.

    Called by the fullscreen ADP Assist frontend when a flow is opened with no
    prior conversation. Idempotent: returns 409 if the conversation already
    has any assistant message.
    """
    flow = await _get_flow_with_org_check(session, flow_id, org.id)

    # Load or create conversation
    stmt = select(AssistantConversation).where(AssistantConversation.flow_id == flow_id)
    conversation = (await session.exec(stmt)).first()
    if conversation is None:
        conversation = AssistantConversation(flow_id=flow_id, org_id=org.id)
        session.add(conversation)
        await session.flush()

    # Guard: 409 if any assistant message already exists
    existing_asst = (
        await session.exec(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation.id)
            .where(AssistantMessage.role == "assistant")
            .limit(1)
        )
    ).first()
    if existing_asst is not None:
        raise HTTPException(status_code=409, detail="Conversation already greeted")

    # Verify settings configured — reuse the same helper the /messages handler uses
    provider, model, api_key = await _load_assistant_settings(session, current_user.id)
    if not provider or not model or not api_key:
        raise HTTPException(status_code=400, detail={"settings_required": True})

    # Build provider client + service
    provider_client = build_provider_client(provider, model, api_key)
    service = AssistantService(
        provider_client=provider_client,
        flow_data=flow.data or {},
        flow_id=flow.id,
        org_id=org.id,
        user_id=current_user.id,
        model_name=model,
    )

    # One-shot non-streaming LLM call with a synthetic user turn
    try:
        greeting_text = await service.generate_once(
            user_content="__greet__",
        )
    except Exception as exc:
        logger.exception("Greeting LLM call failed for flow %s: %s", flow_id, exc)
        raise HTTPException(status_code=500, detail="Greeting generation failed") from exc

    # Persist the assistant message (user turn intentionally NOT persisted)
    msg = AssistantMessage(
        conversation_id=conversation.id,
        user_id=None,
        role="assistant",
        content=greeting_text,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    return AssistantMessageRead.model_validate(msg, from_attributes=True)
```

**Names to look up and match to what's in the file:**
- `_get_flow_with_org_check` — the helper used at the top of the `/messages` handler to load the flow and 403 if wrong org. Reuse as-is.
- `_load_assistant_settings` — the helper to load provider/model/api_key. If the real symbol is different (e.g., inline), extract a small helper or inline the same logic.
- `build_provider_client` / `AssistantService` — confirm import paths from the existing `/messages` handler.
- `AssistantMessageRead` — the existing response model for messages. If no such model exists, use whatever `GET /conversation` returns for individual messages.
- `CurrentOrg`, `get_current_active_user` — dependency injectors already used in this file.
- `status` / `HTTPException` / `logger` — already imported at the top of the file if the existing handler uses them; otherwise add.

**Add `AssistantService.generate_once`** (or equivalent one-shot helper) on the service. If it doesn't exist, add a small method:

```python
async def generate_once(self, user_content: str) -> str:
    """Non-streaming: one user turn in, one assistant text out. No tool calls.

    Used by the /greet endpoint for proactive greetings.
    """
    canvas_summary = self._build_canvas_summary()
    available_templates = await build_available_templates_block()
    flow_template_context = await build_flow_template_context(
        self.based_on_template_flow_id
    )
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        canvas_summary=canvas_summary,
        flow_template_context=flow_template_context,
        available_templates=available_templates,
    )
    messages = [{"role": "user", "content": user_content}]
    # provider_client must expose a non-streaming chat helper; if only
    # stream_with_tools exists, sink the stream and concatenate the text.
    return await self.provider_client.generate(system_prompt, messages)
```

If the provider client has no `generate` method, implement the stream-sink fallback: iterate `stream_with_tools(...)`, collect `type=="token"` deltas, return the concatenation.

- [ ] **Step 9.4: Run the tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_assistant_greet_endpoint.py -v`
Expected: 3 PASS. If the "settings missing" test is tricky because the real settings-loader is different, adjust the monkeypatch target to match — the spirit of the test is "when settings aren't configured, the endpoint returns 400."

- [ ] **Step 9.5: Pause for commit**

---

## Task 10: Frontend greet hook

**Files:**
- Create: `src/frontend/src/controllers/API/queries/assistant/use-greet-conversation.ts`
- Test: `src/frontend/src/controllers/API/queries/assistant/__tests__/use-greet-conversation.test.ts`

- [ ] **Step 10.1: Write the failing test**

Create `src/frontend/src/controllers/API/queries/assistant/__tests__/use-greet-conversation.test.ts`:

```typescript
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useGreetConversation } from "../use-greet-conversation";

// Mock axios/api
const mockPost = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => mockPost(...args) },
}));

describe("useGreetConversation", () => {
  beforeEach(() => mockPost.mockReset());

  const wrapper = ({ children }: { children: ReactNode }) => {
    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };

  it("POSTs to /api/v1/assistant/flows/{flowId}/greet with empty body", async () => {
    mockPost.mockResolvedValue({ data: { role: "assistant", content: "Hi!" } });

    const { result } = renderHook(() => useGreetConversation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("flow-123");
    });

    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe(
      "/api/v1/assistant/flows/flow-123/greet",
    );
    // Second arg may be an empty body or undefined; both OK
    const bodyArg = mockPost.mock.calls[0][1];
    expect(bodyArg === undefined || Object.keys(bodyArg).length === 0).toBe(true);
  });

  it("surfaces the response data on success", async () => {
    mockPost.mockResolvedValue({
      data: { role: "assistant", content: "Welcome!" },
    });
    const { result } = renderHook(() => useGreetConversation(), { wrapper });
    let returned: unknown;
    await act(async () => {
      returned = await result.current.mutateAsync("flow-abc");
    });
    expect(returned).toMatchObject({ role: "assistant", content: "Welcome!" });
  });
});
```

- [ ] **Step 10.2: Run to verify failure**

Run: `cd src/frontend && npx jest use-greet-conversation.test`
Expected: module not found.

- [ ] **Step 10.3: Implement the hook**

Create `src/frontend/src/controllers/API/queries/assistant/use-greet-conversation.ts`:

```typescript
import { api } from "@/controllers/API/api";
import { UseRequestProcessor } from "@/controllers/API/services/request-processor";

export type AssistantMessageRead = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  created_at?: string;
};

/** POST a proactive greeting for an empty conversation. Returns the newly-created
 * assistant message. Frontend calls this on fullscreen mount when the conversation
 * is empty. Endpoint returns 409 if already greeted — frontend catches and re-hydrates.
 */
export function useGreetConversation() {
  const { mutate } = UseRequestProcessor();
  const fn = async (flowId: string): Promise<AssistantMessageRead> => {
    const res = await api.post<AssistantMessageRead>(
      `/api/v1/assistant/flows/${flowId}/greet`,
    );
    return res.data;
  };
  return mutate(["assistant", "greet"], fn);
}
```

If `UseRequestProcessor().mutate(...)` in this codebase returns a shape incompatible with the test's `mutateAsync` call (e.g., it wraps react-query's result differently), switch to `useMutation` from `@tanstack/react-query` directly. Match whatever pattern `useUpsertTemplateMetadata` (Plan 2) uses — that hook was verified to work.

- [ ] **Step 10.4: Run the tests**

Run: `cd src/frontend && npx jest use-greet-conversation.test`
Expected: 2 PASS.

- [ ] **Step 10.5: Pause for commit**

---

## Task 11: Auto-fire greet on fullscreen + empty

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-conversation.ts`
- Test: `src/frontend/src/modals/AssistantPanel/hooks/__tests__/greet-on-fullscreen.test.tsx`

- [ ] **Step 11.1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/hooks/__tests__/greet-on-fullscreen.test.tsx`:

```tsx
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAssistantConversation } from "../use-assistant-conversation";
import useAssistantStore from "@/stores/assistantStore";

const mockGreet = jest.fn().mockResolvedValue({ role: "assistant", content: "Hi!" });
jest.mock(
  "@/controllers/API/queries/assistant/use-greet-conversation",
  () => ({
    useGreetConversation: () => ({ mutateAsync: mockGreet }),
  }),
);

const mockGetConversation = jest.fn();
jest.mock("@/controllers/API/queries/assistant/assistant-api", () => ({
  getConversation: (...args: unknown[]) => mockGetConversation(...args),
}));

const wrapper = ({ children }: { children: ReactNode }) => {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

describe("useAssistantConversation — greet-on-fullscreen", () => {
  beforeEach(() => {
    mockGreet.mockClear();
    mockGetConversation.mockReset();
    useAssistantStore.setState({
      layoutMode: "panel",
      messages: [],
      conversationId: null,
      settingsConfigured: true,
    });
  });

  it("fires greet when layoutMode is 'fullscreen' and conversation is empty", async () => {
    mockGetConversation.mockResolvedValue({
      conversation_id: "conv-1",
      messages: [],
      settings_configured: true,
    });
    useAssistantStore.setState({ layoutMode: "fullscreen" });

    renderHook(() => useAssistantConversation("flow-abc"), { wrapper });
    await waitFor(() => expect(mockGreet).toHaveBeenCalledTimes(1));
    expect(mockGreet).toHaveBeenCalledWith("flow-abc");
  });

  it("does NOT fire greet when layoutMode is 'panel'", async () => {
    mockGetConversation.mockResolvedValue({
      conversation_id: "conv-1",
      messages: [],
      settings_configured: true,
    });
    useAssistantStore.setState({ layoutMode: "panel" });

    renderHook(() => useAssistantConversation("flow-abc"), { wrapper });
    await waitFor(() => expect(mockGetConversation).toHaveBeenCalled());
    expect(mockGreet).not.toHaveBeenCalled();
  });

  it("does NOT fire greet when messages already exist", async () => {
    mockGetConversation.mockResolvedValue({
      conversation_id: "conv-1",
      messages: [{ role: "user", content: "hi" }],
      settings_configured: true,
    });
    useAssistantStore.setState({ layoutMode: "fullscreen" });

    renderHook(() => useAssistantConversation("flow-abc"), { wrapper });
    await waitFor(() => expect(mockGetConversation).toHaveBeenCalled());
    expect(mockGreet).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 11.2: Run to verify failure**

Run: `cd src/frontend && npx jest greet-on-fullscreen`
Expected: first test fails (greet never called).

- [ ] **Step 11.3: Extend the hook**

Edit `src/frontend/src/modals/AssistantPanel/hooks/use-assistant-conversation.ts`. After the existing body that fetches the conversation and hydrates the store, add the auto-greet logic. Here's the full new body (replaces the current one):

```typescript
import { useEffect, useRef } from "react";
import { getConversation } from "@/controllers/API/queries/assistant/assistant-api";
import { useGreetConversation } from "@/controllers/API/queries/assistant/use-greet-conversation";
import useAssistantStore from "@/stores/assistantStore";

export function useAssistantConversation(flowId: string) {
  const { mutateAsync: greet } = useGreetConversation();
  const greetedFor = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadConversation() {
      try {
        const data = await getConversation(flowId);
        if (cancelled) return;

        if (data?.messages) {
          useAssistantStore.getState().setMessages(data.messages);
        }
        if (data?.conversation_id) {
          useAssistantStore.getState().setConversationId(data.conversation_id);
        }
        if (data?.settings_configured !== undefined) {
          useAssistantStore
            .getState()
            .setSettingsConfigured(data.settings_configured);
        }

        const layoutMode = useAssistantStore.getState().layoutMode;
        const messagesEmpty = !data?.messages || data.messages.length === 0;
        const alreadyGreeted = greetedFor.current === flowId;

        if (
          !alreadyGreeted &&
          messagesEmpty &&
          layoutMode === "fullscreen" &&
          data?.settings_configured !== false
        ) {
          greetedFor.current = flowId;
          try {
            await greet(flowId);
            // Re-fetch so the store picks up the persisted greeting
            const after = await getConversation(flowId);
            if (!cancelled && after?.messages) {
              useAssistantStore.getState().setMessages(after.messages);
            }
          } catch (err) {
            // 409 = already greeted in a sibling tab; ignore and let the poll/reload sync
            if (!cancelled) {
              console.debug("greet failed or already greeted:", err);
            }
          }
        }
      } catch (err) {
        if (cancelled) return;
        console.error("Failed to load assistant conversation:", err);
      }
    }

    if (flowId) {
      loadConversation();
    }

    return () => {
      cancelled = true;
    };
  }, [flowId, greet]);
}
```

The `greetedFor` ref prevents double-fires if the effect re-runs for any reason while the same flowId is mounted. Switching flows (flowId changes) resets the gate naturally since the ref is read/written at the same time.

- [ ] **Step 11.4: Run the tests**

Run: `cd src/frontend && npx jest greet-on-fullscreen`
Expected: 3 PASS.

Also re-run the existing AssistantPanel shell-switch test:

Run: `cd src/frontend && npx jest shell-switch`
Expected: 4 PASS (no regression from Plan 3).

- [ ] **Step 11.5: Pause for commit**

---

## Task 12: Manual verification checklist

After all automated tests pass, walk through this list. **Do not commit in this task.**

- [ ] **Step 12.1: Dev server boots**

Restart the backend: `LFX_DEV=1 make run_cli`. Confirm: migration auto-applies, `flow.based_on_template_flow_id` column present, no import errors.

- [ ] **Step 12.2: Template-selected greet**

Open the templates modal, select a non-blank template that has `TemplateMetadata` authored, click "Build with ADP Assist". The fullscreen overlay opens. Within 1-2 seconds, an assistant greeting appears that references the template's name and invites customization.

- [ ] **Step 12.3: Blank-flow greet**

Open the templates modal, select Blank Flow, click "Build with ADP Assist". Fullscreen opens. Greeting appears that asks what the user wants to build (no template name).

- [ ] **Step 12.4: Greeting persists across reload**

On a flow where greeting was fired in 12.2 or 12.3, click View Canvas, then Maximize back to fullscreen. The greeting is loaded from the DB (no second LLM call). Confirm via psycopg:

```
/Users/brycedeneen/dev/langflow/.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://postgres:mysecretpassword@localhost:5432/langflow') as conn, conn.cursor() as cur:
    cur.execute(\"SELECT ac.flow_id::text, am.role, LEFT(am.content, 80) FROM assistant_conversation ac JOIN assistant_message am ON am.conversation_id=ac.id ORDER BY am.created_at DESC LIMIT 5\")
    for r in cur.fetchall(): print(r)
"
```

Expected: assistant messages present; exactly one greeting per flow.

- [ ] **Step 12.5: Template pointer persisted**

From 12.2, confirm the template pointer is on the user's new flow:

```
/Users/brycedeneen/dev/langflow/.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://postgres:mysecretpassword@localhost:5432/langflow') as conn, conn.cursor() as cur:
    cur.execute(\"SELECT name, built_with_assist, based_on_template_flow_id::text FROM flow ORDER BY updated_at DESC LIMIT 3\")
    for r in cur.fetchall(): print(r)
"
```

Expected: the most recent flow shows `built_with_assist=True` and a non-null `based_on_template_flow_id` pointing at the chosen template.

- [ ] **Step 12.6: Blank-flow template matching**

On a Blank-flow fullscreen session, after the generic greeting, type "I want a Slack notifier for new hires." The assistant:
- Responds conversationally,
- Calls `apply_template` (the flow canvas populates with the template's nodes/edges),
- Continues the conversation in template-aware mode — subsequent messages should reference the template's `agent_usage_notes` if authored.

Confirm via psycopg that the previously-null `based_on_template_flow_id` on the Blank flow is now set.

- [ ] **Step 12.7: Opinionated narration**

In any template-driven conversation, ask "add another component to do X" (pick something not in the template). The assistant:
- Picks a specific component,
- Narrates what it added ("I've added a Discord node — what channel should I use?"),
- Does NOT ask "which component would you like?".

- [ ] **Step 12.8: Ready-to-test prompt**

Complete a flow (answer all the assistant's config questions). At some point the assistant says "Your flow is ready — click the Test button" (or equivalent). The Test button in the fullscreen header is the natural next click. **Do not** expect the assistant to flip modes automatically.

- [ ] **Step 12.9: `ON DELETE SET NULL` behavior**

Create a user flow via "Build with ADP Assist" from some template (confirm pointer is set per 12.5). In the DB (or admin UI), delete the template flow. Re-query:

```
/Users/brycedeneen/dev/langflow/.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://postgres:mysecretpassword@localhost:5432/langflow') as conn, conn.cursor() as cur:
    cur.execute(\"SELECT name, based_on_template_flow_id FROM flow WHERE name = %s\", ('<your user flow name>',))
    print(cur.fetchone())
"
```

Expected: user flow still exists; `based_on_template_flow_id` is now `None`.

- [ ] **Step 12.10: Report results**

Report which steps passed/failed + any surprises. Do not mark the plan complete until every step passes.

---

## Acceptance Criteria

1. All backend pytest tests pass:
   `test_flow_based_on_template.py`, `test_flow_template_context.py`, `test_greeting_guidelines_in_prompt.py`, `test_id_regen.py`, `test_apply_template.py`, `test_assistant_greet_endpoint.py` — 18 assertions total.
2. All frontend Jest tests pass: `use-greet-conversation.test.ts`, `greet-on-fullscreen.test.tsx`, plus no regressions on the existing Plan 3 tests (shell-switch, action-bar, adp-assist-button, assistantStore-layout, metadata-edit-form, components-tab).
3. `npx tsc --noEmit` is clean for all new/modified frontend files.
4. Alembic migration applies + rolls back cleanly; Postgres has the new `based_on_template_flow_id` column with correct FK.
5. Manual verification (Task 12) passes every step.
6. User WIP files (`flows.py`, `webhookFieldComponent/index.tsx`, `mcp/util.py`) remain unstaged.

## Out of Scope (hard boundaries)

- Test mode pipeline view, per-component test status, component_test SSE — Plan 5.
- Component-level credential guidance triggered by test failures — Plan 5 (this plan only seeds the prompt guidelines).
- Proactive greeting in panel mode — gated to fullscreen.
- Template application to a non-empty flow — tool refuses.
- Assistant-driven mode switches — the LLM asks the user to click Test; it doesn't flip layoutMode.
- Template management UI, versioning, field-blanking — Plan 7 candidate.
- "Request Professional Services" proposals — Plan 8 candidate.
- MCP ext-apps rich UI widgets — Plan 6 candidate.

## Open Items Flagged During Implementation

- **`AssistantService.generate_once`** may not exist yet on the service class. If so, add it as a small helper (see Task 9.3) that either uses a provider `generate` method or sinks the existing `stream_with_tools` and concatenates token deltas.
- **Settings-loader symbol for the greet endpoint's 400-path test.** Inspect `/messages`'s settings-unconfigured branch to find the exact helper/variable name; adjust the monkeypatch target accordingly. The assertion (`status 400` when settings missing) stays the same.
- **Handle renaming in edge IDs.** The backend `regenerate_flow_ids` helper (Task 7) handles the common case where handle strings begin with the old node id. Exotic handle shapes (older exports, user-edited data) may slip through — if the manual check in Task 12.6 produces orphaned edges, extend the helper with a per-handle test.
