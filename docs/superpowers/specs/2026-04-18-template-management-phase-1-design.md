# Template Management — Phase 1: Save-as-Template + Field Blanking

**Date:** 2026-04-18
**Status:** Draft

## Overview

Phase 1 of the Template Management roadmap. Delivers the authoring path for reusable integration templates: superuser saves any flow as a Template, with a field-review modal that lets them audit exactly which field values get scrubbed before the template ships. Existing starter projects migrate into the new `Template` entity so the catalog has one source of truth. No versioning, no diff, no propagation — those land in Phase 2 and Phase 3.

**Business context:** the product is an enterprise SaaS offering managed integrations. Professional Services authors a template (e.g., "Workday → Payroll Sync") that's pre-wired with the flow logic; clients clone from the catalog, fill in their customer-specific details (credentials, customer IDs, webhook URLs), and run it. Repeat integrations become a catalog-pick instead of a fresh build each time.

## Key Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Scope boundary | **Platform-only in Phase 1.** Org-scoped templates deferred to Phase 2. | Simplest authoring model; org-scope requires permission knobs we don't need yet. The `scope` / `org_id` columns are present from day one so Phase 2 doesn't need a schema change. |
| Who authors templates | **Superuser only.** | Managed-integrations posture — PS owns the catalog. Expanding to org-admin and per-user-flag permissions is a later phase. |
| Entry point | **Share menu → "Save as Template"** (only visible when superuser). | Lives next to "Export", "API access", "MCP Server" — consistent with other flow-level publish actions. |
| Field-blanking UX | **Field-review modal at save time. Passwords auto-blanked and non-toggleable. All other non-empty fields audited per-row with Blank/Keep checkboxes; coarse "Blank all / Keep all" buttons at top.** | Enterprise SaaS expectation of explicit audit. Per-row control handles the webhook URL / customer ID / environment base URL cases that aren't `password=True`. |
| Password escape hatch | **None.** Passwords are always scrubbed. | "Never ever will we ship a template with a password." |
| Storage model | **New `Template` table, separate from `Flow`.** Existing starter projects migrate into Template rows (destructive migration, no rollback needed). | Clean boundaries; Phase 2's `TemplateVersion` hangs off `Template.id` without disturbing Phase 1. Reusing `Flow` with a flag would bite us in Phase 2. |
| Duplicate-name handling | **Names are unique. Re-saving with existing name triggers overwrite-confirm dialog. Overwrite is destructive in Phase 1; Phase 2 makes re-saves into new versions automatically.** | Clean catalog; no orphan rows. Phase 2's upgrade path is: same API shape, different server-side behavior. |
| Catalog unification | **Starter projects migrate into the new `Template` entity; one catalog, one code path.** | Long-term the right boundary — starter projects ARE "PS-authored templates we shipped first." Small migration cost now avoids tech debt in Phase 2. |
| Deletion | **Soft delete.** Clones keep their `based_on_template_id` FK intact; when the Template row is deleted, the FK is set to NULL via `ON DELETE SET NULL`. | Audit trail for "which template did this flow clone from" matters, even post-deletion. |

## Architecture

```
┌──────────────── Superuser: Save flow as Template ─────────────────┐
│                                                                      │
│ [Flow canvas]                                                        │
│    Share ↓                                                           │
│      └─ Save as Template   ← new, superuser only                  │
│           │                                                          │
│           ▼                                                          │
│   Save-as-Template Modal                                             │
│    ① Metadata: name, description, icon, gradient                     │
│    ② Field review: per-node list of non-empty fields                 │
│       Password fields: 🔒 auto-blanked, no toggle                    │
│       Other fields:    ☐ keep / ☑ blank                              │
│       [Blank all]  [Keep all]                                        │
│    ③ [Cancel]  [Save as Template]                                    │
│           │                                                          │
│           ▼                                                          │
│   POST /api/v1/templates                                             │
│    body: { source_flow_id, name, description, icon, gradient,       │
│            blanked_fields: [{ node_id, field_name }, ...] }          │
│           │                                                          │
│           │  409 on name conflict  ────▶ overwrite-confirm modal     │
│           │                                      │                   │
│           │                                      ▼                   │
│           │                             PUT /api/v1/templates/{id}   │
│           │                                                          │
│           ▼                                                          │
│   Template row created (scope='platform', org_id=NULL,               │
│                         nodes/edges snapshot with blanked fields,    │
│                         created_by = current user)                   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────── User (any): browse catalog and clone template ──────────┐
│                                                                      │
│ Template Catalog Gallery                                             │
│   GET /api/v1/templates                                              │
│   Cards: icon, name, description, [Create from template]             │
│           │                                                          │
│           ▼                                                          │
│   GET /api/v1/templates/{id} → nodes + edges                         │
│           │                                                          │
│           ▼                                                          │
│   New Flow created                                                   │
│    nodes/edges: template snapshot (blanked fields stay empty)        │
│    based_on_template_id: template.id                                 │
│    (client fills in blanked fields before running)                   │
└──────────────────────────────────────────────────────────────────────┘
```

## Section 1: Data Model

### New `Template` table

Location: `src/backend/base/langflow/services/database/models/template/model.py`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `name` | str, max 255 | unique, indexed, NOT NULL |
| `description` | str \| None | Text, nullable |
| `icon` | str \| None, max 64 | lucide icon name; mirrors `Flow.icon` |
| `gradient` | str \| None, max 32 | optional visual flair for catalog cards |
| `scope` | Enum (`"platform"`, `"org"`) | default `"platform"`, NOT NULL |
| `org_id` | UUID \| None | FK → org.id, nullable. Phase 1: always NULL. Reserved for Phase 2. |
| `nodes` | JSON | Snapshot of node list after field-blanking. NOT NULL. |
| `edges` | JSON | Snapshot of edges list. NOT NULL. |
| `created_by` | UUID | FK → user.id, NOT NULL |
| `created_at` | datetime | default UTC now |
| `updated_by` | UUID | FK → user.id, NOT NULL |
| `updated_at` | datetime | default UTC now, auto-update on modify |
| `deleted_at` | datetime \| None | nullable; soft-delete sentinel |

**Constraints:**

- `CHECK (scope = 'platform' AND org_id IS NULL) OR (scope = 'org' AND org_id IS NOT NULL)` — enforces scope/org_id coherence. Phase 1 always matches the first branch.
- `UNIQUE (name)` — single-name catalog.

### Changes to `TemplateMetadata` (from Plan 2)

File: `src/backend/base/langflow/services/database/models/component_metadata/model.py` (or wherever `TemplateMetadata` lives).

- Add column: `template_id: UUID | None`, FK → `template.id ON DELETE CASCADE`, unique.
- Keep existing `flow_id` column during the migration; drop it in the same revision once data is copied over.

### Changes to `Flow`

- Add column: `based_on_template_id: UUID | None`, FK → `template.id ON DELETE SET NULL`, nullable.
- Drop column: `based_on_template_flow_id` (in same alembic revision).

### Phase 2 hooks (columns present but unused in Phase 1)

- `Template.scope='org'` + `org_id` FK: Phase 2 uses these for per-org templates.
- Future `template_version` table (Phase 2): joins via `template_id` FK.
- Future `Flow.based_on_template_version_id`: added alongside `based_on_template_id` in Phase 2; Template.id remains the logical-template identity.

## Section 2: API Endpoints

New router: `src/backend/base/langflow/api/v1/templates.py` mounted at `/api/v1/templates`.

### `GET /api/v1/templates`

- **Auth:** any authenticated user.
- **Returns:** `TemplateRead[]` — `{id, name, description, icon, gradient, created_at, updated_at}`. Excludes `nodes` / `edges` / audit fields to keep payloads slim.
- **Filters:** soft-deleted rows (where `deleted_at IS NOT NULL`) are excluded.
- **Scope filter:** Phase 1 only returns `scope='platform'` rows (trivial since that's all we write). Phase 2 extends to include user's org templates.

### `GET /api/v1/templates/{template_id}`

- **Auth:** any authenticated user.
- **Returns:** full `TemplateReadDetail` including `nodes`, `edges`.
- **404** if not found or soft-deleted.

### `POST /api/v1/templates`

- **Auth:** superuser only.
- **Body:**
  ```jsonc
  {
    "source_flow_id": "uuid",
    "name": "Workday → Payroll Sync",
    "description": "Optional description",
    "icon": "briefcase",
    "gradient": "indigo",
    "blanked_fields": [
      { "node_id": "SlackPoster-xyz", "field_name": "webhook_url" },
      { "node_id": "Workday-abc",     "field_name": "customer_id" }
    ]
  }
  ```
- **Behavior:**
  1. Load source Flow's `nodes`/`edges`.
  2. Apply field-blanking: for each entry in `blanked_fields`, clear that field's value in the matching node's template. Additionally, **unconditionally** blank any input where the component definition has `password=True` (server-side enforcement — do not trust frontend to include all passwords).
  3. Write `Template` row with cleaned `nodes`/`edges`.
- **Response:** `201 Created`, body = `TemplateReadDetail`.
- **409 Conflict** if a Template with the same (non-deleted) name exists. Frontend handles by showing the overwrite-confirm dialog, then calling PUT.

### `PUT /api/v1/templates/{template_id}`

- **Auth:** superuser only.
- **Body:** same as POST minus `source_flow_id`. (Content is still sourced from a flow; source_flow_id is re-supplied in the body for consistency.)
- **Behavior:** overwrites content + metadata in place. Updates `updated_at`, `updated_by`. `created_at`, `created_by`, `id` unchanged.
- **Response:** `200 OK`, body = updated `TemplateReadDetail`.
- **404** if not found or soft-deleted.

### `DELETE /api/v1/templates/{template_id}`

- **Auth:** superuser only.
- **Behavior:** sets `deleted_at = now()`. Does not cascade to `Flow.based_on_template_id` (that's `ON DELETE SET NULL`, but soft delete doesn't trigger it — the FK simply points at a row that's filtered out of catalog queries). Clones continue to work; they just lose the ability to reference their origin meaningfully.
- **Response:** `204 No Content`.

### Admin metadata endpoints (retargeted, not new)

Existing endpoints under `/api/v1/admin/metadata/templates/{flow_id}` become `/api/v1/admin/metadata/templates/{template_id}`. CRUD shape unchanged; the resource ID now references Template rows.

### Deprecated endpoint

`GET /api/v1/starter-projects/` — kept during the migration window but returns data sourced from the `template` table. Marked with a deprecation comment; removal scheduled for a subsequent plan once no callers remain.

## Section 3: UX Flow

### 3a. Save as Template modal

Triggered from Share menu → "Save as Template" (only visible to superusers). Modal is a three-section form.

**① Metadata**

- `Name` — required, 255 chars max. Uniqueness check on blur (fetch all template names, compare client-side).
- `Description` — optional, multi-line.
- `Icon` — optional, project's icon picker. Defaults to source flow's current icon if set.
- `Gradient` — optional, swatch picker.

**② Field review**

Lists every Input instance across all nodes in the source flow. Empty fields are hidden (nothing to blank). Fields are grouped by node with the node's display name as a section header.

Each field row shows:

```
field_name         "current value preview"         [☐ keep | ☑ blank]
```

Password fields (`password=True` on their Input class):

```
bot_token         •••••••••••                      [🔒 always blanked]
```

Locked icon, no toggle, not interactive.

Top of panel has:

```
[ Blank all ]   [ Keep all ]
```

These set every (toggleable) row in one click. Clicking "Keep all" does not unlock the password rows.

**③ Save actions**

`Cancel` | `Save as Template`

Submit → POST `/api/v1/templates`. On `409`, the modal flips to:

> ⚠️ A template named **"Workday → Payroll Sync"** already exists.
>
> Overwrite it? Clients who cloned the previous version **won't be automatically notified** — they'll continue to see their existing flow as-is. Versioning arrives in Phase 2; until then, overwriting is destructive to the template's history.
>
> `Cancel` | `Overwrite template`

Overwrite confirm → PUT `/api/v1/templates/{id}`.

On successful POST or PUT: modal closes, toast `"Template '{name}' saved."`, catalog gallery refreshes.

### 3b. Template catalog gallery

Replaces the existing "Starter Projects" gallery location (flow list page / "New Flow" modal — exact entry point confirmed at plan-write time by grepping `useGetStarterProjects` or equivalent). Same visual shell: grid of cards with icon + name + description + `Create from template` button.

Backing query: `GET /api/v1/templates` (via `useListTemplates` hook).

### 3c. Clone action

Existing "clone from starter project" path retargets:
- Fetch `GET /api/v1/templates/{id}` for `nodes`/`edges`.
- Create a new Flow with those nodes and edges. Blanked fields remain empty — the client fills them in before running.
- Set `Flow.based_on_template_id = template.id`.
- Set `Flow.name` = a smart default like `"{template.name} (copy)"`.

### 3d. Admin management UI

Existing `SettingsPage/pages/MetadataPage` "Flows" tab retargets from Flow rows to Template rows:
- Lists all (non-deleted) Templates.
- Each row: name, has-metadata badge, last-updated timestamp, Edit / Delete actions.
- Edit opens the existing TemplateMetadata editor (now keyed by `template_id`).
- Delete triggers `DELETE /api/v1/templates/{id}` (soft delete) with a confirm dialog.

No in-place "edit template content" UI in Phase 1. Content updates require re-saving from a source flow. Phase 2 adds version-aware editing.

## Section 4: Migration Strategy

One-way, destructive. No rollback.

### 4a. Alembic revision

Filename: `alembic/versions/NNNN_template_management.py`

Order of operations (each step individually idempotent):

1. Create `template_scope` enum with values `("platform", "org")`.
2. Create `template` table with columns per Section 1.
3. Add `template_id UUID NULL` column to `template_metadata` with FK → `template.id ON DELETE CASCADE`, unique.
4. Add `based_on_template_id UUID NULL` column to `flow` with FK → `template.id ON DELETE SET NULL`.
5. **Data migration:**
   - For each `Flow` row whose `folder_id` matches the "Starter Projects" folder:
     - Insert new `template` row. Populate `name`, `description`, `icon`, `gradient` from the Flow. `nodes`/`edges` from `Flow.data.nodes` / `Flow.data.edges`. `scope='platform'`, `org_id=NULL`. `created_by` = Flow's creator (or a designated fallback admin user if NULL). Timestamps from the Flow.
     - Record `{old_flow_id → new_template_id}` in an in-memory dict for this migration.
   - For each `template_metadata` row whose `flow_id` is in the mapping: update `template_id` to the mapped new Template ID.
   - For each `Flow` row with `based_on_template_flow_id` set and matching the mapping: update `based_on_template_id` to the mapped new Template ID.
   - For any `Flow.based_on_template_flow_id` not in the mapping (unlikely, but defensive): log a warning and leave `based_on_template_id = NULL`. Phase 2 can reconstruct if needed.
6. Delete the starter-project `Flow` rows. Delete the "Starter Projects" `Folder` row.
7. Drop `template_metadata.flow_id` column.
8. Drop `flow.based_on_template_flow_id` column.

### 4b. Startup code changes

File: `src/backend/base/langflow/initial_setup/setup.py`

- `get_or_create_starter_folder()` (line 743) — **removed.**
- Starter-project seeding loop (around line 1118) — replaced with a **Template upserter** that reads the existing Python graph builders in `src/backend/base/langflow/initial_setup/starter_projects/` and upserts rows in the `template` table keyed by `name`. Same idempotency contract (re-running doesn't duplicate). On first boot after migration, this is effectively a no-op because the alembic revision already created the rows.

Retarget all callers of `STARTER_FOLDER_NAME` / `is_flow_a_starter_project_async`:

- `src/backend/base/langflow/api/v1/flows.py:425, 1027` → query `template` by ID.
- `src/backend/base/langflow/api/v1/projects.py:235` → drop the Starter Projects filter (no longer needed since they're not Folders anymore).
- `src/backend/base/langflow/api/v1/admin/metadata.py:70, 104` → replace folder-join with `template` table query.
- `src/backend/base/langflow/services/assistant/tools/template_apply.py:45` → `is_template_by_id(template_id)` replacement.
- Rename or remove `src/backend/base/langflow/services/database/models/flow/starter.py` — its functions become obsolete.

### 4c. Frontend changes

- New React Query hooks: `useListTemplates`, `useGetTemplate`, `useCreateTemplate`, `useUpdateTemplate`, `useDeleteTemplate`.
- Deprecate `useListTemplateMetadata` → `useListTemplatesWithMetadata` (joins Template + TemplateMetadata by `template_id`).
- Rename `based_on_template_flow_id` → `based_on_template_id` across frontend types, hooks, tests.
- Starter project gallery component retargets to `GET /api/v1/templates`.
- Admin Metadata "Flows" tab retargets to Template resource.

### 4d. Rollout

Deploy alembic revision + backend + frontend together (backward-incompatible JSON shape change). No rollback plan — the migration is one-way and destructive to the Starter Projects folder. If a reversal is ever needed, re-seed from Python graph builders from scratch.

## Section 5: Testing Strategy

### Backend unit + integration tests

- `tests/unit/services/database/test_template_model.py`:
  - Name uniqueness enforcement.
  - Scope/org_id constraint (platform + NULL only; org + non-NULL only).
  - Soft-delete filtering (`deleted_at IS NOT NULL` excluded from default queries).
- `tests/unit/api/v1/test_templates_endpoints.py`:
  - `POST` as superuser succeeds; as regular user → 403.
  - `POST` with existing name → 409.
  - `POST` blanks all password-bearing fields even if they weren't in `blanked_fields[]`.
  - `POST` blanks all fields listed in `blanked_fields[]`.
  - `PUT` overwrites content + metadata; timestamps update correctly.
  - `DELETE` sets `deleted_at`; subsequent GET list filters it out; GET by ID returns 404.
  - `GET` list returns slim payload (no `nodes`/`edges`).
  - `GET` by ID returns full payload.
- `tests/unit/api/v1/admin/test_metadata_retargeting.py`:
  - `/metadata/templates/{template_id}` CRUD works against Template rows.
  - Old `flow_id`-keyed requests are no longer routable.
- `tests/unit/initial_setup/test_template_seeding.py`:
  - Startup upserts Template rows from Python graph builders.
  - Re-running doesn't duplicate.
- `tests/unit/alembic/test_template_migration.py`:
  - Apply the revision against a seeded test DB with mock starter Flow rows + a clone flow with `based_on_template_flow_id` set.
  - Assert Template rows created, `template_metadata.template_id` populated, `flow.based_on_template_id` remapped, starter Flow rows deleted.
- `tests/unit/services/assistant/test_template_apply_retargeted.py`:
  - The existing `template_apply` assistant tool now consults `Template` by `id`, not by folder.

### Frontend tests (Jest)

- `SaveAsTemplateModal.test.tsx`:
  - Renders metadata section + field-review panel with node grouping.
  - Blank/Keep all buttons toggle all non-password rows.
  - Password fields render with lock icon and are non-interactive.
  - Submit builds correct `blanked_fields[]` array from checked rows.
- `SaveAsTemplateModal.overwrite.test.tsx`:
  - Receiving a 409 flips to overwrite-confirm dialog.
  - Confirm triggers PUT.
- `TemplateCatalog.test.tsx`:
  - Renders cards from mocked `useListTemplates`.
  - "Create from template" button calls the clone hook with the right template ID.
- `MetadataPage.flows-tab.test.tsx`:
  - Retargeted to Template resource.
  - Edit / Delete actions call the new hooks.

### Manual verification checklist (before merge)

1. Fresh DB: boot the app → starter projects appear as Templates in the catalog gallery.
2. Existing DB with cloned starter-project flows: apply migration → clones still load, `based_on_template_id` points at the right Template.
3. Superuser: build a flow with Slack (webhook_url + API key) + a config node → Save as Template → field-review shows all non-empty fields, password auto-blanked with lock icon, superuser ticks webhook URL to blank → saved template has no webhook URL, no API key, keeps message template.
4. Non-superuser: Share menu has no "Save as Template" item.
5. Overwrite flow: save-as with existing name → confirm dialog fires → PUT succeeds → catalog shows updated content.
6. Clone from template: "Create from template" → new Flow created with `based_on_template_id` set, blanked fields empty, client fills them in and runs successfully.
7. Soft delete: delete a template → gallery hides it → existing clones continue to load; trying to re-clone from the deleted template is not an option (it's filtered out of the catalog).
8. Re-boot after migration: starter-project Templates are still present; no duplicates created by the upserter.

## Section 6: Out of Scope (Hard Boundaries)

- **Versioning** — Phase 2. No `TemplateVersion` entity in Phase 1.
- **Diff / propagation / cherry-pick** — Phase 3. Node-level cherry-pick decided (not field-level) to keep complexity manageable.
- **LLM-diff feature** — Phase 3 or later.
- **Org-scoped templates (author per-org)** — Phase 2. Columns present but unused.
- **Per-user template-authoring permission flag** — future phase. Phase 1 is superuser only.
- **In-place content editing of Templates** — Phase 2 via versioning.
- **Auto-notification of clients when a template updates** — Phase 2 + 3.
- **Client-facing "your template was updated" UI** — Phase 2.
- **PS cross-org "apply upgrade to client X" tool** — Phase 3.
- **Template export/import as JSON file** — out of scope; use the existing flow export/import if needed.
- **Template search / categorization / tagging** — not needed for Phase 1's catalog size; revisit when catalog grows.
- **Analytics on which templates are most-cloned** — later phase.

## Relationship to Other Specs

- **Supersedes** the `STARTER_FOLDER_NAME` convention in `src/backend/base/langflow/initial_setup/constants.py`. All starter-project semantics move into the Template table.
- **Retargets** Plan 2's `TemplateMetadata` entity: `flow_id` FK → `template_id` FK.
- **Retargets** Plan 4's `Flow.based_on_template_flow_id` FK: → `Flow.based_on_template_id` (points at Template, not another Flow).
- **Depends on** Plan 4's assistant `template_apply` tool, which will be updated in its retargeting task.
- **Unblocks** Phase 2 (versioning infrastructure) — `Template` as a stable logical identity lets versions hang off cleanly.
- **Unblocks** Phase 3 (diff + node-level cherry-pick propagation) — the Template↔Flow lineage is persisted cleanly via `based_on_template_id`.

## Open Items Flagged During Implementation

- **Exact starter-project gallery location in the frontend.** Spec says "replaces the existing Starter Projects gallery"; at plan-write time, grep for `useGetStarterProjects` (or equivalent) and identify the component(s) that render it. Likely the "New Flow" modal and possibly a landing page.
- **Default fallback user for `created_by` in the migration** if a starter-project Flow row has a NULL creator. Pick the first superuser in the DB, or use a designated system user row if one exists. Decide at plan-write time after inspecting the existing data.
- **Existing unit tests for admin metadata endpoints** reference `flow_id` in URL params + body. Plan will catalog the exact set at plan-write time and update them in the retargeting task.
- **`Flow.description` column** — prior followup (Plan 2) flagged that this field may not exist on Flow despite `TemplateMetadataRowRead` exposing `flow_description`. Section 1's `Template` table has its own `description` column — decoupled from Flow's — so this pre-existing concern doesn't block Phase 1.
