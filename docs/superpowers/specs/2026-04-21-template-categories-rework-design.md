# Template Categories Rework — Design

Date: 2026-04-21
Branch: `platform-multi-tenant`
Related prior work: `2026-04-18-template-management-phase-1-design.md`, `2026-04-20-save-as-template-frontend-design.md`, `2026-04-20-fu3-saved-templates-tab-design.md`

## 1. Summary & Scope

Rework Langflow's template categories into an admin-managed taxonomy and move all templates into the database. Built-in starter JSON files are removed; every template lives as a `Template` row. Categories become first-class, CRUD-able, multi-tag entities.

### In scope

1. Migrate the starter JSON fixtures in `src/backend/base/langflow/initial_setup/starter_projects/` into `Template` rows via a one-shot Alembic data migration; remove the runtime Flow-backed starter loader.
2. Introduce a platform-level `Category` model (`name`, `icon`, `color`, `description`, audit fields). Platform admins CRUD categories via inline affordances in the templates modal.
3. Many-to-many `template_category` join table. Any template (platform- or org-scoped) can be tagged with any category.
4. Unfreeze `Template.scope` and `Template.org_id` (Phase 2 unlock): templates can now be org-scoped. "Save as Template" creates an org-scoped template for logged-in org members, visible to every member of that org.
5. Archive + hard-delete actions on templates. Archive is reversible, hides templates from browsing UI, and blocks new flow creation. Hard delete requires confirmation and is refused by the API if any existing `Flow.based_on_template_flow_id` still references the template.
6. Sidebar: flat, alphabetically-sorted category list under the existing "Get started / All templates / Saved Templates" rows. Hardcoded category constants are removed from the frontend.

### Explicitly out of scope

- Org-scoped categories. Categories are platform-global.
- A "personal" template scope separate from org. "Saved Templates" = templates created by the current user regardless of scope.
- Bulk admin operations (bulk tag, bulk archive) and analytics dashboards.
- Cross-org template sharing or a template marketplace.
- Free-form icon or color entry — admins pick from a curated Lucide set and an 8-color Tailwind palette.

### Permissions

| Action | Platform Admin | Org Admin | Org Member |
|---|---|---|---|
| Category CRUD | Yes | No | No |
| Create platform template | Yes | No | No |
| Create org template (via Save as Template) | Yes | Yes | Yes |
| Edit / archive / delete platform template | Yes | No | No |
| Edit / archive / delete org template | Yes | Yes (any in own org) | Yes (own saves only) |
| Tag a template with categories | Whoever can edit the template | same | same |

A single helper `user_can_edit_template(user, template)` centralizes the per-template rule:
- Platform templates → `user.is_platform_admin`.
- Org templates → `user.is_platform_admin` OR (org admin in `template.org_id`) OR (`template.created_by == user.id`).

## 2. Data Model

### 2.1 New table: `category`

```python
class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str = Field(max_length=64, nullable=False)
    icon: str = Field(max_length=64, nullable=False)           # Lucide icon name
    color: str = Field(max_length=16, nullable=False)          # one of the preset palette keys
    description: str | None = Field(max_length=256, default=None)
    created_by: UUID | None = Field(foreign_key="user.id", default=None)  # NULL for seeded rows
    created_at: datetime
    updated_at: datetime
```

Indexes:
- Primary key on `id`.
- Unique index `uq_category_name_lower` on `LOWER(name)` (case-insensitive uniqueness; two categories cannot differ only in case).

No `org_id`, no `sort_order`, no archived/active flag. No slug — `name` serves as the stable public identifier in URLs (`?category={name}`, URL-encoded).

### 2.2 New table: `template_category` (join)

```python
class TemplateCategory(SQLModel, table=True):
    __tablename__ = "template_category"

    template_id: UUID = Field(foreign_key="template.id", primary_key=True, ondelete="CASCADE")
    category_id: UUID = Field(foreign_key="category.id", primary_key=True, ondelete="CASCADE")
```

- Composite primary key on `(template_id, category_id)` prevents duplicate tags.
- `CASCADE` on both sides: deleting a template removes its tag rows; deleting a category detaches it from every template (templates survive with one fewer tag).
- Secondary index on `category_id` alone to support the common "list templates in category X" query.

### 2.3 Changes to `template`

1. **Add** `archived_at: datetime | None` (nullable). NULL = active, timestamp = archived. Unarchive clears the column. Partial index on `(archived_at IS NULL)` to keep the common active-templates query cheap.
2. **Unfreeze `scope` and `org_id`**:
   - Allowed combinations: `(scope="platform", org_id IS NULL)` or `(scope="org", org_id IS NOT NULL)`.
   - Rewrite the existing `ck_template_scope_org_coherence` check constraint to enforce exactly those two combinations. (Phase 1 froze it to platform/NULL-only.)
3. **Make `created_by` nullable**. Seeded platform templates migrated from starter JSON have no authoring user; NULL is the truthful value. Future templates created via the API always populate it.
4. **Rewrite `uq_template_name`** as `uq_template_name_per_scope`, unique on `(COALESCE(org_id, '00000000-0000-0000-0000-000000000000'), LOWER(name))`. Two different orgs can both have a "Customer Onboarding" template; no collision.
5. Drop the Phase 1 comment/guard asserting scope is always platform. Loosen Pydantic validators on the request schemas to accept org-scoped input.

### 2.4 Left alone

- `Flow.tags` remains. Starter-project filtering by tag goes away, but the column may have other callers; removing it is out of scope for this rework.
- `Template.deleted_at` (soft-delete column from Phase 1) stays. It is distinct from `archived_at`:
  - `archived_at` — user-visible retirement, blocks flow creation, reversible via UI.
  - `deleted_at` — the underlying soft-delete used by the DELETE endpoint (Phase 1 behavior). Hard delete (the new action introduced here) is an actual `DELETE` row operation, not a soft-delete.

## 3. API

### 3.1 Categories (new — `/api/v1/categories`)

| Method | Path | Who | Body / Query | Notes |
|---|---|---|---|---|
| GET | `/api/v1/categories` | Any authenticated user | — | Returns all categories, alpha-sorted by name. Backs the sidebar render. |
| GET | `/api/v1/categories/{id}` | Any authenticated user | — | |
| POST | `/api/v1/categories` | Platform admin | `{name, icon, color, description?}` | 409 on case-insensitive name collision. |
| PATCH | `/api/v1/categories/{id}` | Platform admin | any subset of `{name, icon, color, description}` | |
| DELETE | `/api/v1/categories/{id}` | Platform admin | — | Cascades through `template_category`. 204 on success. |

### 3.2 Templates (existing, extended — `/api/v1/templates`)

| Method | Path | Change | Notes |
|---|---|---|---|
| GET | `/api/v1/templates` | Extended | New query params: `?category={name}` (single-category filter), `?scope=platform\|org\|all` (default `all`), `?created_by_me=true` (powers the "Saved Templates" tab), `?include_archived=true`. `include_archived` is accepted when the caller is a platform admin **or** when combined with `?created_by_me=true` (users may surface their own archived templates); any other use returns 403. By default, archived rows are omitted from list responses. |
| GET | `/api/v1/templates/{id}` | Extended | Returns archived templates to anyone with read permission. The client decides how to render. |
| POST | `/api/v1/templates` | Extended | Body now accepts `category_ids: [UUID]`, `scope`, `org_id`. Platform scope requires platform admin; org scope requires membership. |
| PATCH | `/api/v1/templates/{id}` | Extended | Body accepts `category_ids: [UUID]` — **full replace** of the tag set, not additive. |
| POST | `/api/v1/templates/{id}/archive` | New | Sets `archived_at = now()`. Idempotent. |
| POST | `/api/v1/templates/{id}/unarchive` | New | Clears `archived_at`. Idempotent. |
| DELETE | `/api/v1/templates/{id}` | Extended | Hard delete. Returns **409 Conflict** with `{referencing_flow_ids: [...]}` if any `Flow.based_on_template_flow_id` still points at it. Otherwise 204. |

### 3.3 Flow creation guard

`POST /api/v1/flows` with `based_on_template_id` — if the referenced template has `archived_at IS NOT NULL`, return **422** with message `"template is archived"`. No force flag; callers must unarchive the template first.

### 3.4 Deliberate non-endpoints

- No `/categories/{id}/templates` — use `GET /templates?category={name}`.
- No `GET /users/me/templates` — use `GET /templates?created_by_me=true`.
- No bulk endpoints.

## 4. Migration Plan

Three migrations ship together: schema, data, and code cleanup.

### 4.1 Schema migration (Alembic, reversible)

- Create `category` table and `uq_category_name_lower` unique index.
- Create `template_category` table with cascade FKs and the `category_id` secondary index.
- Add `template.archived_at` column plus the partial `archived_at IS NULL` index.
- Drop `uq_template_name`, add `uq_template_name_per_scope`.
- Rewrite `ck_template_scope_org_coherence` to allow `(platform, NULL)` or `(org, NOT NULL)`.
- Alter `template.created_by` to `NULLable`.

Downgrade reverses each step in order.

### 4.2 Data migration (one-shot, same Alembic revision)

**Step 1 — seed categories.** Hardcoded list derived from the current starter-project tag vocabulary:

| Seed name | From old tag | Icon | Color |
|---|---|---|---|
| Assistants | `assistants` | `users-round` | slate |
| Classification | `classification` | `tag` | amber |
| Coding | `coding` | `code` | violet |
| Content Generation | `content-generation` | `book-open` | emerald |
| Q&A | `q-a` | `help-circle` | sky |
| Prompting | `chatbots` | `message-square` | fuchsia |
| RAG | `rag` | `database` | indigo |
| Agents | `agents` | `bot` | rose |

Icons match today's sidebar. Colors are stylistic defaults; admins can edit after.

**Step 2 — create Template rows from starter JSON fixtures.** The JSON files are read by the migration itself (bundled with the revision, not via the runtime loader). For each file:

- Insert a `Template` row: `name`, `description`, `icon`, `gradient` from the JSON; `nodes` and `edges` from `data.nodes` / `data.edges`; `scope="platform"`; `org_id=NULL`; `created_by=NULL`.
- For each string in the JSON `tags` array, insert a `template_category` row linking the new template to the seeded category for that tag.
- **Unknown tag → migration fails loudly.** Surfaces missing seed entries; safer than silently dropping.

**Step 3 — delete pre-existing starter Flow rows.** The current runtime loader creates `Flow` rows; after Step 2 these are shadow duplicates. Identify them via the same marker `src/backend/base/langflow/initial_setup/setup.py` uses today (implementation plan must pin this precisely — likely `user_id IS NULL` plus membership in a specific folder). Delete them.

**Idempotence.** Each step checks for prior existence (category by name, template by `(scope=platform, LOWER(name))`) before inserting. Re-running the migration on an already-migrated DB is a no-op.

### 4.3 Code cleanup (same PR)

- Delete `src/backend/base/langflow/initial_setup/starter_projects/*.json`.
- Delete/trim the starter-loading functions in `src/backend/base/langflow/initial_setup/setup.py` (around lines 661 and 725 per the explore). Leave unrelated setup logic alone.
- Frontend: remove the hardcoded `Category[]` array in `src/frontend/src/modals/templatesModal/index.tsx:100-134`. Replace with a `useGetCategoriesQuery` hook against `GET /api/v1/categories`. Replace the `example.tags?.includes(currentTab)` filter with server-side filtering via `?category={name}`.

### 4.4 Rollout notes

- One-way safe. A downgrade drops the new tables, but the source JSON files have been deleted from the repo — rolling back a deployment requires restoring those files from git. Call this out in the PR description.
- Alembic runs on startup per existing convention — no separate ops step.

## 5. Admin UX (Inline in Templates Modal)

All admin affordances live in the existing templates modal. Non-admins see today's view unchanged (apart from a categories picker in the Save-as-Template dialog). Admins see extra edit controls. No new routes.

### 5.1 Category CRUD (left sidebar)

- Hovering any category row reveals a `...` menu (admins only) with **Edit** and **Delete**.
- **Edit** opens a popover anchored to the row with fields: `name`, `icon` (searchable dropdown of the curated Lucide set), `color` (8-color Tailwind preset picker: slate / amber / violet / emerald / sky / fuchsia / indigo / rose), `description` (short text). Save / Cancel.
- **Delete** opens a confirm dialog: *"Delete {name}? Templates tagged with it will be untagged."* Destructive button styling.
- Below the last category, a **"+ New category"** row (admin-only) opens the same popover in create mode.
- Categories remain alpha-sorted after any edit.

### 5.2 Per-template admin actions (main grid)

- Each template card shows a `...` button in the top-right corner (admin-only, visibility gated by `user_can_edit_template`).
- Menu items:
  - **Edit template** → side panel (slides in from the right of the modal) with: name, description, icon/gradient, **categories multi-select chip picker** (sourced from `GET /api/v1/categories`). Save writes via `PATCH /api/v1/templates/{id}` including the replaced `category_ids`.
  - **Archive** / **Unarchive** → fires `POST /archive` or `POST /unarchive`. Optimistic UI with toast confirmation.
  - **Delete** → confirm dialog: *"Permanently delete {name}? This can't be undone."* On 409, the dialog shows *"Cannot delete — N flow(s) still reference this template."* with a link to view them. No force flag.

### 5.3 Archive visibility

- A **"Show archived"** toggle near the top of the template grid. Visibility rules:
  - **Admins** (platform admin, or org admin viewing their own org): toggle is visible in every view. When on, archived templates across the current filter are shown.
  - **Non-admin users**: toggle is visible only on the **Saved Templates** tab, and only surfaces the user's own archived templates. Hidden on all other views.
- Default off in both cases.
- When on, archived templates render at 50% opacity with a small **"Archived"** pill. Clicking opens an info pane (not a create-flow path). **"Start Building"** is disabled with tooltip *"Unarchive to create flows from this template."* The card's `...` menu surfaces **Unarchive** if the viewer has edit permission.

### 5.4 Save-as-Template dialog (extends existing)

Two additions:

1. **Categories chip picker** (multi-select). Saving without categories is permitted; the template simply won't appear under any category filter.
2. **Scope selector** — visible only when the user has more than one possible scope:
   - Platform admin in an org: *"Save to: [Platform] [Org: {name}]"* radio.
   - Org admin / org member: no selector; always saves to org.
   - Platform admin not in an org: no selector; saves to platform.
   - User outside any org (rare on this branch): no selector; saves to platform if platform admin, else the Save button is disabled with an explanatory tooltip.

### 5.5 Empty states

- Category with no templates: *"No templates in this category yet."* plus a link to *"Save a flow as a template"* (link only rendered if the user has any flows).
- Saved Templates empty: existing copy.
- All archived, when "Show archived" is on and none exist: *"No archived templates."*

### 5.6 Consistency guards

- Sidebar width unchanged; admin affordances are hover-revealed and add no permanent visual weight.
- Non-admin builds render none of: `...` menus, "+ New category", "Show archived", scope selector. The only user-visible change for regular users outside admin flows is the new categories chip picker in the Save-as-Template dialog.

## 6. Implementation Decisions Flagged for the Plan

These are choices that look reasonable but deserve a second look when writing the implementation plan:

1. **`created_by` nullable vs. dedicated `SYSTEM_USER_ID` row.** Spec picks nullable for simplicity and truthfulness. If the codebase already has a system-user convention used elsewhere, prefer it instead.
2. **Full-replace `category_ids` on PATCH vs. additive subresources.** Spec picks full replace since the admin edits the whole tag set at once. If a future workflow needs incremental updates, add subresources then.
3. **Side-panel template editor vs. modal-over-modal.** Spec picks the side panel for context retention. If the slide-in doesn't fit the existing modal layout, fall back to a nested dialog.
4. **Curated ~50 Lucide icons vs. free text.** Spec picks the curated set to prevent typos and icon drift. The exact icon list is an implementation detail; use the set already imported by `genericIconComponent` if feasible.
5. **Archive vs. soft-delete column separation.** Spec keeps `deleted_at` (existing) and adds `archived_at` (new) as distinct concepts. If this feels redundant during implementation, revisit — but they do mean different things (admin-visible retirement vs. tombstone).
