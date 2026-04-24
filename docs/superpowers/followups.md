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

## Cancelled Plan 6: MCP ext-apps integration — 2026-04-18

- **Cancelled during brainstorming (2026-04-18).** Inline widgets via the MCP Apps protocol or a native widget system would be a significant rendering subsystem (sandboxed iframes, `postMessage` bridge, submit endpoints) to solve a problem that text-only conversation already handles. The assistant's existing `set_field` mutation tools already update component values from chat. The only real security concern was "secrets leak into LLM context when users type them in chat" — acceptable for current threat model.

### Future consideration: "Open config panel" deep links (possible Plan 6')

- [ ] **Deep-link from chat to existing component config panel.** For completely non-technical users who shouldn't touch the canvas, the assistant chat should render a button like `"Configure ADP credentials [Open Panel]"` that opens Langflow's existing component config UI. User fills fields there (secrets go to secret service via existing `SecretStrInput` mechanism), closes the panel, returns to chat. Zero new rendering infrastructure — just link-out moments + a way to detect completion. Trigger to prioritize: when the product adds a no-canvas user persona or UX testing shows non-technical users struggling with chat-only data entry.

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

## Plan 5 (ADP Assist Test Mode — 2026-04-18)

### UX polish

- [ ] **PipelineCard tool sub-item styling.** Grouped tools render as plain `Tool: <name>` rows indented under the parent card header. Works functionally but looks thin compared to the card's own chrome. Consider: small tool icon, a left-border accent matching the agent card, or a subtle chip background. See `src/frontend/src/modals/AssistantPanel/FlowPipelineView/pipeline-card.tsx`.


## 2026-04-22 — Backport upstream PR #11893 (`LANGFLOW_ALLOW_CUSTOM_COMPONENTS`)

**Source:** https://github.com/langflow-ai/langflow/pull/11893 (merged 2026-04-05 upstream)

**Why:** On a multi-tenant deploy (ours is the effective main), a tenant who uploads a flow containing a custom Python component executes that code on shared infrastructure. Upstream's gate validates every node's code against a server-side component template cache before execution and refuses anything that doesn't match. Cached template misses during startup block *all* flow execution as a safety fallback. No equivalent exists on `platform-multi-tenant` (none of the PR's files are present: `src/lfx/src/lfx/utils/flow_validation.py`, `src/lfx/src/lfx/utils/component_aliases.py`, `src/frontend/src/utils/customComponentGuards.ts`, no `ALLOW_CUSTOM_COMPONENTS` setting).

**Decisions to brainstorm before planning:**
- Default posture for our multi-tenant deploy: `ALLOW_CUSTOM_COMPONENTS=false` baked into the container image, or opt-in per deployment?
- Platform-admin override: can platform admins run custom components while tenants cannot? (Current upstream design: env-var is global.)
- Frontend gating UX on ADP Assist / Template Management / Data Mapper surfaces.
- How to reconcile the 20+ starter-project JSON edits in the upstream PR with our ADP-specific starter-project content.
- Scope — backport as-is, or fork the gate to be per-org (membership-scoped allowlist)?

**Size estimate:** ~85 files touched upstream (50 backend + 30 frontend + 5 lfx). Multi-day effort.

**Cross-ref:** flagged in `docs/superpowers/plans/2026-04-22-platform-multi-tenant-security-fixes.md` as out of scope.

## 2026-04-23 — Follow-ups surfaced by the LANGFLOW_ALLOW_CUSTOM_COMPONENTS backport

Backport merged to `platform-multi-tenant` 2026-04-23. Coding work is complete and fully tested. These items surfaced during implementation and are orthogonal to the gate itself.

### Deferred: Task 12 manual browser verification

- [ ] **Blocked on pre-existing migration drift (see next item).** Task 12 of the allow-custom-components plan is three scenarios (gate on + tenant, gate on + admin, gate off + tenant) exercising the UI surfaces end-to-end. The dev server refuses to start because of the drift described below. When drift is resolved, run the three scenarios from `docs/superpowers/plans/2026-04-22-allow-custom-components-gate.md` Task 12. Until then, the backport's unit + integration test suites (208 lfx graph + 45 backend API + 11 hook + 16 CodeAreaModal gating + 45 sidebar + 3 upload-precheck) are the validation of record.

### Pre-existing multi-tenant migration drift on `platform-multi-tenant`

- [ ] **`platform-multi-tenant` has partially-reverted metering/notifier/alerting tables in its migration chain.** Running `make dev` against a fresh postgres DB fails at startup with `AutogenerateDiffsDetected`: alembic creates `alert_rule`, `audit_log`, `org_usage_daily`, `flow_usage_daily`, `org_usage_threshold`, `admin_notification` tables via migrations, but the corresponding model classes are no longer declared in the tree. Additional drift: alembic wants to add UniqueConstraints on `apikey.id` / `flow.id` / `user.id` (redundant with primary keys — known autogenerate false-positive) and remove `flow_run.model_usage` / `flow_run.cost_cents` / `trace.flow_run_id` columns.
  **Root cause:** metering/notifier/alerting code was deleted but the migrations that created its schema are still in the alembic chain with no corresponding "drop table" migration.
  **Fix options:** (a) write a new alembic migration that drops the orphaned tables + columns, (b) surgical revert of the migrations that added them, (c) restore the model declarations.
  **Impact:** blocks local `make dev` for anyone with a fresh DB or who drops/recreates it.

### `_new_flow` multi-tenant folder fallback bug (surfaced by Task 5)

- [ ] **`get_or_create_default_folder(session, user_id)` keys on `user_id` only; no org argument.** A multi-membership user (e.g. user with both an auto-provisioned personal org and an explicit test-created org) can hit `CrossOrgFKError` when `_new_flow` is called without an explicit `folder_id`: the folder's `organization_id` resolves via the scoping trigger's first-row membership lookup, which can differ from the `current_org` the flow is being created under. Reproduces in `test_create_flow_accepts_custom_component_for_platform_admin` — worked around via a pre-seeded folder. **Fix:** derive the default folder's `organization_id` from `current_org` (not from membership-roulette). `_new_flow` or `get_or_create_default_folder` should accept and persist an explicit org.
  - File: `src/backend/base/langflow/services/database/models/folder/utils.py::get_default_folder_id`
  - Scoping trigger: `src/backend/base/langflow/services/database/scoping.py::_user_after_insert`

### `test_templates_endpoints.py` — 6 failing tests pre-existing (surfaced by Task 7)

- [ ] **Six tests in `src/backend/tests/unit/api/v1/test_templates_endpoints.py` fail with `"Only platform admins may create platform-scoped templates."`** The tests use a `get_current_active_superuser` fixture that predates the 2026-04-22 security fix (commit `112e55edbe`), which introduced the `is_superuser` vs `is_platform_admin` distinction. The fixture's superuser lacks `is_platform_admin=True`. Either update the fixture, split tests that exercise platform-scoped templates into a separate suite with a platform-admin user, or fold `is_platform_admin=True` into the existing superuser fixture globally. Not caused by the gate backport; verified by stashing the gate-task changes and reproducing identical failures.

### `update_template` (PUT) is still ungated

- [ ] **`PUT /api/v1/templates/{template_id}` (`update_template`) accepts a `source_flow_id` that could introduce custom code.** The handler is currently superuser-only, so it's a latent defense-in-depth gap rather than an active vulnerability. Whenever `update_template` is opened to non-superusers (or if the superuser fixture above gets a non-platform-admin caller), add the same gate wired into `create_template` per Task 7.

## Plan (New-User Org Assignment — 2026-04-23)

### UserManagementModal cleanup

- [ ] **Lint-clean the privileged-flag clearing effect's dep array.** `useEffect(() => { if (isSuperUser || isPlatformAdmin) { ... } }, [isSuperUser, isPlatformAdmin])` at `src/frontend/src/modals/userManagementModal/index.tsx` omits `handleInput` from its deps. It is safe today (the body only drives `setInputState` via `handleInput`, and `setInputState` is stable), but `eslint-plugin-react-hooks/exhaustive-deps` will complain. Inline two `setInputState((prev) => ({ ...prev, organization_id: "", role: "member" }))` calls to dodge the rule entirely.

- [ ] **Edit-mode PATCH body carries the new create-only fields.** `inputState` is now initialized from `CONTROL_NEW_USER`, which includes `organization_id: ""` and `role: "member"`. In edit mode, `handleEditUser` passes the full `inputState` to `PATCH /users/{id}`. The backend `UserUpdate` schema silently ignores unknowns, so this is noise rather than a bug — but consider splitting into `CONTROL_NEW_USER` (create) + `CONTROL_EDIT_USER` (edit), or whitelisting fields in `handleEditUser`.

## 2026-04-23 — Security Advisory Backport follow-ups

**Source:** `docs/superpowers/plans/2026-04-23-security-advisory-backport.md`
**Integrated commits:** `344ed42b4b` (T3), `2ab9f3d228` (T4), `a2bbce48ce` (T1). T2 was reverted (`fdc91e5347`) — see below.
**Triage reports:** `docs/superpowers/security-review-2026-04-23/advisories-{a,b,c}.md`

### Plan premise partially invalid — commit 642e39fcb8 never reached our branch

- [ ] **The plan attributed missing fixes to the 2026-04-15 release-merge revert (`642e39fcb8`); that commit is NOT in `platform-multi-tenant`'s ancestry.** My earlier verification used `git log --all --oneline | grep 642e39fcb8` which walks all refs, not the branch lineage. The commit lives on `origin/aka/main-1` / `origin/release-1.9.0-3`. Two practical consequences: (1) Tasks 1 and 2 found their fixes already applied on `platform-multi-tenant` — only regression-guard tests were added. (2) **Task 5 (revert-audit) is moot for our branch** — there is no revert to audit here. However, the agent reports confirm CVE-2026-33309 was genuinely live on our tree (T3's agent watched a file actually escape to `~/Library/Caches/` during its failing test), so the MISSING/PARTIAL verdicts for T3 and T4 held up on their own merits, not because of a revert story.

### T2 regression test could not be integrated — AUTO_LOGIN harness interaction

- [ ] **`test_download_image_ownership.py` (CVE-2026-33484 regression guard) was reverted (commit `fdc91e5347`).** The tests asserted 401/403 (no auth) and 404 (cross-user) on `GET /api/v1/files/images/{flow_id}/{file_name}`. The production `Depends(get_flow)` protection is already applied at `src/backend/base/langflow/api/v1/files.py:139` — the code is correct. Tests failed because the `client` fixture is auto-authenticated when AUTO_LOGIN is on, so both cases reached the handler, passed `get_flow`, and surfaced a 500 from the storage call instead of a 401/403/404. To reinstate coverage, either (a) add a new `unauthenticated_client` fixture that disables AUTO_LOGIN, (b) patch the settings for this test to disable AUTO_LOGIN, or (c) use a separately-instantiated FastAPI TestClient with explicit auth dependencies.

### Task 5 (Revert Audit) — not executed, see above

- [ ] **Task 5 of the plan was scoped to enumerate what else the `642e39fcb8` revert re-exposed. Since that commit never landed on `platform-multi-tenant`, there is no revert to audit.** Close this item unless/until a similar release-merge revert appears on our branch.

## 2026-04-23 — `/custom_component/update` RCE surface still ungated

**Origin:** Commit `e4867515e` ("require superuser for custom component endpoints") over-gated `POST /api/v1/custom_component/update`. Reverted on the same day because that endpoint is the hot path for every dynamic field refresh (Agent model dropdown via `use-refresh-model-inputs.ts:230`, all template value writes via `use-post-template-value.ts:58`) — superuser-gating it broke the normal-user UI with 403s.

- [ ] **Endpoint is back on `CurrentActiveUser` (its pre-2026-04-23 shape) but still calls `Component(_code=code_request.code)` → `build_custom_component_template(...)`, which compiles and imports user-supplied Python at request time.** That's a pre-run RCE surface for any authenticated user, regardless of the deploy-level `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` setting and regardless of `is_platform_admin`.
- [ ] **Proper fix: integrate `resolve_component_gate_flags` into the handler.** When `allow_custom_components=False AND not caller_is_platform_admin`, the endpoint must NOT compile arbitrary `code_request.code`. Two viable shapes:
  - (a) Look up the component's canonical code server-side using a stable identifier (e.g., `template._type` or a registered-component name in the request) and use that instead of the user-supplied `code`. The user-supplied `code` becomes informational only.
  - (b) Hash-compare `code_request.code` against the registered code for that component type; if they match, accept; if they differ, require the gate. Requires extending the request schema with a component-identity field.
- [ ] **Sibling endpoint `POST /custom_component` remains correctly gated on `get_current_active_superuser`.** It's only invoked from the Code-paste validator (`use-post-validate-component-code.ts`), which the UI already restricts to platform admins via `useCustomComponentsAllowed`. That endpoint and its 403 negative test (`test_custom_component_build_requires_superuser`) are untouched by the revert.

## 2026-04-24 — Tailwind Maximization Phase 1 deferrals

Surfaced while executing `docs/superpowers/plans/2026-04-22-tailwind-maximization.md` Phase 1. These three items fell out of the "dead code + unused styling deps" scope and were deferred so Phase 1 could ship cleanly.

### Chakra number-input replacement

- [ ] **`@chakra-ui/number-input` is still consumed.** Call sites: `src/components/core/parameterRenderComponent/components/floatComponent/index.tsx:7` and `.../intComponent/index.tsx:7`. Removing the dep requires replacing the `<NumberInput>` primitive with either a plain `<input type="number">` + Tailwind styling, or a Radix-based equivalent. Plan Phase 1 opted to delete only the fully-unused Chakra dep (`@chakra-ui/system`) and leave this one until the two call sites can be migrated.

### simple-sidebar ↔ sidebar consolidation blocker

- [ ] **`src/components/ui/simple-sidebar.tsx` cannot be deleted in favor of `ui/sidebar` because the two have materially different APIs.** `simple-sidebar` is a pixel-width-resizable drag-handle sidebar with a parent-width ResizeObserver and width-constraint state; `ui/sidebar` is a cookie-backed section sidebar with no drag behavior. Call sites relying on the unique behavior: `src/components/core/flowToolbarComponent/components/playground-button.tsx` (`SimpleSidebarTrigger`), `src/components/core/playgroundComponent/sliding-container/components/flow-page-sliding-container.tsx` (`useSimpleSidebar`), `src/pages/FlowPage/index.tsx` (multiple exports). Either port the resize/drag/parent-observer features into `ui/sidebar` and then migrate callers, or accept the two-sidebar split as intentional and rename `simple-sidebar` to something non-misleading (e.g., `resizable-sidebar.tsx`). Plan Phase 1 escalation rule triggered; deferred.

### `src/style/classes.css` audit needs visual QA, not grep

- [ ] **The 513-line `src/style/classes.css` is not app-utility CSS; it's a dumping ground of third-party-library styling overrides** (`.react-flow__*`, `.ag-cell*`, `.cm-*` for CodeMirror, `.jse-*` for jsoneditor, `.ace_scrollbar*` for Ace editor, plus `.json-view*` / `.card-shine-effect` / version-animation keyframes). Plan Phase 1's grep-based "0 source refs = dead" audit produces false positives here: those class names are applied by the third-party libs' own DOM rendering, not by our source. Safe cleanup requires per-rule visual QA (boot the app, confirm the library still applies the class, confirm the override is still visually meaningful) rather than a grep. Deferred to a dedicated pass.
