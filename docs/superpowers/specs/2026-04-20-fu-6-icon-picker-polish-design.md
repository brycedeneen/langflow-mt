## FU-6 — Icon Picker Polish

**Date:** 2026-04-20
**Status:** Design
**Scope:** Frontend rewrite of `IconPickerField` inside `SaveAsTemplateModal`. No backend changes.
**Parent spec:** [`2026-04-20-save-as-template-frontend-design.md`](./2026-04-20-save-as-template-frontend-design.md) §10 (FU-6)

---

### 1. Context

The Save-as-Template modal shipped on `platform-multi-tenant` with a placeholder `IconPickerField` that has three notable gaps:

1. **The trigger button and grid render the icon's name as a text string instead of the actual icon.** Users see `FileText`, not the SVG.
2. **No virtualization.** The naive grid renders ~3000 button elements when opened (the current filter over `lucide-react` exports is too permissive — the real renderable-icon count is closer to ~1500, but either is enough to make the popover sluggish).
3. **Plain substring search, no recents, no keyboard navigation.**

This spec defines the polish pass.

### 2. Goals

- **G1.** Render real icons everywhere the picker shows one (trigger and grid).
- **G2.** Search across the full lucide icon set with fuzzy ranking and instant filtering.
- **G3.** Keep the picker fast at the full ~1500-icon scale via virtualization.
- **G4.** Persist the user's most recent 8 icon picks to localStorage and surface them when no query is typed.
- **G5.** Full keyboard support (arrow nav, Enter to select, Escape to close).
- **G6.** Self-contained changes — no impact to the parent modal's API or other consumers.

### 3. Non-goals

- Custom icon upload (needs a backend asset store; deferred).
- Categorized icon groups ("Communication", "AI", etc.) — lucide doesn't ship categories and curating them defeats the breadth advantage.
- Icon recoloring beyond the existing swatch background.
- Internationalized icon search.
- Replacing icon usage elsewhere in the app — this work scopes only to the picker inside `SaveAsTemplateModal`.

### 4. Decisions captured from brainstorming

| # | Question | Answer |
|---|---|---|
| Q1 | Polish bundle | "Recommended" — render actual icons, virtualization, fuzzy search, recents |
| Q2 | Trigger button shape | Icon + name pill (`[icon] FileText ▾`) |
| Q3 | Recents UX | Top 8 in own row, hidden when query is non-empty |
| Q4 | Icon-set strategy | All lucide via `dynamicIconImports`; `react-window` virtualization |

### 5. Architecture

All changes colocated under `src/frontend/src/modals/SaveAsTemplateModal/`:

| File | Status | Purpose |
|---|---|---|
| `IconPickerField.tsx` | rewrite | Trigger button + Popover wrapper; composes the units below. Public API unchanged: `{ value: string; onChange: (name: string) => void }`. |
| `iconPicker/lucideIconNames.ts` | new | `LUCIDE_ICON_NAMES: string[]` derived from lucide-react's `dynamicIconImports` keys (the authoritative list of real icon components). PascalCase normalized for use with the existing `IconComponent`. |
| `iconPicker/useRecentIcons.ts` | new | `() => { recents: string[]; record: (name: string) => void }`. Hook over localStorage key `langflow.template.recentIcons`. LRU, deduped, capped at 8. Resilient to quota errors and malformed JSON. |
| `iconPicker/IconGrid.tsx` | new | Virtualized grid using `react-window`'s `FixedSizeGrid`. Receives a pre-filtered `names: string[]`, `selected`, `onSelect`. Renders cells via the existing `IconComponent` from `@/components/common/genericIconComponent`. Handles arrow-key navigation. |
| `__tests__/IconPickerField.test.tsx` | new | Component-level tests (§7.3). |
| `__tests__/useRecentIcons.test.ts` | new | Hook unit tests (§7.1). |
| `__tests__/lucideIconNames.test.ts` | new | Source list sanity tests (§7.2). |

Dependency add to `src/frontend/package.json`: `react-window` and `@types/react-window`. First usage of `react-window` in the repo — keep the integration self-contained inside `IconGrid.tsx` so a future replacement only touches one file.

The Popover frame and search input come from existing primitives:

- `@/components/ui/command` (the cmdk-based `Command` / `CommandInput` shadcn wrapper, already used in 5 places).
- `@/components/ui/popover` for the floating frame.

cmdk is used **with `shouldFilter={false}`** — it provides the search input + accessible chrome, but filtering and rendering are done by our code so virtualization isn't fought.

### 6. UX & data flow

#### 6.1 Trigger button (closed state)

```
[icon] FileText  ▾
```

- Existing `IconComponent` renders the swatch.
- Name in `text-sm`.
- Chevron from lucide (`ChevronDown`) signals it's a dropdown.
- shadcn `Button variant="outline"` for visual consistency with other modal form controls.
- `aria-label="Choose icon"`.

#### 6.2 Popover (open state)

Width ~340px, max height ~360px.

```
┌───────────────────────────────┐
│  🔍 Search icons…             │  ← cmdk CommandInput, autoFocus
├───────────────────────────────┤
│  Recents                      │  ← only when query is empty AND recents.length > 0
│  [i] [i] [i] [i] [i] [i] [i] [i]
├───────────────────────────────┤
│  All icons                    │
│  [virtualized grid, 6 cols]   │
│  …scroll…                     │
└───────────────────────────────┘
```

- Recents row is non-virtualized (max 8 cells).
- "All icons" grid uses `react-window`'s `FixedSizeGrid` with 6 columns and ~32px row height. Only ~30 cells live in the DOM at once.

#### 6.3 Filtering

- Lowercase substring match against icon name.
- Boost: matches that start with the query rank above mid-string matches.
- Otherwise stable alphabetical order.
- Implemented in a small pure helper (e.g. `iconPicker/filter.ts` or inlined into `IconPickerField`); cheap enough to run on every keystroke without debouncing for ~1500 items.
- We don't pull `fuse.js` for this — icon names are short and well-formed; substring + start-with boost is enough and avoids the indexing cost.

#### 6.4 Selection flow

1. User clicks an icon (mouse), or focuses a cell with arrow keys and hits Enter.
2. `onChange(name)` fires.
3. `recordRecent(name)` is called.
4. Popover closes; query state resets to empty so the next open is fresh.

#### 6.5 Keyboard nav

- cmdk owns the input focus, Escape, and the search-input keystrokes.
- The grid container handles `ArrowUp`/`ArrowDown`/`ArrowLeft`/`ArrowRight`/`Enter`/`Home`/`End` directly. cmdk's own item navigation is bypassed because items aren't `<CommandItem>` children (we use `shouldFilter={false}`).
- Tab moves focus from the search input to the first grid cell, then out of the popover (closing it).

#### 6.6 Empty state

`No icons match "{query}"` in `text-muted-foreground`. No "browse all" link — clearing the search achieves the same thing.

#### 6.7 Recents persistence

- Storage key: `langflow.template.recentIcons`.
- Format: JSON-encoded `string[]`, head = most recent.
- Cap: 8.
- Read on hook mount; write on every `record`.
- Stored names that are no longer in `LUCIDE_ICON_NAMES` are filtered out before display (defensive against future lucide changes).

#### 6.8 Default & migration

- Default value remains `"FileText"` to match the existing modal default. No data migration needed; the picker only writes a string back to `setIcon`.
- Existing localStorage entries from prior sessions (none today) would be respected.

### 7. Testing

Jest + React Testing Library, mirroring patterns already in use in the modal's existing test files.

#### 7.1 `useRecentIcons` unit tests

- Returns `[]` initially when localStorage is empty.
- `record(name)` adds to head; subsequent read returns it first.
- Recording the same name twice deduplicates (moves to head, list length unchanged).
- Cap enforced: recording a 9th unique name evicts the oldest.
- Malformed JSON in localStorage → returns `[]` and overwrites cleanly on next `record`.
- Quota-exceeded write → swallows the error; in-memory state still updates so the UI doesn't desync.
- Persists across hook re-mounts (read back from storage).

#### 7.2 `lucideIconNames` unit tests

- Returns a non-empty array of strings.
- Length is in the expected ballpark (>1000, <3000) — guards against silent regressions if lucide ships a breaking export change.
- Excludes obvious non-components (`createLucideIcon`, etc. — verified by absence).
- Spot-checks: well-known icon names like `FileText`, `Folder`, `Database` are present.

#### 7.3 `IconPickerField` component tests

- Trigger renders the selected icon **and** its name as text.
- Click trigger → popover opens, search input has focus.
- Type "fold" → "Folder" appears, unrelated icons (e.g. "Anchor") do not.
- Click an icon cell → `onChange` fires with that name and the popover closes.
- Reopen after a successful selection → that icon now appears in the recents row.
- Recents row is hidden whenever the search input value is non-empty.
- Empty results render the empty-state copy.
- Escape closes the popover.
- Arrow-key navigation moves focus through grid cells; Enter selects.

#### 7.4 Mocking notes

`react-window`'s `FixedSizeGrid` measures DOM size; in jsdom it sees `width=0, height=0` and renders zero cells. The component test file mocks `react-window` (`jest.mock("react-window", …)` replacing the grid with a plain wrapper that renders all items). This is a one-block setup at the top of the test file.

#### 7.5 Performance budget

Popover open-to-paint should land under ~100ms on a mid-tier laptop with the unfiltered ~1500-icon set. Virtualization renders ~30 cells at a time, well within budget. Spot-check during implementation; no automated perf test in scope.

### 8. Edge cases

- **Renamed/removed lucide icon between releases.** `IconComponent` already falls back gracefully to a default for unknown names. Recents containing now-stale names are filtered out before display.
- **localStorage disabled** (e.g. Safari private mode). `useRecentIcons` reads/writes silently fail; hook permanently returns `recents: []`. No crash.
- **Stored recents contain a name not in the current `LUCIDE_ICON_NAMES`.** Filtered out before render — no broken cell.
- **Rapid open/close.** Popover state is local; closing always resets the query and selection-focus state.

### 9. Risks

- **R1. cmdk + virtualization integration.** cmdk's filter ranking expects to own all `<CommandItem>` children. Mitigation: bypass cmdk's filter via `shouldFilter={false}` and use it only for the input + accessible search-input chrome. Risk is low because we're not asking cmdk to do anything outside its core role.
- **R2. `dynamicIconImports` is a relatively private lucide export.** If a future lucide release removes it, we fall back to a curated allowlist. The unit test that asserts a non-empty list catches this immediately on dependency bump.
- **R3. First `react-window` usage in the repo.** No existing pattern to follow. Mitigation: integration is fully contained in `IconGrid.tsx`; replacing the lib later means changing one file.

### 10. Out of scope (deferred to future work, not tracked here)

- Custom icon upload (requires backend asset store + validation pipeline).
- Categorized icon groups beyond Recents.
- Icon-color customization beyond the existing swatch background.
- Internationalized search (icon names are English; search is over name strings only).
- Sharing the picker with other parts of the app (catalog, component metadata, etc.) — possible follow-up if the picker proves valuable beyond the template modal.

### 11. Implementation plan

Out of scope for this spec. Plan will be written next via `superpowers:writing-plans` and saved to `docs/superpowers/plans/`.
