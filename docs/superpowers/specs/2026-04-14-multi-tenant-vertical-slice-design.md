# Multi-Tenant Vertical Slice — Design

**Date:** 2026-04-14
**Status:** Implemented on `platform-multi-tenant` as of 2026-04-22 (93 multi-tenant tests green). See **Divergences from original design** at the bottom for what changed during implementation.
**Scope:** Foundational vertical slice converting Langflow from single-tenant to multi-tenant. End-to-end: schema → migrations → auth/scoping → query enforcement → MCP isolation → tests. Excludes org switcher UI, invitations, role hierarchy, billing, and admin cross-org endpoints (deferred to follow-up sub-projects).

## Goals

- Introduce `Organization` and `Membership` as first-class entities.
- Associate every tenant-scoped resource (flows, folders, files, variables, API keys, deployments, MCP configs, etc.) with an `organization_id`.
- Enforce per-org isolation at the query layer with explicit args plus a dev/test guardrail.
- Migrate existing single-tenant data into a single "Default Organization" without data loss.
- Preserve the single-org-per-user UX in the slice (no UI changes), while structuring data and dependencies so multi-org-per-user is purely additive later.
- Preserve existing super admin (`User.is_superuser`) behavior, with a clean place to add cross-org "act as" later.

## Non-Goals

- Org switcher, invitations, member-management UI.
- Roles beyond `owner` within an org.
- Billing, quotas, seat limits.
- Admin/cross-org endpoints (the *mechanism* is designed for, but no endpoints are added).
- Postgres Row-Level Security (rejected — would break SQLite support).
- Path-prefixed org URLs or `X-Organization-Id` header on every request (rejected for the slice — the dependency derives org from the user's single membership).

## Architecture

### Data Model

Two new tables.

**`organization`**
| col | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | str | |
| `slug` | str, unique | reserved for future URL/header use |
| `is_personal` | bool | distinguishes auto-created personal orgs from real ones |
| `created_at`, `updated_at` | timestamps | |

**`membership`**
| col | type | notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | FK → user | |
| `organization_id` | FK → organization | |
| `role` | enum: `owner` (only value used in slice; reserved space for `admin`/`member`) | |
| `created_at` | timestamp | |
| unique `(user_id, organization_id)` | | |

**Denormalized `organization_id NOT NULL FK`** added to every tenant-scoped table:

- Flow, Folder, File, Variable, ApiKey, Deployment, DeploymentProviderAccount, MCP server/connection tables, FlowVersion, Message, Transaction, VertexBuild, Job.

**Not org-scoped:** User, auth/session tables. Users belong to organizations via Membership; user identity is global.

**Indexes:** every tenant-scoped table gets an index on `organization_id`. Existing composite indexes that filter by `user_id`/`flow_id`/etc. are recreated as `(organization_id, <existing key>)`.

### Auth & Request Scoping

External auth (JWT/session) is unchanged. The token continues to identify only the User. No org claim is baked into the token in this slice — keeps issuance simple and avoids re-issuing on org switch later.

**New dependencies (FastAPI):**

- `get_current_organization(user = Depends(get_current_active_user)) -> Organization`
  - Looks up `Membership` rows for the user.
  - For the slice: asserts exactly one membership; returns its `Organization`.
  - For superusers: returns their personal org by default. An optional `X-Acting-Org-Id` header (validated for org existence, not membership) overrides — this is the "act as" hook for future admin work, callable from day one but not used by any current endpoint.
  - Raises `403` if no membership found (defensive — should not occur post-migration).
- `get_current_membership(...) -> Membership` — same lookup, returns the row so future role checks have a place to grow.

**Signup / user creation:** after a User row is inserted, a post-commit hook creates a personal `Organization` (`name=f"{username}'s workspace"`, `is_personal=True`) and an owner `Membership`. The CLI superuser-creation path uses the same hook.

**API key auth:** API keys are tenant-scoped; authenticating via API key resolves directly to `(user, organization)` from the key row, bypassing the membership lookup.

**MCP auth:** `CurrentActiveMCPUser` resolves the org through the same dependency.
- Per-project MCP endpoints (`/mcp/{project_id}/...`) inherit isolation naturally — the project lookup filters by current org, so a cross-org `project_id` returns 404.
- The global MCP endpoint scopes the exposed flow set to the current org.

### Query-Layer Enforcement

**Required pattern:** every CRUD function takes `organization_id` and includes it in the WHERE clause. `organization_id` on writes is set from the dependency, never accepted from the request body.

```python
async def get_flow(session, flow_id: UUID, organization_id: UUID) -> Flow | None:
    return await session.scalar(
        select(Flow).where(Flow.id == flow_id, Flow.organization_id == organization_id)
    )
```

```python
async def read_flow(
    flow_id: UUID,
    org: Organization = Depends(get_current_organization),
    session: AsyncSession = Depends(get_session),
):
    flow = await get_flow(session, flow_id, org.id)
    if not flow:
        raise HTTPException(404)
```

**Dev/test guardrail:** a SQLAlchemy `before_execute` event hook, enabled only when `LANGFLOW_ENV in {"dev", "test"}`, inspects every `SELECT`/`UPDATE`/`DELETE` against tenant-scoped tables. If the WHERE clause does not reference `organization_id`, it raises `MissingOrgFilterError`. Catches forgotten filters in CI; zero cost in prod.

**Insert guardrail:** SQLAlchemy `before_insert` on tenant-scoped models raises if `organization_id` is unset. Always on (cheap, prevents silent data corruption).

**Escape hatch:** `with allow_cross_org_query():` context manager suppresses the guardrail. Greppable, audit-friendly. Used by background workers, migrations, and (future) admin endpoints.

**Cross-org FK validator:** when a write references another row by FK (`Flow.folder_id`, etc.), a SQLAlchemy validator confirms the referenced row's `organization_id` matches the inserting/updating row's. Prevents stitching resources from different orgs.

### Migration & Backfill

Single Alembic migration, idempotent and re-runnable on partial failure.

1. Create `organization` and `membership` tables.
2. Insert the default organization (`name="Default Organization"`, `slug="default"`, `is_personal=False`).
3. Backfill memberships: one Membership per existing User → default org, role `owner`.
4. Add `organization_id` column (nullable FK) to every tenant-scoped table.
5. Backfill: `UPDATE <table> SET organization_id = <default_org_id>` per table.
6. Alter `organization_id` to `NOT NULL`; add the index. Use `op.batch_alter_table` to keep SQLite working.
7. **Verification step inside the migration:** assert no tenant-scoped row has NULL `organization_id`. Fails the migration loudly if any table was missed.

**Rollback (downgrade):** drop indexes → drop FK columns → drop membership → drop organization. User data preserved (org_id is dropped per row).

## Components & Files (anticipated)

- `src/backend/base/langflow/services/database/models/organization/` — new model dir (`model.py`, `crud.py`, `__init__.py`).
- `src/backend/base/langflow/services/database/models/membership/` — new model dir.
- `src/backend/base/langflow/services/database/models/{flow,folder,file,variable,api_key,deployment,...}/model.py` — add `organization_id` FK, indexes, `before_insert` registration.
- `src/backend/base/langflow/services/database/scoping.py` — new module: `MissingOrgFilterError`, `before_execute` guardrail, `allow_cross_org_query` context manager, cross-org FK validator.
- `src/backend/base/langflow/api/v1/auth_helpers.py` (or new `org_helpers.py`) — `get_current_organization`, `get_current_membership`.
- `src/backend/base/langflow/api/v1/login.py` and CLI superuser creation — invoke the personal-org hook.
- `src/backend/base/langflow/api/v1/mcp.py`, `mcp_projects.py` — wire org dependency, scope global endpoint.
- All v1/v2 route files — replace `user_id`-only filters with `(user_id?, organization_id)` filters via the dependency.
- `src/backend/base/alembic/versions/<rev>_multi_tenant_foundation.py` — the migration.

## Error Handling

- Missing membership at request time → `403 Forbidden` (defensive).
- Cross-org resource access → `404 Not Found` (avoids leaking existence).
- Cross-org FK reference attempt on write → `400 Bad Request` with a clear message.
- Forgotten org filter in dev/test → `MissingOrgFilterError` raised at query execution, surfacing in test logs / dev console.
- Migration verification failure → migration aborts; no partial NOT NULL state.

## Testing Strategy

**Unit**
- Dependency: `get_current_organization` resolves the single membership; raises `403` on none; honors `X-Acting-Org-Id` for superusers; rejects the header for non-superusers.
- Guardrail: `before_execute` raises on unfiltered tenant query; silent on filtered query; respects `allow_cross_org_query()`.
- `before_insert`: raises when a tenant-scoped row lacks `organization_id`.
- Cross-org FK validator: rejects a Flow referencing a Folder from a different org.

**Cross-org isolation (the most important layer)**
A parametrized fixture builds two orgs (`org_a`, `org_b`), each with a user and a full set of resources. For every tenant-scoped GET/list/update/delete endpoint:
- `user_a` GET on `org_b`'s resource → 404
- `user_a` LIST → only `org_a` rows
- `user_a` UPDATE/DELETE on `org_b`'s resource → 404
- `user_a` cannot create a resource referencing an `org_b` FK

Driven by a parametrized `(endpoint, method)` list — adding a new tenant-scoped route requires one line, keeping coverage mechanical.

**Migration**
On a SQLite fixture pre-loaded with realistic single-tenant data: run `alembic upgrade head`, assert (a) one Default Organization, (b) every user has a Membership, (c) no tenant-scoped row has NULL `organization_id`, (d) `downgrade -1` then `upgrade head` is idempotent.

**MCP isolation**
- `org_a`'s global MCP endpoint exposes only `org_a` flows.
- `user_a` hitting `/mcp/{org_b_project_id}/...` → 404.

**Frontend**
Out of scope. Existing E2E suite should pass unchanged; failures indicate regressions in org-scoped data fetching.

## Open Questions

None blocking. Items intentionally deferred to follow-up sub-projects:

- Org switcher UI, invitation flow, member management.
- Role hierarchy beyond `owner`.
- Admin/cross-org endpoints (the `X-Acting-Org-Id` mechanism is in place; endpoints are not).
- Org claim in JWT (current dependency reads from membership; trivial to swap for a JWT claim later).
- Quotas, billing, seat limits.

---

## Divergences from original design (as implemented, 2026-04-22)

The design above describes intent; what shipped differs in four places:

1. **Scoping guard is permissive, not strict.** The original design called for `before_insert` to raise `MissingOrgIdOnInsertError` when a tenant-scoped row is inserted without `organization_id`. In practice the guard in `services/database/scoping.py` auto-resolves the column via a lookup chain: `flow_id → flow.organization_id`, then `folder_id → folder.organization_id`, then `user_id → membership.organization_id`, and finally falls back to auto-provisioning a personal org (via the `user` `after_insert` hook) or a `system-orphan` org if no attribution is possible. The error classes are still defined but rarely raised. This was done to avoid churning every insert site during the `feat/adp-connector` cutover; long-term we can tighten this.

2. **Role hierarchy landed alongside the slice.** `MembershipRole` has five values (`OWNER`, `ADMIN`, `MEMBER`, `OPERATOR`, `VIEWER`) from the `feat/user-detail-and-roles` work, not just `OWNER`. Default on insert is still `OWNER`.

3. **Multiple memberships per user are tolerated.** `get_current_organization` no longer asserts exactly one membership; it prefers the user's personal org, falling back to the earliest-created org if the user has multiple non-personal memberships. This is load-bearing for the admin UI (users with cross-org access).

4. **Cross-org FK validator is defined but not wired.** `CrossOrgFKError` lives in `scoping.py` but no SQLAlchemy listener invokes it. Defense today relies entirely on every API route's folder/flow lookup filtering by the current org. Cross-org stitching is only possible by bypassing the API layer; the DB-level defense-in-depth validator is an open follow-up.

5. **Admin endpoints shipped.** `api/v1/admin/orgs.py` landed beyond the original non-goals, driven by the user-detail + role-model work. It uses the same `CurrentOrg` dependency with `X-Acting-Org-Id` for cross-org read access.
