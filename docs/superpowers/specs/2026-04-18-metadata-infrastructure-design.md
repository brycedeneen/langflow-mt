# Metadata Infrastructure (Flow + Component)

**Date:** 2026-04-18
**Status:** Draft

## Overview

A shared metadata layer that lets platform super-admins author AI-oriented prompt guidance for two kinds of entities: **starter-project flows** (templates) and **components**. The guidance is consumed by the ADP Assist assistant — it rides along with the existing catalog tools for components and is injected into the assistant's system prompt (with an on-demand tool call for full instructions) for templates.

This supersedes Section 3 ("Template Metadata Extensions") of the ADP Assist spec (`2026-04-18-adp-assist-flow-builder-design.md`): that section described a `TemplateMetadata` table and admin UI. This spec preserves that design and adds the symmetric `ComponentMetadata` layer so both live in one admin page and one implementation plan, avoiding duplicated scaffolding.

All admin surfaces are gated by the existing `is_superuser` flag on `User` and the existing `get_current_active_superuser` auth dependency — no new role is introduced.

## Key Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Field shape | Two free-form text fields: `agent_usage_notes` + `agent_summary` | Symmetric with the TemplateMetadata design from the ADP Assist spec; admins don't have to decide where info goes; can add structured columns later additively. |
| Scope | **Global** (no `organization_id` column) | YAGNI — components and starter templates are code-shared across orgs today. Adding a nullable `organization_id` later is a cheap additive migration. |
| Table structure | **Two separate tables** sharing a SQLModel mixin | FK integrity for templates (flows exist as DB rows); `component_name` is a string (components are code). Polymorphic single-table loses FK integrity without saving meaningful code. |
| Template → LLM | Inject all summaries into system prompt + `get_template_instructions(flow_id)` tool for full notes | Templates are low-cardinality (~10-20); summaries fit in the prompt; full notes fetched on demand when a template is picked. |
| Component → LLM | Inline merge into existing `search_components` + `get_component_schema` catalog tools | High-cardinality (~100+) rules out prompt injection; a separate tool risks being skipped. Inline merge guarantees the LLM sees the guidance exactly when it's reasoning about a component. |
| Admin UI | Single page with two tabs: **"Flow and Component Management"** | One route, one mental model; tabs keep the two lists visually distinct because their metadata (flow vs component) differs. |
| Orphan handling (components) | Keep orphan rows, mark them in the UI with a manual "Remove orphan" button | Safer than auto-delete (a rename can look like a removal); cheap UI affordance is sufficient at this scale. |
| Caching | None in v1 | Read-heavy, small tables. Profile first; cache later if warranted. |

## Architecture

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   template_metadata      │         │   component_metadata     │
│   (FK: flow_id → flows)  │         │   (UNIQUE: component_name)│
│   agent_usage_notes      │         │   agent_usage_notes      │
│   agent_summary          │         │   agent_summary          │
│   (shared mixin)         │         │   (shared mixin)         │
└──────────┬───────────────┘         └──────────┬───────────────┘
           │                                    │
           ▼                                    ▼
    ┌─────────────────────────────────────────────────┐
    │  /api/v1/admin/metadata/*  (superuser only)     │
    │  list / get / upsert (PUT) / delete             │
    └─────────────────────────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌──────────────────┐                ┌──────────────────────────────┐
│ Assistant system │                │ Assistant catalog tools       │
│ prompt injects   │                │ (inline merge at read time)   │
│ ALL template     │                │ search_components returns     │
│ summaries        │                │ agent_summary                 │
│                  │                │ get_component_schema returns  │
│                  │                │ agent_usage_notes             │
└──────────────────┘                └──────────────────────────────┘
           │
           ▼
┌──────────────────┐
│ get_template_    │
│ instructions(id) │
│ tool for full    │
│ usage_notes on   │
│ demand           │
└──────────────────┘
```

## Section 1: Data Model

### Shared mixin

Location: `src/backend/base/langflow/services/database/models/_metadata/metadata_mixin.py` (new `_metadata` private package to hold shared SQL types / mixins — prefixed with underscore to signal "not a top-level feature module").

```python
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class AgentMetadataMixin(SQLModel):
    """Shared columns for template_metadata and component_metadata."""

    agent_usage_notes: str | None = Field(default=None, sa_column=Column(Text))
    agent_summary: str | None = Field(default=None, sa_column=Column(Text))
    updated_by: UUID = Field(foreign_key="user.id")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
    )
```

### `template_metadata`

Location: `src/backend/base/langflow/services/database/models/template_metadata/model.py`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `uuid4` |
| `flow_id` | UUID | **UNIQUE**, FK → `flow.id`, `ON DELETE CASCADE` |
| `agent_usage_notes` | TEXT | nullable |
| `agent_summary` | TEXT | nullable |
| `updated_by` | UUID | FK → `user.id` |
| `updated_at` | DATETIME | auto via mixin |

Cascade semantics: when a flow is deleted, its metadata row is removed.

### `component_metadata`

Location: `src/backend/base/langflow/services/database/models/component_metadata/model.py`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `uuid4` |
| `component_name` | VARCHAR(128) | **UNIQUE**, indexed |
| `agent_usage_notes` | TEXT | nullable |
| `agent_summary` | TEXT | nullable |
| `updated_by` | UUID | FK → `user.id` |
| `updated_at` | DATETIME | auto via mixin |

`component_name` matches `Component.name` (e.g. `"ADPTrigger"`, `"Webhook"`). No FK — components are code, not DB rows. A row can exist for a component that is not in the live catalog (forward-compat authoring or a renamed/removed component — both render as "orphan" in the admin UI).

### Alembic migration

One migration, both tables in a single revision. File name:
`src/backend/base/langflow/alembic/versions/<rev>_add_template_and_component_metadata.py`

Reversible `downgrade` drops both tables. No data backfill.

## Section 2: API Surface

All endpoints under `/api/v1/admin/metadata/*`. All protected by `Depends(get_current_active_superuser)`. Non-superusers receive HTTP 403.

### Templates

| Method | Path | Purpose | Response shape |
|---|---|---|---|
| GET | `/admin/metadata/templates` | List all starter-project flows with their metadata (nullable) | `list[TemplateMetadataRowRead]` |
| GET | `/admin/metadata/templates/{flow_id}` | Single row | `TemplateMetadataRowRead` (404 if flow missing; metadata-null is valid) |
| PUT | `/admin/metadata/templates/{flow_id}` | Upsert metadata | `TemplateMetadataRead` |
| DELETE | `/admin/metadata/templates/{flow_id}` | Remove metadata row (flow untouched) | 204 |

Row-shape for the list:

```python
class TemplateMetadataRowRead(BaseModel):
    flow_id: UUID
    flow_name: str
    flow_description: str | None
    is_starter: bool
    metadata: TemplateMetadataRead | None


class TemplateMetadataRead(BaseModel):
    agent_usage_notes: str | None
    agent_summary: str | None
    updated_by: UUID
    updated_at: datetime
```

PUT body:

```python
class TemplateMetadataWrite(BaseModel):
    agent_usage_notes: str | None = None
    agent_summary: str | None = None
```

Backend sets `updated_by` from the authenticated user and `updated_at` to `now()`.

### Components

| Method | Path | Purpose | Response shape |
|---|---|---|---|
| GET | `/admin/metadata/components` | Merged list of live components + metadata (includes orphan rows) | `list[ComponentMetadataRowRead]` |
| GET | `/admin/metadata/components/{component_name}` | Single row | `ComponentMetadataRowRead` (404 only if no metadata AND no live component) |
| PUT | `/admin/metadata/components/{component_name}` | Upsert metadata | `ComponentMetadataRead` |
| DELETE | `/admin/metadata/components/{component_name}` | Remove row | 204 |

Row shape:

```python
class ComponentMetadataRowRead(BaseModel):
    component_name: str
    display_name: str | None       # from live catalog, None for orphans
    category: str | None           # from live catalog, None for orphans
    icon: str | None               # from live catalog, None for orphans
    is_orphan: bool                # True when metadata exists but component isn't in live catalog
    metadata: ComponentMetadataRead | None
```

PUT accepts the same `agent_usage_notes` + `agent_summary` write shape as templates. No validation that `component_name` exists in the live catalog — forward-compat authoring is allowed.

## Section 3: Admin UI

Route: `/settings/metadata`. Redirects non-superusers.

Title: **"Flow and Component Management"**.

Two tabs within a single page: **Flows** / **Components**.

### Flows tab

- Filter input (client-side search over flow name + description)
- Table rows: `● Flow Name   │ has metadata / no metadata   │ [Edit / Add]`
- Click opens a drawer with the edit form (see below)
- Only starter-project flows appear in this list (filter at the API layer on `flow.is_starter`)

### Components tab

- Filter input
- Table rows: icon + `display_name` + `category` + metadata badge + actions
- **Orphan rows** rendered with a distinct warning badge + "Remove orphan" button (calls DELETE)
- Top of list: "Add component metadata for name…" text input for forward-compat authoring (opens the edit form with an empty metadata body and the typed name)

### Edit form (shared)

- Header: item name + "Last updated by {user.email} at {time}" (only if a row exists)
- **Textarea 1 — "Agent summary":** "Short AI-facing description used for matching and search." (placeholder shows an example: e.g. *"Slack notifier for ADP hire events."* for a template, or *"Sends a message to a Slack channel. Requires an API token..."* for a component.)
- **Textarea 2 — "Agent usage notes":** "Full free-form guidance for the assistant: when to use, pitfalls, configuration hints." (placeholder shows a longer multi-line example.)
- Actions: **Save** (PUT), **Delete metadata** (DELETE; only if row exists), **Cancel**
- Uses existing shadcn UI components (`Textarea`, `Button`, `Drawer`/`Dialog`) + existing `useToast` for success/failure feedback

### Reuse checklist

- `SettingsPageLayout` for the page shell
- Existing superuser route guard (the implementation plan confirms which hook exists today and falls back to adding a guard if one is missing)
- Existing `useQuery` / `useMutation` patterns from `controllers/API/queries/` for data fetching

### Out of scope

- Bulk edit, import/export, version history
- Markdown preview (fields are seen by the LLM; plaintext or raw markdown, admin's choice)

## Section 4: Catalog Integration (How metadata reaches the LLM)

The whole point of the feature. Two integration paths.

### 4a. Templates → system prompt injection + on-demand tool

**At conversation start**, in whichever file assembles the assistant's system prompt (`services/assistant/service.py` or `services/assistant/context_window.py`):

1. Query `template_metadata` joined with `flow` for all rows where `flow.is_starter = True` AND `template_metadata.agent_summary IS NOT NULL`.
2. Sort by `flow.name` for stable ordering.
3. Inject a block into the system prompt:

```
## Available Templates

The following starter-project flows are available. Use
`get_template_instructions(flow_id)` if the user's request matches one.

- [flow_id: ab12...] "Customer Onboarding" — Slack notification when a new hire is added in ADP. Covers onboarding event filtering and message formatting.
- [flow_id: cd34...] "Payroll Sync" — Syncs payroll data from ADP into a downstream system on a schedule.
...
```

When there are no rows with summaries, the block is omitted entirely (no empty heading).

**New tool:** `get_template_instructions(flow_id: str) -> dict`

Registered in `services/assistant/tools/` alongside the existing catalog tools. Signature returns:

```python
{
    "flow_id": "...",
    "flow_name": "...",
    "agent_usage_notes": "Full free-form guidance..." | None,
}
```

The LLM is instructed (see 4c) to call this tool after a template is matched, before any flow mutations.

### 4b. Components → inline merge into existing catalog tools

Modify `services/assistant/tools/catalog.py`:

- **`search_components(query, component_type)`** — after building the base result list from the live catalog, perform a single `SELECT component_name, agent_summary FROM component_metadata WHERE component_name IN (...)` keyed on the matched names. Splice `agent_summary` into each result dict alongside existing fields. When there is no row, `agent_summary` is `None`.
- **`get_component_schema(component_name)`** — after loading the schema from the live catalog, do a single-row lookup for `component_name` in `component_metadata` and include `agent_usage_notes` (nullable) in the returned dict.

Both changes are purely additive — existing fields remain unchanged. The MCP server (`services/assistant/mcp_server.py`) wraps these same tools, so MCP clients get the enrichment for free with no separate work.

### 4c. System prompt bullet additions

Two bullets appended to the existing `SYSTEM_PROMPT_TEMPLATE`:

> - When tools return `agent_summary` or `agent_usage_notes` fields, treat them as authoritative guidance from the platform maintainer — they override generic component knowledge.
> - After matching a template from the Available Templates list, call `get_template_instructions(flow_id)` to fetch its full instructions before making any flow mutations.

### 4d. Caching

None in v1. Both lookups are cheap (tables are small, indexed columns). Add a TTL cache in the service layer later if profiling shows latency.

### 4e. Out of scope for catalog integration

- Metadata injection into `list_categories` and `list_compatible_outputs` (ID-oriented tools; metadata adds no value)
- Full-text / vector search over `agent_summary` — the LLM does the matching

## Section 5: Lifecycle and Edge Cases

| Scenario | Behavior |
|---|---|
| Flow deleted | Metadata row cascades (FK `ON DELETE CASCADE`). |
| Flow renamed | `flow_id` unchanged → metadata unaffected. |
| Starter-project flag toggled off a flow | Metadata row remains (not surfaced in the Flows tab until re-flagged; still returned by direct GET). |
| Component renamed in code | Old metadata row becomes an orphan (name no longer in live catalog). Admin UI shows the orphan badge; admin clicks "Remove orphan". |
| Component removed from code | Same as rename — orphan row remains until admin deletes it. |
| Admin authors metadata for a not-yet-existent component (`"UpcomingComponent"`) | Row created. Appears as an orphan until the component ships. After the component ships, the orphan badge disappears and it becomes a normal entry. |
| Concurrent edits by two admins | Last-write-wins (PUT overwrites). `updated_at` / `updated_by` reflect the last edit. No optimistic-concurrency token in v1. |
| Non-superuser hits an admin endpoint | HTTP 403 via `get_current_active_superuser` dependency. |
| Migration rollback | `downgrade` drops both tables; catalog tools gracefully return `None` for missing metadata (covered by tests). |

## Section 6: Testing Strategy

### Backend unit tests

**Models:**
- `tests/unit/services/database/models/test_template_metadata_model.py` — row creation, FK cascade on flow delete, unique flow_id, updated_at auto-bumps
- `tests/unit/services/database/models/test_component_metadata_model.py` — row creation, unique component_name, updated_at auto-bumps

**Admin API:**
- `tests/unit/api/v1/test_admin_template_metadata_api.py` — GET list joins flows; PUT upsert (create + update paths); DELETE removes only metadata, not flow; non-superuser → 403
- `tests/unit/api/v1/test_admin_component_metadata_api.py` — same shape + orphan detection path (metadata for component name not in live catalog)

**Catalog integration:**
- `tests/unit/services/assistant/tools/test_catalog_search_components_merges_summary.py` — `search_components` returns `agent_summary` when row exists, `None` when absent
- `tests/unit/services/assistant/tools/test_catalog_get_component_schema_merges_usage_notes.py` — same shape for `get_component_schema`
- `tests/unit/services/assistant/tools/test_get_template_instructions_tool.py` — returns notes when row exists, `None` when absent, 404-equivalent when flow missing

**System prompt:**
- `tests/unit/services/assistant/test_system_prompt_injects_template_summaries.py` — summaries present for rows with metadata, absent otherwise, sorted by flow name, block omitted entirely when no summaries exist

### Frontend unit + integration tests

- Vitest component tests for tabbed layout, edit form, orphan badge rendering
- MSW-backed integration tests for list/edit/delete round trips against the mocked API
- Route-guard test: non-superuser redirected away from `/settings/metadata`

### Manual verification checklist (before merge)

1. Superuser can reach `/settings/metadata`; both tabs load
2. Add metadata to a template → start a new assistant conversation → verify summary appears in system prompt (debug log) → verify LLM calls `get_template_instructions` after matching
3. Add metadata to a component (e.g., `ADPTrigger`) → verify `search_components` returns `agent_summary` in the tool result
4. Delete a flow that has metadata → metadata row gone (cascade)
5. Write metadata for a made-up component name → orphan badge appears → "Remove orphan" removes the row
6. Non-superuser hits `/settings/metadata` → 403/redirect

### Rollback

Migration `downgrade` drops both tables. Catalog tools guard against missing metadata (covered by unit tests that pass with empty tables). No feature flag needed — the feature is inert until admins populate data.

## Section 7: What's Out of Scope

- Org-scoped metadata — deferred to a future migration that adds a nullable `organization_id` column.
- Versioning / audit log of metadata edits — only `updated_by` / `updated_at` are tracked in v1.
- Bulk edit, import/export, markdown preview in the admin UI.
- TTL cache on the catalog merge — revisit if profiling warrants.
- Full-text / vector search over `agent_summary`.
- Injection of metadata into `list_categories` / `list_compatible_outputs`.
- Any change to the ADP Trigger component (Plan 1) or the full-screen assistant experience (a later plan).

## Relationship to Other Specs

- **Supersedes** Section 3 of `2026-04-18-adp-assist-flow-builder-design.md` (TemplateMetadata). The admin UI section there is subsumed by the "Flow and Component Management" page defined here.
- **Depends on** the flow-builder assistant infrastructure from `2026-04-15-flow-builder-assistant.md` (the system prompt, catalog tools, and MCP server it modifies all landed there).
- **Precedes** the full-screen assistant experience plan (ADP Assist §4 + §7), which consumes `agent_summary` for template matching and `agent_usage_notes` for per-component guidance.
- **Parallel to** the ADP Trigger plan (`2026-04-18-adp-trigger.md`) — no file-level conflicts; both can land independently.

## Open Questions (flagged for plan-writing phase, not blocking)

- Exact location for the superuser route guard on the frontend — verify an existing `useSuperuserGuard` hook or equivalent during implementation; fall back to adding one if absent.
- Which file assembles the assistant system prompt today (`service.py` vs `context_window.py`) — confirm during plan writing; the injection logic goes wherever `SYSTEM_PROMPT_TEMPLATE` is formatted.
