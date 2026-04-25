# Template Agent Metadata — Edit Surface & Assistant Rewiring

**Date:** 2026-04-25
**Status:** Implemented
**Branch context:** `platform-multi-tenant`

## Problem

Two related defects, both surfaced by the user noticing that templates do not appear in **Settings → Flow and Component Management → Flows**:

1. **No way to edit AI metadata on templates.** The new `Template` table has no `agent_summary` or `agent_usage_notes` columns. The legacy `TemplateMetadata` model still has them but is keyed by `flow_id`, and the migration that introduced `Template` (`8663a8995703_seed_categories_and_migrate_starter_…`) deleted every starter-project Flow row. Every legacy metadata row is now orphaned and unreachable.
2. **The assistant's per-flow template context is silently broken.** `Flow.based_on_template_flow_id` is an FK to `flow.id` with `ON DELETE SET NULL`. The migration cascaded NULLs across every existing pointer. `build_flow_template_context` always returns `""`, and the MCP tools (`list_template_summaries_for_prompt`, `fetch_template_usage_notes`) find no rows.

Both defects share a root cause: the data model moved, the consumers didn't.

## Goal

Give platform admins a single edit surface for template name, description, icon, gradient, categories, **agent summary, and agent usage notes**, and rewire the assistant to read those notes from the Template table.

Out of scope: backfilling lost metadata (none is reachable), renaming MCP tools, surfacing `agent_summary` to end users on the card, redesigning the templates modal.

## Non-Goals

- A new "Edit Flow" button or any new affordance — the existing `⋯` admin menu on the template card is sufficient and already opens `TemplateEditPanel`.
- Repurposing the Settings → Flows tab as a list view of templates.
- Migration of historical TemplateMetadata content.

## Design

### 1. Data model

**Add to `Template` (`services/database/models/template/model.py`):**
```python
agent_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
agent_usage_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
```
Both nullable. Reuses the model's existing `updated_by` / `updated_at` audit columns.

**Add to `Flow` (`services/database/models/flow/model.py`):**
```python
based_on_template_id: UUID | None = Field(
    default=None,
    sa_column=Column(Uuid(), ForeignKey("template.id", ondelete="SET NULL"), nullable=True),
)
```

**Drop from `Flow`:** `based_on_template_flow_id`. There are no flows currently using this column on the branch (the migration cleared them all to NULL), so dropping it now is cheaper than carrying a dead column.

**Drop:** the `template_metadata` table, its model, and its `__init__.py` export. All rows are orphaned.

### 2. Migration

One Alembic revision performs:
1. `add_column template.agent_summary` (Text, nullable)
2. `add_column template.agent_usage_notes` (Text, nullable)
3. **Backfill** template agent fields from `initial_setup/starter_projects/*.metadata.json`: for each `<Template Name>.metadata.json` that has a matching `template.name`, populate `agent_summary` and `agent_usage_notes`. (Today only `ADP Worker Sync to SFTP.metadata.json` exists — but this preserves it instead of losing it.)
4. `add_column flow.based_on_template_id` (Uuid, nullable, FK → `template.id`, `ON DELETE SET NULL`)
5. `drop_column flow.based_on_template_flow_id` (drop FK first if needed)
6. `drop_table template_metadata`

Downgrade reverses (drop new columns, recreate empty `template_metadata`, recreate `flow.based_on_template_flow_id` FK to `flow.id`). Downgrade does **not** restore data — the spec explicitly accepts this.

**Startup seeder cleanup:** `create_or_update_template_metadata` in `initial_setup/setup.py` and its caller in `main.py` are deleted. The Alembic migration's one-time backfill replaces it; future template metadata is admin-authored via the UI, not seeded.

### 3. API

**`TemplatePatch`** gains two optional fields:
```python
class TemplatePatch(BaseModel):
    name: str | None = PydanticField(default=None, max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    category_ids: list[UUID] | None = None
    agent_summary: str | None = None       # new
    agent_usage_notes: str | None = None   # new
```

**Patch semantics — `model_fields_set`:** today's handler uses `if body.field is not None` to decide whether to apply, which means there's no way to clear `description`, `icon`, or `gradient` (sending `null` is indistinguishable from omitting). For the new agent fields, admins genuinely need to clear values (so a removed `agent_summary` stops being injected into prompts). The patch handler switches to `if "field" in body.model_fields_set` for **all** patchable fields, making `null` an explicit clear and omission a no-op. This is a behavior change for existing fields, but the previous behavior was a latent bug — no caller can be relying on "clear is impossible."

Auth unchanged (existing `canEditTemplate` rule: platform admin or org admin of the template's org).

**`TemplateRead` and `TemplateReadDetail`** include both new fields. `agent_summary` is needed by the assistant's prompt-injection helper; `agent_usage_notes` is included for symmetry and to avoid a second fetch from the edit panel.

**Routes removed:**
- `GET /api/v1/admin/metadata/templates`
- `GET /api/v1/admin/metadata/templates/{flow_id}`
- `PATCH /api/v1/admin/metadata/templates/{flow_id}`
- `DELETE /api/v1/admin/metadata/templates/{flow_id}`

The component-metadata routes in `admin/metadata.py` stay; the file is trimmed to component-only or split (implementation may decide).

**Clone-from-template path:** wherever a Flow is created from a Template (templates modal "Use this template" + Save-as-Template + ADP Assist clone), set `flow.based_on_template_id = template.id`. Stop setting `based_on_template_flow_id` (it no longer exists after this PR).

### 4. Assistant rewiring (`services/assistant/`)

| File | Change |
|---|---|
| `tools/metadata_lookup.py` | `list_template_summaries_for_prompt` queries `Template` where `agent_summary IS NOT NULL`. Returns `[{template_id, template_name, agent_summary}]`. `fetch_template_usage_notes(template_id)` queries `Template` by id. Returns `{template_id, template_name, agent_usage_notes}`. |
| `flow_template_context.py` | Param renamed `based_on_template_id`. Body otherwise unchanged. Caller (per-message context builder) reads `flow.based_on_template_id`. |
| `mcp_server.py` | Two MCP tools update arg names + docstrings from `flow_id` → `template_id`. Tool names unchanged. |
| `tools/template_apply.py` | `apply_template` currently treats its `template_flow_id` arg as a `Flow` id and queries the (empty) Flow table. Rewrite to query `Template` by id; replace `is_flow_a_starter_project_async` check with `template.deleted_at is None and template.archived_at is None`. Set `target.based_on_template_id = template_uuid`. Param name → `template_id` (semantics align with reality). |
| `tools/registry.py` | Update the `apply_template` tool definition: `template_flow_id` → `template_id`, descriptions reference templates not "starter-project flow." |
| `tools/template_metadata.py` | `get_template_instructions(flow_id)` → `get_template_instructions(template_id)`. Forwards to renamed `fetch_template_usage_notes`. |
| `service.py` | `AssistantService.__init__` param `based_on_template_flow_id` → `based_on_template_id`; instance attr renamed. System prompt text unchanged. |
| `api/v1/assistant.py` | Two call sites pass `based_on_template_flow_id=flow.based_on_template_flow_id` → use the new column name. |
| `api/v1/templates.py` | Delete-guard query (`select(Flow.id).where(Flow.based_on_template_flow_id == template_id)`) → use `Flow.based_on_template_id`. |
| `api/v1/flows.py` | Archive-guard already does `session.get(Template, flow.based_on_template_flow_id)` (passing what is in practice a template id) — switch the column to `flow.based_on_template_id`. Logic unchanged. |

No backwards-compat shims. The MCP tools are consumed only by the assistant itself.

### 5. Frontend

**`TemplateEditPanel`** (`src/frontend/src/modals/templatesModal/components/TemplateEditPanel/index.tsx`) gains two text inputs:

- **Agent summary** — short `Textarea` (~2 rows) or `Input`. Helper text: *"Short description the assistant uses to match this template to user requests."*
- **Agent usage notes** — `Textarea` (~6–8 rows, resize-y). Helper text: *"Guidance the assistant injects when a user works with a flow created from this template."*

Both fields nullable; empty string normalizes to `null` in the PATCH body. Local state mirrors existing fields' pattern (reset on `open` toggle). No new save button — uses the existing footer.

**Frontend types:** `TemplateRead` adds `agent_summary?: string | null` and `agent_usage_notes?: string | null`. `useUpdateTemplate()` hook signature gains the same two optional fields. Templates modal card itself does not render the new fields — they're admin-authored metadata, not user-facing copy.

**Settings → Flows tab — removed:**
- Delete `flows-tab.tsx`, `useListTemplateMetadata`, and any helpers used only by it.
- The "Flow and Component Management" page becomes Components-only. Implementation may rename the section to "Component Management" or keep the existing header.

### 6. Component boundaries

- `Template` model owns the metadata fields (one source of truth, reuses its audit columns).
- API surface is the existing `PATCH /templates/{id}` — no new endpoint.
- Assistant module reads only the `Template` model; it does not know about the old `TemplateMetadata`.
- Frontend edit affordance is the existing `TemplateEditPanel`; it does not know about the assistant.

### 7. Error handling

- PATCH validation: existing `TemplatePatch` partial-update behavior covers both new fields. No new error codes.
- Assistant: lookups return `None` for missing/cleared notes. `build_flow_template_context` returns `""` (existing behavior preserved).
- Migration: no data loss path — orphaned `TemplateMetadata` rows are explicitly accepted as lost.

## Testing

### Backend
- **Migration smoke test** (existing harness pattern): upgrade/downgrade round-trip, assert columns added/dropped, FK present on `flow.based_on_template_id`.
- **`PATCH /templates/{id}`** — extend existing patch test:
  - Set `agent_summary` and `agent_usage_notes`; GET reflects them.
  - Explicit `null` clears each.
  - Non-admin / non-owner gets 403 (one test covers both new fields).
- **Assistant lookups** — replace existing `metadata_lookup` tests (which seed `TemplateMetadata` + Flow) with Template-row equivalents. Cover: rows with `agent_summary=None` excluded; non-existent template_id returns notes=None.
- **`build_flow_template_context`** — three cases: pointer is None → `""`; pointer to template with notes → markdown block; pointer to template without notes → `""`.
- **Removed routes** — one test asserts `/api/v1/admin/metadata/templates` returns 404; delete the rest of the old route tests.

### Frontend
- **`TemplateEditPanel`** — extend existing component test: type into both new fields, submit, assert PATCH body includes them.
- **Settings page** — update the "Flow and Component Management" test to assert only Components is rendered.

### Manual verification (UI)
1. Log in as platform admin → open templates modal → `⋯` on a card → **Edit** → set summary + notes → save → reopen → values persist.
2. Open Settings → confirm Flows tab is gone, Components tab still works.
3. Create a flow from a template whose `agent_usage_notes` is set → in the assistant chat, confirm the "Current Flow Template" block appears in the system prompt (debug log or behavioral verification).

## Open Questions

None. The two judgment calls (drop `based_on_template_flow_id` now; drop `template_metadata` rather than archive) were confirmed during brainstorming.
