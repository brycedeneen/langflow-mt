# FU-3: Saved Templates Tab — Wire `/api/v1/templates` into New Flow modal

## Background

Template management Phase 1 shipped the `Template` SQL model, `/api/v1/templates`
CRUD, and the Save-as-Template modal, but the New Flow catalog gallery
(`src/frontend/src/modals/templatesModal/`) still reads only starter-project
flows from `useFlowsManagerStore.examples` (populated by `GET /api/v1/flows/basic_examples/`).

Rows created via Save-as-Template are therefore invisible in the New Flow modal.
This is known deferred follow-up FU-3.

## Goal

Give users a way to see and launch the templates they (or other superusers) have
saved via `POST /api/v1/templates`, without disturbing the existing starter
gallery rendering.

## Approach

Add a dedicated **"Saved Templates"** tab to the New Flow modal's nav. The tab
is fed by `useListTemplates()` (slim `TemplateRead` rows) and rendered with a new
card component styled around `icon` + `gradient`. On selection, fetch full
`TemplateReadDetail` (which contains `nodes`/`edges`) and hand the decoded data
to the existing `useAddFlow` flow.

### Why a dedicated tab rather than merging into "All templates"

- `TemplateRead` has no `tags` column, so templates cannot participate in the
  existing per-category filters.
- Starter flows and templates have incompatible shapes (bg images vs.
  icon/gradient, `FlowType.data.nodes` vs. `Template.nodes`). Merging would
  require a shape adapter whose only consumer is the gallery.
- The list endpoint returns all `platform`-scoped rows to every user; a
  dedicated surface makes that boundary explicit and future-proofs for Phase 2
  org-scoped templates.

## Changes

### 1. `modals/templatesModal/index.tsx`

- Append `{ title: "Saved Templates", icon: "Bookmark", id: "saved" }` to the
  first nav category (the group that already holds "Get started" and
  "All templates").
- Render `<SavedTemplatesContent … />` when `currentTab === "saved"`.
- Extend `handleCreateFromSelection(withAssist)`:
  - If `selectedTemplate` starts with `tpl:`, strip the prefix, call an
    imperative `api.get<TemplateReadDetail>(getURL("TEMPLATES") + "/" + id)`,
    build `{ name, description, data: { nodes, edges } }`, run `updateIds` on
    `data`, then `addFlow({ flow, built_with_assist: withAssist })`.
  - Existing branches (`"blank"` and starter-flow IDs) stay unchanged.
- `track()` call passes the template name (from the detail response) as
  `template` so analytics stay coherent.

### 2. `modals/templatesModal/components/SavedTemplatesContent/index.tsx` (new)

- Calls `useListTemplates()`.
- Loading state: lightweight skeleton grid (3 placeholder cards) matching the
  layout used in `TemplateCategoryComponent`.
- Empty state: centered copy "No saved templates yet. Save a flow as a template
  from the flow toolbar to see it here." — no action button.
- Error state: centered "Couldn't load saved templates" with a retry callback
  invoking `refetch` from the query hook.
- Populated state: a grid of `<SavedTemplateCardComponent />`.
- Accepts `selectedTemplate`, `onSelectTemplate`, `loading` props (same
  contract used by `TemplateContentComponent`).

### 3. `modals/templatesModal/components/SavedTemplateCardComponent/index.tsx` (new)

- Props: `template: TemplateRead`, `selected: boolean`, `onSelect: () => void`,
  `loading: boolean`.
- Renders a card with:
  - Gradient strip / background derived from `template.gradient` (fallback
    gradient when null).
  - Icon badge from `template.icon` via the shared icon renderer (fallback
    icon when null).
  - `template.name` as title.
  - `template.description` as supporting line (truncated after two lines).
- Uses the same selection ring / focus affordances as
  `TemplateGetStartedCardComponent` so the Action Bar's selection behavior is
  unchanged.
- `data-testid="saved-template-card-{id}"`.

### 4. Selection id scheme

- The modal's local `selectedTemplate: string | null` gains a `tpl:<uuid>`
  convention for rows from the Template API.
- `"blank"` and starter-flow UUIDs retain their existing meaning.
- Scheme is entirely modal-local; no contract leaks to backend or to
  `useAddFlow`.

### 5. Detail fetch

- Direct `api.get<TemplateReadDetail>` call, *not* `useGetTemplate()` — the
  list-page cache doesn't have the detail rows, and forcing a query hook at
  click-time adds timing ceremony without benefit.
- Wrapped in the same `setLoading(true) / finally setLoading(false)` sequence
  already used by `handleCreateFromSelection`.

### 6. Types

- Reuse `TemplateRead` / `TemplateReadDetail` from `@/types/template`.
- No new shared types needed.

## Out of Scope (explicit)

- Search / filter within the Saved Templates tab.
- Grouping saved templates by tag or category.
- Rendering saved templates inside the "All templates" tab.
- Edit / rename / delete actions on cards (covered by future FU for template
  management UI).
- Per-user filtering (Phase 1 is platform-scoped; every user sees every row).
- Pagination; lists are expected to remain small in Phase 1.
- Surfacing saved templates on the Get Started tab — those three cards remain
  hardcoded starter flows.

## Testing

Jest tests colocated in `__tests__` dirs next to each new component:

- `SavedTemplatesContent.test.tsx`
  - renders cards from a mocked `useListTemplates` response.
  - renders empty state when the list is `[]`.
  - renders error state when the query hook reports error, and calls `refetch`
    when the retry link is clicked.
- `SavedTemplateCardComponent.test.tsx`
  - renders name, description, icon, and applies gradient styling.
  - falls back gracefully when `icon`/`gradient`/`description` are null.
  - calls `onSelect` on click; shows selected state when `selected=true`.
- `TemplatesModal.test.tsx` (extended)
  - clicking the "Saved Templates" nav item switches `currentTab`.
  - selecting a saved-template card + clicking "Start building" calls
    `addFlow` with a flow object whose `data.nodes` / `data.edges` match the
    mocked `TemplateReadDetail` response.

## Migration / Rollout

- No backend changes; the endpoint already exists and returns the right data.
- No feature flag — the Saved Templates tab is harmless when the table is
  empty (empty-state copy guides the user).
- No DB migration.
