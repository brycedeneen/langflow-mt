# Tailwind Phase 7 — clear the deck — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all five Phase 7 deferrals (7a–7e) of the Tailwind Maximization plan in one session: 5 sequential commits on a shared worktree branch, unified verification gate, single ff-merge into `platform-multi-tenant`.

**Architecture:** Single worktree (`tailwind/phase-7`) with 5 commits landed back-to-back. Each commit has its own commit-local verification gate (typecheck + jest + build + ORPHAN sweep limited to that piece's scope). If any commit-local gate fails, the chain stops and reports. After all 5 commits land, run the unified end-of-chain verification gate, pause for the user's smoke-test approval, then ff-merge → push to `fork` → cleanup. **Cadence: Option A** — auto-commit per piece on green gate; single pause-and-ask before the ff-merge.

**Tech Stack:** React 19, TypeScript, Tailwind v4 (CSS-first config), shadcn primitives wrapping Radix, lucide-react for icons, framer-motion (partially being reduced), Jest for unit tests, Vite for build, Biome for lint/format.

**Spec:** `docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md`

**Standing instructions:**
- **Pause and ask before the ff-merge.** Every other commit lands automatically when its commit-local verification gate passes (Option A cadence — confirmed by user 2026-04-26).
- **Stage explicit file paths.** Never `git add -A`/`.`/`-a`. The repo has unrelated WIP — only stage files this plan touches.
- **No upstream PR.** Push to `fork` (`brycedeneen/langflow-mt`), NOT `origin` (`langflow-ai/langflow`).
- **Worktree-first.** All edits happen in `.worktrees/tailwind-phase-7`.
- **Subagent commit hygiene.** Subagents never `git add` or commit. Subagents never modify files outside their assigned scope. Controller stages explicit paths and commits per-piece.
- **No new tests.** Existing jest + build + grep sweeps + manual eyeball post-merge.

---

## Task 0 — Worktree setup

**Files:** None modified.

- [ ] **Step 1: Create worktree from `platform-multi-tenant` HEAD**

Run from `/Users/brycedeneen/dev/langflow`:
```bash
git worktree add .worktrees/tailwind-phase-7 -b tailwind/phase-7 platform-multi-tenant
```
Expected: worktree at `.worktrees/tailwind-phase-7/` on new branch `tailwind/phase-7`.

- [ ] **Step 2: Install frontend deps**

```bash
cd .worktrees/tailwind-phase-7/src/frontend && npm install
```
Expected: clean install on warm cache.

- [ ] **Step 3: Confirm baseline**

```bash
cd .worktrees/tailwind-phase-7/src/frontend && npm run type-check 2>&1 | tail -5
```
Expected: only the 2 pre-existing TagRead errors in `src/hooks/flows/use-add-flow.ts:126` and `src/pages/MainPage/hooks/use-handle-duplicate.ts:24`. Anything else means dirty baseline — STOP and report.

```bash
npm run test -- --silent 2>&1 | tail -5
```
Expected: only the 14 pre-existing `SaveAsTemplateModal.test.tsx` failures, ≥3105 pass.

```bash
npm run build 2>&1 | tail -3
```
Expected: clean build.

- [ ] **Step 4: Capture baselines for end-of-chain comparisons**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/tailwind-phase-7

mkdir -p /tmp/p7-baseline

# 7a: framer-motion importer count
grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include="*.ts" --include="*.tsx" \
  > /tmp/p7-baseline/framer-motion-files.txt
wc -l < /tmp/p7-baseline/framer-motion-files.txt > /tmp/p7-baseline/framer-motion-count.txt

# 7b: ShadTooltip caller count
grep -rln "ShadTooltip" src/frontend/src --include="*.ts" --include="*.tsx" \
  > /tmp/p7-baseline/shadtooltip-files.txt
wc -l < /tmp/p7-baseline/shadtooltip-files.txt > /tmp/p7-baseline/shadtooltip-count.txt

# 7c: static-name vs dynamic-name ForwardedIconComponent counts
grep -rEn '<(Forwarded)?IconComponent[[:space:]]+name="[a-zA-Z]' src/frontend/src --include="*.tsx" \
  > /tmp/p7-baseline/icon-static-sites.txt
grep -rEn '<(Forwarded)?IconComponent[^>]*name=\{' src/frontend/src --include="*.tsx" \
  > /tmp/p7-baseline/icon-dynamic-sites.txt

# 7e: --color-* token count in @theme
awk '/^@theme/,/^}/' src/frontend/src/style/index.css | grep -cE "^\s*--color-" \
  > /tmp/p7-baseline/color-token-count.txt

echo "Baselines captured:"
echo "  framer-motion files: $(cat /tmp/p7-baseline/framer-motion-count.txt)"
echo "  shadtooltip files: $(cat /tmp/p7-baseline/shadtooltip-count.txt)"
echo "  icon static sites: $(wc -l < /tmp/p7-baseline/icon-static-sites.txt)"
echo "  icon dynamic sites: $(wc -l < /tmp/p7-baseline/icon-dynamic-sites.txt)"
echo "  color tokens: $(cat /tmp/p7-baseline/color-token-count.txt)"
```

Expected output (approximate):
```
framer-motion files: 3
shadtooltip files: 108
icon static sites: 173
icon dynamic sites: 24
color tokens: 125
```

All later tasks operate inside `.worktrees/tailwind-phase-7`. Paths below are worktree-relative.

---

## Task 1 — Commit 1: 7a — framer-motion partial removal

**Files:**
- Modify: `src/frontend/src/components/ui/disclosure.tsx`
- Modify: `src/frontend/src/components/common/animatedNumbers/index.tsx`
- Modify: `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx`

### Task 1.1 — Read each consumer to understand its framer-motion use

- [ ] **Step 1: Read each file and identify the `motion.*` calls**

```bash
grep -nE "motion\.|AnimatePresence|useAnimat|MotionValue" \
  src/frontend/src/components/ui/disclosure.tsx \
  src/frontend/src/components/common/animatedNumbers/index.tsx \
  src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx
```

For each match, classify the role:
- **Decorative** = fade/scale/opacity/transform animations that are pure visual flourish.
- **Load-bearing height-collapse** = the specific case where DOM `height: auto` needs to animate to `0` (or vice versa) and the framework needs to measure the actual rendered height. Only one site qualifies, in `flowBuildingComponent` — the error-display block.
- **Numeric tween** = `animate({ from: x, to: y, onUpdate })` style numeric interpolation in `animatedNumbers`.

Record findings in a scratch note before editing.

### Task 1.2 — Convert `disclosure.tsx`

- [ ] **Step 1: Replace the `motion.div` open/close with the grid-`fr` pattern**

The disclosure component animates content open/close. Same pattern as `AnimatedConditional` from the simple-sidebar work:

Before (sketch — actual file may differ):
```tsx
<motion.div
  initial={false}
  animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }}
  transition={{ duration: 0.3, ease: "easeInOut" }}
>
  {children}
</motion.div>
```

After:
```tsx
<div
  data-open={open}
  className="grid grid-rows-[0fr] transition-[grid-template-rows] duration-300 ease-in-out data-[open=true]:grid-rows-[1fr] overflow-hidden"
>
  <div className="min-h-0 overflow-hidden">
    {children}
  </div>
</div>
```

Notes:
- Grid-`fr` is the exact technique that worked for `AnimatedConditional`. Reuse the pattern.
- Remove the `import { motion } from "framer-motion"` line if no other `motion.*` use remains in the file.
- Preserve every prop, ref, and event handler around the converted element.

- [ ] **Step 2: Verify**

```bash
grep -n "framer-motion\|motion\." src/frontend/src/components/ui/disclosure.tsx
```
Expected: empty.

```bash
cd src/frontend && npm run type-check 2>&1 | grep "disclosure\.tsx"
```
Expected: empty (no errors in this file).

### Task 1.3 — Convert `animatedNumbers/index.tsx`

- [ ] **Step 1: Inspect the current implementation**

Read the file. Identify the `animate({...})` or `MotionValue` use. The component animates a number from previous value → new value using framer-motion's spring/tween.

- [ ] **Step 2: Replace with `requestAnimationFrame` + CSS counter**

If the animation is a simple linear or eased number tween, the simpler replacement is a manual `requestAnimationFrame` loop tracking `from → to` over `duration`:

```tsx
import { useEffect, useRef, useState } from "react";

export function AnimatedNumber({ value, duration = 300, format }: {
  value: number;
  duration?: number;
  format?: (n: number) => string;
}) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const startTimeRef = useRef<number | null>(null);
  const rafRef = useRef<number>();

  useEffect(() => {
    fromRef.current = display;
    startTimeRef.current = null;

    const tick = (now: number) => {
      if (startTimeRef.current === null) startTimeRef.current = now;
      const elapsed = now - startTimeRef.current;
      const t = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const current = fromRef.current + (value - fromRef.current) * eased;
      setDisplay(current);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  return <span>{format ? format(display) : Math.round(display)}</span>;
}
```

(Adjust the actual signature to match the existing component's props — read the file first and preserve the public API.)

If the existing component is heavier (multi-digit roll, etc.), use the simpler-fallback option: drop the animation entirely and render the raw number. The visual difference for fast-changing numbers is minimal; document the simplification in the commit message.

- [ ] **Step 3: Verify**

```bash
grep -n "framer-motion\|motion\." src/frontend/src/components/common/animatedNumbers/index.tsx
```
Expected: empty.

```bash
cd src/frontend && npm run type-check 2>&1 | grep "animatedNumbers"
```
Expected: empty.

### Task 1.4 — Partial conversion of `flowBuildingComponent/index.tsx`

- [ ] **Step 1: Map every `motion.*` use in the file to "decorative" or "load-bearing"**

```bash
grep -nE "motion\.|AnimatePresence" src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx
```

For each line, examine the surrounding JSX:
- If the animated property is `opacity`, `transform`, `scale`, `x`, `y`, `rotate`: **decorative** — convert.
- If the animated property is `height` AND the from/to includes `"auto"` (literal string): **load-bearing height-collapse** — leave as-is.
- If `AnimatePresence` is used to gate exit animations: convert by adding a delayed-unmount hook (see prior commit `7eb956edb6` — `useDelayedUnmount` already exists in the codebase at `src/frontend/src/utils/useDelayedUnmount.ts`).

- [ ] **Step 2: Convert the decorative sites**

For each decorative `motion.div`:
- Replace `motion.div` with `div`.
- Move animation props to Tailwind classes / inline style:
  - `animate={{ opacity: x }}` → `style={{ opacity: x }}` or className with `transition-opacity duration-...`.
  - `animate={{ scale: x }}` / `transform: ...` → `style={{ transform: \`scale(${x})\` }}` with `transition-transform duration-...`.
- Preserve the `transition.duration`, `ease`, and `delay` semantics via Tailwind utilities (e.g., `duration-300 ease-in-out`).

- [ ] **Step 3: Leave the height-collapse site untouched**

The error-display block uses `motion.div` to animate `height: auto ↔ 0`. **Do not touch this site.** Add an inline comment near it noting:

```tsx
// 7a: load-bearing — animates height: auto ↔ 0 for error display.
// CSS-only replacement requires DOM measurement; deferred per
// docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md.
```

- [ ] **Step 4: Verify file partially converted but framer-motion still imported**

```bash
grep -c "motion\." src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx
```
Expected: ≥1 (the height-collapse site remains). NOT zero.

```bash
grep -c "from ['\"]framer-motion['\"]" src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx
```
Expected: 1 (still imported for the height-collapse site).

### Task 1.5 — Commit 1 verification gate

- [ ] **Step 1: Sweep — framer-motion file count drops 3 → 1**

```bash
grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: exactly one file, `src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx`.

- [ ] **Step 2: Typecheck + jest + build**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
```
Expected: only the 2 pre-existing TagRead errors.

```bash
cd src/frontend && npm run test -- --silent 2>&1 | tail -5
```
Expected: only the 14 pre-existing `SaveAsTemplateModal.test.tsx` failures.

```bash
cd src/frontend && npm run build 2>&1 | tail -3
```
Expected: clean.

If any check shows new failures: STOP. Report what failed. Do not proceed to Task 2.

### Task 1.6 — Commit 7a

- [ ] **Step 1: Stage explicit paths and commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/tailwind-phase-7
git add \
  src/frontend/src/components/ui/disclosure.tsx \
  src/frontend/src/components/common/animatedNumbers/index.tsx \
  src/frontend/src/pages/FlowPage/components/flowBuildingComponent/index.tsx
git diff --cached --name-only
```
Expected: exactly the 3 paths above.

```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 7a — framer-motion partial removal

Convert decorative framer-motion uses in disclosure.tsx and
animatedNumbers/index.tsx to plain CSS. Convert decorative uses in
flowBuildingComponent/index.tsx to CSS as well; leave the load-bearing
height-collapse block (height: auto ↔ 0 for error display) on framer-motion.

framer-motion importer files: 3 → 1. Dep stays installed for the one
remaining consumer.

Phase 7a of docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Confirm**

```bash
git log -1 --stat
```

---

## Task 2 — Commit 2: 7b — inline `shadTooltipComponent`

**Files:**
- Modify: ~108 caller files (exact list determined by audit in Task 2.1)
- Delete: `src/frontend/src/components/common/shadTooltipComponent/` directory
- Modify (likely): one or two parent components to ensure `TooltipProvider` is in scope (audit determines)

### Task 2.1 — Audit ShadTooltip call sites

- [ ] **Step 1: Read the wrapper to understand its API**

```bash
cat src/frontend/src/components/common/shadTooltipComponent/index.tsx
```

Document the prop shape: which props pass through to which underlying primitives (`Tooltip`, `TooltipTrigger`, `TooltipContent`). Note any defaults (e.g., default `delayDuration`, default `side`).

- [ ] **Step 2: Build the call-site map**

```bash
grep -rEn "<ShadTooltip\b" src/frontend/src --include="*.tsx" \
  > /tmp/p7-shadtooltip-sites.txt
wc -l /tmp/p7-shadtooltip-sites.txt
```

Expected: ~108 lines.

- [ ] **Step 3: Verify TooltipProvider is in scope at every call site's tree**

`ui/sidebar.tsx`'s `SidebarProvider` already wraps with `TooltipProvider`. Verify:

```bash
grep -n "TooltipProvider" src/frontend/src/components/ui/sidebar.tsx
```

Expected: at least one match (the wrap inside `SidebarProvider`).

For surfaces NOT under `SidebarProvider` (typically modals rendered as portals, top-level pages without the sidebar layout), confirm a `TooltipProvider` is reachable. Audit:

```bash
grep -rln "TooltipProvider" src/frontend/src --include="*.tsx" | head -20
```

If a call site lacks a `TooltipProvider` ancestor, add one in the nearest sensible parent (likely the modal's root or the page's root). Document each addition in the commit message.

- [ ] **Step 4: Bucket call sites for parallel dispatch**

Group the ~108 call sites into 6-8 surface-area bundles:
- `modals/` (export, import, share, prompt, model-provider, etc.)
- `pages/FlowPage/` (canvas + toolbar + side panels)
- `pages/AdminPage/` (organizations, users, etc.)
- `pages/MainPage/` (empty page, dashboard)
- `components/core/playgroundComponent/`
- `components/core/parameterRenderComponent/`
- `components/common/` (icons, headers, layouts)
- Misc (everything else)

Save the bundles with their call-site lists to `/tmp/p7-shadtooltip-bundles.json` for subagent dispatch.

### Task 2.2 — Dispatch parallel subagents

- [ ] **Step 1: For each bundle, dispatch one parallel subagent**

Each subagent receives:
- The bundle's surface-area name and the list of files it owns
- The exact `<ShadTooltip>` → `<Tooltip><TooltipTrigger asChild><TooltipContent>` conversion recipe
- Hard constraints (only edit listed files; don't touch the wrapper itself; no commits)
- Verification step (typecheck filtered to its files)

Conversion recipe to embed in every subagent prompt:

```
For each <ShadTooltip ...>{children}</ShadTooltip> in your files:

Old:
<ShadTooltip side={X} content={Y} delayDuration={Z}>
  {trigger}
</ShadTooltip>

New:
<Tooltip delayDuration={Z}>
  <TooltipTrigger asChild>{trigger}</TooltipTrigger>
  <TooltipContent side={X}>{Y}</TooltipContent>
</Tooltip>

Imports change:
- DELETE: import ShadTooltip from "@/components/common/shadTooltipComponent";
- ADD: import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
  (Don't add if already imported.)

Edge cases:
- If `delayDuration` prop is absent in the original, omit it from the new <Tooltip> too — Radix's default applies.
- If `content` prop value is JSX (not a string), preserve the JSX tree verbatim inside <TooltipContent>.
- If the original has `<ShadTooltip>` wrapping a forwardRef'd component that doesn't accept ref correctly, asChild may need a Slot wrapper — this is rare but flag if encountered.
- If the trigger is a primitive HTML element like `<button>` (not a forwardRef'd component), `asChild` works fine.
```

Subagents do their bundle's edits, then run `npm run type-check` filtered to the changed files. Report back with class-removed counts and any edge cases.

- [ ] **Step 2: Wait for all subagents to report**

If any subagent reports BLOCKED, investigate. Common issues:
- `TooltipProvider` not in scope at a specific surface → controller adds one.
- `content` prop has a complex JSX subtree the subagent isn't sure about → controller reviews manually.

Don't proceed until every subagent reports DONE.

### Task 2.3 — Sweep: confirm `ShadTooltip` is gone everywhere

- [ ] **Step 1: Run the sweep**

```bash
grep -rln "ShadTooltip\|shadTooltipComponent" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: zero output. If anything remains, it's a missed call site or a stale import — track down and fix.

- [ ] **Step 2: Delete the wrapper directory**

```bash
git rm -r src/frontend/src/components/common/shadTooltipComponent/
```

If TypeScript exports any `ShadTooltipProps` or similar from a shared types file, find and delete:

```bash
grep -rln "ShadTooltipProps\|ShadTooltipType" src/frontend/src --include="*.ts" --include="*.tsx"
```
For each remaining reference, delete the type or reroute to `ui/tooltip` types.

### Task 2.4 — Commit 2 verification gate

- [ ] **Step 1: Typecheck + jest + build**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
cd src/frontend && npm run test -- --silent 2>&1 | tail -5
cd src/frontend && npm run build 2>&1 | tail -3
```
Expected: only pre-existing failures, build clean. If any new failures, STOP.

- [ ] **Step 2: Sweep**

```bash
grep -rln "ShadTooltip\|shadTooltipComponent" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l
```
Expected: 0.

```bash
ls src/frontend/src/components/common/shadTooltipComponent 2>&1
```
Expected: "No such file or directory".

### Task 2.5 — Commit 7b

- [ ] **Step 1: Stage explicit paths**

```bash
git status --short | awk '{print $NF}' > /tmp/p7-7b-changed.txt
cat /tmp/p7-7b-changed.txt | head -20
echo "Total: $(wc -l < /tmp/p7-7b-changed.txt)"
git add $(cat /tmp/p7-7b-changed.txt)
```

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 7b — inline shadTooltipComponent

Replace the ShadTooltip wrapper at every call site with direct use of
Tooltip / TooltipTrigger / TooltipContent from ui/tooltip. Delete the
common/shadTooltipComponent/ directory.

The wrapper added a memoization layer (Radix is already optimized) and
a thin prop-passing API. Removing it is consistent with the Phase 5
accordionComponent inline pattern.

Phase 7b of docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log -1 --stat | head -10
```

---

## Task 3 — Commit 3: 7c — static-name icon inlines

**Files:**
- Modify: ~150-170 caller files (the static-name subset of ~197 `<ForwardedIconComponent name=...>` sites)
- DO NOT delete `ForwardedIconComponent`. Keep it for the 24 dynamic-name sites.

### Task 3.1 — Build the static-name → lucide-export map

- [ ] **Step 1: Extract every static-name call**

```bash
grep -rEn '<(Forwarded)?IconComponent[[:space:]]+name="[a-zA-Z]' src/frontend/src --include="*.tsx" \
  > /tmp/p7-icon-static-raw.txt
wc -l /tmp/p7-icon-static-raw.txt
```

Expected: ~173 lines (matches Task 0 baseline).

- [ ] **Step 2: Extract unique `name` values**

```bash
sed -E 's/.*name="([^"]+)".*/\1/' /tmp/p7-icon-static-raw.txt | sort -u > /tmp/p7-icon-names.txt
wc -l /tmp/p7-icon-names.txt
```

Expected: ~70-100 unique icon names.

- [ ] **Step 3: Verify each name exists in lucide-react**

Write a Python script to check each name against `node_modules/lucide-react`:

```python
# /tmp/p7-icon-name-check.py
import json, os, re
WORKTREE = "/Users/brycedeneen/dev/langflow/.worktrees/tailwind-phase-7"
LUCIDE_INDEX = f"{WORKTREE}/src/frontend/node_modules/lucide-react/dist/lucide-react.d.ts"

with open(LUCIDE_INDEX) as f:
    lucide_d_ts = f.read()

with open("/tmp/p7-icon-names.txt") as f:
    names = [n.strip() for n in f if n.strip()]

found, missing = [], []
for n in names:
    # Lucide exports are PascalCase; the wrapper's `name` prop already uses PascalCase
    pattern = re.compile(r"\b" + re.escape(n) + r"\b")
    if pattern.search(lucide_d_ts):
        found.append(n)
    else:
        missing.append(n)

with open("/tmp/p7-icon-found.txt", "w") as f:
    for n in found:
        f.write(n + "\n")

with open("/tmp/p7-icon-missing.txt", "w") as f:
    for n in missing:
        f.write(n + "\n")

print(f"Found in lucide: {len(found)}")
print(f"Missing (likely app-specific icons): {len(missing)}")
print("Missing names:")
for n in missing[:30]:
    print(f"  - {n}")
```

```bash
python3 /tmp/p7-icon-name-check.py
```

Expected: most names found in lucide; a small minority (5-20) missing because they're app-specific icons in `src/frontend/src/icons/`.

- [ ] **Step 4: For missing names, decide treatment**

For each missing name:
- If the app has a corresponding icon component in `src/frontend/src/icons/<Name>/index.tsx` — that name is dynamic-lookup-handled by `ForwardedIconComponent`, leave the call site alone.
- If the missing name is a typo or a deprecated icon — flag in the commit message, don't try to fix.

Save the "convertible" list (found in lucide) for Task 3.2:

```bash
cp /tmp/p7-icon-found.txt /tmp/p7-icon-convertible.txt
```

### Task 3.2 — Bucket the static-name sites for parallel dispatch

- [ ] **Step 1: Filter call sites to those whose name is convertible**

```bash
python3 -c "
with open('/tmp/p7-icon-convertible.txt') as f:
    convertible = set(n.strip() for n in f if n.strip())

import re
with open('/tmp/p7-icon-static-raw.txt') as f:
    sites = [ln.rstrip() for ln in f if ln.strip()]

with open('/tmp/p7-icon-convertible-sites.txt', 'w') as out:
    for ln in sites:
        m = re.search(r'name=\"([^\"]+)\"', ln)
        if m and m.group(1) in convertible:
            out.write(ln + '\n')
print(f'Convertible call sites: {sum(1 for _ in open(\"/tmp/p7-icon-convertible-sites.txt\"))}')
"
```

- [ ] **Step 2: Group by file, then bucket files into ~8 surface-area bundles**

```bash
cut -d: -f1 /tmp/p7-icon-convertible-sites.txt | sort -u > /tmp/p7-icon-files.txt
wc -l /tmp/p7-icon-files.txt
```

Expected: ~100-130 unique files. Bundle them by surface area (similar grouping to Task 2.1's bundles for shadTooltip).

### Task 3.3 — Dispatch parallel subagents

- [ ] **Step 1: For each bundle, dispatch one parallel subagent**

Each subagent receives:
- Its bundle's file list and the call sites within those files (filtered to convertible names only)
- The conversion recipe
- The list of "non-convertible" names (so the subagent KNOWS to leave those untouched)
- Hard constraints (don't modify `ForwardedIconComponent` itself; no commits)

Conversion recipe:

```
For each <ForwardedIconComponent name="X" {...other props}/> in your files
where X is in the convertible-names list:

Old:
import ForwardedIconComponent from "@/components/common/genericIconComponent";
...
<ForwardedIconComponent name="X" className="..." size={20} />

New:
import { X } from "lucide-react";
...
<X className="..." size={20} />

Other-props handling:
- Preserve every prop verbatim except `name`.
- If an existing import from lucide-react is in the file, add the new icon to the existing destructured import (alphabetize the import members).
- If after the conversion the file has zero remaining <ForwardedIconComponent> uses, REMOVE the `import ForwardedIconComponent` line.
- If the file has at least one remaining <ForwardedIconComponent> use (a dynamic-name site or a non-convertible name site), KEEP the ForwardedIconComponent import.

Names to leave alone (non-convertible):
[list embedded from /tmp/p7-icon-missing.txt]
```

- [ ] **Step 2: Wait for all subagents to report**

Each reports per-class call-site count converted, lucide imports added, and any ForwardedIconComponent imports removed.

### Task 3.4 — Sweep + Commit 3 verification

- [ ] **Step 1: Sweep**

```bash
# Count remaining static-name sites — should drop to near-zero (only the non-convertible ones)
grep -rEn '<(Forwarded)?IconComponent[[:space:]]+name="[a-zA-Z]' src/frontend/src --include="*.tsx" | wc -l
```

Expected: < 30 (the non-convertible app-specific icons).

```bash
# Dynamic-name count should be unchanged
grep -rEn '<(Forwarded)?IconComponent[^>]*name=\{' src/frontend/src --include="*.tsx" | wc -l
```

Expected: same as baseline (~24).

- [ ] **Step 2: Typecheck + jest + build**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
cd src/frontend && npm run test -- --silent 2>&1 | tail -5
cd src/frontend && npm run build 2>&1 | tail -3
```
Expected: only pre-existing failures, build clean.

If a subagent imported a lucide name that isn't actually exported (the audit script may have produced a false-positive against the lucide types file), the build catches it. Fix the offending file's import.

### Task 3.5 — Commit 7c

- [ ] **Step 1: Stage explicit paths and commit**

```bash
git status --short | awk '{print $NF}' > /tmp/p7-7c-changed.txt
echo "Total: $(wc -l < /tmp/p7-7c-changed.txt)"
git add $(cat /tmp/p7-7c-changed.txt)
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 7c — static-name icon inlines

Replace static-name <ForwardedIconComponent name="X" /> uses with direct
imports from lucide-react. Affects ~150-170 call sites across ~100 files.
Bundle benefits from tree-shaking the lucide imports.

Dynamic-name sites (~24) keep using ForwardedIconComponent for runtime
icon lookup. App-specific icons (in src/icons/) also keep using the wrapper.

Phase 7c of docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Commit 4: 7d — small-wrapper audit

**Files:** Determined by per-wrapper audit results.

### Task 4.1 — Per-wrapper audit

For each of the 3 wrappers:

- [ ] **Step 1: Read the wrapper file**

```bash
cat src/frontend/src/components/ui/refreshButton.tsx
cat src/frontend/src/components/ui/dialog-with-no-close.tsx
cat src/frontend/src/components/ui/disclosure.tsx
```

Identify:
- The exported component(s) and their public API
- Whether the wrapper has real behavior (state, refs, complex composition) or is a thin styled-primitive

- [ ] **Step 2: Build precise caller list per wrapper**

For each wrapper, run a Python audit (similar to Phase 4's audit, with longest-first regex for prefix safety):

```bash
python3 -c "
import re, os
WORKTREE = '/Users/brycedeneen/dev/langflow/.worktrees/tailwind-phase-7/src/frontend/src'
EXPORTS = {
    'refreshButton': ['RefreshButton'],
    'dialog-with-no-close': ['DialogWithNoClose'],
    'disclosure': ['Disclosure', 'DisclosurePanel', 'DisclosureButton'],
}
for wrapper, exports in EXPORTS.items():
    print(f'=== {wrapper} ===')
    callers = set()
    for export in exports:
        pattern = re.compile(r'\b' + re.escape(export) + r'\b')
        for root, dirs, files in os.walk(WORKTREE):
            dirs[:] = [d for d in dirs if d != 'node_modules']
            for fn in files:
                if not fn.endswith(('.ts', '.tsx')):
                    continue
                full = os.path.join(root, fn)
                if wrapper in full and full.endswith(f'{wrapper}.tsx'):
                    continue  # skip wrapper file itself
                with open(full, encoding='utf-8', errors='replace') as f:
                    text = f.read()
                if pattern.search(text):
                    callers.add(full)
    print(f'  callers: {len(callers)}')
    for c in sorted(callers)[:15]:
        print(f'    {c.replace(WORKTREE, \"\")}')
"
```

Expected output: a per-wrapper count and sample list.

- [ ] **Step 3: For each wrapper, apply the decision matrix**

- `0 real callers` → DELETE the wrapper file. Skip remaining steps for that wrapper.
- `1-3 real callers` AND wrapper body has no behavior beyond styling a primitive → INLINE the wrapper at the call sites and delete the wrapper file.
- `>3 real callers` OR wrapper has real behavior → KEEP. Add a one-line comment to the wrapper file explaining its role if not already obvious.

Document each decision in `/tmp/p7-7d-decisions.txt`:

```
refreshButton: KEEP (24 callers, has X behavior)
dialog-with-no-close: INLINE (2 callers, thin styled primitive)
disclosure: DELETE (after 7a conversion, 0 callers — was already on the chopping block)
```

(The above is illustrative; the actual decisions depend on the audit results.)

### Task 4.2 — Execute decisions per wrapper

- [ ] **Step 1: For each "DELETE" decision**

```bash
git rm src/frontend/src/components/ui/<wrapper>.tsx
```

Verify no remaining imports:
```bash
grep -rln "from.*<wrapper>" src/frontend/src --include="*.ts" --include="*.tsx"
```
Expected: empty.

- [ ] **Step 2: For each "INLINE" decision**

For each call site of the wrapper:
1. Open the call site file.
2. Replace the wrapper component with its inlined body.
3. Migrate any internal imports (the wrapper's imports become the call site's imports).
4. Update the call site to use the inlined props directly.

Then `git rm` the wrapper file.

- [ ] **Step 3: For each "KEEP" decision**

If the wrapper file lacks a top comment explaining its role, add one:

```tsx
// <Wrapper>: <one-sentence role>. Used by <N> callers across <surface area>.
```

### Task 4.3 — Commit 4 verification

- [ ] **Step 1: Typecheck + jest + build**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
cd src/frontend && npm run test -- --silent 2>&1 | tail -5
cd src/frontend && npm run build 2>&1 | tail -3
```
Expected: only pre-existing failures.

- [ ] **Step 2: Sweep — for any DELETED wrapper, no remaining references**

```bash
# For each wrapper that was deleted, confirm no callers remain
# (skip this step for wrappers that were KEEP)
for w in refreshButton dialog-with-no-close disclosure; do
  if [ ! -f "src/frontend/src/components/ui/${w}.tsx" ]; then
    count=$(grep -rln "from.*${w}\|${w^}" src/frontend/src --include="*.ts" --include="*.tsx" | wc -l | tr -d ' ')
    echo "$w (deleted): residual references = $count"
  fi
done
```

Expected: `residual references = 0` for every deleted wrapper.

### Task 4.4 — Commit 7d

- [ ] **Step 1: Stage and commit**

```bash
git status --short | awk '{print $NF}' > /tmp/p7-7d-changed.txt
git add $(cat /tmp/p7-7d-changed.txt)
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 7d — small-wrapper audit

Per-wrapper decisions (refreshButton, dialog-with-no-close, disclosure):
[summarize the decisions from /tmp/p7-7d-decisions.txt — fill in actual
results from the audit].

Wrappers identified as dead are removed. Thin wrappers with ≤3 callers
are inlined at call sites. Used wrappers (>3 callers or real behavior)
are kept with a top-level role comment.

Phase 7d of docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Commit 5: 7e — conservative palette consolidation

**Files:**
- Modify: `src/frontend/src/style/index.css` (the `@theme` block and possibly `:root`/`.dark` blocks)
- Modify (if any consolidation requires renaming a token used elsewhere): the call-site files

### Task 5.1 — Audit per-token

- [ ] **Step 1: Resolve each `--color-*` to its final value in both `:root` and `.dark`**

Write a Python script that:
1. Parses `index.css` to find every `--color-*` declaration in the `@theme` block.
2. For each, traces `var(--foo)` chains through `:root { ... }` and `.dark { ... }` blocks separately.
3. Records the final value in light mode and dark mode.

```python
# /tmp/p7-color-resolve.py
import re

with open("/Users/brycedeneen/dev/langflow/.worktrees/tailwind-phase-7/src/frontend/src/style/index.css") as f:
    text = f.read()

# Extract all --foo: VALUE; declarations from each block
def extract_block(name):
    """Return dict of var-name -> raw-value string for the block."""
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*\{{(.*?)^\}}", re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    if not m:
        return {}
    block = m.group(1)
    return dict(re.findall(r"--([a-zA-Z0-9_-]+):\s*([^;]+);", block))

theme = extract_block("@theme")
root = extract_block(":root")
dark = extract_block("\\.dark")

def resolve(value, scope, depth=0):
    """Recursively resolve var() references against `scope`."""
    if depth > 5:
        return value
    m = re.match(r"^\s*var\(--([a-zA-Z0-9_-]+)\)\s*$", value)
    if m and m.group(1) in scope:
        return resolve(scope[m.group(1)], scope, depth + 1)
    # Inside hsl(var(...)) or rgba(var(...)) — keep wrapper, resolve inner
    m2 = re.match(r"^\s*(hsl|rgba|rgb)\(var\(--([a-zA-Z0-9_-]+)\)\)\s*$", value)
    if m2 and m2.group(2) in scope:
        return f"{m2.group(1)}({resolve(scope[m2.group(2)], scope, depth + 1)})"
    return value.strip()

# For every theme color token, resolve in light and dark scopes
for name, value in theme.items():
    if not name.startswith("color-"):
        continue
    light = resolve(value, root)
    darkv = resolve(value, dark) if dark else light
    print(f"{name}\t{light}\t{darkv}")
```

```bash
python3 /tmp/p7-color-resolve.py > /tmp/p7-color-resolved.tsv
wc -l /tmp/p7-color-resolved.tsv
```

Expected: ~125 lines (matches Task 0 baseline).

- [ ] **Step 2: Group by (light_value, dark_value) — find duplicate pairs**

```bash
python3 -c "
from collections import defaultdict
groups = defaultdict(list)
with open('/tmp/p7-color-resolved.tsv') as f:
    for ln in f:
        parts = ln.rstrip().split('\t')
        if len(parts) != 3: continue
        name, light, dark = parts
        groups[(light, dark)].append(name)

print('=== Tokens sharing identical (light, dark) values ===')
for (l, d), names in sorted(groups.items()):
    if len(names) > 1:
        print(f'  light=[{l}] dark=[{d}]:')
        for n in names:
            print(f'    {n}')
"
```

Expected: a list of duplicate groups. Many will be intentional (e.g., `--color-foreground` and `--color-input-foreground` may both resolve to the same value in both modes but serve different roles).

- [ ] **Step 3: Apply the keep-list filter**

For each duplicate group, classify:
- **Both names role-distinct (KEEP both):** if both names match the keep-list pattern (`--color-status-*`, `--color-note-*`, `--color-flow-*`, `--color-chat-*`, `--color-datatype-*`, `--color-accent-*`, `--color-{selected,hover,ring,border,input,background,foreground,placeholder*}`, `--adp-red`, etc.), keep both. Document the "two distinct roles, identical value" case as a comment near the tokens in `index.css`.
- **One role-distinct, one not:** keep the role-distinct one, mark the other for consolidation.
- **Neither role-distinct:** mark both as candidates; pick the more-descriptive name to keep, mark the other for consolidation.

Save the consolidation list to `/tmp/p7-color-consolidate.txt`:
```
<delete-name> -> <keep-name>
```

- [ ] **Step 4: Stop if list is empty**

If after the keep-list filter there are zero consolidation candidates, skip Tasks 5.2 and 5.3 — there's nothing to do for 7e. Make a note in the commit message that conservative analysis found no obvious duplicates worth consolidating, and Commit 5 is a no-op (skip it; just note in the chain).

### Task 5.2 — Apply consolidations

For each `<delete-name> -> <keep-name>` pair:

- [ ] **Step 1: Update call sites that use the deleted token**

```bash
grep -rln "<delete-name>" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css"
```

For each result, replace the deleted-token name with the keep-name. The token name appears in:
- Tailwind class: `bg-<delete-name-suffix>` → `bg-<keep-name-suffix>`
- CSS: `var(--<delete-name>)` → `var(--<keep-name>)`

Note: Tailwind class names use the part after `--color-`. So if `--color-foo` is deleted in favor of `--color-bar`, then `bg-foo` becomes `bg-bar` in JSX.

- [ ] **Step 2: Delete the token from `index.css`**

Edit the `@theme` block: remove the `--<delete-name>: ...;` line.
If the `--delete-name`'s right-hand side referenced a `:root` / `.dark` variable that's now orphaned, also delete that.

### Task 5.3 — Commit 5 verification

- [ ] **Step 1: Re-run resolve and confirm token count dropped**

```bash
python3 /tmp/p7-color-resolve.py | wc -l
```

Expected: less than the 125 baseline.

- [ ] **Step 2: Typecheck + jest + build**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -5
cd src/frontend && npm run test -- --silent 2>&1 | tail -5
cd src/frontend && npm run build 2>&1 | tail -3
```
Expected: only pre-existing failures.

- [ ] **Step 3: Sweep — every deleted token has zero remaining references**

```bash
while read -r line; do
  delete_name=$(echo "$line" | awk '{print $1}')
  count=$(grep -rln "${delete_name}" src/frontend/src --include="*.ts" --include="*.tsx" --include="*.css" | wc -l | tr -d ' ')
  if [ "$count" -gt 0 ]; then
    echo "ORPHAN: $delete_name still referenced ($count files)"
  fi
done < /tmp/p7-color-consolidate.txt
```

Expected: empty (no ORPHAN lines).

### Task 5.4 — Commit 7e (or skip if no-op)

- [ ] **Step 1: If consolidation list was non-empty, stage and commit**

```bash
git add src/frontend/src/style/index.css [+ any call-site files]
git commit -m "$(cat <<'EOF'
refactor(frontend): tailwind-max phase 7e — conservative palette consolidation

Consolidate N token pairs whose final values are identical in both light
and dark modes AND have no role distinction. Role-distinct semantic
tokens (status/note/flow/chat/accent/datatype, shadcn base, ADP brand)
are explicitly kept.

[summary of consolidations from /tmp/p7-color-consolidate.txt]

Phase 7e of docs/superpowers/specs/2026-04-26-tailwind-phase-7-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If empty: don't commit. Note in the chain summary that 7e analysis ran clean — no obvious duplicates after the keep-list filter.

---

## Task 6 — Final unified verification gate

**Files:** None modified.

After all 5 commits land (or 4, if 7e was a no-op), run the full verification gate against the cumulative state.

- [ ] **Step 1: Typecheck**

```bash
cd src/frontend && npm run type-check 2>&1 | tail -10
```
Expected: only the 2 pre-existing TagRead errors.

- [ ] **Step 2: Jest**

```bash
cd src/frontend && npm run test -- --silent 2>&1 | tail -8
```
Expected: only the 14 pre-existing `SaveAsTemplateModal.test.tsx` failures, ≥3105 pass.

- [ ] **Step 3: Production build**

```bash
cd src/frontend && npm run build 2>&1 | tail -8
```
Expected: clean.

- [ ] **Step 4: Per-piece counter check**

```bash
echo "=== 7a — framer-motion files (3 → 1) ==="
grep -rln "from ['\"]framer-motion['\"]" src/frontend/src --include="*.ts" --include="*.tsx"

echo "=== 7b — ShadTooltip references ==="
grep -rln "ShadTooltip\|shadTooltipComponent" src/frontend/src --include="*.ts" --include="*.tsx" | head
echo "  (expected: empty)"

echo "=== 7c — static-name ForwardedIconComponent count ==="
grep -rEn '<(Forwarded)?IconComponent[[:space:]]+name="[a-zA-Z]' src/frontend/src --include="*.tsx" | wc -l
echo "  (expected: drop from 173 to ≤30)"

echo "=== 7c — dynamic-name ForwardedIconComponent count (should be unchanged) ==="
grep -rEn '<(Forwarded)?IconComponent[^>]*name=\{' src/frontend/src --include="*.tsx" | wc -l
echo "  (expected: ~24, unchanged from baseline)"

echo "=== 7d — wrapper file presence ==="
ls -la src/frontend/src/components/ui/refreshButton.tsx \
       src/frontend/src/components/ui/dialog-with-no-close.tsx \
       src/frontend/src/components/ui/disclosure.tsx 2>&1 | head

echo "=== 7e — color token count ==="
awk '/^@theme/,/^}/' src/frontend/src/style/index.css | grep -cE "^\s*--color-"
echo "  (expected: ≤125, may equal 125 if 7e was a no-op)"
```

Compare each against the baseline captured in Task 0 Step 4.

- [ ] **Step 5: Comprehensive ORPHAN sweep**

Use the smart Python `\b`-aware scanner pattern from Phase 4 to find any class/component name that was deleted/inlined but is still referenced anywhere.

Specifically for the symbols this plan touched:
- `ShadTooltip`, `shadTooltipComponent`
- Each deleted wrapper from 7d
- Any deleted `--color-*` token from 7e

```bash
python3 -c "
import re, os
SYMBOLS_TO_CHECK = []
# Add ShadTooltip
SYMBOLS_TO_CHECK.append(('ShadTooltip', '7b wrapper'))
SYMBOLS_TO_CHECK.append(('shadTooltipComponent', '7b directory'))
# Add 7d wrappers (only those that were DELETED — read /tmp/p7-7d-decisions.txt)
try:
    with open('/tmp/p7-7d-decisions.txt') as f:
        for ln in f:
            if 'DELETE' in ln or 'INLINE' in ln:
                wrapper = ln.split(':')[0].strip()
                SYMBOLS_TO_CHECK.append((wrapper, '7d'))
except FileNotFoundError:
    print('No 7d decisions file (Task 4 skipped?)')
# Add 7e deleted tokens
try:
    with open('/tmp/p7-color-consolidate.txt') as f:
        for ln in f:
            parts = ln.split('->')
            if len(parts) == 2:
                deleted = parts[0].strip()
                SYMBOLS_TO_CHECK.append((deleted, '7e'))
except FileNotFoundError:
    print('No 7e consolidate file (Task 5 was no-op)')

WORKTREE = '/Users/brycedeneen/dev/langflow/.worktrees/tailwind-phase-7/src/frontend/src'
for sym, source in SYMBOLS_TO_CHECK:
    pattern = re.compile(r'\b' + re.escape(sym) + r'\b')
    hits = []
    for root, dirs, files in os.walk(WORKTREE):
        dirs[:] = [d for d in dirs if d != 'node_modules']
        for fn in files:
            if not fn.endswith(('.ts', '.tsx', '.css')):
                continue
            full = os.path.join(root, fn)
            try:
                with open(full, encoding='utf-8', errors='replace') as f:
                    for i, line in enumerate(f, 1):
                        if 'data-testid' in line:
                            continue
                        if pattern.search(line):
                            hits.append((full.replace(WORKTREE, ''), i))
            except Exception:
                pass
    if hits:
        print(f'  ORPHAN: {sym} ({source}) — {len(hits)} refs')
        for h in hits[:3]:
            print(f'    {h[0]}:{h[1]}')
print('Done.')
"
```

Expected: no ORPHAN lines.

If any orphan, investigate and fix before proceeding.

---

## Task 7 — Pause for smoke tests, then ff-merge + push + cleanup

**Files:** None modified.

- [ ] **Step 1: Compose chain summary for the user**

Pull together a short summary covering, for each commit:
- 7a: framer-motion file count 3 → 1; behavioral change: none.
- 7b: ShadTooltip wrapper deleted; ~108 call sites converted; behavioral change: none (Radix primitive's defaults match wrapper's defaults).
- 7c: ~150-170 static-name icon sites converted to direct lucide imports; ~24 dynamic-name sites unchanged.
- 7d: per-wrapper decisions [fill in from /tmp/p7-7d-decisions.txt].
- 7e: N token consolidations (or "no-op — no obvious duplicates after keep-list filter").
- Verification gate: typecheck/jest/build/sweep all clean.

- [ ] **Step 2: Pause and ask for ff-merge approval**

Ask the user verbatim:

*"All Phase 7 commits landed on `tailwind/phase-7`. Verification gate clean. Ready to ff-merge into `platform-multi-tenant` and push to `fork`. The merge will trigger Vite HMR in your main checkout. OK to proceed, or do you need time for smoke tests first?"*

**Wait for explicit approval before proceeding.**

- [ ] **Step 3: ff-merge into `platform-multi-tenant`**

```bash
cd /Users/brycedeneen/dev/langflow

# Pre-merge sanity
git merge-base --is-ancestor platform-multi-tenant tailwind/phase-7 \
  && echo "ff possible" || echo "NOT a strict descendant — STOP"

# Check for WIP overlap with files in our commit
git diff --name-only platform-multi-tenant tailwind/phase-7 > /tmp/p7-merge-files.txt
git status --short | awk '$1 ~ /M/ {print $2}' > /tmp/p7-wip-files.txt
comm -12 <(sort /tmp/p7-merge-files.txt) <(sort /tmp/p7-wip-files.txt)
```

If `comm` output is non-empty, there's WIP overlap. Use the stash → ff-merge → pop dance from earlier in the session:

```bash
# Only run this if there's WIP overlap:
git stash push -u -m "phase-7-merge-temp"
git merge --ff-only tailwind/phase-7
git stash pop
# Check for stash conflicts; if any, report and stop
git status --short | grep -E "^UU|^AA|^DD" && echo "STASH POP CONFLICT — investigate" || echo "stash pop clean"
```

If no WIP overlap, the merge is straightforward:

```bash
# No WIP overlap — direct ff-merge:
git merge --ff-only tailwind/phase-7
```

Verify post-merge:
```bash
git log -6 --oneline platform-multi-tenant
```
Expected: HEAD now points to the 7e (or 7d if 7e was no-op) commit, with the chain visible.

- [ ] **Step 4: Push to `fork` (NOT `origin`)**

```bash
git push fork platform-multi-tenant
```

**Critical:** push to `fork` (`brycedeneen/langflow-mt`), NOT `origin` (`langflow-ai/langflow`). The memory rule "No upstream PRs — never push or PR to langflow-ai/langflow" applies.

- [ ] **Step 5: Cleanup worktree + branch**

```bash
git worktree remove .worktrees/tailwind-phase-7
git branch -d tailwind/phase-7
```

Verify:
```bash
git worktree list
git branch --list "tailwind/*"
```
Expected: only the main checkout remains; no stray `tailwind/*` branches.

- [ ] **Step 6: Hand back to user**

Report:
- The new HEAD SHA on `platform-multi-tenant`.
- Per-commit diff stats (one line each, from `git log --stat`).
- Any followups created (e.g., dynamic-name icon sites that couldn't be converted, palette tokens that couldn't be consolidated, etc.).
- Suggest manual eyeball on the 5 anchor surfaces (flow canvas, playground, settings, admin users, admin orgs) plus any tooltip-heavy or icon-heavy pages.
