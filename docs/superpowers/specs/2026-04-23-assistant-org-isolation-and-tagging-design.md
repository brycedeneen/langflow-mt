# Assistant Org-Isolation + Tagging — Design

**Roadmap items:** P1 #19 (reframed) + P1 #18
**Roadmap source:** `docs/superpowers/specs/2026-04-22-integration-platform-roadmap.md`
**Branch:** `p1/batch-1` (Sprint 2 of five)

## Background

Two items from the P1 roadmap bundle into a single sprint because both touch flows and templates at the service + API layer. Their intents are orthogonal — one is a defense-in-depth audit, the other is a feature — so they live in two clearly separated parts of this doc.

### Roadmap wording vs. actual intent (#19)

The roadmap labels this item **"metadata taxonomy extension — add the org-level policy layer on top of the existing component/template metadata."** In brainstorming the user clarified the real intent is narrower and different:

> "This was about not letting the agent get / access data from other orgs."

The work is therefore an **assistant data-access isolation audit**, not a taxonomy refactor. Existing metadata tables stay global (no per-org fork). Templates stay global (no per-org catalog filtering). When this spec lands, update the roadmap entry to match.

### Reusable primitives

- `PlatformAdmin = Annotated[User, Depends(require_platform_admin)]` at `src/backend/base/langflow/api/utils/core.py:94` — enforces `User.is_platform_admin`.
- Cross-org FK validator (`CrossOrgFKError`) — defends the ORM layer but does not cover every service-level call site that assistant tools use. That gap is the reason #19 needs a targeted audit.
- Existing admin CRUD pattern for `template_metadata` and `component_metadata` in `src/backend/base/langflow/api/v1/admin/metadata.py` — clone for the tag admin endpoints.
- Template and Flow models already exist; `Flow.tags: list[str] | None` JSON field is present but **unused** (no API filter, no UI). It will be dropped in the Part B migration.

---

# Part A — Assistant data-access isolation (#19)

## A.1 Goals

- Every assistant-callable tool or endpoint that reads the following MUST filter by the actor's active organization:
  - `Flow`
  - `FlowRun` / run logs
  - Attachments / uploaded files
  - Any tool surface that could be added in the future
- A regression test exists for each tool proving "actor in org A, target in org B" raises 403 or 404 (consistent choice documented below).

## A.2 Non-goals (v1)

- Template-catalog filtering (tabled — templates are global).
- Per-org `component_metadata` (stays global by design).
- Centralized `ActiveOrgDep` dependency that refactors every endpoint to declare org context. Good idea, but pairs better with P1 #15 (Org-level AI policy) as a separate project.
- OIDC / SAML / SSO work. Unrelated.

## A.3 Inventory method

Before any code changes, produce an inventory file (`docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md` — disposable; committed only if it is still useful post-fix).

For each of the following entry points, list every service/DB call that fetches `Flow`, `FlowRun`, `File`, `Message`, or `Attachment`:

- `src/backend/base/langflow/api/v1/assistant.py` — Flow Builder Assistant endpoints + their tool-call handlers.
- `src/backend/base/langflow/api/v1/component_assist.py` — per-component assistant SSE endpoint.
- Any module under `src/backend/base/langflow/services/component_assist/` that the above depend on.
- Any tool function the assistant can call (catalog lookup, component schema fetch, flow JSON read, attachment fetch).

For each call, record:

| Column | Meaning |
|--------|---------|
| Call site (file:line) | Where the DB fetch happens |
| Entity read | `Flow` / `FlowRun` / `File` / etc. |
| org_id filter today? | ✅ / ⚠️ / ❌ |
| Guard strategy | "explicit filter" / "via session_scope_readonly + FK validator" / "missing" |

Anything marked ⚠️ (implicit only — e.g., relies on `user.organizations` being a subset that happens to match) or ❌ (no filter) becomes a patch target. ✅ rows still get a regression test.

## A.4 Guard helper

Add `guard_assistant_org_scope` to `src/backend/base/langflow/services/assistant/guards.py` (new module):

```python
from lfx.services.database.models.organization.model import Organization

class CrossOrgAccessError(PermissionError):
    """Raised when an assistant tool tries to touch data outside the actor's active org."""

def guard_assistant_org_scope(
    *,
    actor_org_id: UUID,
    target_org_id: UUID | None,
    target_label: str,
) -> None:
    """Belt-and-suspenders check inside every assistant tool.

    Raises CrossOrgAccessError when target_org_id is set and differs from actor_org_id.
    Accepts target_org_id=None for globals (templates, platform-curated things) — those
    short-circuit to a no-op rather than failing.
    """
```

The helper is secondary defense: the primary fix is that DB queries filter by org. But calling it at tool entry gives us an observability + test hook, and catches bugs where a future query gets reintroduced without the filter.

## A.5 HTTP response contract

Cross-org access returns **404 Not Found**, not 403. Rationale:

- A 403 leaks existence ("that flow exists, just not for you").
- The target does not exist *in the actor's scope*, which is exactly what a 404 communicates.
- Matches how the cross-org FK validator already behaves for direct-ORM access.

Implement by translating `CrossOrgAccessError` to `HTTPException(404, "not found")` in the two assistant routers. Do not re-expose 403 anywhere.

## A.6 Regression test pattern

Per tool, one parametrized test lives in `src/backend/tests/unit/api/v1/test_assistant_org_isolation.py`:

```python
@pytest.mark.parametrize("tool_name, factory", ASSISTANT_TOOLS)
async def test_cross_org_returns_404(client, two_org_fixture, tool_name, factory):
    actor, other_org = two_org_fixture
    foreign_target = factory(other_org)
    response = await client.post(f"/api/v1/assistant/{tool_name}", json={"id": foreign_target.id}, headers=actor.auth)
    assert response.status_code == 404
```

`ASSISTANT_TOOLS` is a registry populated by each tool's module at import time, so adding a new tool automatically inherits the test coverage. Missing a registry entry fails a meta-test that verifies `len(ASSISTANT_TOOLS) == number_of_assistant_mounted_routes`.

## A.7 Schema changes

**None.** This section is purely filter-audit + helper + tests.

## A.8 Deliverables

- Inventory note (disposable).
- `guards.py` module + `CrossOrgAccessError`.
- Patch to any call site marked ⚠️ or ❌ to make org filter explicit.
- Regression test file with registry + parametrized test + meta-test.
- One commit per logical group: `feat(assist): org-scope guard helper + 404 contract`, `fix(assist): close cross-org leak at <site>` (per leak), `test(assist): cross-org isolation regression matrix`.

---

# Part B — Tagging for flows and templates (#18)

## B.1 Goals

- Platform admins curate a **global vocabulary of tags** (platform-wide, not per-org). Tags have name, color, optional description.
- Any member with edit permission on a flow or template can **assign** existing tags to it.
- Users can **filter** flows and templates by tag in the UI.
- Tag chips display on the flow card and template card.

## B.2 Non-goals (v1)

- AND-combinator filter (multi-select intersection). Initial UX is OR — "show flows with tag X or Y." AND is a P1.5 follow-up if demanded.
- Per-org tag vocabularies. Vocabulary is platform-global; only platform admins can mutate it.
- Free-hex color input. Colors come from a fixed palette for consistency and contrast.
- Tag usage counts, suggestion engine, auto-tagging.
- Migrating the unused `Flow.tags` JSON field — no rows have values, so we just drop the column.

## B.3 Schema

### New table: `tag`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `name` | VARCHAR(64) | unique, case-insensitive (citext or functional unique index) |
| `color` | VARCHAR(32) | one of the palette names (see B.5) |
| `description` | TEXT | nullable |
| `created_by` | UUID | FK `user.id`, nullable (SET NULL on delete) |
| `created_at` | TIMESTAMPTZ | auto |
| `updated_at` | TIMESTAMPTZ | auto-bump |

### New table: `flow_tag`

| Column | Type | Notes |
|--------|------|-------|
| `flow_id` | UUID | FK `flow.id` CASCADE |
| `tag_id` | UUID | FK `tag.id` CASCADE |
| PK | composite | `(flow_id, tag_id)` |

Index on `tag_id` for "list flows with tag X" queries.

### New table: `template_tag`

| Column | Type | Notes |
|--------|------|-------|
| `template_id` | UUID | FK `template.id` CASCADE |
| `tag_id` | UUID | FK `tag.id` CASCADE |
| PK | composite | `(template_id, tag_id)` |

Index on `tag_id`.

### Migration housekeeping

Drop `Flow.tags: list[str] | None` JSON column (column is present but never used — no rows have values in platform-multi-tenant). Dropping it removes a confusing dead field that a future engineer would otherwise repurpose.

## B.4 API

### Admin CRUD (`PlatformAdmin` only)

Mirror the existing `src/backend/base/langflow/api/v1/admin/metadata.py` pattern.

```
GET    /api/v1/admin/tags
POST   /api/v1/admin/tags          body: {name, color, description?}
GET    /api/v1/admin/tags/{id}
PUT    /api/v1/admin/tags/{id}     body: {name?, color?, description?}
DELETE /api/v1/admin/tags/{id}     cascades to flow_tag + template_tag rows
```

Name collisions return 409. Using an invalid palette name returns 422. Deletion is hard delete (no soft-delete): if a platform admin decides a tag shouldn't exist, its associations go with it.

### Read-only list (any authenticated user)

```
GET /api/v1/tags
```

Returns the full vocabulary. No pagination in v1 (tag count is bounded by admin discipline — if it grows past 200, add pagination then).

### Assign to entities

```
PUT /api/v1/flows/{id}/tags         body: {tag_ids: [...]}    # replaces full set
PUT /api/v1/templates/{id}/tags     body: {tag_ids: [...]}    # replaces full set
```

PUT-replaces-set semantics, not PATCH-merge. Server validates every `tag_id` exists and the actor has edit permission on the flow/template (existing helpers cover this). Unknown `tag_ids` → 422.

### Filter

```
GET /api/v1/flows?tag_id=<id>&tag_id=<id>        # OR semantics — returns flows with ANY listed tag
GET /api/v1/templates?tag_id=<id>&tag_id=<id>    # same
```

Filter combines with existing `folder_id` and scope filters via AND (tag-filter ∧ folder-filter).

## B.5 Color palette

Fixed palette exposed as a named enum on the API. UI renders each swatch from the corresponding Tailwind token.

| Name | Hex | Tailwind token (approx) |
|------|-----|-------------------------|
| `slate`  | `#64748b` | `bg-slate-500` |
| `red`    | `#ef4444` | `bg-red-500` |
| `orange` | `#f97316` | `bg-orange-500` |
| `amber`  | `#f59e0b` | `bg-amber-500` |
| `green`  | `#22c55e` | `bg-green-500` |
| `teal`   | `#14b8a6` | `bg-teal-500` |
| `sky`    | `#0ea5e9` | `bg-sky-500` |
| `blue`   | `#3b82f6` | `bg-blue-500` |
| `violet` | `#8b5cf6` | `bg-violet-500` |
| `pink`   | `#ec4899` | `bg-pink-500` |

10 colors. Contrast-checked for the chip text colour used today. If a designer later wants different swatches, swap the hex values — API surface is the name, not the hex.

## B.6 UI

### Admin tab

Under the existing Settings > Metadata page (`src/frontend/src/pages/SettingsPage/pages/MetadataPage/`), add a third tab **"Tags"** alongside Flows and Components. Visible only when `currentUser.is_platform_admin === true`.

Standard CRUD table:
- Name (text input)
- Color (swatch dropdown from the 10-palette)
- Description (optional text input)
- Created by / updated at (read-only)
- Row actions: edit drawer, delete button with confirm

### Tag picker (flow + template)

Reuse the existing multi-select combobox pattern from `save-as-template` modal. Renders selected tags as chips, typing filters the options, no "create new" affordance for regular users (platform-admin-only). Accessible from:

- Flow header (next to flow name) — new control.
- Save-as-Template modal — add below the category picker.
- Template edit drawer (if one exists) — inline.

### Filter UI

- **Flow listing** — add a chip filter row above the sidebar tree, visible when there is at least one tag assigned to any visible flow. Click a chip to toggle filter include/exclude.
- **Templates modal** — add the same chip filter row above the category grid.

### Card display

- Flow card / sidebar item — show up to 2 chips; `+N` badge for more, hover tooltip shows all.
- Template card — show up to 3 chips.

Truncation is display-only; full set is still returned from the API.

## B.7 Role enforcement summary

| Action | Allowed for |
|--------|-------------|
| Create / edit / delete tag (vocabulary) | `is_platform_admin=True` |
| List tags | Any authenticated user |
| Assign tags to a flow | Anyone who can edit that flow (existing perm) |
| Assign tags to a template | Anyone who can edit that template (`user_can_edit_template`) |
| Filter by tag | Any authenticated user |

Super admins are **not** automatically platform admins — the two flags are separate. Only `is_platform_admin` gates vocabulary CRUD. Confirmed against `src/backend/base/langflow/api/utils/core.py:94`.

## B.8 Deliverables

- Alembic migration: create `tag`, `flow_tag`, `template_tag`; drop `flow.tags`.
- SQLModel definitions for each table.
- Admin CRUD router (new file `src/backend/base/langflow/api/v1/admin/tags.py`).
- Public list router (add to existing `api/v1/` root).
- Flow and template assign endpoints added to existing routers.
- Filter parameter wired into `read_flows()` and template list endpoint.
- Frontend: Metadata page > Tags tab (new), flow header chip, template save/edit chip, filter chip row on both listings.
- Tests: backend admin CRUD tests, assign-endpoint tests, filter tests, frontend tests for tag picker + filter behavior.

Logical commits:
1. `feat(db): tag + flow_tag + template_tag tables; drop unused flow.tags`
2. `feat(api): tag admin CRUD + public list (platform-admin gated)`
3. `feat(api): assign tags + filter flows/templates by tag`
4. `feat(ui): tag admin tab under Settings > Metadata`
5. `feat(ui): tag chips on flow + template, filter row in listings`

---

## Cross-cutting: sprint sequencing

Part A and Part B are independent and can land in either order. Recommended order: **Part A first**, because:

- It is smaller (no schema, no UI).
- Landing it early de-risks any tag-endpoint work in Part B from accidentally introducing cross-org leaks through the new `tag_ids` query parameter.

## Follow-ups explicitly carried forward

- AND-combinator tag filter (P1.5) — implement when a customer asks for "flows with both X and Y".
- `ActiveOrgDep` centralized middleware (P1) — pair with the future #15 org-level AI policy project.
- Template-catalog cross-org scoping — stays tabled; re-open only if org-specific template features return to the roadmap.
- Update `2026-04-22-integration-platform-roadmap.md` to rename the P1 bullet currently labeled "Metadata taxonomy extension" to "Assistant data-access isolation" with a pointer to this spec.
