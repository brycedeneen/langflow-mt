# simple-sidebar rename + animated-close removal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `ui/simple-sidebar` → `ui/resizable-sidebar`, replace its `motion.div` calls + every `AnimatedConditional` consumer with stock CSS, and delete `ui/animated-close.tsx`. Drops 2 framer-motion importer files (current 5 → 3).

**Architecture:** A coherent single-commit refactor across 7 frontend files, executed in an isolated worktree branched from `platform-multi-tenant`. No behavior change; pixel-level visual parity is the bar. No new tests — relies on existing jest + Playwright suites for regression catch.

**Tech Stack:** React 19, TypeScript, Tailwind v4 (CSS-first config), shadcn primitives wrapping Radix, framer-motion (being reduced), Jest for unit tests, Playwright for e2e.

**Spec:** `docs/superpowers/specs/2026-04-25-simple-sidebar-and-animated-close-design.md`

**Standing instructions (from user's memory / AGENTS.md):**
- **Never `git commit` without explicit approval.** The commit task explicitly pauses and asks.
- **Stage explicit file paths.** Never use `git add -A`, `git add .`, or `git commit -a`. The repo has unrelated WIP — only stage files modified by this plan.
- **No upstream PR.** All work lands on `platform-multi-tenant`.
- **Worktree-first.** Every change happens inside the worktree set up in Task 0; the parent checkout stays untouched.
- **Jest, not Vitest.** Frontend tests run via `npm run test`.
- **Cadence:** User opted for "a ton of work before committing." All implementation tasks land first; the verification gate (Task 7) and commit (Task 8) come once at the end.

---

## Task 0 — Worktree setup

**Files:** None modified; sets up the workspace.

- [ ] **Step 1: Create the worktree**

Run (from `/Users/brycedeneen/dev/langflow`):
```bash
git worktree add .worktrees/tailwind-deframer-sidebar -b tailwind/deframer-sidebar platform-multi-tenant
```
Expected: `.worktrees/tailwind-deframer-sidebar` exists; new branch `tailwind/deframer-sidebar` checked out at the tip of `platform-multi-tenant`.

- [ ] **Step 2: Install frontend deps in the worktree**

Run:
```bash
cd .worktrees/tailwind-deframer-sidebar/src/frontend && npm install
```
Expected: deps install cleanly; `node_modules` populated. The lockfile is shared, so this is fast on a warm cache.

- [ ] **Step 3: Confirm baseline tests pass before changing anything**

Run:
```bash
cd .worktrees/tailwind-deframer-sidebar/src/frontend && npm run type-check && npm run test -- --silent
```
Expected: typecheck clean, jest green. If anything fails, **stop and report** — don't start work on top of a red baseline.

- [ ] **Step 4: Snapshot baseline framer-motion counts**

Run (from worktree root):
```bash
grep -rn "framer-motion" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l
grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l
```
Expected: 7 references across 5 files. Record the exact numbers — Task 7 step 5 will diff them.

**All remaining tasks operate inside `.worktrees/tailwind-deframer-sidebar`.** All file paths below are relative to that worktree root.

---

## Task 1 — Rename `simple-sidebar.tsx` to `resizable-sidebar.tsx` (file + internal symbols)

**Files:**
- Rename: `src/frontend/src/components/ui/simple-sidebar.tsx` → `src/frontend/src/components/ui/resizable-sidebar.tsx`

**Note:** This task only renames the file and its internal symbols. The framer-motion → CSS rewrite happens in Task 3. Keeping rename and CSS rewrite separate makes review easier (diff one shows pure renames, diff three shows pure CSS changes).

- [ ] **Step 1: Move the file via `git mv`**

Run (from worktree root):
```bash
git mv src/frontend/src/components/ui/simple-sidebar.tsx src/frontend/src/components/ui/resizable-sidebar.tsx
```
Expected: git tracks the rename; file path changes.

- [ ] **Step 2: Rename internal symbols**

Open `src/frontend/src/components/ui/resizable-sidebar.tsx` and apply these mechanical renames (every occurrence in the file):

| Old | New |
|---|---|
| `SimpleSidebarContext` | `ResizableSidebarContext` |
| `useSimpleSidebar` | `useResizableSidebar` |
| `SimpleSidebarProvider` | `ResizableSidebarProvider` |
| `SimpleSidebarResizeHandle` | `ResizableSidebarResizeHandle` |
| `SimpleSidebar` | `ResizableSidebar` |
| `SimpleSidebarTrigger` | `ResizableSidebarTrigger` |
| `SimpleSidebarHeader` | `ResizableSidebarHeader` |
| `SimpleSidebarContent` | `ResizableSidebarContent` |
| `--simple-sidebar-width` | `--resizable-sidebar-width` |
| `--simple-sidebar-parent-width` | `--resizable-sidebar-parent-width` |
| `data-simple-sidebar=` | `data-resizable-sidebar=` |
| `group/simple-sidebar-wrapper` | `group/resizable-sidebar-wrapper` |
| `displayName = "SimpleSidebarProvider"` | `displayName = "ResizableSidebarProvider"` |
| `displayName = "SimpleSidebar"` | `displayName = "ResizableSidebar"` |
| ...(every `SimpleSidebar*.displayName` similarly)... | ...rename to match... |
| `"SIMPLE_SIDEBAR_WIDTH"` constant name | `"RESIZABLE_SIDEBAR_WIDTH"` (the `const SIMPLE_SIDEBAR_WIDTH = "400px"` line) |
| `MIN_SIDEBAR_WIDTH` and `MAX_SIDEBAR_WIDTH` | unchanged (already generic) |

Critically **preserve unchanged**:
- `data-testid="playground-btn-flow-io"` on the Trigger button — Playwright depends on it.
- `data-sidebar="trigger"` attribute — also a Playwright/test-friendly hook.

- [ ] **Step 3: Verify the file is internally consistent**

Run:
```bash
grep -n "SimpleSidebar\|simple-sidebar" src/frontend/src/components/ui/resizable-sidebar.tsx
```
Expected: zero results. If anything matches, you missed a rename.

- [ ] **Step 4: Typecheck — expect failures at importer sites only**

Run:
```bash
cd src/frontend && npm run type-check
```
Expected: type errors at the 3 importer files (which Task 2 fixes). Errors *inside* `resizable-sidebar.tsx` mean a missed internal rename — go fix it before Task 2.

---

## Task 2 — Update the 3 simple-sidebar importer files

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/index.tsx` (uses `SimpleSidebar`, `SimpleSidebarProvider`)
- Modify: `src/frontend/src/components/core/flowToolbarComponent/components/playground-button.tsx` (uses `SimpleSidebarTrigger`)
- Modify: `src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx` (uses `useSimpleSidebar`)

These three are independent and can be done in parallel by separate subagents.

- [ ] **Step 1: Migrate `pages/FlowPage/index.tsx`**

Edit `src/frontend/src/pages/FlowPage/index.tsx`:
- Change the import path from `@/components/ui/simple-sidebar` to `@/components/ui/resizable-sidebar`.
- Change every imported name `SimpleSidebar*` to `ResizableSidebar*` (e.g. `SimpleSidebar` → `ResizableSidebar`, `SimpleSidebarProvider` → `ResizableSidebarProvider`).
- Change every JSX usage in the file from `<SimpleSidebar*>` to `<ResizableSidebar*>` and the closing tags accordingly.

Verify with:
```bash
grep -n "SimpleSidebar\|simple-sidebar" src/frontend/src/pages/FlowPage/index.tsx
```
Expected: zero results.

- [ ] **Step 2: Migrate `flowToolbarComponent/components/playground-button.tsx`**

Edit the file:
- Change `import { SimpleSidebarTrigger } from "@/components/ui/simple-sidebar";` to `import { ResizableSidebarTrigger } from "@/components/ui/resizable-sidebar";`.
- Change every JSX usage `<SimpleSidebarTrigger ...>` to `<ResizableSidebarTrigger ...>`.

Verify:
```bash
grep -n "SimpleSidebar\|simple-sidebar" src/frontend/src/components/core/flowToolbarComponent/components/playground-button.tsx
```
Expected: zero results.

- [ ] **Step 3: Migrate `playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx`**

Edit the file:
- Change `import { useSimpleSidebar } from "@/components/ui/simple-sidebar";` to `import { useResizableSidebar } from "@/components/ui/resizable-sidebar";`.
- Change `const { setOpen, setWidth } = useSimpleSidebar();` to `const { setOpen, setWidth } = useResizableSidebar();`.

Note: this file *also* gets the AnimatedConditional rewrite in Task 4. Don't touch that yet.

Verify:
```bash
grep -n "SimpleSidebar\|simple-sidebar\|useSimpleSidebar" src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx
```
Expected: zero results.

- [ ] **Step 4: Sweep the whole frontend for stragglers**

Run (from worktree root):
```bash
grep -rn "SimpleSidebar\|simple-sidebar\|useSimpleSidebar" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: zero results across the entire tree. (Tests, comments, anywhere — all gone.)

- [ ] **Step 5: Typecheck must be clean**

Run:
```bash
cd src/frontend && npm run type-check
```
Expected: zero errors. If any remain, they're either a missed importer or a missed internal rename in Task 1.

---

## Task 3 — Replace `motion.div` with CSS inside `resizable-sidebar.tsx`

**Files:**
- Modify: `src/frontend/src/components/ui/resizable-sidebar.tsx` (only)

This task removes the framer-motion dependency from the renamed file. It does *not* change rendered behavior — the same widths, the same x-translation, the same opacity, the same "no animation while dragging or in fullscreen" rules.

- [ ] **Step 1: Remove the dead and motion imports**

In `src/frontend/src/components/ui/resizable-sidebar.tsx`:
- Delete the line `import { motion } from "framer-motion";` (around line 3).
- Delete the line `import { AnimatedConditional } from "./animated-close";` (around line 9). It's a dead import — `AnimatedConditional` is not referenced anywhere in this file. Verify with `grep -n "AnimatedConditional" src/frontend/src/components/ui/resizable-sidebar.tsx` before deleting (expected: only the import line) and after (expected: nothing).

- [ ] **Step 2: Delete the now-unused `transitionDuration` memo**

Inside the `ResizableSidebar` forwardRef component, delete the `transitionDuration` `React.useMemo` block:

```tsx
const transitionDuration = React.useMemo(() => {
  if (fullscreen) return 0;
  return isResizing ? 0 : 0.3;
}, [isResizing, fullscreen]);
```

The "skip transition while dragging or fullscreen" rule moves to a CSS data-attribute selector in Step 3.

- [ ] **Step 3: Rewrite the two `motion.div`s as plain `<div>`s**

Inside `ResizableSidebar`, find the two `motion.div` elements and replace the entire `return (...)` block with the following. Preserve `spacerWidth`, `sidebarWidth`, `xPosition`, `open`, `side`, `fullscreen`, `isResizing`, `className`, `children`, `props.style`, and the `resizable` prop logic exactly.

```tsx
return (
  <div
    ref={ref}
    className={cn(" flex h-full")}
    data-open={open}
    data-side={side}
    data-fullscreen={fullscreen}
  >
    {/* Spacer: handles the sidebar gap */}
    <div
      className={cn(
        "relative h-full bg-transparent transition-[width] duration-300 ease-in-out",
        "data-[resizing=true]:transition-none data-[fullscreen=true]:transition-none",
      )}
      data-resizing={isResizing}
      data-fullscreen={fullscreen}
      style={{ width: spacerWidth }}
    />
    {/* Sidebar overlay */}
    <div
      className={cn(
        "absolute inset-y-0 z-50 flex h-full transition-[width,transform,opacity] duration-300 ease-in-out",
        "data-[resizing=true]:transition-none data-[fullscreen=true]:transition-none",
        className,
      )}
      data-resizing={isResizing}
      data-fullscreen={fullscreen}
      style={{
        ...props.style,
        width: sidebarWidth,
        transform: `translateX(${xPosition})`,
        opacity: open ? 1 : 0,
        left: side === "left" ? 0 : "auto",
        right: side === "right" ? 0 : "auto",
        pointerEvents: open ? "auto" : "none",
      }}
    >
      <div
        data-resizable-sidebar="sidebar"
        className="flex h-full w-full flex-col bg-background relative"
        style={{ visibility: open ? "visible" : "hidden" }}
      >
        {children}
        {resizable && open && !fullscreen && (
          <ResizableSidebarResizeHandle side={side} />
        )}
      </div>
    </div>
  </div>
);
```

Notes:
- The spacer's only animated property is `width`, but I list `transition-[width]` to be explicit and to match framer-motion's behavior.
- The sidebar overlay animates three properties (`width`, `transform`, `opacity`) so the transition list covers all three.
- `data-resizing={isResizing}` is what `data-[resizing=true]:transition-none` reads. React renders booleans on `data-*` attrs as `"true"`/`"false"` strings, so this matches.
- `data-fullscreen={fullscreen}` likewise.

- [ ] **Step 4: Confirm framer-motion is gone from this file**

Run:
```bash
grep -n "framer-motion\|motion\." src/frontend/src/components/ui/resizable-sidebar.tsx
```
Expected: zero results.

- [ ] **Step 5: Typecheck**

Run:
```bash
cd src/frontend && npm run type-check
```
Expected: clean.

---

## Task 4 — Replace `AnimatedConditional` in `flow-page-sliding-container.tsx` (1 site, fixed width)

**Files:**
- Modify: `src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx`

- [ ] **Step 1: Remove the AnimatedConditional import**

Delete this line:
```tsx
import { AnimatedConditional } from "@/components/ui/animated-close";
```

- [ ] **Step 2: Replace the single usage**

Find this block (around line 138):
```tsx
<AnimatedConditional isOpen={sidebarOpen} width="236px">
  {children}
</AnimatedConditional>
```

Replace with:
```tsx
<div
  data-open={sidebarOpen}
  className="overflow-hidden whitespace-nowrap transition-[width] duration-300 ease-in-out"
  style={{ width: sidebarOpen ? "236px" : 0 }}
>
  {children}
</div>
```

(`{children}` here is whatever was already inside the `AnimatedConditional` — keep it verbatim.)

- [ ] **Step 3: Verify**

Run:
```bash
grep -n "AnimatedConditional\|animated-close" src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx
```
Expected: zero results.

---

## Task 5 — Replace `AnimatedConditional` in `chat-header.tsx` (4 sites, auto width via grid trick)

**Files:**
- Modify: `src/frontend/src/components/core/playgroundComponent/chat-view/chat-header/components/chat-header.tsx`

This file has 4 `<AnimatedConditional>` sites, all without a `width` prop, so they animate `0 ↔ auto`. The replacement uses the `grid grid-cols-[0fr ↔ 1fr]` trick.

- [ ] **Step 1: Remove the AnimatedConditional import**

Delete this line:
```tsx
import { AnimatedConditional } from "@/components/ui/animated-close";
```

- [ ] **Step 2: Replace each usage with the grid-`fr` pattern**

For each `<AnimatedConditional isOpen={X}>...</AnimatedConditional>` (4 sites at approximately lines 80, 117, 156, 164 — verify with `grep -n "AnimatedConditional" .../chat-header.tsx`), replace with:

```tsx
<div
  data-open={X}
  className="grid grid-cols-[0fr] transition-[grid-template-columns] duration-300 ease-in-out data-[open=true]:grid-cols-[1fr] overflow-hidden whitespace-nowrap"
>
  <div className="min-w-0 overflow-hidden">
    {/* original children */}
  </div>
</div>
```

Where `X` is the original `isOpen` expression (`isSessionDropdownVisible`, `!isFullscreen`, `isFullscreen`, etc.) and the original children stay verbatim inside the inner `<div className="min-w-0 overflow-hidden">`.

If a call site passed any `className` prop on the original `<AnimatedConditional>`, merge it with the outer wrapper's className via `cn(...)` — don't drop it. (Spot-check the file: at the time this plan was written, none of the 4 sites pass `className`, but verify before assuming.)

- [ ] **Step 3: Verify all 4 sites are converted**

Run:
```bash
grep -n "AnimatedConditional\|animated-close" src/frontend/src/components/core/playgroundComponent/chat-view/chat-header/components/chat-header.tsx
```
Expected: zero results.

- [ ] **Step 4: Typecheck**

Run:
```bash
cd src/frontend && npm run type-check
```
Expected: clean.

---

## Task 6 — Delete `animated-close.tsx`

**Files:**
- Delete: `src/frontend/src/components/ui/animated-close.tsx`

**Pre-condition:** Tasks 3, 4, and 5 are all done — `AnimatedConditional` has zero importers anywhere.

- [ ] **Step 1: Sweep for any straggler imports**

Run (from worktree root):
```bash
grep -rn "AnimatedConditional\|animated-close" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: zero results. If anything matches, fix it before deleting the file.

- [ ] **Step 2: Delete the file**

Run:
```bash
git rm src/frontend/src/components/ui/animated-close.tsx
```
Expected: file removed; git tracks the deletion.

- [ ] **Step 3: Typecheck**

Run:
```bash
cd src/frontend && npm run type-check
```
Expected: clean.

---

## Task 7 — Verification gate

**Files:** None modified.

This is the per-phase verification bar from the parent plan, run end-to-end. **Do not skip any step.** Each is a gate — if a gate fails, fix the underlying cause before moving on (do *not* increase a timeout, mock around it, or weaken an assertion).

- [ ] **Step 1: Typecheck clean**

Run:
```bash
cd src/frontend && npm run type-check
```
Expected: zero errors.

- [ ] **Step 2: Jest green**

Run:
```bash
cd src/frontend && npm run test -- --silent
```
Expected: all tests pass. If a test mocked `framer-motion`, `simple-sidebar`, or `animated-close`, fix the mock to match the new shape — don't disable the test.

- [ ] **Step 3: Production build succeeds**

Run:
```bash
cd src/frontend && npm run build
```
Expected: bundle builds without errors.

- [ ] **Step 4: Playwright e2e green**

Run (from worktree root):
```bash
make tests_frontend
```
Expected: full suite passes. Pre-existing failures from the parent plan's pre-flight (Step 5 of Phase 0) are tolerated; *new* failures must be investigated. Particular surfaces to scrutinize if anything fails:
- Anything testing the playground sidebar (drag-resize, open/close, fullscreen).
- Anything testing the chat header session dropdown / fullscreen toggle.
- Anything testing the flow page sliding container (the 236px sidebar).

- [ ] **Step 5: Confirm framer-motion footprint dropped**

Run (from worktree root):
```bash
grep -rn "framer-motion" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l
grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l
```
Expected: reference count went from 7 → 5; file count went from 5 → 3. The remaining 3 importer files are `disclosure.tsx`, `animatedNumbers/index.tsx`, `flowBuildingComponent/index.tsx`.

- [ ] **Step 6: Sweep — old names fully gone**

Run (from worktree root):
```bash
grep -rn "SimpleSidebar\|simple-sidebar\|useSimpleSidebar\|AnimatedConditional\|animated-close" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: zero results across the whole frontend tree.

- [ ] **Step 7: Manual eyeball on the running dev server**

Start the dev server from the worktree:
```bash
make frontend
```
Vite serves on port 3000, backend on 7860. Visit each surface and confirm no broken layout, no console errors, no visual regressions:

1. **Flow canvas** (`/flows/<any>`) — flow loads, nodes render, connections draw.
2. **Playground** (open a flow → click Playground):
   - Chat input renders, messages display.
   - **Drag the playground sidebar resize handle** — width changes smoothly during drag.
   - **Open/close the sidebar via the trigger** — slides in/out with animation.
   - **Toggle fullscreen** — sidebar expands to 100% width with no animation glitch.
   - **Open/close the session dropdown in the chat header** — content reveals/hides via the grid-`fr` animation; verify it looks smooth and the layout doesn't jump.
3. **Settings page** (`/settings/general`) — layout intact.
4. **Admin → Users page** — table renders.
5. **Admin → Organizations page** — list renders.
6. **Flow page sliding container** — open a flow page that uses the sliding 236px sidebar, toggle it open and closed, verify smooth `width` animation.

If any surface shows a regression, **stop and fix before commit.** A console error or pixel-level glitch in animation easing is acceptable to flag-and-keep-going only with explicit user approval.

---

## Task 8 — Commit (after explicit approval)

**Files:** All files modified by Tasks 1–6.

- [ ] **Step 1: Summarize what changed**

Write a short summary to share with the user covering:
- Files renamed (1 — simple-sidebar.tsx → resizable-sidebar.tsx).
- Files deleted (1 — animated-close.tsx).
- Files modified (4 — FlowPage/index.tsx, playground-button.tsx, flow-page-sliding-container.tsx, chat-header.tsx).
- framer-motion footprint: 7 refs / 5 files → 5 refs / 3 files.
- Verification gate results from Task 7.

- [ ] **Step 2: Pause and ask for commit permission**

Ask the user verbatim: *"All tasks complete and verification gate passed. OK to commit on `tailwind/deframer-sidebar`?"*

**Do NOT commit without explicit approval.** This is an absolute rule from the user's standing instructions.

- [ ] **Step 3: Commit (after approval)**

Stage only the files this plan touched:
```bash
git add \
  src/frontend/src/components/ui/resizable-sidebar.tsx \
  src/frontend/src/components/ui/simple-sidebar.tsx \
  src/frontend/src/components/ui/animated-close.tsx \
  src/frontend/src/pages/FlowPage/index.tsx \
  src/frontend/src/components/core/flowToolbarComponent/components/playground-button.tsx \
  src/frontend/src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx \
  src/frontend/src/components/core/playgroundComponent/chat-view/chat-header/components/chat-header.tsx
```

(The first three paths cover the rename + deletion; `git add` against the now-deleted `simple-sidebar.tsx` and `animated-close.tsx` records the deletions in the index. If `git status` shows the renames as one entry already, only stage the new path; the rename is recorded automatically.)

Do NOT use `git add -A` or `git add .`.

Then commit:
```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): rename simple-sidebar → resizable-sidebar, delete animated-close

Resolves three coupled deferrals from the Tailwind Maximization plan:
- Phase 1: simple-sidebar ↔ ui/sidebar consolidation (rename, not merge)
- Phase 2: animated-close (AnimatedConditional) — replaced with CSS
- Phase 7a progress: framer-motion footprint 7 refs / 5 files → 5 / 3

The two components model different problems (per-pixel drag-resize overlay
vs. cookie-persisted sectioned menu) and don't merge cleanly. Renaming
to resizable-sidebar makes the split honest. Both files no longer
import framer-motion; transitions are plain Tailwind/CSS now.

Spec: docs/superpowers/specs/2026-04-25-simple-sidebar-and-animated-close-design.md
Plan: docs/superpowers/plans/2026-04-25-simple-sidebar-and-animated-close.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Confirm commit landed**

Run:
```bash
git log -1 --stat
```
Expected: one commit on `tailwind/deframer-sidebar` showing the file rename, deletion, and 4 modifications. No extra files (verify via the stat that only the expected paths appear).

- [ ] **Step 5: Hand back to user**

Report the commit SHA and ask whether to merge `tailwind/deframer-sidebar` into `platform-multi-tenant` and clean up the worktree, or leave the branch in place for separate review.
