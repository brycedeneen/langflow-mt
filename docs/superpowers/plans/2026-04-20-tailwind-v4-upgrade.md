# Tailwind CSS v3 → v4 Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Langflow frontend from `tailwindcss@3.4.4` to `tailwindcss@^4`, then refactor to v4's idiomatic CSS-first configuration so `tailwind.config.mjs` and `postcss.config.js` can be deleted.

**Architecture:** Two phases on `platform-multi-tenant`. Phase C is a mechanical upgrade using the `@tailwindcss/upgrade` codemod, keeping `tailwind.config.mjs` alive via the v4 `@config` directive — lands as a working-state checkpoint commit. Phase B moves theme tokens to a CSS `@theme` block, converts inline plugins to `@utility`/`@custom-variant` declarations, loads remaining plugins via `@plugin`, and deletes the JS config entirely.

**Tech Stack:** Vite + React + TypeScript, Tailwind CSS v4, `@tailwindcss/vite` plugin, `tw-animate-css`, `@tailwindcss/forms`, `@tailwindcss/typography`.

**Reference spec:** [`docs/superpowers/specs/2026-04-20-tailwind-v4-upgrade-design.md`](../specs/2026-04-20-tailwind-v4-upgrade-design.md)

**User commit policy (memory-enforced):** NEVER commit without explicit permission. Every "Commit" step in this plan MUST pause and ask the user first.

---

## Phase C — v4 Compat Upgrade

### Task 1: Pre-flight verification

**Files:**
- Read: `src/frontend/package.json`, `src/frontend/tailwind.config.mjs`

- [ ] **Step 1: Confirm working tree is clean enough to isolate the upgrade diff**

Run: `git status --short`
Expected: any pre-existing changes are unrelated to Tailwind (e.g., starter project JSON edits on `platform-multi-tenant`). Note them, do not revert.

- [ ] **Step 2: Confirm current Tailwind version is v3**

Run: `cd src/frontend && npm ls tailwindcss`
Expected: `tailwindcss@3.4.x`. If not v3, STOP and alert the user — this plan assumes v3.

- [ ] **Step 3: Confirm `postcss.config.js` exists and matches the expected baseline**

Run: `cat src/frontend/postcss.config.js`
Expected output:
```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```
If different, STOP and alert the user.

---

### Task 2: Install v4 + swap CSS directives manually

**Why manual, not codemod:** the `@tailwindcss/upgrade` codemod failed three times against this project's JS config — v4's plugin-loader validator rejects rules that were fine under v3 (`:focus-visible` masquerading as utility, descendant-combinator selectors in `addUtilities`, the `e()` plugin-API helper used by the dynamic truncate generator). We migrate manually, which is also the path you'd end up on for any project with heavy custom plugins.

**Prep already done on this branch** (part of the Phase C commit in Task 8):
- `src/frontend/src/App.css`, `src/frontend/src/style/applies.css`, `src/frontend/src/style/index.css` each have a `@config "<relative-path>";` directive added above the `@tailwind` directives.
- `src/frontend/tailwind.config.mjs` had three non-class rules removed from the `addUtilities` plugin — `:focus-visible`, `.dark .theme-attribution ...`, `.dark .theme-attribution ... a` — and the identical styles added as plain CSS at the bottom of `src/frontend/src/style/index.css` (outside any `@layer`).

**Files:**
- Modify: `src/frontend/package.json` (via npm)
- Modify: `src/frontend/src/App.css`, `src/frontend/src/style/applies.css`, `src/frontend/src/style/index.css`

- [ ] **Step 1: Install Tailwind v4**

```bash
cd src/frontend && npm install --save-dev tailwindcss@^4
```

- [ ] **Step 2: Replace `@tailwind` directives in all three CSS entry files**

Three CSS files are imported as entry points in `src/index.tsx`. Each has its own `@tailwind base; @tailwind components; @tailwind utilities;` block that must be replaced with a single `@import "tailwindcss";`.

For each file, replace this exact three-line block:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```
with:
```css
@import "tailwindcss";
```

Files:
- `src/frontend/src/App.css` — `@import "./style/custom-ace-overrides.css";` and `@config "../tailwind.config.mjs";` stay at top.
- `src/frontend/src/style/applies.css` — `@config "../../tailwind.config.mjs";` stays at top.
- `src/frontend/src/style/index.css` — `@config "../../tailwind.config.mjs";` stays at top.

**Ordering in v4:** `@import "tailwindcss";` must come BEFORE `@config` for the config to be picked up. After this step the top of each file should look like:
```css
@import "tailwindcss";
@config "<relative-path>";
```
If `@config` was above `@tailwind` in the current file (the controller's prep put it there), swap so `@import` is first.

- [ ] **Step 3: Do NOT commit yet.**

---

### Task 3: Install and register the `@tailwindcss/vite` plugin

v4 uses a first-class Vite plugin instead of PostCSS. Simpler and faster than keeping PostCSS around.

**Files:**
- Modify: `src/frontend/vite.config.mts`
- Delete: `src/frontend/postcss.config.js`
- Modify: `src/frontend/package.json` (via npm)

- [ ] **Step 1: Install the Vite plugin**

```bash
cd src/frontend && npm install --save-dev @tailwindcss/vite@^4
```

Expected: adds `"@tailwindcss/vite": "^4.x.x"` to `devDependencies`.

- [ ] **Step 2: Register the Vite plugin**

Edit `src/frontend/vite.config.mts`. Add the import and register in the `plugins` array.

Change the import block from:
```ts
import react from "@vitejs/plugin-react-swc";
import * as dotenv from "dotenv";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";
```
to:
```ts
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import * as dotenv from "dotenv";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";
```

Change `plugins: [react(), svgr()]` to `plugins: [tailwindcss(), react(), svgr()]`.

- [ ] **Step 3: Delete `postcss.config.js`**

```bash
rm src/frontend/postcss.config.js
```

Verify nothing else in the frontend references it:
```bash
grep -r "postcss.config" src/frontend --exclude-dir=node_modules --exclude-dir=build 2>/dev/null
```
Expected: no matches (or only matches in lockfiles/comments — human-verify).

---

### Task 4: Package.json cleanup — remove dead plugins

**Files:**
- Modify: `src/frontend/package.json`

- [ ] **Step 1: Remove unused/obsolete plugins**

Run from `src/frontend/`:
```bash
npm uninstall @tailwindcss/container-queries @tailwindcss/line-clamp tailwindcss-dotted-background autoprefixer
```

Rationale:
- `@tailwindcss/container-queries` — built into v4 core.
- `@tailwindcss/line-clamp` — built into v3.3+; not actually imported by `tailwind.config.mjs`; just a stale dep.
- `tailwindcss-dotted-background` — not referenced anywhere in the codebase; confirmed unused.
- `autoprefixer` — v4 auto-prefixes via Lightning CSS. PostCSS config is gone too.

- [ ] **Step 2: Confirm the remaining Tailwind-family deps**

Run: `cd src/frontend && npm ls | grep -Ei 'tailwind|autoprefixer|postcss'`

Expected state:
- `tailwindcss@^4.x.x` (in `devDependencies`)
- `@tailwindcss/vite@^4.x.x` (in `devDependencies`)
- `@tailwindcss/forms` (dependencies — still there, still used)
- `@tailwindcss/typography` (devDependencies — still there, still used)
- `tailwindcss-animate` (devDependencies — still there; replaced in Task 5)
- `postcss` (devDependencies — still there; safe to leave, other tooling may transitively use it. Do not remove.)
- NO `autoprefixer`, NO `@tailwindcss/container-queries`, NO `@tailwindcss/line-clamp`, NO `tailwindcss-dotted-background`, NO `@tailwindcss/postcss`.

---

### Task 5: Replace `tailwindcss-animate` with `tw-animate-css`

`tailwindcss-animate` is unmaintained and incompatible with v4. The community drop-in replacement `tw-animate-css` exposes the same API.

**Files:**
- Modify: `src/frontend/package.json`
- Modify: `src/frontend/tailwind.config.mjs:8`

- [ ] **Step 1: Swap the package**

Run from `src/frontend/`:
```bash
npm uninstall tailwindcss-animate && npm install --save-dev tw-animate-css
```

- [ ] **Step 2: Update the import in `tailwind.config.mjs`**

Open `src/frontend/tailwind.config.mjs`. Change line 8 from:
```js
import tailwindcssAnimate from "tailwindcss-animate";
```
to:
```js
import tailwindcssAnimate from "tw-animate-css";
```

The variable name stays the same — the plugin registration in the `plugins` array does not change.

---

### Task 6: Drop dead config from `tailwind.config.mjs`

**Files:**
- Modify: `src/frontend/tailwind.config.mjs`

- [ ] **Step 1: Remove the `variants` block**

Tailwind removed the `variants` config in v3. The block is dead code. Delete lines 12-17 of `src/frontend/tailwind.config.mjs`:

Remove:
```js
  variants: {
    extend: {
      display: ["group-hover"],
      textColor: ["group-increment-hover", "group-decrement-hover"],
    },
  },
```

- [ ] **Step 2: Remove the `tailwindcss-dotted-background` plugin**

In `src/frontend/tailwind.config.mjs`:

Delete line 9 (`import tailwindcssDottedBackground from "tailwindcss-dotted-background";`).

In the `plugins` array (around line 488), delete the line `tailwindcssDottedBackground,`.

Verify the rest of the plugins array is intact: `tailwindcssContainerQueries, tailwindcssAnimate, tailwindcssForms({...}), plugin(...), tailwindcssTypography, plugin(...), plugin(...)`.

Note: `tailwindcssContainerQueries` still imports from `@tailwindcss/container-queries`, which we uninstalled. Leave the import/usage for now — it will be removed in Task 7.

- [ ] **Step 3: Remove the `@tailwindcss/container-queries` plugin**

v4 has container queries in core (`@container`, `@md:`, etc.). The plugin's job is done.

In `src/frontend/tailwind.config.mjs`:

Delete line 3: `import tailwindcssContainerQueries from "@tailwindcss/container-queries";`.

In the `plugins` array, delete `tailwindcssContainerQueries,`.

---

### Task 7: Build, rename deprecated classes, smoke test

Without the codemod, we do the deprecated-class renames ourselves. Some renames are mandatory (v4 removed the old names) and will break the build until fixed. Others are visual-parity renames (v4 shifted default scales) and only show up in smoke testing.

**Files:**
- Modify: files across `src/frontend/src/` identified by targeted greps

- [ ] **Step 1: First build to flush out hard errors**

```bash
cd src/frontend && npm run build 2>&1 | tee /tmp/tw-build.log
```

If the build succeeds outright, go to Step 3. If it fails with "unknown utility" errors, go to Step 2.

- [ ] **Step 2: Rename deprecated utility classes (only those that v4 strictly removed)**

Run these targeted greps from the repo root (worktree root). Each finds usages of a class name that changed in v4:

| v3 class | v4 class | Rationale |
|---|---|---|
| `bg-opacity-X` | `bg-*/X` | Opacity modifiers moved to slash syntax |
| `text-opacity-X` | `text-*/X` | same |
| `border-opacity-X` | `border-*/X` | same |
| `flex-grow` | `grow` | renamed |
| `flex-shrink` | `shrink` | renamed |
| `overflow-ellipsis` | `text-ellipsis` | renamed |
| `decoration-slice` | `box-decoration-slice` | renamed |
| `decoration-clone` | `box-decoration-clone` | renamed |

For each entry, run:
```bash
grep -rn "\\b<v3-class>\\b" src/frontend/src/ --include='*.ts' --include='*.tsx' --include='*.html' 2>/dev/null
```
If hits found, Edit each file to replace.

Rerun `npm run build`. If more "unknown utility" errors appear, address them one-by-one (grep + Edit + re-build).

- [ ] **Step 3: Rename visual-parity classes (shadows, outlines)**

v4 shifted the shadow scale and changed `outline-none`. Without these renames the app builds but looks subtly wrong.

Shadow scale (v3 → v4 equivalent to preserve visual appearance):
- `shadow-sm` → `shadow-xs`
- `shadow` (no suffix) → `shadow-sm`
- `shadow-md` → (unchanged, still `shadow-md`)
- `shadow-lg` → (unchanged)

Outline:
- `outline-none` → `outline-hidden` (v4's `outline-none` now means `outline-style: none`; `outline-hidden` preserves the old behavior of a transparent outline for accessibility)

For each rename:
```bash
grep -rn "\\b<v3-class>\\b" src/frontend/src/ --include='*.ts' --include='*.tsx' --include='*.html' 2>/dev/null | wc -l
```
Then Edit each file. Be careful with `shadow` (the no-suffix form) — use word-boundary grep and inspect each hit before replacing since "shadow" may appear in unrelated contexts.

- [ ] **Step 4: Border default color change**

v4 defaults `border-*` utilities with no explicit color to `currentColor` instead of `gray-200`. Places that relied on the implicit default will now inherit text color (often black), visually darker/jarring. To identify at-risk sites:
```bash
grep -rn "\\bborder\\b\\|\\bborder-[trbl]\\b\\|\\bborder-x\\b\\|\\bborder-y\\b" src/frontend/src/ --include='*.ts' --include='*.tsx' 2>/dev/null | grep -v "border-" | head -30
```
For visual parity, add `border-border` (Tailwind-friendly shorthand for `hsl(var(--border))`) to any element that previously relied on the gray-200 default. This step is fix-as-you-see — do it during smoke testing, not up front, unless the build complains.

- [ ] **Step 5: Rebuild and type-check**

```bash
cd src/frontend && npm run build
cd src/frontend && npm run type-check
```
Both must exit 0.

- [ ] **Step 6: Start the dev server and smoke-test**

```bash
cd src/frontend && npm start
```

Open the app (default http://localhost:3000). Walk through this checklist:

1. Landing/home view renders without broken layout.
2. Open the flow builder / canvas. Create a new flow. The canvas dot background renders (uses `canvas` / `canvas-dot` colors).
3. Drag a node onto the canvas. Node shell, ring/border, icon colors look correct in both light and dark mode (toggle via user menu).
4. Open a modal — e.g., the API modal from the flow toolbar. Shadow, border, backdrop render correctly.
5. Open the templates modal from the home screen. Cards render; hover states visible.
6. Navigate to Admin → Users. Table renders, badges render.
7. Navigate to Admin → Organizations (if membership allows). List renders.
8. Open the embed modal. Styled correctly.
9. Toggle dark mode; repeat spot-checks.
10. Numeric input spinners (intComponent, floatComponent) — hover states change color correctly.
11. `truncate-background`, `truncate-muted`, `truncate-canvas`, `truncate-secondary-hover` utilities still work (inputListComponent, session-selector).

Any visible regression is a FAIL. Note it, then either fix inline (obvious: missing border-gray-200, collapsed shadow) or STOP and alert the user for non-obvious cases.

- [ ] **Step 7: Stop the dev server**

Ctrl-C.

---

### Task 8: Commit Phase C checkpoint

**Files:**
- Commit: all modified files from Tasks 2-6

- [ ] **Step 1: Review the full diff one more time**

Run from the repo root:
```bash
git status
git diff --stat src/frontend/
```

Expected: changes to `src/frontend/package.json`, `src/frontend/package-lock.json`, `src/frontend/vite.config.mts`, `src/frontend/tailwind.config.mjs`, `src/frontend/src/App.css`, `src/frontend/src/style/applies.css`, `src/frontend/src/style/index.css`, manual class renames across `src/frontend/src/`, and deletion of `src/frontend/postcss.config.js`. Also includes the plan file (`docs/superpowers/plans/2026-04-20-tailwind-v4-upgrade.md`) if updated during execution.

- [ ] **Step 2: Ask the user before committing**

The user's memory rule: never commit without permission. Show the user the summary and ask:

> "Phase C is ready: Tailwind v4 + Vite plugin + JS config via `@config` compat. Build passes, smoke test clean. The diff touches ~N files. Want me to commit it as the Phase C checkpoint?"

Wait for explicit "yes" before running the commit.

- [ ] **Step 3: Commit (only after user says yes)**

Stage only frontend files (not the unrelated starter-project JSON changes flagged in Task 1):
```bash
git add src/frontend/
```

Commit:
```bash
git commit -m "$(cat <<'EOF'
build(frontend): upgrade tailwind to v4 (compat mode)

Manual v4 migration (the @tailwindcss/upgrade codemod rejects this
project's plugin config). Install @tailwindcss/vite plugin, swap
@tailwind directives for @import "tailwindcss" in App.css, applies.css,
and style/index.css, and keep tailwind.config.mjs via @config directive.

Also: drop postcss.config.js + autoprefixer (v4 auto-prefixes), remove
unused @tailwindcss/container-queries (built in), @tailwindcss/line-
clamp (built in, unused), and tailwindcss-dotted-background (unused).
Swap tailwindcss-animate for tw-animate-css. Extract three non-class
rules out of the addUtilities plugin and into plain CSS so v4's
stricter validator accepts the config. Rename deprecated utilities
that v4 removed.

CSS-first refactor follows in phase B.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Verify: `git log --oneline -1` shows the new commit; `git status` shows working tree clean (or only the pre-existing starter-project JSON changes).

---

## Phase B — Idiomatic CSS-First Refactor

### Task 9: Verify `@tailwindcss/forms` actually has consumers

The current config uses `strategy: "class"`, which means the plugin only styles elements that explicitly opt in via `.form-input`, `.form-select`, `.form-checkbox`, etc. If no code uses those classes, the plugin is dead weight.

**Files:**
- Read-only: `src/frontend/src/**/*.{ts,tsx,html,css}`

- [ ] **Step 1: Grep for form plugin class usage**

Run from repo root:
```bash
grep -rE "\\bform-(input|select|multiselect|textarea|checkbox|radio)\\b" src/frontend/src/ --include='*.ts' --include='*.tsx' --include='*.html' --include='*.css' 2>/dev/null | head -20
```

- [ ] **Step 2: Record the decision**

If the grep returns matches → keep `@tailwindcss/forms`, load via `@plugin` in Task 17.

If the grep returns zero matches → remove `@tailwindcss/forms` from dependencies and skip the `@plugin "@tailwindcss/forms"` line in Task 17. Run:
```bash
cd src/frontend && npm uninstall @tailwindcss/forms
```

Note the decision in a comment for the remaining tasks. For the remainder of this plan, the term "FORMS_PLUGIN_KEPT" refers to this boolean decision — Task 17 checks it.

---

### Task 10: Build the `@theme` block — colors (scalar + flattened objects)

This is the bulk of the theme migration. `theme.extend.colors` becomes `--color-*` CSS custom properties inside a single `@theme` block in `src/style/index.css`.

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Locate insertion point**

`src/style/index.css` currently starts with (after Phase C):
```css
@import "tailwindcss";
@config "../../tailwind.config.mjs";

@layer base {
  :root { ... }
  .dark { ... }
}
```

The `@theme` block goes **between** the `@config` line and `@layer base`. We will eventually delete the `@config` line in Task 19 once everything has moved.

- [ ] **Step 2: Add the `@theme` block with color tokens**

Insert this block immediately after `@config "../../tailwind.config.mjs";` (a blank line between them):

```css
@theme {
  /* Static scalar colors */
  --color-frozen-blue: rgba(128, 190, 219, 0.86);
  --color-frosted-glass: rgba(255, 255, 255, 0.8);
  --color-component-icon: var(--component-icon);
  --color-flow-icon: var(--flow-icon);
  --color-low-indigo: var(--low-indigo);
  --color-chat-send: var(--chat-send);
  --color-connection: var(--connection);
  --color-almost-dark-gray: var(--almost-dark-gray);
  --color-almost-light-blue: var(--almost-light-blue);
  --color-almost-medium-gray: var(--almost-medium-gray);
  --color-almost-medium-green: var(--almost-medium-green);
  --color-almost-medium-red: var(--almost-medium-red);
  --color-btn-shadow: var(--round-btn-shadow);
  --color-build-trigger: var(--build-trigger);
  --color-chat-trigger: var(--chat-trigger);
  --color-chat-trigger-disabled: var(--chat-trigger-disabled);
  --color-dark-blue: var(--dark-blue);
  --color-dark-gray: var(--dark-gray);
  --color-dark-red: var(--dark-red);
  --color-high-dark-gray: var(--high-dark-gray);
  --color-high-indigo: var(--high-indigo);
  --color-high-light-gray: var(--high-light-gray);
  --color-info-background: var(--info-background);
  --color-info-foreground: var(--info-foreground);
  --color-light-blue: var(--light-blue);
  --color-light-gray: var(--light-gray);
  --color-light-slate: var(--light-slate);
  --color-medium-blue: var(--medium-blue);
  --color-status-blue: var(--status-blue);
  --color-medium-dark-gray: var(--medium-dark-gray);
  --color-medium-dark-green: var(--medium-dark-green);
  --color-medium-dark-red: var(--medium-dark-red);
  --color-medium-emerald: var(--medium-emerald);
  --color-medium-gray: var(--medium-gray);
  --color-medium-high-indigo: var(--medium-high-indigo);
  --color-medium-indigo: var(--medium-indigo);
  --color-medium-low-gray: var(--medium-low-gray);
  --color-status-green: var(--status-green);
  --color-status-red: var(--status-red);
  --color-status-yellow: var(--status-yellow);
  --color-status-gray: var(--status-gray);
  --color-success-background: var(--success-background);
  --color-success-foreground: var(--success-foreground);
  --color-accent-pink-foreground: hsl(var(--accent-pink-foreground));
  --color-accent-purple-foreground: hsl(var(--accent-purple-foreground));
  --color-accent-red-foreground: hsl(var(--accent-red-foreground));
  --color-chat-bot-icon: var(--chat-bot-icon);
  --color-chat-user-icon: var(--chat-user-icon);
  --color-ice: var(--ice);
  --color-selected: var(--selected);
  --color-hover: var(--hover);
  --color-discord-color: var(--discord-color);
  --color-slider-input-border: var(--slider-input-border);

  /* HSL-wrapped scalar colors */
  --color-note-amber: hsl(var(--note-amber));
  --color-note-neutral: hsl(var(--note-neutral));
  --color-note-rose: hsl(var(--note-rose));
  --color-note-blue: hsl(var(--note-blue));
  --color-note-lime: hsl(var(--note-lime));
  --color-border: hsl(var(--border));
  --color-input: hsl(var(--input));
  --color-ring: hsl(var(--ring));
  --color-error-red: hsl(var(--error-red));
  --color-error-red-border: hsl(var(--error-red-border));
  --color-node-selected: hsl(var(--node-selected));
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-emerald-smooth: hsl(var(--emaral-smooth));
  --color-emerald-hard: hsl(var(--emeral-hard));
  --color-placeholder: hsl(var(--placeholder));
  --color-hard-zinc: hsl(var(--hard-zinc));
  --color-smooth-red: hsl(var(--smooth-red));
  --color-placeholder-foreground: hsl(var(--placeholder-foreground));
  --color-code-background: hsl(var(--code-background));
  --color-code-description-background: hsl(var(--code-description-background));
  --color-code-foreground: hsl(var(--code-foreground));
  --color-node-ring: hsl(var(--node-ring));
  --color-neon-fuschia: hsl(var(--neon-fuschia));
  --color-digital-orchid: hsl(var(--digital-orchid));
  --color-plasma-purple: hsl(var(--plasma-purple));
  --color-electric-blue: hsl(var(--electric-blue));
  --color-holo-frost: hsl(var(--holo-frost));
  --color-terminal-green: hsl(var(--terminal-green));
  --color-cosmic-void: hsl(var(--cosmic-void));
  --color-zinc-foreground: hsl(var(--zinc-foreground));
  --color-red-foreground: hsl(var(--red-foreground));
  --color-indigo-foreground: hsl(var(--indigo-foreground));

  /* Object-shaped colors (flattened) */
  --color-error: var(--error);
  --color-error-background: var(--error-background);
  --color-error-foreground: var(--error-foreground);

  --color-warning: hsl(var(--warning));
  --color-warning-foreground: hsl(var(--warning-foreground));
  --color-warning-text: hsl(var(--warning-text));

  --color-filter-foreground: var(--filter-foreground);
  --color-filter-background: var(--filter-background);

  --color-beta-background: var(--beta-background);
  --color-beta-foreground: var(--beta-foreground);
  --color-beta-foreground-soft: var(--beta-foreground-soft);

  --color-canvas: hsl(var(--canvas));
  --color-canvas-dot: hsl(var(--canvas-dot));

  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-primary-hover: hsl(var(--primary-hover));

  --color-secondary: hsl(var(--secondary));
  --color-secondary-foreground: hsl(var(--secondary-foreground));
  --color-secondary-hover: hsl(var(--secondary-hover));

  --color-destructive: hsl(var(--destructive));
  --color-destructive-foreground: hsl(var(--destructive-foreground));

  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));

  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));

  --color-accent-amber: hsl(var(--accent-amber));
  --color-accent-amber-foreground: hsl(var(--accent-amber-foreground));

  --color-accent-emerald: hsl(var(--accent-emerald));
  --color-accent-emerald-foreground: hsl(var(--accent-emerald-foreground));
  --color-accent-emerald-hover: hsl(var(--accent-emerald-hover));

  --color-accent-indigo: hsl(var(--accent-indigo));
  --color-accent-indigo-foreground: hsl(var(--accent-indigo-foreground));

  --color-accent-blue: hsl(var(--accent-blue));
  --color-accent-blue-foreground: hsl(var(--accent-blue-foreground));

  --color-accent-pink: hsl(var(--accent-pink));
  --color-accent-pink-foreground: hsl(var(--accent-pink-foreground));

  --color-popover: hsl(var(--popover));
  --color-popover-foreground: hsl(var(--popover-foreground));

  --color-card: hsl(var(--card));
  --color-card-foreground: hsl(var(--card-foreground));

  --color-tooltip: hsl(var(--tooltip));
  --color-tooltip-foreground: hsl(var(--tooltip-foreground));

  --color-code-block: #18181B;
  --color-code-block-muted: #27272A;

  --color-datatype-yellow: hsl(var(--datatype-yellow));
  --color-datatype-yellow-foreground: hsl(var(--datatype-yellow-foreground));
  --color-datatype-blue: hsl(var(--datatype-blue));
  --color-datatype-blue-foreground: hsl(var(--datatype-blue-foreground));
  --color-datatype-gray: hsl(var(--datatype-gray));
  --color-datatype-gray-foreground: hsl(var(--datatype-gray-foreground));
  --color-datatype-lime: hsl(var(--datatype-lime));
  --color-datatype-lime-foreground: hsl(var(--datatype-lime-foreground));
  --color-datatype-red: hsl(var(--datatype-red));
  --color-datatype-red-foreground: hsl(var(--datatype-red-foreground));
  --color-datatype-violet: hsl(var(--datatype-violet));
  --color-datatype-violet-foreground: hsl(var(--datatype-violet-foreground));
  --color-datatype-emerald: hsl(var(--datatype-emerald));
  --color-datatype-emerald-foreground: hsl(var(--datatype-emerald-foreground));
  --color-datatype-fuchsia: hsl(var(--datatype-fuchsia));
  --color-datatype-fuchsia-foreground: hsl(var(--datatype-fuchsia-foreground));
  --color-datatype-purple: hsl(var(--datatype-purple));
  --color-datatype-purple-foreground: hsl(var(--datatype-purple-foreground));
  --color-datatype-cyan: hsl(var(--datatype-cyan));
  --color-datatype-cyan-foreground: hsl(var(--datatype-cyan-foreground));
  --color-datatype-indigo: hsl(var(--datatype-indigo));
  --color-datatype-indigo-foreground: hsl(var(--datatype-indigo-foreground));
}
```

Compare against `tailwind.config.mjs` lines 119-333 to confirm completeness — if the engineer sees a color in the JS config not in the CSS block above, STOP and add it to the plan before proceeding.

**Note:** Tailwind v4 color tokens must map `--color-<name>` to a valid CSS color. For colors that were `hsl(var(--x))` in the JS config, we keep the `hsl(...)` wrapper in the token. For colors that were already fully-formed (rgb/hex/keyword), no wrapping needed.

---

### Task 11: Extend the `@theme` block — fonts, shadows, sizes, radius, borders, spacing, blur, z-index, breakpoints

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Append to the `@theme` block (same block opened in Task 10) — before the closing `}`:**

```css
  /* Fonts */
  --font-sans: var(--font-sans), ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: var(--font-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --font-chivo: var(--font-chivo), ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;

  /* Shadows */
  --shadow-frozen-ring: 0 0 10px 2px rgba(128, 190, 230, 0.5);
  --shadow-node: 0 0px 15px -3px rgb(0 0 0 / 0.1), 0 0px 6px -4px rgb(0 0 0 / 0.1);
  --shadow-frosted-ring: 0 0 10px 2px rgba(128, 190, 230, 0.7);

  /* Text sizes */
  --text-xxs: 11px;
  --text-mmd: 13px;

  /* Border radius (preserve var-based expressions) */
  --radius-lg: var(--radius);
  --radius-md: calc(var(--radius) - 2px);
  --radius-sm: calc(var(--radius) - 4px);

  /* Backdrop blur */
  --blur-xs: 2px;

  /* Z-index */
  --z-60: 60;
  --z-70: 70;
  --z-80: 80;
  --z-90: 90;
  --z-100: 100;
  --z-999: 999;

  /* Breakpoints */
  --breakpoint-mdd: 720px;
  --breakpoint-xl: 1200px;
  --breakpoint-2xl: 1400px;
  --breakpoint-3xl: 1500px;
```

**Naming note on fractional tokens:** v4 CSS token names cannot contain `.`, so the original `w-4.5`, `h-4.5`, `border-1.5`, `border-1.75` class names no longer resolve. We do NOT add replacement tokens (awkward naming + vanishingly few usages). Instead, Task 18 inlines these four class patterns as arbitrary values (`w-[18px]`, `border-[1.5px]`, etc.).

- [ ] **Step 2: Add keyframes and animation tokens**

After the `@theme` block closes, add the keyframes as standard CSS (keyframes live outside `@theme`), then re-open a second `@theme` block just for animation tokens. v4 allows multiple `@theme` blocks; they are merged.

```css
@keyframes overlayShow {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes overlayHide {
  from { opacity: 1; }
  to   { opacity: 0; }
}
@keyframes contentShow {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.95);
    clip-path: inset(50% 0);
    box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.1);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
    clip-path: inset(0% 0);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  }
}
@keyframes contentHide {
  from {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
    clip-path: inset(0% 0);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.95);
    clip-path: inset(50% 0);
    box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.1);
  }
}
@keyframes wiggle {
  0%, 100% { transform: scale(100%); }
  50%      { transform: scale(120%); }
}
@keyframes jiggle {
  0%, 100% { transform: rotate(-1deg); }
  50%      { transform: rotate(1deg); }
}
@keyframes border-beam {
  100% { offset-distance: 100%; }
}
@keyframes pulse-pink {
  0%, 100% { background-color: hsla(var(--accent-pink), 1); }
  50%      { background-color: hsla(var(--accent-pink), 0.4); }
}

@theme {
  --animate-overlayShow: overlayShow 400ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-overlayHide: overlayHide 500ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-contentShow: contentShow 400ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-contentHide: contentHide 500ms cubic-bezier(0.16, 1, 0.3, 1);
  --animate-wiggle: wiggle 150ms ease-in-out 1;
  --animate-slow-wiggle: wiggle 500ms ease-in-out 1;
  --animate-pulse-pink: pulse-pink 2s linear infinite;
  --animate-jiggle: jiggle 150ms ease-in-out infinite;
  --animate-border-beam: border-beam calc(var(--duration) * 1s) infinite linear;
}
```

- [ ] **Step 3: Verify via build (still with `@config` active)**

Run: `cd src/frontend && npm run build`

Expected: succeeds. At this point both the `@theme` tokens and the `tailwind.config.mjs` are active; v4 merges them. If the CSS build flags a syntax error, fix it before proceeding.

---

### Task 12: Convert static inline utilities to `@utility` blocks

The first inline `plugin(({ addUtilities })...)` in `tailwind.config.mjs` (lines 383-487) defines static utility classes. These become v4 `@utility` declarations.

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Append `@utility` blocks to `index.css`**

After the second `@theme` block from Task 11, before the `@layer base { ... }` block, insert:

```css
@utility scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
}

@utility gutter-stable {
  scrollbar-gutter: stable;
}

@utility truncate-multiline {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

@utility truncate-doubleline {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

@utility word-break-break-word {
  word-break: break-word;
}

@utility arrow-hide {
  &::-webkit-datatype-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  &::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
}

@utility password {
  -webkit-text-security: disc;
  font-family: text-security-disc;
}

@utility stop {
  -webkit-animation-play-state: paused;
  -moz-animation-play-state: paused;
  animation-play-state: paused;
}

@utility custom-scroll {
  cursor: auto;
  &::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  &::-webkit-scrollbar-track {
    background-color: hsl(var(--muted));
  }
  &::-webkit-scrollbar-thumb {
    background-color: hsl(var(--border));
    border-radius: 999px;
  }
  &::-webkit-scrollbar-thumb:hover {
    background-color: hsl(var(--placeholder-foreground));
  }
  &::-webkit-scrollbar-corner {
    background-color: transparent;
  }
}

@utility text-align-last-left {
  text-align-last: left;
}

@utility text-align-last-right {
  text-align-last: right;
}

@utility note-node-markdown {
  line-height: 1;
  & ul li::marker {
    color: black;
  }
  & ol li::marker {
    color: black;
  }
  & h1, & h2, & h3, & h4, & h5, & h6, & p, & ul, & ol {
    margin-bottom: 0.25rem;
  }
}
```

- [ ] **Step 2: Move global (non-utility) rules out of the inline plugin**

The inline plugin also defined two global selector rules that are NOT tied to a utility class:

```css
.dark .theme-attribution .react-flow__attribution {
  background-color: rgba(255, 255, 255, 0.2);
  padding: 0px 5px;
}
.dark .theme-attribution .react-flow__attribution a {
  color: black;
}
:focus-visible {
  outline: none !important;
  outline-offset: 0px !important;
}
```

Add these three rules as plain CSS, placed immediately after the `@utility` blocks (above `@layer base`). They are global styles, not utilities.

- [ ] **Step 3: Verify build**

Run: `cd src/frontend && npm run build`

Expected: succeeds. If a utility clashes or the CSS parser balks, fix before proceeding.

---

### Task 13: Replace the dynamic per-color truncate generator with 4 static `@utility` blocks

The last inline `plugin(({ addUtilities, theme, e }) => {...})` in `tailwind.config.mjs` (lines 489-535) generates `.truncate-<color>` utilities for every color in the theme. Only 4 variants are actually used in the codebase:
- `truncate-background` (used in `inputListComponent/index.tsx`)
- `truncate-muted` (used in `session-selector.tsx`)
- `truncate-canvas` (used in `session-selector.tsx` with `dark:` prefix)
- `truncate-secondary-hover` (used in `session-selector.tsx`, also `group-hover:` variant)

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Append 4 static `@utility` blocks**

After the existing `@utility` blocks from Task 12:

```css
@utility truncate-background {
  position: relative;
  overflow: hidden;
  pointer-events: none;
  &::after {
    content: "";
    position: absolute;
    inset: 0 0 0 0;
    background: linear-gradient(to right, transparent 80%, hsl(var(--background)));
  }
}

@utility truncate-muted {
  position: relative;
  overflow: hidden;
  pointer-events: none;
  &::after {
    content: "";
    position: absolute;
    inset: 0 0 0 0;
    background: linear-gradient(to right, transparent 80%, hsl(var(--muted)));
  }
}

@utility truncate-canvas {
  position: relative;
  overflow: hidden;
  pointer-events: none;
  &::after {
    content: "";
    position: absolute;
    inset: 0 0 0 0;
    background: linear-gradient(to right, transparent 80%, hsl(var(--canvas)));
  }
}

@utility truncate-secondary-hover {
  position: relative;
  overflow: hidden;
  pointer-events: none;
  &::after {
    content: "";
    position: absolute;
    inset: 0 0 0 0;
    background: linear-gradient(to right, transparent 80%, hsl(var(--secondary-hover)));
  }
}
```

- [ ] **Step 2: Verify the `group-hover:truncate-secondary-hover` and `dark:truncate-canvas` variants resolve**

Both variants are v4 built-ins that work on any utility class, including custom ones. No extra config needed. Run the build to confirm:

```bash
cd src/frontend && npm run build
```

Expected: succeeds. If v4 reports `group-hover:truncate-secondary-hover` as unknown, STOP and alert the user.

---

### Task 14: Convert custom variants to `@custom-variant`

The fourth inline plugin (lines 536-539) registers two custom variants used by numeric input spinners.

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Append `@custom-variant` declarations**

After the `@utility` blocks:

```css
@custom-variant group-increment-hover (&:is(:merge(.group-increment):hover *));
@custom-variant group-decrement-hover (&:is(:merge(.group-decrement):hover *));
```

**Translation note:** The original JS plugin used `:merge(.group-increment):hover &`. In v4's `@custom-variant` DSL the target element is `&` and we write the selector from its perspective. The compiled form above expresses "when this element is a descendant of a hovered `.group-increment` group." If v4 syntax differs from what compiles, iterate — the test is that `group-increment-hover:text-*` classes in `intComponent/index.tsx` and `floatComponent/index.tsx` continue to work.

- [ ] **Step 2: Smoke-test the numeric input spinners**

Run `npm start`, navigate to a flow, add any node with an integer input (e.g. `IntComponent`). Hover the increment/decrement buttons — the color change on the spinner should be visible. If it does not change on hover, STOP and iterate the `@custom-variant` selector.

---

### Task 15: Load remaining plugins via `@plugin`

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Add `@plugin` directives**

Near the top of `src/style/index.css` — after the `@import "tailwindcss";` line but before the `@theme` block — add:

```css
@plugin "@tailwindcss/typography";
@plugin "tw-animate-css";
```

If Task 9 determined FORMS_PLUGIN_KEPT is true, also add `@plugin "@tailwindcss/forms";` to the list. The v4 plugin system currently has limited support for plugin options, so the `strategy: "class"` option may need to be inlined later; verify form inputs still render after the build.

- [ ] **Step 2: Verify build**

Run: `cd src/frontend && npm run build`

Expected: succeeds.

---

### Task 16: Replace the `safelist` with `@source inline`

The JS config had `safelist: ["bg-status-blue", "bg-status-green", "bg-status-red", "bg-status-yellow"]` because those classes are composed dynamically at runtime and the content scanner misses them.

**Files:**
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Add the source directive**

Near the top of `src/style/index.css`, after `@import "tailwindcss";`, add:

```css
@source inline("bg-status-{blue,green,red,yellow}");
```

- [ ] **Step 2: Verify via build**

Run: `cd src/frontend && npm run build` and then check that the generated CSS contains all four classes:

```bash
grep -E "bg-status-(blue|green|red|yellow)" src/frontend/build/assets/*.css | head -10
```

Expected: each of the four classes appears in the build output.

---

### Task 17: Delete `tailwind.config.mjs` and `@config` directive

**Files:**
- Delete: `src/frontend/tailwind.config.mjs`
- Modify: `src/frontend/src/style/index.css`

- [ ] **Step 1: Remove the `@config` directive**

Open `src/frontend/src/style/index.css`. Delete the line `@config "../../tailwind.config.mjs";`.

- [ ] **Step 2: Run the build with the `@config` removed but the file still present**

Run: `cd src/frontend && npm run build`

Expected: succeeds — everything the config provided now lives in CSS. If the build fails with "unknown utility" or "unknown color," a theme token is missing. STOP and add it to the `@theme` block. Common culprits: a color in the JS config not moved in Task 10, a keyframe not added in Task 11, or a utility that relied on the old plugin.

- [ ] **Step 3: Delete the config file**

Only after Step 2 succeeds:
```bash
rm src/frontend/tailwind.config.mjs
```

- [ ] **Step 4: Rebuild to confirm**

Run: `cd src/frontend && npm run build`

Expected: succeeds. This is the end state of Phase B.

---

### Task 18: Inline fractional-name utilities as arbitrary values

The v3 config defined `w-4.5`/`h-4.5`/`border-1.5`/`border-1.75` utilities. v4 CSS token names cannot contain `.`, so those class names no longer resolve. Replace each usage with arbitrary-value syntax.

**Files:**
- Modify: files identified by the grep below

- [ ] **Step 1: Find all usages**

Run:
```bash
grep -rn "\\bw-4\\.5\\b\\|\\bh-4\\.5\\b\\|\\bborder-1\\.5\\b\\|\\bborder-1\\.75\\b" src/frontend/src/ --include='*.ts' --include='*.tsx' 2>/dev/null
```

Record the full list before editing. If the result is zero lines, skip the rest of this task.

- [ ] **Step 2: Replace each occurrence**

For each line the grep returned, replace the class substring:
- `w-4.5` → `w-[18px]`
- `h-4.5` → `h-[18px]`
- `border-1.5` → `border-[1.5px]`
- `border-1.75` → `border-[1.75px]`

Use the Edit tool, one file at a time, verifying the surrounding context for each change.

- [ ] **Step 3: Rebuild**

Run: `cd src/frontend && npm run build`

Expected: succeeds.

- [ ] **Step 4: Re-grep to confirm no stragglers**

Run the same grep from Step 1 again. Expected: zero lines.

---

### Task 19: Type-check and smoke test

**Files:**
- None (verification)

- [ ] **Step 1: Type-check**

Run: `cd src/frontend && npm run type-check`

Expected: exits 0. Ctrl-C to stop the dev server chain.

- [ ] **Step 2: Run the dev server and repeat the Task 7 smoke checklist**

Run: `cd src/frontend && npm start`

Walk through the same checklist from Task 7, Step 3:
1. Landing view.
2. Flow builder canvas (dot background, node drop).
3. Node shell colors (light and dark mode).
4. API modal.
5. Templates modal.
6. Admin → Users.
7. Admin → Organizations.
8. Embed modal.
9. Dark mode toggle.

Pay extra attention to:
- Custom truncate utilities (`truncate-background`, etc.) — check `inputListComponent` and `session-selector` components.
- Spinner hover behavior on integer/float inputs (Task 14 variants).
- Numeric-size overrides (if Task 18 inlined anything).
- Animations (`animate-contentShow`, `animate-wiggle`, etc.) — fire modals, toasts.
- `@tailwindcss/forms` behavior if FORMS_PLUGIN_KEPT.

Any regression is a FAIL. STOP and alert the user with a specific description.

- [ ] **Step 3: Stop the dev server**

Ctrl-C.

---

### Task 20: Commit Phase B

**Files:**
- Commit: all modified files from Tasks 10-18

- [ ] **Step 1: Review the diff**

Run:
```bash
git status
git diff --stat src/frontend/
```

Expected: `src/frontend/src/style/index.css` heavily modified, `src/frontend/tailwind.config.mjs` deleted, possibly small edits in files touched by Task 18.

- [ ] **Step 2: Ask the user before committing**

> "Phase B is ready: theme migrated to CSS, all inline plugins converted, `tailwind.config.mjs` deleted. Build and type-check pass, smoke test clean. Want me to commit?"

Wait for explicit yes.

- [ ] **Step 3: Commit (only after user says yes)**

```bash
git add src/frontend/
git commit -m "$(cat <<'EOF'
refactor(frontend): migrate tailwind to idiomatic v4 CSS-first config

Move theme tokens (colors, fonts, shadows, sizes, radius, animations,
breakpoints) to @theme in src/style/index.css. Convert inline plugin
utilities to @utility blocks. Replace dynamic per-color truncate
generator with 4 static @utility blocks matching actual call sites.
Convert group-increment/decrement-hover to @custom-variant. Load
typography/animate (and forms, if kept) via @plugin. Replace runtime
safelist with @source inline. Delete tailwind.config.mjs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Verify: `git log --oneline -2` shows Phase C checkpoint and Phase B refactor as two distinct commits.

---

## End State

After Task 20:

1. `src/frontend/package.json` has `tailwindcss@^4`, `@tailwindcss/vite@^4`, `tw-animate-css`, `@tailwindcss/typography`, and — conditionally — `@tailwindcss/forms`.
2. Removed entirely: `autoprefixer`, `@tailwindcss/container-queries`, `@tailwindcss/line-clamp`, `tailwindcss-animate`, `tailwindcss-dotted-background`.
3. Files gone: `src/frontend/tailwind.config.mjs`, `src/frontend/postcss.config.js`.
4. All Tailwind config lives in `src/frontend/src/style/index.css` via `@import`, `@plugin`, `@source`, `@theme`, `@utility`, and `@custom-variant` directives.
5. Two commits on `platform-multi-tenant`: Phase C compat checkpoint + Phase B idiomatic refactor.
6. Build passes. Type-check passes. Manual smoke test clean.
