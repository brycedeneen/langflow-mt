# ADP Assist Layout Modes + Template Modal + Flow List Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit discipline:** The project owner batches commits to the **end** of the plan. Every task ends with "Pause for commit" meaning **stage with `git add`, do not run `git commit`**. At plan completion, the controller proposes one batched commit message for user approval.

**Goal:** Ship the "enter points" and "shell" for the full ADP Assist experience — three new layout modes for the assistant (panel / fullscreen / test), a redesigned template modal with radio selection and an "ADP Assist" launcher, and an ADP Assist button on every flow card — plus the small backend field (`built_with_assist`) and frontend plumbing to support them. This plan deliberately does **not** implement the conversational template-building (Plan 4) or the pipeline view (Plan 5); both plug into the layout states defined here.

**Architecture:** `assistantStore` gains a `layoutMode: "panel" | "fullscreen" | "test"` state plus `selectedTestComponent: string | null`. `AssistantPanel/index.tsx` branches on the mode to render either the existing 400px side panel, a new full-viewport overlay, or a placeholder test shell. The templates modal keeps a selected-template id in local state, removes its footer "Blank Flow" button in favor of a first-in-grid "Blank Flow" card, and grows an action bar with Cancel / Start Building / Build with ADP Assist buttons. The flow list's `ListComponent` grows an "ADP Assist" icon beside the existing dropdown trigger that opens the flow in fullscreen. `Flow.built_with_assist` (nullable bool) lands on the DB model so flows created through the ADP Assist path can be rendered more prominently in the list.

**Tech Stack:** React 18, Zustand, @tanstack/react-query, shadcn/ui (Radix), Tailwind, TypeScript; SQLModel + Alembic + FastAPI + Pydantic v2; pytest + Jest.

---

## Spec reference

Authoritative design: `docs/superpowers/specs/2026-04-18-adp-assist-flow-builder-design.md` §1, §2, §8. The template-context-seeding behavior of "Build with ADP Assist" (§2's entry → §4's conversational flow) is **out of scope for this plan**; Plan 4 will wire the template context into the assistant's first message. For now, "Build with ADP Assist" creates the flow, navigates to the flow page, and opens the assistant in fullscreen mode with no template context — identical to what a user would get by clicking the new full-screen toggle on an existing flow.

---

## File Structure

### New files — backend

- `src/backend/base/langflow/alembic/versions/<rev>_add_built_with_assist_to_flow.py`

### Modified files — backend

- `src/backend/base/langflow/services/database/models/flow/model.py` — add `built_with_assist: bool | None` column to `FlowBase`
- `src/backend/tests/unit/services/database/models/test_flow_model_built_with_assist.py` — new unit test covering default + persistence

### New files — frontend

- `src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx` — fullscreen-mode shell (ADP Assist branding header, Test/View Canvas/Close buttons, message list + composer inside)
- `src/frontend/src/modals/AssistantPanel/test-shell.tsx` — split view: placeholder for pipeline view on left + chat on right (Plan 5 replaces the placeholder)
- `src/frontend/src/modals/AssistantPanel/mode-toggle-button.tsx` — small icon button in panel header that switches `layoutMode` from `"panel"` to `"fullscreen"`
- `src/frontend/src/modals/templatesModal/components/BlankFlowCardComponent/index.tsx` — first-in-grid selectable card representing "Blank Flow"
- `src/frontend/src/modals/templatesModal/components/actionBar.tsx` — footer action bar (Cancel / Start Building / Build with ADP Assist buttons)
- `src/frontend/src/pages/MainPage/components/list/adp-assist-button.tsx` — small round icon button rendered on each flow card
- `src/frontend/src/utils/assist-entry.ts` — shared helper `openFlowInFullscreenAssist(flowId, navigate)` used by both the templates modal and the flow-list button

### Modified files — frontend

- `src/frontend/src/stores/assistantStore.ts` — add `layoutMode`, `selectedTestComponent`, `setLayoutMode`, `setSelectedTestComponent`
- `src/frontend/src/modals/AssistantPanel/index.tsx` — branch on `layoutMode` to render panel/fullscreen/test shell
- `src/frontend/src/modals/AssistantPanel/components/panel-header.tsx` — render the new mode-toggle button beside the existing close button
- `src/frontend/src/modals/templatesModal/index.tsx` — add `selectedTemplate` state, drop footer Blank Flow button, render the new `ActionBar`, prepend a `BlankFlowCardComponent` to the grid
- `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx` — render selected-state visual (highlighted border + radio dot) when `selectedTemplate === this.id`
- `src/frontend/src/modals/templatesModal/components/GetStartedComponent/index.tsx` — pass `selectedTemplate` / `onSelectTemplate` through to cards; no longer triggers immediate flow creation on click
- `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx` — same pass-through
- `src/frontend/src/pages/MainPage/components/list/index.tsx` — render `AdpAssistButton` next to the ellipsis menu
- `src/frontend/src/pages/FlowPage/index.tsx` — render `AssistantPanel` in fullscreen overlay position when `layoutMode !== "panel"`
- `src/frontend/src/types/flow/index.ts` — add `built_with_assist?: boolean` to `FlowType`

### Jest tests — new

- `src/frontend/src/stores/__tests__/assistantStore-layout.test.ts` — layout-mode setter round trips
- `src/frontend/src/modals/AssistantPanel/__tests__/shell-switch.test.tsx` — AssistantPanel renders the correct shell per `layoutMode`
- `src/frontend/src/modals/templatesModal/__tests__/action-bar.test.tsx` — action-bar disabled state + click handlers
- `src/frontend/src/pages/MainPage/components/list/__tests__/adp-assist-button.test.tsx` — button click calls `openFlowInFullscreenAssist`

---

## Design notes

### Layout state

```ts
type LayoutMode = "panel" | "fullscreen" | "test";
```

- `panel` — existing 400px right-sidebar. Default. What users see today.
- `fullscreen` — overlay covers the entire flow canvas. Header bar: "ADP Assist" brand text, Test button, View Canvas toggle, Close button.
- `test` — split view within fullscreen: pipeline placeholder on left, chat on right. Only reachable from `fullscreen` via the Test button. "Back to chat" button returns to `fullscreen`.

Close button from any non-panel mode returns to `panel` AND closes the panel (`panelOpen = false, layoutMode = "panel"`). View Canvas button from any non-panel mode just minimizes: `layoutMode = "panel"` (panel stays open). This matches the spec.

### Entry points (matrix)

| Entry point | panelOpen | layoutMode |
|---|---|---|
| Existing toolbar "Assistant" button | toggled | (unchanged — existing default) |
| Template modal "Start Building" | false | "panel" |
| Template modal "Build with ADP Assist" | true | "fullscreen" |
| Flow card ADP Assist icon | true | "fullscreen" |
| New fullscreen toggle in panel header | true | "fullscreen" |

### `built_with_assist` semantics

Set to `true` **only** when the flow was created through the "Build with ADP Assist" template-modal entry. Other entry points (flow card icon, fullscreen toggle on an existing flow) do not flip it — existing flows keep their flag. The flag is surfaced on `FlowType` so the flow-card renderer can lift the ADP Assist icon more prominently. Persistence: on flow create only; no automatic flip from `false` to `true` later.

---

## Task 1: Backend — `built_with_assist` column on `FlowBase`

**Files:**
- Modify: `src/backend/base/langflow/services/database/models/flow/model.py`
- Test: `src/backend/tests/unit/services/database/models/test_flow_model_built_with_assist.py`

- [x] **Step 1.1: Write the failing test**

Create `src/backend/tests/unit/services/database/models/test_flow_model_built_with_assist.py`:

```python
"""Unit tests for the built_with_assist flag on Flow."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from langflow.services.database.models import Flow, User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


def _user(s: Session) -> User:
    u = User(username="u", password="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def test_built_with_assist_defaults_to_false(session):
    user = _user(session)
    flow = Flow(name="F", user_id=user.id)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    assert flow.built_with_assist is False


def test_built_with_assist_is_persistable_and_readable(session):
    user = _user(session)
    flow = Flow(name="F", user_id=user.id, built_with_assist=True)
    session.add(flow)
    session.commit()
    session.refresh(flow)
    assert flow.built_with_assist is True

    loaded = session.exec(select(Flow).where(Flow.id == flow.id)).one()
    assert loaded.built_with_assist is True
```

- [x] **Step 1.2: Run to verify failure**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_flow_model_built_with_assist.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'built_with_assist'` (or `AttributeError` on the first test).

- [x] **Step 1.3: Add the column**

Edit `src/backend/base/langflow/services/database/models/flow/model.py`. In the `FlowBase` class (near the existing `webhook` field around line where `webhook: bool | None` is declared), add:

```python
    built_with_assist: bool | None = Field(
        default=False,
        nullable=True,
        description="Set to True when the flow was created via the ADP Assist template-modal entry point",
    )
```

- [x] **Step 1.4: Verify tests pass**

Run: `uv run pytest src/backend/tests/unit/services/database/models/test_flow_model_built_with_assist.py -v`
Expected: 2 PASS.

- [x] **Step 1.5: Pause for commit**

Stage with `git add`. Do not commit.

---

## Task 2: Alembic migration for `built_with_assist`

**Files:**
- Create: `src/backend/base/langflow/alembic/versions/<rev>_add_built_with_assist_to_flow.py`

- [x] **Step 2.1: Verify current head**

Run: `cd src/backend/base/langflow && uv run alembic heads`
Expected: one head (`460a5ee548b6` — the metadata infrastructure migration). If there are multiple heads, STOP and escalate — the chain is branched.

- [x] **Step 2.2: Generate the revision**

Run from repo root:

```
cd src/backend/base/langflow && uv run alembic revision --autogenerate -m "add built_with_assist to flow"
```

Open the generated file. Verify:
- `down_revision: Union[str, None] = '460a5ee548b6'`
- `upgrade()` contains `op.add_column('flow', sa.Column('built_with_assist', sa.Boolean(), nullable=True))` (possibly wrapped in `batch_alter_table`)
- `downgrade()` drops the same column

If autogenerate produced something unexpected (e.g., also tries to alter unrelated columns), trim to just the `built_with_assist` add/drop.

- [x] **Step 2.3: Hand-write fallback (only if autogen was empty)**

Replace the upgrade/downgrade with:

```python
def upgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("built_with_assist", sa.Boolean(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_column("built_with_assist")
```

- [x] **Step 2.4: Apply the migration**

Run: `make alembic-upgrade`
Expected: one `ALTER TABLE flow ADD COLUMN built_with_assist` and "Target revision: <new hash> (head)".

- [x] **Step 2.5: Verify column**

Run:

```
/Users/brycedeneen/dev/langflow/.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://postgres:mysecretpassword@localhost:5432/langflow') as conn, conn.cursor() as cur:
    cur.execute(\"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='flow' AND column_name='built_with_assist'\")
    print(cur.fetchall())
"
```

Expected: `[('built_with_assist', 'boolean', 'YES')]`.

- [x] **Step 2.6: Roundtrip**

Run: `make alembic-downgrade` (column dropped) → `make alembic-upgrade` (column recreated). Both should succeed.

- [x] **Step 2.7: Pause for commit**

Stage with `git add`. Do not commit.

---

## Task 3: Frontend `FlowType` — add `built_with_assist`

**Files:**
- Modify: `src/frontend/src/types/flow/index.ts`

- [x] **Step 3.1: Edit the TS type**

Open `src/frontend/src/types/flow/index.ts`. Find the `FlowType` type alias. Add `built_with_assist?: boolean;` after `webhook?: boolean;`:

```typescript
  webhook?: boolean;
  built_with_assist?: boolean;
```

- [x] **Step 3.2: Verify tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep -i "built_with_assist" | head -5`
Expected: no errors mentioning the new field.

- [x] **Step 3.3: Pause for commit**

Stage with `git add`.

---

## Task 4: `assistantStore` — layout-mode state

**Files:**
- Modify: `src/frontend/src/stores/assistantStore.ts`
- Test: `src/frontend/src/stores/__tests__/assistantStore-layout.test.ts`

- [x] **Step 4.1: Write the failing test**

Create `src/frontend/src/stores/__tests__/assistantStore-layout.test.ts`:

```typescript
import useAssistantStore from "@/stores/assistantStore";

describe("assistantStore layout mode", () => {
  beforeEach(() => {
    // Reset to defaults between tests
    useAssistantStore.setState({
      layoutMode: "panel",
      selectedTestComponent: null,
      panelOpen: false,
    });
  });

  it("defaults layoutMode to 'panel'", () => {
    expect(useAssistantStore.getState().layoutMode).toBe("panel");
  });

  it("defaults selectedTestComponent to null", () => {
    expect(useAssistantStore.getState().selectedTestComponent).toBeNull();
  });

  it("setLayoutMode updates the state", () => {
    useAssistantStore.getState().setLayoutMode("fullscreen");
    expect(useAssistantStore.getState().layoutMode).toBe("fullscreen");
    useAssistantStore.getState().setLayoutMode("test");
    expect(useAssistantStore.getState().layoutMode).toBe("test");
    useAssistantStore.getState().setLayoutMode("panel");
    expect(useAssistantStore.getState().layoutMode).toBe("panel");
  });

  it("setSelectedTestComponent updates the state", () => {
    useAssistantStore.getState().setSelectedTestComponent("Webhook-abc");
    expect(useAssistantStore.getState().selectedTestComponent).toBe("Webhook-abc");
    useAssistantStore.getState().setSelectedTestComponent(null);
    expect(useAssistantStore.getState().selectedTestComponent).toBeNull();
  });
});
```

- [x] **Step 4.2: Run to verify failure**

Run: `cd src/frontend && npx jest assistantStore-layout`
Expected: FAIL on the first `toBe("panel")` assertion with `undefined`.

- [x] **Step 4.3: Extend the store**

Edit `src/frontend/src/stores/assistantStore.ts`. Find the `AssistantStoreState` type and add:

```typescript
  layoutMode: "panel" | "fullscreen" | "test";
  setLayoutMode: (mode: "panel" | "fullscreen" | "test") => void;
  selectedTestComponent: string | null;
  setSelectedTestComponent: (id: string | null) => void;
```

In the store body (`create<AssistantStoreState>((set, get) => ({ ... }))`), add defaults and setters alongside the existing `panelOpen`:

```typescript
  layoutMode: "panel",
  setLayoutMode: (mode) => set({ layoutMode: mode }),
  selectedTestComponent: null,
  setSelectedTestComponent: (id) => set({ selectedTestComponent: id }),
```

- [x] **Step 4.4: Verify tests pass**

Run: `cd src/frontend && npx jest assistantStore-layout`
Expected: 4 tests PASS.

- [x] **Step 4.5: Pause for commit**

Stage.

---

## Task 5: `panel-header.tsx` — fullscreen toggle button

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/mode-toggle-button.tsx`
- Modify: `src/frontend/src/modals/AssistantPanel/components/panel-header.tsx`

- [x] **Step 5.1: Create the toggle button**

Create `src/frontend/src/modals/AssistantPanel/mode-toggle-button.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useAssistantStore from "@/stores/assistantStore";

/** Toggle between panel and fullscreen layout modes. Only rendered in panel mode. */
export function ModeToggleButton() {
  const layoutMode = useAssistantStore((s) => s.layoutMode);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);

  if (layoutMode !== "panel") return null;

  return (
    <ShadTooltip content="Enter full-screen ADP Assist">
      <button
        aria-label="Enter full-screen ADP Assist"
        onClick={() => setLayoutMode("fullscreen")}
        className="inline-flex h-7 w-7 items-center justify-center rounded hover:bg-muted"
      >
        <ForwardedIconComponent name="Maximize2" className="h-4 w-4" />
      </button>
    </ShadTooltip>
  );
}
```

- [x] **Step 5.2: Render the button in the panel header**

Edit `src/frontend/src/modals/AssistantPanel/components/panel-header.tsx`. Add the import:

```tsx
import { ModeToggleButton } from "../mode-toggle-button";
```

Render `<ModeToggleButton />` just before the existing Close button. (Look for the existing close button JSX — it's in the header's right-side button cluster. Insert the new button before it so the order is Clear → Enter Fullscreen → Close.)

- [x] **Step 5.3: Verify tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep -E "mode-toggle|panel-header" | head -10`
Expected: no errors in the two files you touched.

- [x] **Step 5.4: Pause for commit**

---

## Task 6: Fullscreen shell

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx`

- [x] **Step 6.1: Create the component**

Create `src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useAssistantStore from "@/stores/assistantStore";
import { Composer } from "./components/composer";
import { MessageList } from "./components/message-list";
import { SettingsRequired } from "./components/settings-required";

type Props = {
  flowId: string;
  onSend: (text: string) => void;
};

/** Full-viewport overlay shell hosting the ADP Assist chat.
 *
 * Header: branding + Test button + View Canvas + Close.
 * Body: message list + composer.
 */
export function FullscreenShell({ flowId, onSend }: Props) {
  const messages = useAssistantStore((s) => s.messages);
  const settingsConfigured = useAssistantStore((s) => s.settingsConfigured);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);
  const setPanelOpen = useAssistantStore((s) => s.setPanelOpen);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <header className="flex h-14 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="Bot" className="h-5 w-5" />
          <span className="text-lg font-semibold">ADP Assist</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("test")}
            data-testid="adp-assist-test-btn"
          >
            <ForwardedIconComponent name="FlaskConical" className="mr-1 h-4 w-4" />
            Test
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("panel")}
            data-testid="adp-assist-view-canvas-btn"
          >
            <ForwardedIconComponent name="PanelLeft" className="mr-1 h-4 w-4" />
            View Canvas
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setLayoutMode("panel");
              setPanelOpen(false);
            }}
            aria-label="Close ADP Assist"
            data-testid="adp-assist-close-btn"
          >
            <ForwardedIconComponent name="X" className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex flex-1 flex-col overflow-hidden">
        {!settingsConfigured ? (
          <SettingsRequired />
        ) : (
          <>
            <MessageList messages={messages} />
            <Composer onSend={onSend} />
          </>
        )}
      </div>
    </div>
  );
}
```

**Note:** If `Composer`, `MessageList`, or `SettingsRequired` are default exports in the existing `components/*.tsx` files rather than named exports, use default imports (e.g., `import Composer from "./components/composer"`). Look at how `AssistantPanel/index.tsx` imports them today and match.

- [x] **Step 6.2: Verify tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep fullscreen-shell | head -5`
Expected: no errors specific to this file. Fix any import shape mismatches.

- [x] **Step 6.3: Pause for commit**

---

## Task 7: Test shell (placeholder for pipeline view)

**Files:**
- Create: `src/frontend/src/modals/AssistantPanel/test-shell.tsx`

- [x] **Step 7.1: Create the component**

Create `src/frontend/src/modals/AssistantPanel/test-shell.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useAssistantStore from "@/stores/assistantStore";
import { Composer } from "./components/composer";
import { MessageList } from "./components/message-list";

type Props = {
  flowId: string;
  onSend: (text: string) => void;
};

/** Split-view test shell: pipeline placeholder on the left, chat on the right.
 *
 * The pipeline placeholder will be replaced by <FlowPipelineView /> in Plan 5.
 * This shell's job is to establish the layout, header controls, and wire the
 * "Back to chat" / "View Canvas" / "Close" buttons so the rest of the
 * experience is navigable during Plan 3 testing.
 */
export function TestShell({ flowId, onSend }: Props) {
  const messages = useAssistantStore((s) => s.messages);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);
  const setPanelOpen = useAssistantStore((s) => s.setPanelOpen);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <header className="flex h-14 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="Bot" className="h-5 w-5" />
          <span className="text-lg font-semibold">ADP Assist — Test</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("fullscreen")}
            data-testid="adp-assist-back-to-chat-btn"
          >
            <ForwardedIconComponent name="ArrowLeft" className="mr-1 h-4 w-4" />
            Back to chat
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("panel")}
            data-testid="adp-assist-view-canvas-btn"
          >
            <ForwardedIconComponent name="PanelLeft" className="mr-1 h-4 w-4" />
            View Canvas
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setLayoutMode("panel");
              setPanelOpen(false);
            }}
            aria-label="Close ADP Assist"
            data-testid="adp-assist-close-btn"
          >
            <ForwardedIconComponent name="X" className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex w-1/2 flex-col items-center justify-center border-r text-muted-foreground">
          <ForwardedIconComponent
            name="GitBranch"
            className="mb-2 h-8 w-8 opacity-50"
          />
          <div className="text-sm">
            Pipeline view will appear here (Plan 5).
          </div>
        </div>
        <div className="flex w-1/2 flex-col">
          <MessageList messages={messages} />
          <Composer onSend={onSend} />
        </div>
      </div>
    </div>
  );
}
```

- [x] **Step 7.2: Verify tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep test-shell | head -5`
Expected: clean.

- [x] **Step 7.3: Pause for commit**

---

## Task 8: `AssistantPanel/index.tsx` — branch on `layoutMode`

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/index.tsx`
- Test: `src/frontend/src/modals/AssistantPanel/__tests__/shell-switch.test.tsx`

- [x] **Step 8.1: Write the failing test**

Create `src/frontend/src/modals/AssistantPanel/__tests__/shell-switch.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import AssistantPanel from "../index";
import useAssistantStore from "@/stores/assistantStore";

// Mock the hooks that do actual work
jest.mock("../hooks/use-assistant-conversation", () => ({
  __esModule: true,
  useAssistantConversation: () => ({ stale: false }),
}));
jest.mock("../hooks/use-assistant-stream", () => ({
  __esModule: true,
  useAssistantStream: () => ({ sendMessage: jest.fn() }),
}));
// Mock child components so tests don't rely on their internals
jest.mock("../components/composer", () => ({
  __esModule: true,
  Composer: () => <div data-testid="composer" />,
}));
jest.mock("../components/message-list", () => ({
  __esModule: true,
  MessageList: () => <div data-testid="message-list" />,
}));
jest.mock("../components/settings-required", () => ({
  __esModule: true,
  SettingsRequired: () => <div data-testid="settings-required" />,
}));

describe("AssistantPanel shell switch", () => {
  beforeEach(() => {
    useAssistantStore.setState({
      panelOpen: true,
      layoutMode: "panel",
      settingsConfigured: true,
      messages: [],
    });
  });

  it("renders the panel shell when layoutMode is 'panel'", () => {
    useAssistantStore.setState({ layoutMode: "panel" });
    render(<AssistantPanel flowId="flow-1" />);
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
    // Fullscreen-specific close button should NOT be present
    expect(screen.queryByTestId("adp-assist-close-btn")).toBeNull();
  });

  it("renders the fullscreen shell when layoutMode is 'fullscreen'", () => {
    useAssistantStore.setState({ layoutMode: "fullscreen" });
    render(<AssistantPanel flowId="flow-1" />);
    expect(screen.getByTestId("adp-assist-close-btn")).toBeInTheDocument();
    expect(screen.getByTestId("adp-assist-test-btn")).toBeInTheDocument();
  });

  it("renders the test shell when layoutMode is 'test'", () => {
    useAssistantStore.setState({ layoutMode: "test" });
    render(<AssistantPanel flowId="flow-1" />);
    expect(screen.getByTestId("adp-assist-back-to-chat-btn")).toBeInTheDocument();
  });

  it("renders nothing when panelOpen is false", () => {
    useAssistantStore.setState({ panelOpen: false });
    const { container } = render(<AssistantPanel flowId="flow-1" />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [x] **Step 8.2: Run to verify failure**

Run: `cd src/frontend && npx jest shell-switch`
Expected: tests that assert on `adp-assist-*-btn` fail because `AssistantPanel` always renders the panel shell today.

- [x] **Step 8.3: Refactor `AssistantPanel/index.tsx`**

Edit `src/frontend/src/modals/AssistantPanel/index.tsx`. Add the two new imports alongside the existing ones:

```tsx
import { FullscreenShell } from "./fullscreen-shell";
import { TestShell } from "./test-shell";
```

In the component body, read `layoutMode`:

```tsx
const layoutMode = useAssistantStore((s) => s.layoutMode);
```

Keep the existing early return `if (!panelOpen) return null;`.

After the early return, branch:

```tsx
if (layoutMode === "fullscreen") {
  return <FullscreenShell flowId={flowId} onSend={sendMessage} />;
}
if (layoutMode === "test") {
  return <TestShell flowId={flowId} onSend={sendMessage} />;
}
// fall through to existing panel shell below
```

Leave the existing panel-shell JSX (the 400px `<div>` with `PanelHeader`, `MessageList`, `Composer`) unchanged — it now only renders when `layoutMode === "panel"`.

- [x] **Step 8.4: Run tests**

Run: `cd src/frontend && npx jest shell-switch`
Expected: 4 PASS.

- [x] **Step 8.5: Pause for commit**

---

## Task 9: `FlowPage/index.tsx` — hide canvas behind fullscreen overlay

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/index.tsx`

- [x] **Step 9.1: Hide the canvas when fullscreen**

Edit `src/frontend/src/pages/FlowPage/index.tsx`. Near where `AssistantPanel` is rendered at the bottom, and where the canvas (`<FlowPageMainContent>`) is rendered, read `layoutMode` from the store:

```tsx
import useAssistantStore from "@/stores/assistantStore";
// ...
const layoutMode = useAssistantStore((s) => s.layoutMode);
const panelOpen = useAssistantStore((s) => s.panelOpen);
const isOverlay = panelOpen && layoutMode !== "panel";
```

Wrap or conditionally hide the canvas when `isOverlay` is true — the overlay shell uses `fixed inset-0 z-50` so technically the canvas underneath can still be hit for events. Add `aria-hidden` + `pointer-events-none` to the canvas container when the overlay is active. Find the existing `<main>` that wraps `<FlowPageMainContent>` and change its className dynamically:

```tsx
<main
  className={cn(
    /* existing classes */,
    isOverlay && "pointer-events-none",
  )}
  aria-hidden={isOverlay}
>
```

This is the minimum — the overlay covers the canvas visually via `z-50`, and we just ensure the canvas can't receive events when hidden.

- [x] **Step 9.2: Verify tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep "pages/FlowPage/index" | head -5`
Expected: no errors.

- [x] **Step 9.3: Pause for commit**

---

## Task 10: Shared entry-point helper

**Files:**
- Create: `src/frontend/src/utils/assist-entry.ts`

- [x] **Step 10.1: Create the helper**

Create `src/frontend/src/utils/assist-entry.ts`:

```typescript
import type { NavigateFunction } from "react-router-dom";
import useAssistantStore from "@/stores/assistantStore";

/** Open a flow in fullscreen ADP Assist mode.
 *
 * Used by:
 *  - Template modal "Build with ADP Assist" button (new flow)
 *  - Flow list ADP Assist icon (existing flow)
 *  - (future) any "open in assistant" entry
 *
 * Navigates to the flow page and sets layoutMode before the page mounts so the
 * assistant opens in fullscreen without a flash of the panel state.
 */
export function openFlowInFullscreenAssist(
  flowId: string,
  navigate: NavigateFunction,
): void {
  const store = useAssistantStore.getState();
  store.setPanelOpen(true);
  store.setLayoutMode("fullscreen");
  navigate(`/flow/${flowId}`);
}
```

- [x] **Step 10.2: Pause for commit**

---

## Task 11: Blank Flow card

**Files:**
- Create: `src/frontend/src/modals/templatesModal/components/BlankFlowCardComponent/index.tsx`

- [x] **Step 11.1: Create the component**

Create `src/frontend/src/modals/templatesModal/components/BlankFlowCardComponent/index.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

type Props = {
  selected: boolean;
  onSelect: () => void;
};

/** First-in-grid "Blank Flow" card — selectable like any other template. */
export function BlankFlowCardComponent({ selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid="blank-flow-card"
      className={cn(
        "group relative flex h-full min-h-[170px] w-full flex-col items-start justify-between rounded-lg border-2 bg-background p-4 text-left transition-colors hover:bg-muted",
        selected ? "border-primary" : "border-border",
      )}
    >
      <div
        className={cn(
          "absolute right-3 top-3 h-4 w-4 rounded-full border-2",
          selected ? "border-primary bg-primary" : "border-muted-foreground",
        )}
        aria-hidden
      />
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-muted">
        <ForwardedIconComponent name="Plus" className="h-5 w-5" />
      </div>
      <div className="flex w-full flex-col gap-1">
        <div className="text-sm font-semibold">Blank Flow</div>
        <div className="text-xs text-muted-foreground">
          Start from scratch with an empty canvas.
        </div>
      </div>
    </button>
  );
}
```

- [x] **Step 11.2: Pause for commit**

---

## Task 12: Templates modal action bar

**Files:**
- Create: `src/frontend/src/modals/templatesModal/components/actionBar.tsx`
- Test: `src/frontend/src/modals/templatesModal/__tests__/action-bar.test.tsx`

- [x] **Step 12.1: Write the failing test**

Create `src/frontend/src/modals/templatesModal/__tests__/action-bar.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ActionBar } from "../components/actionBar";

describe("ActionBar", () => {
  it("disables Start Building and Build with ADP Assist when nothing selected", () => {
    render(
      <ActionBar
        selectedTemplate={null}
        onCancel={jest.fn()}
        onStartBuilding={jest.fn()}
        onBuildWithAssist={jest.fn()}
      />,
    );
    const startBuilding = screen.getByRole("button", { name: /start building/i });
    const buildWithAssist = screen.getByRole("button", {
      name: /build with adp assist/i,
    });
    expect(startBuilding).toBeDisabled();
    expect(buildWithAssist).toBeDisabled();
  });

  it("enables both action buttons when a template is selected", () => {
    render(
      <ActionBar
        selectedTemplate="blank"
        onCancel={jest.fn()}
        onStartBuilding={jest.fn()}
        onBuildWithAssist={jest.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /start building/i }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: /build with adp assist/i }),
    ).toBeEnabled();
  });

  it("invokes the right handler on click", () => {
    const onCancel = jest.fn();
    const onStart = jest.fn();
    const onAssist = jest.fn();
    render(
      <ActionBar
        selectedTemplate="some-flow-id"
        onCancel={onCancel}
        onStartBuilding={onStart}
        onBuildWithAssist={onAssist}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    fireEvent.click(screen.getByRole("button", { name: /start building/i }));
    fireEvent.click(screen.getByRole("button", { name: /build with adp assist/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onAssist).toHaveBeenCalledTimes(1);
  });
});
```

- [x] **Step 12.2: Run to verify failure**

Run: `cd src/frontend && npx jest action-bar.test`
Expected: module not found.

- [x] **Step 12.3: Create the component**

Create `src/frontend/src/modals/templatesModal/components/actionBar.tsx`:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type Props = {
  /** Id of the selected template, "blank" for the blank flow card, or null. */
  selectedTemplate: string | null;
  onCancel: () => void;
  onStartBuilding: () => void;
  onBuildWithAssist: () => void;
};

export function ActionBar({
  selectedTemplate,
  onCancel,
  onStartBuilding,
  onBuildWithAssist,
}: Props) {
  const disabled = selectedTemplate === null;
  return (
    <div className="flex w-full items-center justify-end gap-2 pb-4">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onCancel}
        data-testid="template-modal-cancel"
      >
        Cancel
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={disabled}
        onClick={onStartBuilding}
        data-testid="template-modal-start-building"
      >
        Start Building
      </Button>
      <Button
        type="button"
        size="sm"
        disabled={disabled}
        onClick={onBuildWithAssist}
        data-testid="template-modal-build-with-assist"
      >
        <ForwardedIconComponent name="Bot" className="mr-1 h-4 w-4" />
        Build with ADP Assist
      </Button>
    </div>
  );
}
```

- [x] **Step 12.4: Run tests**

Run: `cd src/frontend && npx jest action-bar.test`
Expected: 3 PASS.

- [x] **Step 12.5: Pause for commit**

---

## Task 13: Template card — selected visual state

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx`

- [x] **Step 13.1: Read the existing file**

Open `src/frontend/src/modals/templatesModal/components/TemplateCardComponent/index.tsx`. Identify the outer element (likely a `<Card>` or `<button>`).

- [x] **Step 13.2: Add `selected` + `onSelect` props**

Modify the component's props:

```tsx
type Props = /* existing props */ & {
  selected?: boolean;
  onSelect?: () => void;
};
```

Apply `selected` visually: add a 2px border (`border-primary`) to the outer element's className when `selected`, and render a small radio dot (reuse the pattern from `BlankFlowCardComponent`) in the top-right corner. Change the root element's `onClick` to call `onSelect?.()` **instead of** creating the flow immediately. The old "immediate create" behavior is replaced by the action-bar buttons.

The exact code depends on the existing component. Illustration of the minimum change:

```tsx
<div
  className={cn(
    "existing classes here",
    selected && "border-2 border-primary",
  )}
  onClick={onSelect}
>
  {selected ? (
    <div className="absolute right-3 top-3 h-4 w-4 rounded-full border-2 border-primary bg-primary" aria-hidden />
  ) : (
    <div className="absolute right-3 top-3 h-4 w-4 rounded-full border-2 border-muted-foreground" aria-hidden />
  )}
  {/* existing card content unchanged */}
</div>
```

Remove any direct `addFlow()` call from this file — the template creation now happens at the modal level via the action bar.

- [x] **Step 13.3: Pause for commit**

---

## Task 14: Templates modal — selected state + blank card + action bar

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/index.tsx`
- Modify: `src/frontend/src/modals/templatesModal/components/GetStartedComponent/index.tsx`
- Modify: `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx`

- [x] **Step 14.1: Add selection state in the modal**

Edit `src/frontend/src/modals/templatesModal/index.tsx`. Add state:

```tsx
import { useState } from "react";
// ...
const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
```

Pass `selectedTemplate` + `onSelectTemplate={setSelectedTemplate}` to both `GetStartedComponent` and `TemplateContentComponent` (same props). Also pass `selectedTemplate` to `BlankFlowCardComponent` inside `GetStartedComponent` (see 14.2).

- [x] **Step 14.2: Render the blank card in `GetStartedComponent`**

Edit `src/frontend/src/modals/templatesModal/components/GetStartedComponent/index.tsx`. At the top of the grid (before the existing template card loop), render:

```tsx
<BlankFlowCardComponent
  selected={selectedTemplate === "blank"}
  onSelect={() => onSelectTemplate("blank")}
/>
```

Thread the new `selectedTemplate` and `onSelectTemplate` props into the component's signature. Pass `selected={selectedTemplate === tmpl.id}` and `onSelect={() => onSelectTemplate(tmpl.id)}` to each existing `TemplateCardComponent` in the loop.

Add the import:

```tsx
import { BlankFlowCardComponent } from "../BlankFlowCardComponent";
```

- [x] **Step 14.3: Thread props through `TemplateContentComponent`**

Edit `src/frontend/src/modals/templatesModal/components/TemplateContentComponent/index.tsx` — add the same two props and forward `selected` / `onSelect` down to each `TemplateCardComponent`.

- [x] **Step 14.4: Replace the footer with the ActionBar**

Back in `src/frontend/src/modals/templatesModal/index.tsx`. Replace the existing `BaseModal.Footer` block (the one with the "Start from scratch" text + "Blank Flow" button) with:

```tsx
<BaseModal.Footer>
  <ActionBar
    selectedTemplate={selectedTemplate}
    onCancel={() => setOpen(false)}
    onStartBuilding={() => handleCreateFromSelection(false)}
    onBuildWithAssist={() => handleCreateFromSelection(true)}
  />
</BaseModal.Footer>
```

Add the import:

```tsx
import { ActionBar } from "./components/actionBar";
import { openFlowInFullscreenAssist } from "@/utils/assist-entry";
import { useNavigate } from "react-router-dom";
```

Add the creation handler inside the modal component:

```tsx
const navigate = useNavigate();

const handleCreateFromSelection = async (withAssist: boolean) => {
  if (!selectedTemplate) return;
  handleFlowCreating(true);
  try {
    // "blank" goes through addFlow(); a template id goes through addFlow({ from_template_id: ... })
    const id =
      selectedTemplate === "blank"
        ? await addFlow()
        : await addFlow({ from_template_id: selectedTemplate });
    track("New Flow Created", {
      template: selectedTemplate === "blank" ? "Blank Flow" : selectedTemplate,
      entry: withAssist ? "build-with-assist" : "start-building",
    });
    setOpen(false);
    if (withAssist) {
      openFlowInFullscreenAssist(id, navigate);
    } else {
      navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
    }
  } finally {
    handleFlowCreating(false);
  }
};
```

**Verify `addFlow` signature.** Read `src/frontend/src/pages/MainPage/components/modalsComponent/index.tsx` and/or wherever `addFlow` is defined — its real signature may differ from what's shown above (e.g., it may take a full `FlowType` instead of `{ from_template_id }`). If so, match the existing call sites — the goal is "create a flow whose data is seeded from the selected template." Pattern-match the pre-existing `handleFlowCreating` behavior from the old Blank Flow button and the old TemplateCard click handlers.

If the correct call requires a template object rather than an id, resolve the template at the modal level (store the `FlowType` object instead of a string id) — that's a small refactor of the selection state.

- [x] **Step 14.5: Smoke-test tsc**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | grep -E "templatesModal|ActionBar|BlankFlow" | head -10`
Expected: clean.

- [x] **Step 14.6: Pause for commit**

---

## Task 15: Backend — set `built_with_assist=true` when assist flag is passed on flow create

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (**WIP file**; see note below)
- Test: `src/backend/tests/unit/api/v1/test_flow_create_built_with_assist.py`

**Note on WIP file:** `flows.py` is a file the repo owner was actively editing when this plan was written (it has uncommitted changes on webhook auth). Be extra careful: read-before-edit, preserve all surrounding code, and never re-run `git add` on lines you didn't intend to stage. If there's any ambiguity, escalate.

- [x] **Step 15.1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_flow_create_built_with_assist.py`:

```python
"""The POST /flows endpoint must honor built_with_assist=True in the body."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models import Flow
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_create_flow_with_built_with_assist_true_persists_the_flag(
    client: AsyncClient, logged_in_headers
):
    response = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={
            "name": "Assist-Created Flow",
            "data": {"nodes": [], "edges": []},
            "built_with_assist": True,
        },
    )
    assert response.status_code in (200, 201)
    flow_id = response.json()["id"]

    async with session_scope() as session:
        row = (
            await session.exec(select(Flow).where(Flow.id == flow_id))
        ).one()
        assert row.built_with_assist is True


@pytest.mark.asyncio
async def test_create_flow_without_built_with_assist_defaults_to_false(
    client: AsyncClient, logged_in_headers
):
    response = await client.post(
        "/api/v1/flows/",
        headers=logged_in_headers,
        json={
            "name": "Plain Flow",
            "data": {"nodes": [], "edges": []},
        },
    )
    assert response.status_code in (200, 201)
    flow_id = response.json()["id"]

    async with session_scope() as session:
        row = (
            await session.exec(select(Flow).where(Flow.id == flow_id))
        ).one()
        assert row.built_with_assist is False
```

- [x] **Step 15.2: Run to verify (may already pass)**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_flow_create_built_with_assist.py -v`

Because `built_with_assist` is a field on `FlowBase` → `FlowCreate`, the existing flow-create endpoint may already honor it via Pydantic deserialization. If the tests already pass, skip Step 15.3 and go to 15.4.

- [x] **Step 15.3 (only if 15.2 failed): Wire the flag through**

Open `src/backend/base/langflow/api/v1/flows.py`. Find the `create_flow` handler. It takes a `FlowCreate`-shaped body. Confirm the handler constructs the DB row via `Flow(**flow_create.model_dump())` or similar — if so, nothing to add; the field rides along. If the handler copies fields explicitly (e.g., `Flow(name=flow_create.name, data=flow_create.data, ...)`), append `built_with_assist=getattr(flow_create, "built_with_assist", False)`.

**Do not restructure or refactor.** The minimum edit is adding one kwarg to the Flow constructor or one line to an explicit field-copy block.

- [x] **Step 15.4: Re-run the tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_flow_create_built_with_assist.py -v`
Expected: 2 PASS.

- [x] **Step 15.5: Pause for commit**

---

## Task 16: Templates modal — pass `built_with_assist` to backend on assist creation

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/index.tsx`

- [x] **Step 16.1: Extend the create call**

In the `handleCreateFromSelection` handler added in Task 14.4, pass `built_with_assist: withAssist` to `addFlow`. Example adjustments:

```tsx
const id =
  selectedTemplate === "blank"
    ? await addFlow({ built_with_assist: withAssist })
    : await addFlow({
        from_template_id: selectedTemplate,
        built_with_assist: withAssist,
      });
```

**Confirm `addFlow`'s actual signature accepts extra fields.** If `addFlow` is defined in a hook/util (e.g., `useAddFlow` or `flowsManagerStore.addFlow`), check its signature — it may accept a `Partial<FlowType>` which already includes optional fields. If it doesn't, the simplest path is to pass the flag into whatever partial-flow-object argument it accepts and let it pass through to the POST body.

If `addFlow` does NOT currently accept arbitrary overrides, extend it:

```tsx
// Example if addFlow((partial?: Partial<FlowType>) => Promise<string>) is the signature:
const id = await addFlow({
  name: selectedTemplate === "blank" ? undefined : /* template.name */,
  data: selectedTemplate === "blank" ? { nodes: [], edges: [] } : /* template.data */,
  built_with_assist: withAssist,
});
```

Leave pre-existing call sites of `addFlow` alone — only the new one in Task 14's handler should set `built_with_assist`.

- [x] **Step 16.2: Pause for commit**

---

## Task 17: Flow-list ADP Assist button

**Files:**
- Create: `src/frontend/src/pages/MainPage/components/list/adp-assist-button.tsx`
- Test: `src/frontend/src/pages/MainPage/components/list/__tests__/adp-assist-button.test.tsx`
- Modify: `src/frontend/src/pages/MainPage/components/list/index.tsx`

- [x] **Step 17.1: Write the failing test**

Create `src/frontend/src/pages/MainPage/components/list/__tests__/adp-assist-button.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { AdpAssistButton } from "../adp-assist-button";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockOpenFullscreen = jest.fn();
jest.mock("@/utils/assist-entry", () => ({
  openFlowInFullscreenAssist: (flowId: string, navigate: unknown) =>
    mockOpenFullscreen(flowId, navigate),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("AdpAssistButton", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockOpenFullscreen.mockReset();
  });

  it("opens the flow in fullscreen assist mode on click", () => {
    render(<AdpAssistButton flowId="abc-123" builtWithAssist={false} />);
    fireEvent.click(
      screen.getByRole("button", { name: /open in adp assist/i }),
    );
    expect(mockOpenFullscreen).toHaveBeenCalledTimes(1);
    expect(mockOpenFullscreen).toHaveBeenCalledWith("abc-123", mockNavigate);
  });

  it("applies the highlighted class when builtWithAssist is true", () => {
    const { container } = render(
      <AdpAssistButton flowId="abc-123" builtWithAssist={true} />,
    );
    const button = container.querySelector("button");
    expect(button?.className).toMatch(/text-primary/);
  });
});
```

- [x] **Step 17.2: Run to verify failure**

Run: `cd src/frontend && npx jest adp-assist-button.test`
Expected: module not found.

- [x] **Step 17.3: Create the component**

Create `src/frontend/src/pages/MainPage/components/list/adp-assist-button.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { openFlowInFullscreenAssist } from "@/utils/assist-entry";
import { cn } from "@/utils/utils";

type Props = {
  flowId: string;
  builtWithAssist: boolean;
};

export function AdpAssistButton({ flowId, builtWithAssist }: Props) {
  const navigate = useNavigate();
  return (
    <ShadTooltip content="Open in ADP Assist">
      <button
        type="button"
        aria-label="Open in ADP Assist"
        onClick={(e) => {
          e.stopPropagation();
          openFlowInFullscreenAssist(flowId, navigate);
        }}
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted",
          builtWithAssist && "text-primary",
        )}
      >
        <ForwardedIconComponent name="Bot" className="h-4 w-4" />
      </button>
    </ShadTooltip>
  );
}
```

- [x] **Step 17.4: Render the button in the flow card**

Edit `src/frontend/src/pages/MainPage/components/list/index.tsx`. Add the import:

```tsx
import { AdpAssistButton } from "./adp-assist-button";
```

In the actions cluster (the right-side `<div className="ml-5 flex items-center gap-2">` that contains the ellipsis `DropdownMenu`), render `<AdpAssistButton />` **before** the dropdown trigger:

```tsx
<div className="ml-5 flex items-center gap-2">
  <AdpAssistButton
    flowId={flowData.id}
    builtWithAssist={!!flowData.built_with_assist}
  />
  <DropdownMenu>
    {/* existing trigger + content */}
  </DropdownMenu>
</div>
```

- [x] **Step 17.5: Run tests**

Run: `cd src/frontend && npx jest adp-assist-button.test`
Expected: 2 PASS.

- [x] **Step 17.6: Pause for commit**

---

## Task 18: Manual verification

After all automated tests pass, walk through this checklist. **Do not commit in this task** — it is a validation gate.

- [x] **Step 18.1: Dev server boots**

Run `LFX_DEV=1 make run_cli`. Confirm: no import errors; migration auto-applies; `flow` table has the new `built_with_assist` column.

- [x] **Step 18.2: Panel mode unchanged (regression)**

On an existing flow, click the toolbar "Assistant" button. Confirm the 400px right-sidebar panel still opens as before. Send a test message — it should still route through the usual assistant codepath.

- [x] **Step 18.3: Enter fullscreen from the panel**

With the panel open, click the new Maximize icon in the header. Confirm:
- Overlay covers the entire viewport.
- "ADP Assist" title visible.
- Test, View Canvas, Close buttons all clickable.
- Composer + messages visible inside.

- [x] **Step 18.4: View Canvas returns to panel**

From fullscreen, click View Canvas. Confirm: overlay disappears, panel reappears at 400px.

- [x] **Step 18.5: Close button exits entirely**

From fullscreen, click Close. Confirm: overlay disappears AND the panel does not reappear. Re-open via toolbar button → panel mode again.

- [x] **Step 18.6: Test mode shows placeholder**

From fullscreen, click Test. Confirm: split view renders with "Pipeline view will appear here (Plan 5)." on the left + chat on the right. Back to chat button returns to fullscreen.

- [x] **Step 18.7: Templates modal selection**

Open the templates modal. Confirm:
- "Blank Flow" now appears as the first card in the grid (with the Plus icon).
- Clicking a card shows the selected border + radio dot.
- Only one card selected at a time.
- The footer shows three buttons: Cancel, Start Building, Build with ADP Assist.
- With nothing selected, the two right-side buttons are disabled.

- [x] **Step 18.8: Start Building path**

Select a template (any). Click Start Building. Confirm:
- Modal closes.
- You land on the new flow's canvas.
- Panel is closed (default behavior).

- [x] **Step 18.9: Build with ADP Assist path**

Create another flow: select a template, click Build with ADP Assist. Confirm:
- Modal closes.
- You land on the new flow's canvas.
- Fullscreen ADP Assist overlay is open.

- [x] **Step 18.10: `built_with_assist` persisted**

Run the SQL:

```
/Users/brycedeneen/dev/langflow/.venv/bin/python -c "
import psycopg
with psycopg.connect('postgresql://postgres:mysecretpassword@localhost:5432/langflow') as conn, conn.cursor() as cur:
    cur.execute(\"SELECT name, built_with_assist FROM flow ORDER BY updated_at DESC LIMIT 5\")
    for r in cur.fetchall():
        print(r)
"
```

Expected: the flow you created via Build with ADP Assist shows `True`; the one created via Start Building shows `False`.

- [x] **Step 18.11: Flow-list ADP Assist button**

Navigate to the main flow list. Confirm:
- Each flow card has a small Bot icon button next to the ellipsis menu.
- Clicking it opens the flow in fullscreen ADP Assist.
- The icon is highlighted (primary color) on the flow that has `built_with_assist=true`.

- [x] **Step 18.12: Report results**

Report to the controller: which steps passed, which didn't, and any surprises.

---

## Acceptance Criteria

1. All backend pytest tests in `test_flow_model_built_with_assist.py` and `test_flow_create_built_with_assist.py` pass (4 total).
2. All Jest tests pass: `assistantStore-layout`, `shell-switch`, `action-bar`, `adp-assist-button` (13 assertions).
3. `npx tsc --noEmit` is clean for all new/modified frontend files.
4. Alembic migration applies + rolls back cleanly; Postgres gets the new column.
5. Manual verification (Task 18) passes every step.
6. User WIP files (`flows.py`, `webhookFieldComponent/index.tsx`, `mcp/util.py`) remain unstaged except for Task 15's one-line `flows.py` edit (if needed per Step 15.3 — this is the only plan that intentionally touches that WIP file, and only minimally).

## Out of Scope

- Conversational template-context seeding (assistant's first message seeded from `TemplateMetadata.agent_instructions`) — Plan 4.
- Template matching from blank flows ("What kind of integration would you like to build?") — Plan 4.
- Test mode pipeline DAG view + per-component test states + component_test SSE — Plan 5.
- Any backend changes to the assistant service itself (system prompt, tools, etc.) — already done in Plan 2.
- Redesign of the assistant settings page.

## Open Items Flagged During Implementation

- **`addFlow` signature** — the existing hook may or may not accept a `built_with_assist` override directly. Task 14/16 resolve by grep and adapt; the fallback is to extend the hook to forward extra fields to the POST body.
- **`flows.py` WIP conflict** — Task 15 has a one-line edit in a file the owner is actively modifying. The implementer must read-before-edit and never `git add` lines they didn't add. If the existing `create_flow` handler already passes fields via `flow_create.model_dump()`, Task 15 requires NO code change (only the tests land).
- **`Maximize2` / `FlaskConical` / `GitBranch` icon names** — assumed to exist in the Lucide icon set used by `ForwardedIconComponent`. If any are missing, substitute (e.g., `Maximize`, `TestTube`, `Network`).
- **Alembic head on execution** — before Task 2 runs `alembic revision`, the implementer runs `alembic heads` to confirm `460a5ee548b6` is still the single head. If not, adjust the `down_revision`.
