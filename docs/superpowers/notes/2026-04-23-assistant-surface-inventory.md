# Assistant Data-Access Surface Inventory

**Date:** 2026-04-23
**Scope:** Part A (Sprint 2) of the Assistant Org-Isolation spec — every surface an assistant-authenticated caller (or the Flow Builder Assistant's LLM tool-loop) can reach, and whether that surface scopes its DB reads by `organization_id`.
**Out-of-scope per spec A.3:** template-catalog filtering, per-org component metadata, OIDC/SAML. Those rows are marked `N/A — out of scope`.
**Target entities in scope:** `Flow`, `FlowRun`, `File`, `Message`, `Attachment`, `AssistantConversation`, `AssistantMessage`, `Variable`.

## Methodology

1. Enumerated `@router.(get|post|put|delete|patch)` decorators in `api/v1/assistant.py` and `api/v1/component_assist.py`.
2. Enumerated tool definitions from `services/assistant/tools/registry.py` (`CATALOG_TOOLS`, `MUTATION_TOOLS`, `INSPECTION_TOOLS`). No LangChain `bind_tools` / `@tool` / `StructuredTool` are used — tools are plain async functions dispatched by the orchestrator in `services/assistant/service.py` (`CATALOG_DISPATCH`, `FlowMutationTools`, `FlowInspectionTools`).
3. Traced each route and each tool to the DB query (direct `select(...)` or service call).
4. Cross-referenced with `services/database/scoping.py::TENANT_SCOPED_TABLES` to distinguish tables where `MissingOrgFilterError` fires in dev/test from tables that have no ORM-layer safety net. Note: `install_scoping_guards(..., enforce_select=_env in {"dev","test"})` — prod does **not** raise on missing org filter, so every ❌ is a real runtime leak.
5. Cross-referenced with `CrossOrgFKError` (scoping.py L65, L208-220) which catches cross-org inserts at the mapper `before_insert` hook.

## Legend

- ✅ explicit `organization_id` filter (or direct `org_id` match on the table)
- ⚠️ implicit (e.g. filtered by `flow_id` after the flow itself was org-checked — chain-of-custody safe but fragile)
- ❌ missing filter — a real leak in prod
- `N/A` not applicable: pure in-memory / registry lookup, or out-of-scope per spec A.3

## HTTP routes

| # | Route | File:line | Entity read | Filter today | Status |
|---|-------|-----------|-------------|--------------|--------|
| 1 | `GET /assistant/flows/{flow_id}/conversation` | `api/v1/assistant.py:194` | `Flow`, then `AssistantConversation`, `AssistantMessage`, `Variable` | `Flow`: `_get_flow_with_org_check` (L89) asserts `flow.organization_id == org.id`; `AssistantConversation` filtered by `flow_id` (L209) after flow-org check; `AssistantMessage` filtered by `conversation_id` (L221); `Variable` filtered by `organization_id` + `name.in_(...)` (L110-113) | ⚠️ conversation lookup relies on chain-of-custody from the flow check; `Flow` + `Variable` are ✅ |
| 2 | `POST /assistant/flows/{flow_id}/messages` | `api/v1/assistant.py:331` | `Flow`, `Variable`, `AssistantConversation`, `AssistantMessage`; inside `_persist_assistant_turn`: `Flow` (write) | `Flow`: `_get_flow_with_org_check` (L342); `Variable`: org-filtered (L110-113); `AssistantConversation` by `flow_id` only (L352); new conversation created with `org_id=org.id` (L355) ✅; `AssistantMessage` by `conversation_id` (L364); persistence `db.get(Flow, flow_id)` at L301 has **no** org check on reload — but the outer handler already validated ownership this turn | ⚠️ persistence reload + conversation lookup rely on chain-of-custody |
| 3 | `DELETE /assistant/flows/{flow_id}/conversation` | `api/v1/assistant.py:491` | `Flow`, `AssistantConversation` | `Flow`: `_get_flow_with_org_check` (L499); `AssistantConversation` by `flow_id` (L501) | ⚠️ conversation lookup chain-of-custody |
| 4 | `GET /assistant/settings` | `api/v1/assistant.py:515` | `Variable` | `organization_id == org.id` + `name.in_(...)` (L110-113) | ✅ |
| 5 | `PUT /assistant/settings` | `api/v1/assistant.py:535` | `Variable` (upsert) | `_upsert_variable` selects by `organization_id == org.id AND name == ...` (L144-147); create writes `organization_id=org_id` (L159) | ✅ |
| 6 | `POST /assistant/flows/{flow_id}/greet` | `api/v1/assistant.py:569` | `Flow`, `Variable`, `AssistantConversation`, `AssistantMessage` | `Flow`: `_get_flow_with_org_check` (L587); `Variable`: org-filtered; `AssistantConversation` by `flow_id` (L595), new one gets `org_id=org.id` (L598) ✅; `AssistantMessage` by `conversation_id` | ⚠️ conversation lookup chain-of-custody |
| 7 | `POST /assistant/components/messages` | `api/v1/component_assist.py:129` | `Flow`, `Variable` | `_get_flow_with_org_check` (L145); `Variable` org-filtered | ✅ |

### HTTP-route notes

- `_get_flow_with_org_check` (`assistant.py:89-98`) is the canonical org gate. It `session.get(Flow, flow_id)` (no filter), then compares `flow.organization_id == org_id` in Python and raises 403 on mismatch. **Spec A.3 says cross-org should return 404, not 403** — Task 2 already landed a handler, but `_get_flow_with_org_check` still raises 403 directly. Task 5 will need to route this through `CrossOrgAccessError` / 404 or update the helper.
- `AssistantConversation.flow_id` is `unique=True, index=True` (model L12), so a conversation id collision is impossible across orgs. But the schema still stores `org_id` (model L13, `foreign_key="organization.id"`) — Task 5 should add the explicit `.where(AssistantConversation.org_id == org.id)` clause as defense-in-depth even though the `flow_id` uniqueness currently makes this redundant.
- `AssistantConversation` and `AssistantMessage` are **not** in `TENANT_SCOPED_TABLES` (scoping.py L37-50). They bypass the dev/test `MissingOrgFilterError` guard. This amplifies ⚠️ into "no safety net at any layer".

## Assistant tools (non-HTTP)

Tools are dispatched from `AssistantService._execute_tool` (`services/assistant/service.py:325`). Registry at `services/assistant/tools/registry.py`. Grouped per registry.

### Catalog tools (`CATALOG_TOOLS`)

| # | Tool | File:line | Entity read | Filter today | Status |
|---|------|-----------|-------------|--------------|--------|
| 8 | `list_categories` | `tools/catalog.py:39` → `agentic/utils/component_search` | registry (in-memory) | N/A | N/A — registry |
| 9 | `search_components` | `tools/catalog.py:53` + `metadata_lookup.fetch_component_summaries` | `ComponentMetadata` | `component_name.in_(names)` only (metadata_lookup.py:20) | N/A — component metadata out of scope (spec A.3) |
| 10 | `get_component_schema` | `tools/catalog.py:78` + `metadata_lookup.fetch_component_usage_notes` | `ComponentMetadata` | `component_name == ...` only (metadata_lookup.py:31) | N/A — component metadata out of scope |
| 11 | `list_compatible_outputs` | `tools/catalog.py:98` | registry (in-memory) | N/A | N/A — registry |
| 12 | `get_template_instructions` | `tools/template_metadata.py:10` → `metadata_lookup.fetch_template_usage_notes` | `Flow`, `TemplateMetadata` | `Flow.id == parsed` (metadata_lookup.py:84) — **no org filter**; `TemplateMetadata.flow_id == parsed` — no org filter | N/A — templates out of scope per spec A.3 |
| 13 | `apply_template` | `tools/template_apply.py:18` | `Flow` (target AND template, both reads + target write) | target: `Flow.id == target_uuid` (L38) — no org filter; template: `Flow.id == template_uuid` (L41) — no org filter; writes back via `target.data =` / `target.based_on_template_flow_id =` at L59-60 | ❌ target-flow mutation without org check — the spec carves out template filtering but **not** target-flow writes. The LLM calling `apply_template(target_flow_id=<victim_flow>, template_flow_id=<any_template>)` can overwrite any flow whose id is guessed/leaked. See "Notable" below. |

### Mutation tools (`MUTATION_TOOLS`)

All methods on `FlowMutationTools` operate on the in-memory `flow_data` dict loaded by the route handler after `_get_flow_with_org_check`. They do not read `Flow` from the DB.

| # | Tool | File:line | Entity read | Filter today | Status |
|---|------|-----------|-------------|--------------|--------|
| 14 | `add_component` | `tools/mutation.py:113` | in-memory flow_data + registry `get_component_by_name` | N/A | N/A — in-memory |
| 15 | `connect_edge` | `tools/mutation.py:236` | in-memory flow_data | N/A | N/A — in-memory |
| 16 | `set_field_value` | `tools/mutation.py:301` | in-memory flow_data | N/A | N/A — in-memory |
| 17 | `remove_component` | `tools/mutation.py:328` | in-memory flow_data | N/A | N/A — in-memory |
| 18 | `add_sticky_note` | `tools/mutation.py:355` | in-memory flow_data | N/A | N/A — in-memory |
| 19 | `create_secret_variable` | `tools/mutation.py:197` | `Variable` (write) | `VariableService.create_variable(user_id=self.user_id, organization_id=self.org_id, ...)` — service validates `organization_id` on insert (scoping.py `CrossOrgFKError` path for FK parents, though `Variable` has no FK to flow so this is a simple insert). `org_id` is explicitly passed through. | ✅ |

### Inspection tools (`INSPECTION_TOOLS`)

| # | Tool | File:line | Entity read | Filter today | Status |
|---|------|-----------|-------------|--------------|--------|
| 20 | `get_node_field_value` | `tools/inspection.py:33` | in-memory flow_data | N/A | N/A — in-memory |
| 21 | `get_webhook_credentials` | `tools/inspection.py:52` | secret store key `{org_id}/webhooks/{flow_id}` | org_id is the actor's `self.org_id` passed from the route (assistant.py:402) | ✅ |
| 22 | `list_user_variables` | `tools/inspection.py:78` | `Variable` via `VariableService.list_variables` → `get_all(user_id=user_id)` (service.py:223-224) | **`user_id` filter only** — no `organization_id` filter. The `Variable` table is tenant-scoped (scoping.py L37) so dev/test would raise `MissingOrgFilterError`, but **prod does not enforce** (`enforce_select=_env in {"dev","test"}` only). A user in multiple orgs sees variable names across orgs. | ❌ leak |

### System-prompt injection helpers (indirect assistant surface)

Invoked from `AssistantService.send_message` (`service.py:366-369`) to build the system prompt. The LLM doesn't call these directly, but their output goes straight into the prompt it reads.

| # | Helper | File:line | Entity read | Filter today | Status |
|---|--------|-----------|-------------|--------------|--------|
| 23 | `build_available_templates_block` → `fetch_template_summaries` | `metadata_lookup.py:39` | `TemplateMetadata`, `Flow` | `TemplateMetadata.agent_summary.is_not(None)`; `Flow.id.in_(flow_ids)` — no org filter on either | N/A — templates out of scope |
| 24 | `build_flow_template_context` → `fetch_template_usage_notes` | `metadata_lookup.py:73` | `Flow`, `TemplateMetadata` | same as #12 — no org filter | N/A — templates out of scope |

### MCP server surface (`services/assistant/mcp_server.py`)

A standalone MCP server that wraps the catalog tools. Not mounted in the HTTP router tree (unless/until a transport is attached separately), so not directly reachable from an assistant-authenticated HTTP caller unless exposed through MCP. The underlying tools (#8-#12) are the same — same status applies.

## Summary counts

- **Total surfaces:** 24 (7 HTTP routes + 12 assistant tools + 2 system-prompt helpers + 3 nominal re-exports not counted separately here; MCP server reuses catalog tools).
- **✅ explicit org filter:** 5 (HTTP #4, #5, #7; tools #19, #21)
- **⚠️ implicit (chain-of-custody):** 4 (HTTP #1, #2, #3, #6 — all rely on `_get_flow_with_org_check` having run; the conversation/message/persistence reads themselves have no `organization_id` clause)
- **❌ missing filter (real leak):** 2 (tool #13 `apply_template` target-flow read+write; tool #22 `list_user_variables` user-only scope)
- **N/A out-of-scope or in-memory:** 13 (catalog/template metadata out-of-scope per spec A.3; mutation + inspection in-memory tools; system-prompt template helpers)

## Fix targets for Task 5 (narrowed scope — 2 items)

Scope decision (2026-04-23, user): Task 5 fixes only the two ❌ leaks. The four ⚠️ defense-in-depth hardening items are deferred to P1.5 follow-ups (see next section). Templates/components are N/A per spec A.3.

### ❌ — must fix in Task 5

1. **`list_user_variables`** — `services/assistant/tools/inspection.py:78-98`. The call `service.list_variables(user_id=self.user_id, session=session)` needs an `organization_id=self.org_id` filter. `VariableService.list_variables` / `get_all` currently only filter by `user_id` (`services/variable/service.py:223-224, 292-294`). Fix by either:
   - Adding an `organization_id` parameter to `VariableService.list_variables` and threading it through, or
   - Filtering in the tool after the service call.
   Also wrap with `guard_assistant_org_scope(...)` as defense-in-depth.

2. **`apply_template`** — `services/assistant/tools/template_apply.py:18-73`. Two problems bundled:
   - **Target flow read (L38):** `select(Flow).where(Flow.id == target_uuid)` has no org filter. Add `.where(Flow.organization_id == actor_org_id)`.
   - **Target flow write (L59-62):** mutates `target.data` and `target.based_on_template_flow_id` with an LLM-supplied `target_flow_id`. The tool is the security boundary — even if the orchestrator always passes its own `self.flow_id`, a prompt-injected LLM could pass any UUID. Fix: require `actor_org_id` be passed into the tool and verify the loaded target's `organization_id` matches via `guard_assistant_org_scope`.
   - Template-side *read* is carved out (spec A.3); only target-flow read+write is in scope.

### N/A — confirmed out of scope (spec A.3)

- Tools #9, #10, #12, #13 (template metadata reads), #23, #24 (template prompt injection). Do **not** patch in Task 5. If the spec exclusion is ever lifted, re-scope.

## Deferred follow-ups (P1.5)

Not in Sprint 2. Track for a future hardening pass.

### Defense-in-depth (four ⚠️ items)

1. **Align `_get_flow_with_org_check` to 404 contract** — `api/v1/assistant.py:89-98` raises `HTTPException(status_code=403)`; spec A.3 + Task 2's handler want 404. Route through `guard_assistant_org_scope` (or raise `CrossOrgAccessError`). Touches all flow-scoped routes (#1, #2, #3, #6, #7) through a single helper change.

2. **Add explicit org filter to `AssistantConversation` lookups** — `assistant.py:209, 352, 501, 595`. All filter by `flow_id` only. Column exists (`AssistantConversation.org_id`). Chain-of-custody safe today because `flow_id` is unique, but fragile.

3. **Org re-check in `_persist_assistant_turn`** — `assistant.py:301`. Background task re-loads `Flow` via `db.get(Flow, flow_id)` with no org assertion. Pass `org_id` into the task closure and re-filter.

4. **Add `AssistantConversation` + `AssistantMessage` to `TENANT_SCOPED_TABLES`** — `scoping.py:37-50`. Both tables are absent, so the dev/test `MissingOrgFilterError` guard never fires on them. Adds a safety net in non-prod environments.

### Platform-level

5. **Enable `enforce_select=True` in production for the SELECT-level scoping guard** — `install_scoping_guards(..., enforce_select=_env in {"dev","test"})`. Currently prod silently tolerates missing `organization_id` filters. Turning this on in prod would make every future ❌ in an assistant tool (or anywhere else) raise instead of leak. Requires a shadow-run to audit which queries in the hot path currently lack the filter before enabling.

## Notable / worth flagging for the controller

1. **`apply_template` cross-org flow write** — this is the sharpest tool in the inventory. The LLM *could* be induced (prompt injection, tool-call hallucination) to call `apply_template(target_flow_id=<victim_uuid>, template_flow_id=<any>)` and overwrite another org's flow data wholesale. Even though the `AssistantService` orchestrator is the only in-tree caller and it passes `flow_id` from the org-checked route, the tool itself has **no `org_id` parameter** and no org assertion. Worth fixing even if no concrete exploit path exists today. This is the one ❌ the spec does NOT already exclude.

2. **`list_user_variables` scope** — `Variable` is user-scoped historically, but the fork added `Variable.organization_id` (model L45, `nullable=False`). The assistant tool filters by `user_id` only. A user who belongs to multiple orgs will see variable names across all orgs. `create_secret_variable` (#19) correctly writes `organization_id=self.org_id`, so new writes are properly partitioned — but reads leak across the boundary. This is a straightforward `WHERE organization_id = ?` add plus a `VariableService.list_variables(organization_id=...)` kwarg.

3. **SELECT-guard prod gap** — `install_scoping_guards(..., enforce_select=_env in {"dev","test"})`. In prod, missing `organization_id` filters do not raise. Every ❌ in this inventory is a real runtime leak, not a test-only invariant violation. Worth calling out in the Task 5 PR body.

4. **`AssistantConversation` / `AssistantMessage` tables absent from `TENANT_SCOPED_TABLES`** (scoping.py L37-50). Unlike `flow`, `folder`, `variable`, etc., these two assistant tables have no ORM-level guard in dev/test. If a future refactor widens `AssistantMessage` access, the safety net will not catch it. Adding them to `TENANT_SCOPED_TABLES` is a cheap hardening step (out of this task, could be a follow-up on top of Task 5).

5. **`_get_flow_with_org_check` status code** — emits 403, spec says 404. Task 2 shipped the 404 plumbing; adapting this helper is a one-line Task 5 change.

6. **CrossOrgFKError coverage** — the insert-time FK validator (scoping.py L208-220) catches `flow_id`/`folder_id` mismatches on inserts into tenant-scoped tables. It does NOT help `apply_template` (which is an **update** to an existing flow whose org is already "correct" from the DB's view) or `list_user_variables` (which is a read). So the fork's defense-in-depth layer does not cover our two ❌ cases.

7. **MCP server reuse** — `services/assistant/mcp_server.py` exposes the catalog + `get_template_instructions` tools via the MCP protocol. If an MCP transport is ever mounted, the same ❌ / N/A statuses apply. Worth keeping in mind for Part B / Sprint 3.

## Appendix: trace artifacts

- `TENANT_SCOPED_TABLES` (scoping.py L37-50): `flow, folder, file, variable, apikey, deployment, deployment_provider_account, flow_version, message, transaction, vertex_build, job`. Conspicuously absent: `assistant_conversation`, `assistant_message`.
- `_suppress` / `allow_cross_org_query` (scoping.py L52, L70-76): a contextvar escape hatch. Grep shows it is not used inside any assistant tool — we are not masking the leaks by suppression.
- `Variable.organization_id` (variable/model.py:45): `nullable=False`, `foreign_key="organization.id"`.
- `AssistantConversation.org_id` (assistant/model.py:13): `index=True, foreign_key="organization.id"` — populated on create, but never used as a filter on any read.
