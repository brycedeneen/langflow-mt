# Tailwind CSS v3 → v4 Upgrade

**Date:** 2026-04-20
**Scope:** `src/frontend/` only. Docusaurus docs site (`docs/`) is out of scope.

## Goal

Upgrade the Langflow frontend from `tailwindcss@3.4.4` to `tailwindcss@^4`, and in a second phase, migrate to v4's idiomatic CSS-first configuration for long-term maintainability. Delete `tailwind.config.mjs` and `postcss.config.js`; all theme, utilities, plugins, and variants live in CSS.

## Current State

- `src/frontend/tailwind.config.mjs` — ~540 lines. Heavy custom theme keyed on HSL CSS variables (`--primary`, `--muted`, etc.), four inline `plugin()` calls, a dynamic per-color truncate utility generator.
- `src/frontend/postcss.config.js` — loads `tailwindcss` and `autoprefixer`.
- Plugins in use: `@tailwindcss/forms` (class strategy), `@tailwindcss/typography`, `@tailwindcss/container-queries`, `tailwindcss-animate`, plus inline plugins.
- Unused (remove): `@tailwindcss/line-clamp`, `tailwindcss-dotted-background`.
- Storybook has only one story; Chromatic coverage is effectively nil.

## Approach

Two phases, two distinct commit states on `platform-multi-tenant`:

- **Phase C** — mechanical v4 upgrade using the `@tailwindcss/upgrade` codemod. Keep `tailwind.config.mjs` alive via v4's `@config` directive for backwards compatibility. Land as a known-working checkpoint.
- **Phase B** — idiomatic refactor: move theme tokens into a CSS `@theme` block, convert inline plugins to `@utility` / `@custom-variant` declarations, load remaining JS plugins via `@plugin`, delete `tailwind.config.mjs` and `postcss.config.js`.

Regression guard: manual smoke testing of the flow builder, nodes, modals, and admin pages. Storybook expansion for future Chromatic coverage is tracked as separate follow-up work.

## Phase C — v4 Compat Upgrade

**Steps:**

1. `cd src/frontend && npx @tailwindcss/upgrade@latest` on a clean tree. Review the diff — the codemod handles class renames (`shadow-sm` → `shadow-xs`, `outline-none` → `outline-hidden`, `bg-opacity-*` shorthand, explicit `border-gray-200` where v4's `currentColor` default would change behavior).
2. Switch build integration to the Vite plugin:
   - `vite.config.ts`: import and register `@tailwindcss/vite`.
   - Delete `src/frontend/postcss.config.js`.
3. Replace `@tailwind base; @tailwind components; @tailwind utilities;` in `src/style/index.css` with `@import "tailwindcss";` + `@config "../../tailwind.config.mjs";`.
4. Package.json edits in `src/frontend/package.json`:
   - Remove: `tailwindcss@^3`, `autoprefixer`, `@tailwindcss/container-queries`, `@tailwindcss/line-clamp`, `tailwindcss-dotted-background`.
   - Add: `tailwindcss@^4`, `@tailwindcss/vite@^4`, `tw-animate-css`.
   - Keep: `@tailwindcss/forms`, `@tailwindcss/typography`, `tailwindcss-animate` (replaced in step 5).
5. In `tailwind.config.mjs`, swap `import tailwindcssAnimate from "tailwindcss-animate"` → `import tailwindcssAnimate from "tw-animate-css"` (same API).
6. Drop dead config in `tailwind.config.mjs`: the `variants.extend` block (removed in Tailwind v3 — dead code), and the `tailwindcssDottedBackground` import/plugin registration.
7. `npm run build` + `npm run type-check` must succeed. Manual smoke: flow builder canvas, node creation/edit, one modal (API modal), admin pages (users, organizations), templates modal. No visible regressions.
8. Commit as "Phase C checkpoint" — **pause and ask the user before committing**.

**Risk areas to eyeball during smoke:**
- Borders previously inheriting gray-200 (v4 defaults to `currentColor`). The codemod usually patches this; verify cards, inputs, node outlines.
- Shadow scale shifted — containers may look slightly flatter.
- Ring widths on focus (3px → 1px default).
- Form inputs via `@tailwindcss/forms` class strategy — should be unaffected.

## Phase B — Idiomatic CSS-First Refactor

**Steps:**

1. **Move theme tokens → `@theme` block in `src/style/index.css`:**
   - Flatten object-shaped colors: `primary: { DEFAULT, foreground, hover }` becomes `--color-primary`, `--color-primary-foreground`, `--color-primary-hover`. Same for `secondary`, `destructive`, `muted`, `accent`, `accent-*`, `popover`, `card`, `tooltip`, `datatype-*`, `canvas`, `beta`, `filter`, `warning`, `error`, `code-block`.
   - Scalar colors (`status-blue`, `frozen-blue`, etc.) → `--color-<name>: <value>;`.
   - Fonts → `--font-sans`, `--font-mono`, `--font-chivo`.
   - Shadows → `--shadow-frozen-ring`, `--shadow-node`, `--shadow-frosted-ring`.
   - Font sizes → `--text-xxs`, `--text-mmd`.
   - Border radius → `--radius-lg`, `--radius-md`, `--radius-sm` (preserving the `var(--radius)`-based expressions).
   - Border widths → `--border-1.5`, `--border-1.75`.
   - Spacing → `--spacing-4.5: 18px;`.
   - Backdrop blur → `--blur-xs: 2px;`.
   - Z-index → `--z-60`…`--z-999`.
   - Container breakpoints → `--breakpoint-mdd: 720px;`, `--breakpoint-xl: 1200px;`, `--breakpoint-2xl: 1400px;`, `--breakpoint-3xl: 1500px;`.
   - Keyframes (`overlayShow`, `overlayHide`, `contentShow`, `contentHide`, `wiggle`, `jiggle`, `border-beam`, `pulse-pink`) → `@keyframes` blocks, referenced by `--animate-<name>` tokens.

2. **Static utilities → `@utility` blocks** (converted from the first inline `plugin()` call):
   - `scrollbar-hide`, `gutter-stable`, `truncate-multiline`, `truncate-doubleline`, `word-break-break-word`, `arrow-hide`, `password`, `stop`, `custom-scroll`, `text-align-last-left`, `text-align-last-right`, `note-node-markdown`.
   - Global rules in that same plugin (`:focus-visible`, `.dark .theme-attribution .react-flow__attribution`) are not utilities — move to a plain CSS block in `index.css` or `applies.css`.

3. **Dynamic truncate generator → 4 static `@utility` blocks.** Only 4 variants are used in the codebase (`truncate-background`, `truncate-muted`, `truncate-canvas`, `truncate-secondary-hover`). The generator currently produces ~60 unused utilities; drop it entirely.

4. **Custom variants → `@custom-variant`:**
   ```css
   @custom-variant group-increment-hover (&:is(:merge(.group-increment):hover &));
   @custom-variant group-decrement-hover (&:is(:merge(.group-decrement):hover &));
   ```

5. **Remaining JS plugins → `@plugin` directives:**
   ```css
   @plugin "@tailwindcss/forms";
   @plugin "@tailwindcss/typography";
   @plugin "tw-animate-css";
   ```
   Verify `@tailwindcss/forms` is actually pulling its weight — the class strategy only activates on explicit `.form-*` class usage. If grep finds no `.form-*` references, drop the plugin.

6. **Safelist replacement.** The current `safelist: ["bg-status-blue", "bg-status-green", "bg-status-red", "bg-status-yellow"]` covers classes composed dynamically at runtime. Replace with v4's source directive:
   ```css
   @source inline("bg-status-{blue,green,red,yellow}");
   ```

7. **Delete:**
   - `src/frontend/tailwind.config.mjs`
   - The `@config` directive from `src/style/index.css` (no longer needed).

8. `npm run build` + `npm run type-check` must succeed. Repeat the manual smoke test. Regressions here are most likely around theme variable naming (a missed color mapping = a missing class).

9. Commit as "Phase B idiomatic refactor" — **pause and ask the user before committing**.

## Files Impacted

**Phase C:**
- `src/frontend/package.json` — dependency swaps
- `src/frontend/vite.config.ts` — add `@tailwindcss/vite`
- `src/frontend/postcss.config.js` — deleted
- `src/frontend/tailwind.config.mjs` — trim `variants`, `tailwindcssDottedBackground`; swap animate plugin
- `src/frontend/src/style/index.css` — replace `@tailwind` directives with `@import` + `@config`
- `src/frontend/src/**/*.{ts,tsx,css}` — codemod-driven class renames (volume depends on codebase)

**Phase B:**
- `src/frontend/src/style/index.css` — absorbs theme, utilities, variants, plugin loads
- `src/frontend/tailwind.config.mjs` — deleted
- `src/frontend/src/style/applies.css`, `classes.css` — inspect for conflicts with the new theme (edit only if needed)

**Not touched:**
- `docs/` — Docusaurus site's own Tailwind setup, separate upgrade
- `.worktrees/*` — other in-flight branches

## Success Criteria

1. `cd src/frontend && npm run build` succeeds with no Tailwind warnings.
2. `npm run type-check` passes.
3. `npm start` runs; manual smoke test passes with no visible regressions: flow builder, node creation/edit, API modal, admin (users + organizations), templates modal.
4. At end of Phase B, these are gone from the repo: `tailwind.config.mjs`, `postcss.config.js`, `autoprefixer`, `tailwindcss@3`, `@tailwindcss/container-queries`, `@tailwindcss/line-clamp`, `tailwindcss-animate`, `tailwindcss-dotted-background`.
5. Two distinct commit states on `platform-multi-tenant`: Phase C checkpoint + Phase B refactor.

## Out of Scope / Deferred

- Docusaurus docs site Tailwind upgrade.
- Storybook story expansion (tracked as separate follow-up task).
- Chromatic setup changes.
- Any visual redesign — purity of behavior is the goal, not refreshed styling.
