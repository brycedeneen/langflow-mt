# ADP Assist Follow-ups

Deferred items surfaced during implementation of prior plans. Pick up when revisiting the owning area.

## Plan 2 (Metadata Infrastructure — 2026-04-18)

### UI affordances

- [ ] **Orphan-authoring input on Components tab.** Spec §3 called for an inline "Add component metadata for name…" text input at the top of the Components tab so admins can pre-stage metadata for a component that hasn't shipped yet. Implementation skipped it. `PUT /api/v1/admin/metadata/components/{name}` accepts any string, so the backend path already works — just the UI surface is missing. Small frontend task (~20–30 lines in `components-tab.tsx`).

### Verification items still untested at runtime

- [ ] **Non-superuser 403 on admin API.** Code-reviewed only. Worth confirming with a real non-superuser token hitting `/api/v1/admin/metadata/templates`.
- [ ] **Flow-delete cascade for template_metadata.** Migration declares `ON DELETE CASCADE` and a unit test covers it against SQLite, but the Postgres behavior on a real flow-delete flow through the UI hasn't been observed.
- [ ] **`get_template_instructions` tool call path.** Exercised only via unit tests. The live LLM round-trip ("assistant calls the tool after matching a template") has not been observed.

### Schema nits

- [ ] **`Flow.description` field.** `TemplateMetadataRowRead` exposes `flow_description` but the `Flow` model may not have a `description` column. The admin list handler uses `getattr(flow, "description", None)` so it silently returns `None`. Either confirm the column exists and remove the `getattr` defensive, or drop the field from the response schema.

### Incidental changes shipped under this commit (review-worthy)

- [ ] **Alembic idempotency patches** on pre-existing migrations `26b3d04efba1_organization_runs_limits.py` and `b8d0abf646b6_flow_run_config.py`. Added to fix a test-harness collision (fresh-DB `create_all` + Alembic running both). Not triggered by normal deploy flow. Confirm the guards are the long-term shape you want; consider whether `alembic stamp` would be a cleaner answer.
- [ ] **`admin.py` → `admin/` package refactor.** `src/backend/base/langflow/api/v1/admin.py` was split into `admin/__init__.py` (aggregator) + `admin/orgs.py` (prior contents) + `admin/metadata.py` (new). Not in plan; accepted during execution.

## Plan 3 (Assist Layout + Entry Points — 2026-04-18)

### UI gaps vs. spec

- [ ] **Overlay offsets are hardcoded.** Both `fullscreen-shell.tsx` and `test-shell.tsx` use `fixed top-[48px] ... md:left-[17.5rem]` — literal values matching the app-header height (`h-[48px]`) and the flow-builder `SidebarProvider width="17.5rem"`. If either of those values change, the overlay will misalign. Cleaner long-term: introduce a CSS variable set by the header/sidebar that the overlay consumes.

### Incidental changes shipped under this commit (review-worthy)

- [ ] **`alembic/env.py` modified twice** to add URL-scheme normalization: (a) `postgresql://` → `postgresql+psycopg://` (Plan 2 Task 4), and (b) `sqlite://` → `sqlite+aiosqlite://` (Plan 3 Task 15). Both were added so `LANGFLOW_DATABASE_URL` env-var works with the async alembic driver. Needed for `make alembic-upgrade` to target the real dev DB (instead of only SQLite in-memory). Confirm the long-term shape you want — e.g., lift into a dedicated URL-sanitizer util.

## Possible Plan 6: MCP ext-apps integration

- [ ] **Revisit after Plan 4 lands.** `@modelcontextprotocol/ext-apps` (https://www.npmjs.com/package/@modelcontextprotocol/ext-apps) lets MCP servers declare rich UI widgets that the assistant chat can render inline. Clear fit for structured-input moments: ADP auth config (client_id / client_secret / mTLS cert / key), credential pickers, component configurators. Defer to post-Plan 4 because: (1) Plan 4 will surface the actual friction points, (2) the package is new and likely still stabilizing, (3) text-only credential collection in Plan 4 is a swap, not a refactor — easy to upgrade later. Trigger to prioritize: if Plan 4's conversational credential flow feels clunky, pause Plan 4 at a natural boundary and slot this in as Plan 6.
