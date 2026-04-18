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

## Possible Plan 7: Template management system

- [ ] **Deferred from Plan 4 brainstorm (2026-04-18).** Three bundled capabilities that would replace the current "starter projects seeded from JSON fixtures" model with a DB-backed admin-managed template catalog:
  - **"Save as template" UI** — super-admin action on any flow that promotes it into the template catalog. Removes the need to hand-edit JSON fixtures.
  - **Field-level persistence rules** — per-component-input knowledge of which values carry forward when saved as a template (URLs, prompts) versus which get blanked out (credentials, API keys, mTLS material). Implementation options: add a `sensitive: true` flag on the component's Input classes, or admin override UI at save-time, or both.
  - **Template versioning** — immutable snapshots so existing user flows point to the version they were cloned from. Admin edits create a new version without retroactively affecting prior-version users. Enables an "LLM reviews template changes" feature: the assistant can diff the current version against a user's cloned version and flag "this template was updated, here's what changed, would you like to incorporate any of it?"
  - **Migration path for Plan 4's `Flow.based_on_template_flow_id`** — today it points at the template's flow id; when versioning lands, it evolves to point at a `template_version_id` (new entity). Small migration.

  Defer because: (1) Plan 4 (conversational experience) works with today's simpler template-as-starter-project model; (2) the LLM-diff feature is speculative; (3) proper data model deserves dedicated design time. Candidate trigger: concrete request from a super admin to self-author a template, or pain around re-seeding starter projects.

## Possible Plan 8: "Request Professional Services" feature

- [ ] **Deferred from Plan 4 brainstorm (2026-04-18).** Lets a client, mid-conversation with ADP Assist, request a human implementor with an auto-generated proposal of effort. Surfaces cleanly whenever the assistant can't fully close a flow, or the client wants a quote before signing up for services.

  **Moving parts:**
  - Two new columns on `ComponentMetadata`: `integration_hours_low: int | null` + `integration_hours_high: int | null`, edited from the existing "Component Management" admin UI.
  - New assistant tool `generate_services_proposal(flow_id)` that walks the flow's nodes, pulls hour estimates from each component's metadata, sums the ranges, and writes a natural-language summary (what the flow does, what components are involved, where uncertainty is highest).
  - Frontend: "Request Professional Services" action — either a header button in fullscreen mode or a suggested-action card in the assistant chat. Opens a proposal modal (components list + hours range + narrative summary + Submit).
  - **Ticket creation integration** — the longest pole. Varies per deployment: Zendesk, Salesforce, email, custom PS intake. Needs concrete decision before build.
  - New `ProposalRecord` DB table: snapshot of what the client saw + when + who submitted, so the PS team arrives with context.

  Defer because: (1) the ticket-integration target is unknown and shapes most of the work; (2) all the pieces are additive — no Plan 4 rework required when we add them later; (3) worth waiting until real users show us the "I need a human" moments, so the trigger surface is grounded in actual usage patterns.

## Plan 4 (Full-Screen Assistant Experience — 2026-04-18)

### Bugs surfaced during Plan 4 manual verification

- [x] **RESOLVED: `connect_edge` tool creates 0 edges even when called successfully.** Observed on flow `f18b737f-dd4c-4cee-89b7-349fc211b037` during Plan 4 verification. **Root cause was not in the tool itself** — it was in the SSE endpoint's `event_generator` in `src/backend/base/langflow/api/v1/assistant.py`. Persistence scheduling lived inside the `try:` block; when the stream raised (rate limit, network drop, provider timeout) persistence was skipped and in-memory mutations — including every successful `connect_edge` — vanished. Nodes appeared in the DB because the frontend's debounced `useAutoSaveFlow` caught up in time for them but not for later edge mutations. **Fix:** moved persistence scheduling into a `finally:` block + lifted `service = AssistantService(...)` out of the `try:` so `finally:` can read `service.mutation_tools.flow_data`. Regression test at `src/backend/tests/unit/api/v1/test_assistant_stream_partial_persistence.py` uses a `ProviderClient` that raises mid-stream and asserts partial mutations persist. (Original hypothesis about handle-string format turned out to be wrong; the edge data shape was correct all along.)

- [ ] **Backend `'Depends' object has no attribute 'exec'` warning during token auth.** Appears intermittently in the backend logs ("Unexpected error during token authentication"). Not triggered by our Plan 4 changes but worth investigating — may be a FastAPI dependency-resolution bug in an auth middleware that's leaking a `Depends(...)` placeholder instead of the resolved session.

### UX polish deferred by user

- [ ] **Break long assistant messages into multiple turns.** Today the assistant writes one long wall of text spanning all of its intermediate reasoning. Better: emit each distinct step as its own chat bubble ("Let me search for the Slack component…" → tool call → "Got it, now I'll add it…" → tool call → etc.). Requires either (a) prompting the LLM to split, (b) rendering tool-call intervals as implicit message boundaries, or (c) streaming-level frontend splitting on sentence boundaries. User deferred during Plan 4 verification.
