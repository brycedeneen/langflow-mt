# Flow/Folder Ownership Transition Worklist

Purpose: every call site below replaces `user_id == current_user.id` (and equivalent
`.where(Flow.user_id == ...)` / `.where(Folder.user_id == ...)` filters) with
`assert_org_role(flow.organization_id, MIN_ROLE)` (or the equivalent
`OrgRoleViewer` / `OrgRoleMember` / `OrgRoleOperator` FastAPI dependency) in
Tasks 22-26.

`MIN_ROLE` per endpoint family:
- **Viewer+** for flow/folder read endpoints
- **Member+** for flow/folder CRUD write endpoints
- **Operator+** for flow execution endpoints (run/build/stream/cancel/webhook)

Roles helper already exists at `src/backend/base/langflow/api/utils/authz.py`
(exports `assert_org_role`, `require_org_role`, and the
`OrgRoleOwner/Admin/Member/Operator/Viewer` annotated deps). `CurrentOrg` is a
FastAPI dep via `src/backend/base/langflow/api/utils/org_helpers.py::get_current_organization`.

`user_id` stays on `Flow`/`Folder` as a created_by attribution column (the
migration from plan Task 3 made its FK `ON DELETE SET NULL`).

## Flow endpoints

### Reads (→ Viewer+)

- `src/backend/base/langflow/api/v1/flows.py:414-508` — `GET /flows/` (`read_flows`) — current: `stmt = select(Flow).where(Flow.user_id == current_user.id)` with an `OR Flow.user_id IS NULL` leg when `AUTO_LOGIN` is on, then ANDed with `Flow.organization_id == current_org.id OR Flow.organization_id IS NULL`. Replace with: scope by org only (`Flow.organization_id == current_org.id`) plus `OrgRoleViewer` gate; drop user_id legs. Hit lines: 466-470, 473.
- `src/backend/base/langflow/api/v1/flows.py:511-521` — helper `_read_flow(session, flow_id, user_id, organization_id)` — current: `.where(Flow.user_id == user_id)` plus optional org filter. Replace with org-scoped lookup (`Flow.id == flow_id AND Flow.organization_id == current_org.id`) and caller-side `assert_org_role(..., VIEWER)`. Used by `read_flow`, `update_flow`, `delete_flow`, `generate_or_reset_webhook_api_key`. Hit line: 518.
- `src/backend/base/langflow/api/v1/flows.py:524-536` — `GET /flows/{flow_id}` (`read_flow`) — delegates to `_read_flow`. Ownership collapses into the helper refactor above.
- `src/backend/base/langflow/api/v1/flows.py:539-551` — `GET /flows/public_flow/{flow_id}` (`read_public_flow`) — **shared helper:** calls `get_user_by_flow_id_or_endpoint_name` then re-enters `read_flow` with that synthesized user. Once `read_flow` stops requiring user match, the synthetic-user indirection is redundant; decide in Task 22 whether to keep it for telemetry or drop it.
- `src/backend/base/langflow/api/v1/flow_version.py:68-73` — helper `_get_user_flow` — current: `.where(Flow.user_id == user_id)`. Used by all four version endpoints below (`list_flow_versions`, `get_single_flow_version`, `create_snapshot`, `activate_version`, `delete_version_entry`). The first two are reads (Viewer+); the others are writes (Member+). Refactor the helper to accept org context and gate with the appropriate role at each call site.
- `src/backend/base/langflow/api/v1/flow_version.py:87-101` — `GET /flow_versions/` (`list_flow_versions`) — read, Viewer+. Note: `get_flow_version_list(..., current_user.id, ...)` also filters by user id internally — check for symmetrical filter inside the repository layer.
- `src/backend/base/langflow/api/v1/flow_version.py:109-121` — `GET /flow_versions/{version_id}` (`get_single_flow_version`) — read, Viewer+. Also passes `current_user.id` into `get_flow_version_entry_or_raise`.
- `src/backend/base/langflow/api/v1/traces.py:45-99` — `GET /monitor/traces` (`get_traces`) — delegates to `fetch_traces(current_user.id, ...)`. Read, Viewer+.
- `src/backend/base/langflow/api/v1/traces.py:102-135` — `GET /monitor/traces/{trace_id}` (`get_trace`) — delegates to `fetch_single_trace(current_user.id, trace_id)`. Read, Viewer+.
- `src/backend/base/langflow/api/v1/monitor.py:44-63` — `GET /monitor/messages/sessions` (`get_message_sessions`) — joins `Flow` and filters `Flow.user_id == current_user.id` (line 55). Read, Viewer+.
- `src/backend/base/langflow/api/v1/monitor.py:66-99` — `GET /monitor/messages` (`get_messages`) — same join + `Flow.user_id == current_user.id` (line 80). Read, Viewer+.
- `src/backend/base/langflow/api/v1/flows.py:1003-1063` — `POST /flows/download/` (`download_multiple_file`) — current: `Flow.user_id == user.id AND Flow.id.in_(flow_ids) AND (Flow.organization_id == current_org.id OR NULL)`. Read (exporting existing flows). Viewer+. Hit line: 1015.
- `src/backend/base/langflow/api/v1/flows.py:1064-1099` — `GET /flows/basic_examples/` (`read_basic_examples`) — reads starter flows filtered by `Flow.user_id == user.id` (line 988). These are system-owned example flows; once scoping moves to org, consider whether examples are org-scoped or global. Read, Viewer+. Hit lines: 988, 1015 (second in `_basic_examples` helper path).

### Writes (→ Member+)

- `src/backend/base/langflow/api/v1/flows.py:208-356` — helper `_new_flow` — used by `create_flow`, `upsert_flow` (create path), `upload_file`. Uses `user_id` parameter for:
  - folder validation query (line 237: `Folder.user_id == user_id`)
  - name uniqueness (line 250) and auto-rename `like` (line 253)
  - endpoint-name uniqueness (line 283) and auto-rename (line 295)
  - folder-existence validation (line 331)
  Migrate uniqueness + folder checks to be scoped by `organization_id` instead of `user_id`. `user_id` stays only as the `created_by` attribution column (still assigned on line 243). **Shared helper — decide in Task 23.**
- `src/backend/base/langflow/api/v1/flows.py:359-411` — `POST /flows/` (`create_flow`) — entry point for `_new_flow`. Add `OrgRoleMember` gate.
- `src/backend/base/langflow/api/v1/flows.py:554-659` — `PATCH /flows/{flow_id}` (`update_flow`) — uses `_read_flow` (see reads above) + folder-ownership re-check at line 624 (`Folder.user_id == current_user.id`). Write, Member+.
- `src/backend/base/langflow/api/v1/flows.py:662-728` — `PUT /flows/{flow_id}` (`upsert_flow`) — direct ownership probe at line 688 (`existing_flow.user_id != current_user.id or ...`) plus `_update_existing_flow` (Member+). Write, Member+.
- `src/backend/base/langflow/api/v1/flows.py:731-818` — helper `_update_existing_flow` — folder check (line 755: `Folder.user_id == user_id`), name-uniqueness check (line 766: `Flow.user_id == user_id`), endpoint-name uniqueness (line 780: `Flow.user_id == user_id`). **Shared helper — decide in Task 23.**
- `src/backend/base/langflow/api/v1/flows.py:821-852` — `POST /flows/{flow_id}/webhook-api-key` — calls `_read_flow` for ownership, then mutates secret store. Write, Member+.
- `src/backend/base/langflow/api/v1/flows.py:855-885` — `DELETE /flows/{flow_id}` (`delete_flow`) — calls `_read_flow` for ownership, then `cascade_delete_flow`. Write, Member+.
- `src/backend/base/langflow/api/v1/flows.py:888-909` — `POST /flows/batch/` (`create_flows`) — assigns `flow.user_id = current_user.id` without ownership filter (no read-before-write). Stamp `created_by` from `current_user.id`, keep `organization_id = current_org.id`, gate Member+.
- `src/backend/base/langflow/api/v1/flows.py:912-962` — `POST /flows/upload/` (`upload_file`) — reuses `_new_flow`. Write, Member+.
- `src/backend/base/langflow/api/v1/flows.py:965-1001` — `DELETE /flows/` (`delete_multiple_flows`) — current: `Flow.user_id == user.id AND Flow.id.in_(flow_ids) AND (org match OR null)` (line 988). Replace user filter with org filter. Write, Member+.
- `src/backend/base/langflow/api/v1/flow_version.py:124-152` — `POST /flow_versions/` (`create_snapshot`) — uses `_get_user_flow`. Write, Member+.
- `src/backend/base/langflow/api/v1/flow_version.py:155-220` — `POST /flow_versions/{version_id}/activate` (`activate_version`) — uses `_get_user_flow` + passes `current_user.id` to `create_flow_version_entry`. Write, Member+.
- `src/backend/base/langflow/api/v1/flow_version.py:223-238` — `DELETE /flow_versions/{version_id}` (`delete_version_entry`) — uses `_get_user_flow` + passes `current_user.id` to `delete_flow_version_entry`. Write, Member+.
- `src/backend/base/langflow/api/v1/traces.py:138-167` — `DELETE /monitor/traces/{trace_id}` (`delete_trace`) — joins `Flow` + filters `Flow.user_id == current_user.id` (line 155). Write, Member+.
- `src/backend/base/langflow/api/v1/traces.py:170-196` — `DELETE /monitor/traces?flow_id=...` (`delete_traces_by_flow`) — filters `Flow.user_id == current_user.id` (line 183). Write, Member+.
- `src/backend/base/langflow/api/v1/monitor.py` — `DELETE /monitor/builds`, `DELETE /monitor/messages`, `PUT /monitor/messages/{id}`, `DELETE /monitor/messages/session/{session_id}`: these currently rely on the `get_current_active_user` dep with no ownership filter at the router layer (the v1 CRUD in `vertex_builds.crud` and `messages.crud` may or may not filter; inspect when touching them in Task 23). Flag as Member+ once org scoping is chosen. **Shared helpers in crud/ layer — decide in Task 23.**

### Execution (→ Operator+)

- `src/backend/base/langflow/api/v1/chat.py:58-135` — `POST /build/{flow_id}/vertices` (`retrieve_vertices_order`, deprecated) — no ownership check today beyond `get_current_active_user`. Add Operator+ gate against flow's org.
- `src/backend/base/langflow/api/v1/chat.py:138-203` — `POST /build/{flow_id}/flow` (`build_flow`) — loads flow via `session.get` with no user filter (line 178); `start_flow_build` delegates execution. Add Operator+ gate.
- `src/backend/base/langflow/api/v1/chat.py:206-221` — `GET /build/{job_id}/events` (`get_build_events`) — only checks `get_current_active_user`; cannot easily check org until the queue entry carries `organization_id`. **Needs follow-up design:** Task 25 should ensure build jobs are resolvable to an org so Operator+ can be enforced. For now, inventory-only.
- `src/backend/base/langflow/api/v1/chat.py:224-259` — `POST /build/{job_id}/cancel` (`cancel_build`) — same as above. Operator+ once job→org mapping exists.
- `src/backend/base/langflow/api/v1/chat.py:262-432` — `POST /build/{flow_id}/vertices/{vertex_id}` (`build_vertex`, deprecated) — Operator+.
- `src/backend/base/langflow/api/v1/chat.py:517-559` — `GET /build/{flow_id}/{vertex_id}/stream` (`build_vertex_stream`, deprecated) — Operator+.
- `src/backend/base/langflow/api/v1/chat.py:580-659` — `POST /build_public_tmp/{flow_id}/flow` (`build_public_tmp`) — public flow build, authorized via `AccessTypeEnum.PUBLIC` on the flow + a deterministic `client_id` cookie; no per-user check today. Keep current behavior (public == anyone); no role gate.
- `src/backend/base/langflow/api/v1/chat.py:662-678` — `GET /build_public_tmp/{job_id}/events` — public, no auth. Leave.
- `src/backend/base/langflow/api/v1/chat.py:681-710` — `POST /build_public_tmp/{job_id}/cancel` — public, no auth. Leave.
- `src/backend/base/langflow/api/v1/endpoints.py:393-407` — helper `check_flow_user_permission` — current: `if flow.user_id != api_key_user.id: raise 403`. Used by `_run_flow_internal` (line 441) and `experimental_run_flow` (line 1004). Replace with Operator+ membership check on `flow.organization_id` for the API-key user. **Shared helper — decide in Task 25.**
- `src/backend/base/langflow/api/v1/endpoints.py:548-603` — `POST /run/{flow_id_or_name}` (`simplified_run_flow`) — API-key path; relies on `check_flow_user_permission`. Operator+.
- `src/backend/base/langflow/api/v1/endpoints.py:606-672` — `POST /run/session/{flow_id_or_name}` (`simplified_run_flow_session`) — session-auth path; relies on `check_flow_user_permission`. Operator+.
- `src/backend/base/langflow/api/v1/endpoints.py:716-771` — `GET /webhook-events/{flow_id_or_name}` (`webhook_events_stream`) — already uses the new multi-tenant helper `_authorize_sse_subscriber` which checks org membership first and falls back to `flow.user_id == user.id` only for legacy flows (line 689). Once legacy rows are backfilled we can drop the fallback. Operator+. **Shared helper `_authorize_sse_subscriber` — already mostly on the new model; decide in Task 25 whether to promote Viewer (consume-only) vs Operator (execute).**
- `src/backend/base/langflow/api/v1/endpoints.py:802-938` — `POST /webhook/{flow_id_or_name}` (`webhook_run_flow`) — authorized by per-flow webhook API key (validated via secret store at line 832). No user role gate applied; leave the API-key authorization as primary, but the enqueue path at line 867 uses `_db_flow.organization_id` for routing — already org-aware.
- `src/backend/base/langflow/api/v1/endpoints.py:941-1064` — `POST /run/advanced/{flow_id_or_name}` (`experimental_run_flow`) — uses `check_flow_user_permission` AND then re-queries the flow with `Flow.user_id == api_key_user.id` filter (line 1026) before using its data. Replace both with Operator+ on org. Operator+.
- `src/backend/base/langflow/api/v1/endpoints.py:1101-*` — `POST /upload/{flow_id}` — already deprecated (raises 400). Skip.
- `src/backend/base/langflow/helpers/flow.py:399-414` — helper `get_flow_by_id_or_endpoint_name` — used as a FastAPI `Depends` in all `/run/*` and `/webhook*` endpoints. Currently accepts optional `user_id` and filters `Flow.user_id == uuid_user_id` only when resolving by endpoint_name. Since it's a dep injected with no user context, the filter is effectively a no-op today; Task 25 can remove the branch and make endpoint-name resolution org-scoped (or leave global if endpoint_name is intended to be globally unique). **Shared helper — decide in Task 25.**

## Folder endpoints

### Reads (→ Viewer+)

- `src/backend/base/langflow/api/v1/projects.py:219-241` — `GET /projects/` (`read_projects`) — current: `or_(Folder.user_id == current_user.id, Folder.user_id == None) AND or_(Folder.organization_id == current_org.id, Folder.organization_id == None)` (lines 230-231). Replace with org-only scoping + Viewer+.
- `src/backend/base/langflow/api/v1/projects.py:244-310` — `GET /projects/{project_id}` (`read_project`) — current: `Folder.user_id == current_user.id AND (Folder.organization_id == current_org.id OR NULL)` at lines 265-266, plus `flows_from_current_user_in_project = [flow for flow in project.flows if flow.user_id == current_user.id]` (line 303). Replace with org scoping + Viewer+; drop the post-query per-user flow filter (org scoping already handles it).
- `src/backend/base/langflow/api/v1/projects.py:612-666` — `GET /projects/download/{project_id}` (`download_file`) — current: `Folder.user_id == current_user.id AND (...)` at line 624, plus `Flow.folder_id == project_id` (no user filter on flows). Read/export, Viewer+.
- `src/backend/base/langflow/api/v1/folders.py:34-61` — `GET /folders/{folder_id}` (redirect) — thin redirect to `/projects/{folder_id}`. Inherit Viewer+ via the project endpoint.
- `src/backend/base/langflow/api/v1/folders.py:28-32` — `GET /folders/` (redirect) — redirect to `/projects/`. Inherit Viewer+.

### Writes (→ Member+)

- `src/backend/base/langflow/api/v1/projects.py:55-216` — `POST /projects/` (`create_project`) — name uniqueness / auto-rename scoped by `Folder.user_id == current_user.id` (lines 74, 80). Replace with org-scoped uniqueness; still stamp `created_by` from `current_user.id`. Member+.
- `src/backend/base/langflow/api/v1/projects.py:313-506` — `PATCH /projects/{project_id}` (`update_project`) — ownership check (line 328: `Folder.user_id == current_user.id`) + per-user flow enumeration for MCP payload (line 340: `Flow.user_id == current_user.id`). Replace both with org scoping. Member+.
- `src/backend/base/langflow/api/v1/projects.py:509-609` — `DELETE /projects/{project_id}` (`delete_project`) — ownership check + cascade (line 519: `Flow.folder_id == project_id AND Flow.user_id == current_user.id`; line 529: `Folder.user_id == current_user.id`). Replace both with org scoping. Member+.
- `src/backend/base/langflow/api/v1/projects.py:668-*` — `POST /projects/upload/` (`upload_file`) — delegates to `_new_flow` (which has its own per-user checks to migrate). Member+.
- `src/backend/base/langflow/api/v1/folders.py:22-26` — `POST /folders/` — thin redirect. Member+.
- `src/backend/base/langflow/api/v1/folders.py:63-70` — `PATCH /folders/{folder_id}` — thin redirect. Member+.
- `src/backend/base/langflow/api/v1/folders.py:72-79` — `DELETE /folders/{folder_id}` — thin redirect. Member+.

## Shared helpers (decide in Task 22-25 depending on who calls first)

- `src/backend/base/langflow/api/v1/flows.py::_new_flow` — Tasks 22/23.
- `src/backend/base/langflow/api/v1/flows.py::_read_flow` — Tasks 22/23/25.
- `src/backend/base/langflow/api/v1/flows.py::_update_existing_flow` — Task 23.
- `src/backend/base/langflow/api/utils/core.py::cascade_delete_flow` — deletion helper. No user check today (pure `flow_id`-based cascade); callers gate, helper stays. Confirm in Task 23.
- `src/backend/base/langflow/api/v1/flow_version.py::_get_user_flow` — Tasks 22/23.
- `src/backend/base/langflow/api/v1/endpoints.py::check_flow_user_permission` — Task 25.
- `src/backend/base/langflow/api/v1/endpoints.py::_authorize_sse_subscriber` — Task 25 (already largely migrated; just tighten role).
- `src/backend/base/langflow/api/v1/endpoints.py::verify_public_flow_and_get_user` (resides in `api/utils/core.py:396`) — public-flow path, no ownership gate. Leave.
- `src/backend/base/langflow/helpers/flow.py::get_flow_by_id_or_endpoint_name` — Task 25.
- `src/backend/base/langflow/helpers/flow.py::list_flows`, `list_flows_by_flow_folder`, `list_flows_by_folder_id`, `get_flow_by_id_or_name`, `find_flow`, `generate_unique_flow_name`, `load_flow_by_id_or_name` (lines 36-438) — internal component/flow helpers called from LFX components (not HTTP). They filter `Flow.user_id` to scope to the running flow's owner. **Out of scope for the HTTP transition** (these are runtime helpers, not access gates); revisit later if multi-tenant runtime context needs org id too.
- `src/backend/base/langflow/services/tracing/repository.py::fetch_traces`, `fetch_single_trace`, `delete_traces_for_flow` (lines 151, 157, 225) — called by the `traces.py` router; refactor together with the router endpoints in Tasks 22/23.
- `src/backend/base/langflow/services/database/models/folder/utils.py::create_default_folder_if_it_doesnt_exist`, `get_default_folder_id` — internal bootstrap utilities (each user still gets a default folder); keep per-user for now. **Out of scope.**
- `src/backend/base/langflow/helpers/folders.py::generate_unique_folder_name` — only called from `initial_setup/setup.py` paths that predate org scoping. Out of scope for HTTP CRUD.
- `src/backend/base/langflow/initial_setup/setup.py` lines 678, 1154, 1166 — initial-setup bootstrap (Assistant folder, default folder, legacy-name lookups). Out of scope.
- `src/backend/base/langflow/services/database/service.py` lines 318, 340 — setup-time superuser scoping. Out of scope.
- `src/backend/base/langflow/api/utils/mcp/config_utils.py` lines 297, 307 — MCP config user-scoped helpers. Not part of flow/folder CRUD surface; out of scope for this transition.
- `src/backend/base/langflow/services/flow/flow_runner.py:230` — `clear_user_state` admin/reset helper. Out of scope.
- `src/lfx/src/lfx/base/mcp/util.py:391` — lfx-side flow listing for MCP tool surface, scoped by `Flow.user_id`. Out of scope for HTTP transition; if/when lfx runs across orgs, revisit.

## MCP-projects folder endpoints — decide during Task 24

`src/backend/base/langflow/api/v1/mcp_projects.py` has ~7 `Folder.user_id == user.id` (or `current_user.id`) filters at lines 121, 187, 229, 334, 489, 968, 1510. These are MCP-specific auth gates (the module is separate from `projects.py`). They should move to Member+ (for mutations) or Viewer+ (for reads) against the folder's org, but the module is outside the core folder CRUD router. Flag for Task 24 follow-up.

## Out-of-scope (per plan Non-Goals)

Per the plan's "Not covered (deliberately deferred per spec Non-Goals / Known Gaps)":

> API keys, variables, files, deployments, flow_runs, messages, transactions, jobs, vertex_builds — stay per-user.

Hits observed during this audit that belong to those families (not to be changed in Tasks 22-26):

- `src/backend/base/langflow/api/v2/files.py` lines 199, 294, 358, 381, 478, 727 — `UserFile.user_id == current_user.id`.
- `src/backend/base/langflow/api/v2/mcp.py:187` — `Variable.user_id == current_user.id`.
- `src/backend/base/langflow/api/v1/mcp_utils.py:136` — `UserFile.user_id == current_user.id`.
- `src/backend/base/langflow/api/v1/templates.py:201` — `Membership.user_id` filter (templates-scoped membership resolution, not flow ownership).
- `src/backend/base/langflow/api/v1/endpoints.py:1025-1026` — commented-out query (leave, cleanup only).
- `src/backend/base/langflow/api/v1/users.py:147` — user self-identity check (`current_user.id == user_id`); not an ownership gate.

## Tasks blocked on this worklist

- **Task 22** — flow reads: `flows.py::_read_flow`, `read_flow`, `read_flows`, `read_public_flow`, `download_multiple_file`, `read_basic_examples`; `flow_version.py::list_flow_versions`, `get_single_flow_version`; `traces.py::get_traces`, `get_trace`; `monitor.py::get_message_sessions`, `get_messages`.
- **Task 23** — flow writes: `flows.py::_new_flow`, `_update_existing_flow`, `create_flow`, `update_flow`, `upsert_flow`, `delete_flow`, `delete_multiple_flows`, `generate_or_reset_webhook_api_key`, `create_flows`, `upload_file`; `flow_version.py::create_snapshot`, `activate_version`, `delete_version_entry`; `traces.py::delete_trace`, `delete_traces_by_flow`; `monitor.py` mutation endpoints (after deciding ownership strategy).
- **Task 24** — folder CRUD: `projects.py::read_projects`, `read_project`, `create_project`, `update_project`, `delete_project`, `download_file`, `upload_file`; `folders.py` redirect endpoints; revisit MCP-projects folder gates.
- **Task 25** — flow execution: `chat.py::build_flow`, `retrieve_vertices_order`, `build_vertex`, `build_vertex_stream`, `get_build_events`, `cancel_build`; `endpoints.py::_run_flow_internal`, `simplified_run_flow`, `simplified_run_flow_session`, `experimental_run_flow`, `webhook_events_stream`, `check_flow_user_permission`, `_authorize_sse_subscriber`; `helpers/flow.py::get_flow_by_id_or_endpoint_name`. Public-flow variants (`build_public_tmp/*`) unchanged.
- **Task 26** — follow-up cleanups (whatever Tasks 22-25 leave on the floor: `user_id` now attribution-only, callers of shared helpers, tests that asserted per-user 404 behavior).
