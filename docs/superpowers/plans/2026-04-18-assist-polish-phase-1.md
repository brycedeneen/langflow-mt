# Assist Polish — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Small UX polish for the ADP Assist overlay shells and the Plan 5 pipeline-card tool sub-items. Two bundled items; no brainstorming required.

**Architecture:** Frontend-only. Two unrelated files touched: overlay shells (`fullscreen-shell.tsx` + `test-shell.tsx`) gain CSS variable–driven offsets, and `pipeline-card.tsx` gets a visual refresh on the grouped-tool rows.

**Tech Stack:** React + TypeScript + Tailwind. Jest for tests.

---

## Scope notes

**In scope** (this plan):
- (i) Replace hardcoded `top-[48px]` / `md:left-[17.5rem]` in the overlay shells with CSS variables.
- (ii) Better visual treatment for grouped tool sub-items in `PipelineCard`.

**Out of scope** (deferred to separate brainstorm):
- "Break long assistant messages into multiple turns" — UX-architecture decision, needs its own brainstorm session.

---

## File Structure

**Modified:**
- `src/frontend/src/style/index.css` (or equivalent global stylesheet — plan will confirm at task 1)
- `src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx`
- `src/frontend/src/modals/AssistantPanel/test-shell.tsx`
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx`

**Test files updated (existing):**
- `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx`

---

## Task 1: Define CSS variables for overlay offsets

**Files:**
- Modify: global stylesheet (likely `src/frontend/src/style/index.css` — confirm at task start)

Lightweight approach: define two CSS variables in `:root` with the current hardcoded values. Overlay components consume them via `var(--name)`. When the header height or sidebar width ever changes, the values update in one place.

This is simpler than a ResizeObserver-driven "header publishes its actual height" approach — the values are stable today. If they ever need to be dynamic, upgrade later.

- [x] **Step 1: Locate the global stylesheet**

Run `grep -rn "@tailwind base" src/frontend/src/` to find where Tailwind's base layer is declared. That file (or the sibling `index.css`) is where we add the `:root` block.

Expected location: `src/frontend/src/style/index.css` or `src/frontend/src/index.css`. Confirm and note in the subagent report.

- [x] **Step 2: Add the CSS variables**

Add to the `:root` block (creating it if none exists):

```css
:root {
  --assist-overlay-top: 48px;
  --assist-overlay-left: 17.5rem;
}
```

Immediately above the block, a short comment:

```css
/* Overlay offsets for ADP Assist fullscreen/test shells. Match the app
   header height (h-[48px]) and the flow-builder sidebar width (17.5rem).
   Update here when either changes. */
```

- [x] **Step 3: Stage**

```bash
git add src/frontend/src/style/index.css   # or confirmed path
```

---

## Task 2: Consume CSS variables in `fullscreen-shell.tsx`

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx`

- [x] **Step 1: Read the existing overlay div**

Open `fullscreen-shell.tsx`. Find the outermost `<div>` that uses `fixed top-[48px] ... md:left-[17.5rem]`. Typical shape:

```tsx
<div className="fixed top-[48px] bottom-0 right-0 left-0 md:left-[17.5rem] z-50 flex flex-col bg-background">
```

- [x] **Step 2: Replace hardcoded values with CSS variables**

Tailwind arbitrary-value syntax accepts CSS variables inline:

```tsx
<div className="fixed top-[var(--assist-overlay-top)] bottom-0 right-0 left-0 md:left-[var(--assist-overlay-left)] z-50 flex flex-col bg-background">
```

No other changes in the file.

- [x] **Step 3: Run the AssistantPanel test suite to verify nothing breaks**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel --no-coverage`
Expected: ALL PASS. These tests don't assert pixel values, so the change should be transparent.

- [x] **Step 4: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/fullscreen-shell.tsx
```

---

## Task 3: Consume CSS variables in `test-shell.tsx`

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/test-shell.tsx`

- [x] **Step 1: Apply the same swap**

Find the same `fixed top-[48px] ... md:left-[17.5rem]` pattern in `test-shell.tsx` (should be identical to `fullscreen-shell.tsx`). Replace with `top-[var(--assist-overlay-top)]` / `md:left-[var(--assist-overlay-left)]`.

- [x] **Step 2: Re-run the suite**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel --no-coverage`
Expected: ALL PASS.

- [x] **Step 3: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/test-shell.tsx
```

---

## Task 4: Improve PipelineCard tool sub-item styling

**Files:**
- Modify: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx`
- Modify: `src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx`

Grouped tools currently render as bare `Tool: <name>` list items. Goal: cleaner visual treatment — small wrench/tool icon, subtle chip background, improved typography.

- [x] **Step 1: Update the existing grouped-children test to allow flexibility**

The current test asserts `getByText(/Tool: Tool1/)` and `getByText(/Tool: Tool2/)`. After the styling change we may decide to drop the literal `Tool:` prefix (e.g., render as `🔧 Tool1`). Before changing the component, loosen the assertion so it tolerates the new format:

Find in `pipeline-card.test.tsx`:

```tsx
it("renders grouped children as indented sub-items", () => {
  // ...
  expect(screen.getByText(/Tool: Tool1/)).toBeInTheDocument();
  expect(screen.getByText(/Tool: Tool2/)).toBeInTheDocument();
});
```

Change to:

```tsx
it("renders grouped children as indented sub-items", () => {
  // ...
  expect(screen.getByText("Tool1")).toBeInTheDocument();
  expect(screen.getByText("Tool2")).toBeInTheDocument();
});
```

- [x] **Step 2: Run the test — should still pass against the current implementation**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx --no-coverage`
Expected: 6 PASS (tests pass because `Tool: Tool1` contains `Tool1`).

- [x] **Step 3: Update the grouped-children rendering**

In `pipeline-card.tsx`, find the current grouped-children block:

```tsx
{groupedChildren.length > 0 && (
  <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
    {groupedChildren.map((child) => (
      <li key={child.id}>
        Tool: {child.data.display_name || child.id}
      </li>
    ))}
  </ul>
)}
```

Replace with:

```tsx
{groupedChildren.length > 0 && (
  <ul className="mt-2 space-y-1">
    {groupedChildren.map((child) => (
      <li
        key={child.id}
        className="flex items-center gap-2 rounded border border-border/60 bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
      >
        <ForwardedIconComponent name="Wrench" className="h-3 w-3 shrink-0" />
        <span className="truncate">{child.data.display_name || child.id}</span>
      </li>
    ))}
  </ul>
)}
```

Add the `ForwardedIconComponent` import at the top of the file if it's not already there:

```tsx
import ForwardedIconComponent from "@/components/common/genericIconComponent";
```

- [x] **Step 4: Re-run the test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx --no-coverage`
Expected: 6 PASS.

- [x] **Step 5: Stage**

```bash
git add src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx \
        src/frontend/src/modals/AssistantPanel/FlowPipelineView/__tests__/pipeline-card.test.tsx
```

---

## Task 5: Manual verification

**Files:** none modified.

- [x] **Step 1: Boot the dev server** (`make frontend` + backend running).

- [x] **Step 2: Overlay offsets — open ADP Assist in fullscreen mode.** Confirm the overlay sits below the app header (no overlap) and right of the sidebar (no overlap). Resize the browser window — overlay should maintain its offsets at all widths.

- [x] **Step 3: Overlay offsets — switch to Test mode.** Confirm the same offsets hold.

- [x] **Step 4: Tool sub-item styling — open a flow with an Agent + Tools shape in Test mode.** Confirm the grouped tool rows under the Agent card now render with:
  - A small wrench icon before each name.
  - A subtle bordered/muted background that visually groups them.
  - Readable spacing; no horizontal overflow.

- [x] **Step 5: Report readiness for commit.** Human will batch-commit.

---

## Open Items

- **If the global stylesheet isn't at `src/frontend/src/style/index.css`**, find the actual Tailwind entry point at task 1 and confirm before proceeding. Don't create a new stylesheet — use the existing one.
- **If `ForwardedIconComponent`'s `Wrench` variant doesn't render** (lucide name mismatch), try `Hammer`, `Tool`, or `Settings2` as alternatives.
- **CSS variable dynamic publishing** — the plan takes the lightweight approach (hardcoded defaults in `:root`). If the app header height or sidebar width ever becomes dynamic (user-resizable sidebar, e.g.), upgrade to a ResizeObserver-driven "component publishes its actual size" approach in a follow-up.
- **Commit discipline:** all tasks stage-only. Human batches the commit at end of plan (matches the pattern of Plans 1–5).
