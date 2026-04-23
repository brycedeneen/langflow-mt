# `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` Backport — Design

**Date:** 2026-04-22
**Branch:** `platform-multi-tenant`
**Source:** upstream PR [#11893](https://github.com/langflow-ai/langflow/pull/11893) (merged upstream 2026-04-05)
**Cross-refs:** `docs/superpowers/plans/2026-04-22-platform-multi-tenant-security-fixes.md` (Task 7 recorded this as a follow-up); `docs/superpowers/followups.md` (2026-04-22 entry)

---

## Goal

Close the custom-component arbitrary-code-execution hole on the `platform-multi-tenant` branch. Today, any tenant who uploads a flow containing a custom Python component executes that code on shared infrastructure. Upstream PR #11893 gates this behavior behind `LANGFLOW_ALLOW_CUSTOM_COMPONENTS`; none of its files exist on this branch.

## Design decisions (resolved during brainstorming)

| Question | Decision |
|---|---|
| Default posture | `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false` baked into the container image. |
| Scope | Backport upstream's gate as-is + add a single platform-admin override. Not per-org allowlist. |
| Override semantics | Unconditional — `is_platform_admin=true` bypasses the gate regardless of the env var. Rationale: platform admins can already change the env var; conditioning the bypass on a second flag would add friction without security. |
| Enforcement points | Execution + save/import + template-create (upstream's posture + one extra site for our `POST /api/v1/templates`). |
| Starter-project JSON edits (20+ upstream) | Skipped. Our starters at `src/backend/base/langflow/initial_setup/starter_projects/` are Python files that build flows programmatically from typed components — no raw custom code to strip. |
| ADP Assist gating | None. Assist mutates flows via tools that pick from the shipped catalog; it cannot emit a custom-component node. |
| Data Mapper gating | None. It is a dedicated component with its own agent, not a custom-code surface. |
| Template Management gating | Transitive only. Execution gate catches it at run time. Plus the explicit gate on `POST /api/v1/templates` per the enforcement-points decision. |

## Out of scope

- Per-org allowlist / request-access UX. Deferred until a tenant actually asks. Current posture: non-platform-admins see a tooltip saying the action is not allowed, with no approval path.
- Runtime sandboxing of custom code (seccomp, gVisor, WASM). The gate is preventive ("refuse to run it at all"), not containment. Sandboxing is a separate, larger project.
- Retroactive scan of flows already saved by tenants. On deploy, any pre-existing custom-component flow simply fails to execute until a platform admin removes the custom code or flips the env var. Acceptable because (a) the population is small, (b) failure is loud and local to the flow owner.
- Starter-project JSON edits from upstream. N/A — see decision table.

## Architecture

Four building blocks:

### 1. Gate library (lfx)

**New files (both new, ported from upstream):**

- `src/lfx/src/lfx/utils/flow_validation.py` — ~250 LOC, one public entry point:

  ```python
  def validate_flow_components(
      flow_data: dict,
      *,
      allow_custom: bool,
      caller_is_platform_admin: bool,
  ) -> None:
      """Raise CustomComponentNotAllowedError if the flow contains a node
      whose `code` does not match a cached component template. No-op when
      allow_custom is True or caller_is_platform_admin is True."""
  ```

  Walks `flow_data["nodes"]`, compares each node's `data.node.template.code.value` against the server-side component template cache. A mismatch ⇒ "custom". A cold cache on startup ⇒ fail-closed (blocks all flow execution until populated) — inherits upstream behavior verbatim.

- `src/lfx/src/lfx/utils/component_aliases.py` — small helper module (port upstream as-is, used by `flow_validation.py` to resolve component type aliases during cache lookup).

- New exception class `CustomComponentNotAllowedError` (in `flow_validation.py`).

### 2. Setting

**Modified file:** `src/backend/base/langflow/services/settings/base.py`

Add:

```python
allow_custom_components: bool = Field(
    default=False,
    description=(
        "When False, non-platform-admin users cannot create, upload, or "
        "execute flows containing custom Python components. Platform "
        "admins always bypass this gate."
    ),
)
```

Existing env-var resolution handles `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true|false|1|0`. Container image does not set the env var; default remains `False` for the fleet.

### 3. Platform-admin override

One short-circuit at the top of `validate_flow_components`:

```python
if caller_is_platform_admin or allow_custom:
    return
```

This is the sole behavioral divergence from upstream. Rationale captured in the decisions table above.

### 4. Enforcement call sites

| # | Call site | File | What it validates | Error shape |
|---|---|---|---|---|
| 1 | Flow execution | `src/lfx/src/lfx/graph/graph/base.py` (build-vertex entry) | `flow.data` before any vertex runs | Raises `CustomComponentNotAllowedError`; surfaces through the existing SSE build stream as a build error (same channel as any other vertex failure — no new frontend rendering) |
| 2 | Create flow | `src/backend/base/langflow/api/v1/flows.py::create_flow` | `body.data` | HTTP 403, body `{"detail": "Custom components are not allowed on this deployment."}` |
| 3 | Upload / import | same file, `upload_file` + JSON-import entry | parsed JSON payload | Same as #2 |
| 4 | Create template | `src/backend/base/langflow/api/v1/templates.py::create_template` | source flow's `data` after `_load_source_and_blank` | Same as #2 |

Each call site is ~5 lines: load `get_settings_service().settings`, grab `current_user.is_platform_admin`, call `validate_flow_components(...)`, catch the exception, translate to HTTP 403.

The template-create gate (#4) stacks on top of the org binding shipped in the 2026-04-22 security-fix plan (commit `112e55edbe`) — no interaction issues; both checks happen after `_load_source_and_blank` returns.

## Frontend

### Single source of truth

**New file:** `src/frontend/src/utils/customComponentGuards.ts`

```ts
export function useCustomComponentsAllowed(): boolean {
  const isPlatformAdmin = useAuthStore(s => s.userData?.is_platform_admin);
  const { data: config } = useGetConfig({});
  return Boolean(isPlatformAdmin || config?.allow_custom_components);
}
```

The flag `allow_custom_components` is surfaced by the backend via the existing `GET /api/v1/config` endpoint (`src/backend/base/langflow/api/v1/endpoints.py::get_config`). The backend change is a one-line addition to the `ConfigResponse` model and the handler. The frontend consumer is `useGetConfig` (`src/controllers/API/queries/config/use-get-config.ts`); the new field is added to the TypeScript `ConfigResponse` interface in the same file.

### Gated surfaces

| Surface | Behavior when guard returns `false` |
|---|---|
| "New Custom Component" sidebar button | Button disabled; tooltip: *"Custom components are not allowed on this deployment."* |
| Component code editor panel ("Edit Code" action) | Action disabled. Existing custom-component nodes remain visible but read-only so tenants can inspect what a flow contains. |
| Flow-import dialog | Client-side precheck walks pasted/uploaded JSON; shows inline error before submit when the JSON contains custom-code nodes. Backend gate is the real line of defense; this is purely a UX affordance. |

*Exact file paths for each of the three gated surfaces resolved during plan authoring — the components exist on this branch; this spec does not hard-code their paths because they may have been renamed since upstream authored the PR.*

### Non-gated surfaces (explicit)

- **ADP Assist** — tool surface picks from the catalog; no path to emit custom code.
- **Data Mapper** — dedicated component, no custom-code authoring surface.
- **Template gallery / instantiation** — source flows are vetted by admins who create them; execution gate catches any slip.

## Data flow

```
┌──────────────────┐    POST /flows    ┌────────────────────┐
│ Tenant browser   │──────────────────▶│ create_flow        │
│ (non-admin)      │                   │  ├ load settings    │
└──────────────────┘                   │  ├ get is_pa=False │
         ▲                             │  ├ validate_flow_  │
         │  403                         │  │   components(…) │
         │                             │  │    │            │
         └─────────────────────────────│  │    ├ allow=F    │
                                        │  │    ├ is_pa=F    │
                                        │  │    └ walk nodes │
                                        │  │        ├ match  │
                                        │  │        │  cache │
                                        │  │        │  ✓ ok  │
                                        │  │        └ mismatch→raise
                                        │  └ HTTP 403       │
                                        └────────────────────┘
```

Platform admin path: the `is_pa=True` short-circuit returns before the cache walk, so platform-admin requests have zero overhead vs. pre-backport.

## Error handling

- **Backend errors** translate uniformly to HTTP 403 + the `detail` string above for the three API call sites (create/upload/template). Execution path raises through to the existing SSE build-error channel — no new renderer.
- **Frontend errors** are UX-only; backend remains the enforcement boundary. If the frontend precheck misses a case, the backend still rejects.
- **Cold template cache** fail-closes. Monitored the same as any other startup-time failure.
- **Corrupt/missing `code` field** treated as "custom" (stricter of the two interpretations) — prevents a bad-data bypass.

## Testing

### Backend (pytest-asyncio, 3 new files)

1. `src/lfx/tests/unit/utils/test_flow_validation.py` — gate unit tests:
   - Catalog-only flow → accepted regardless of flags
   - Custom-code flow, `allow_custom=False`, non-admin → raises
   - Same flow, `allow_custom=True` → accepted
   - Same flow, `allow_custom=False`, `caller_is_platform_admin=True` → accepted (override)
   - Empty flow → no-op accept
   - Flow whose `code` matches a cached template byte-for-byte → accepted (no false positives on shipped components)
   - Cold template cache → fail-closed

2. `src/backend/tests/unit/api/v1/test_custom_component_gate.py` — API enforcement tests, one per call site:
   - `test_create_flow_rejects_custom_component_for_tenant` → 403
   - `test_create_flow_accepts_custom_component_for_platform_admin` → 201
   - `test_upload_flow_rejects_custom_component_for_tenant` → 403
   - `test_create_template_rejects_custom_source_flow_for_tenant` → 403
   - `test_execution_blocks_custom_component_for_tenant` → build fails; exception surfaces through the SSE stream
   - Parametrized on `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true|false` to cover both postures

3. `src/backend/tests/unit/services/test_settings_allow_custom.py` — setting defaults to `False`; honors env var across `"true"`, `"1"`, `"True"`.

### Frontend (Jest)

4. `src/frontend/src/utils/__tests__/customComponentGuards.test.tsx`:
   - Hook returns `true` for platform admin regardless of config
   - Hook returns `true` for any user when `allow_custom_components=true`
   - Hook returns `false` otherwise
   - One render test per gated surface (sidebar button, code editor, import dialog) asserting disabled state + tooltip text

### Regression sweep (no new files)

- `pytest src/backend/tests/unit/api/v1/test_templates_cross_org.py` — verify the 2026-04-22 scope fixes still pass with the new template-create gate layered in
- `pytest src/backend/tests/unit/api/v1/test_flows_*.py` — existing flow CRUD suites with `allow_custom=True` to confirm default-off doesn't break dev fixtures

### Manual verification (in plan, before merge)

- Dev server with `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`, non-platform-admin caller: sidebar button disabled, code editor disabled, uploading a custom-code flow JSON shows inline error
- Same server, platform admin: all UI unchanged, can create and run a custom component
- Dev server with `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true`, non-admin caller: all UI unchanged

## Size estimate

~15–20 files vs. upstream's 85:

| Category | Files | Notes |
|---|---|---|
| New backend | 2 (`flow_validation.py` + `component_aliases.py` in lfx) | Ported from upstream |
| Modified backend | 5 (`settings/base.py`, `api/v1/endpoints.py` [config response], `api/v1/flows.py`, `api/v1/templates.py`, `lfx/graph/graph/base.py`) | Each ≤10 LOC delta |
| New frontend | 1 (`utils/customComponentGuards.ts`) | — |
| Modified frontend | 4 (`controllers/API/queries/config/use-get-config.ts` [ConfigResponse type], sidebar button, code editor, import dialog) | Each ≤15 LOC delta |
| New tests | 4 (3 backend + 1 frontend) | See Testing section |
| Skipped vs. upstream | 20+ starter JSONs, ADP Assist, Data Mapper, per-org allowlist | See decisions table |

## Rollout

1. Merge this backport on `platform-multi-tenant` with `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` unset (default `False`). Tenants immediately blocked; platform admins immediately bypassed.
2. Monitor flow-execution failures in the first 48 hours. Any custom-component flow that tenants rely on today will fail loudly — we expect the population is small; owners flagged to platform admins for remediation.
3. No data migration required.
4. Rollback: revert the four-commit series. No schema change.
