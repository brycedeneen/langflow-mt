# Platform Admin — Design Spec

**Date:** 2026-04-15
**Status:** Approved for implementation planning
**Scope:** Introduce a platform-wide administrator role that can manage organizations and user-to-organization assignments from the UI.

## Motivation

The recently-introduced `Organization` + `Membership` model establishes org-scoped data isolation, but offers no way to administer across orgs. Operators, support, and setup/onboarding flows all require a cross-org management surface: creating orgs, assigning users to orgs, and deleting orgs. The existing `User.is_superuser` flag predates the org model and is overloaded (legacy "god-mode" within a single-tenant install); reusing it risks authorization drift. This spec introduces a distinct `is_platform_admin` concept and a dedicated admin API + UI surface.

## Non-Goals

- **Org impersonation / "act as" another org** — platform admins cannot use normal org-scoped endpoints (`/api/v1/flows`, etc.) against an org they do not belong to. A future spec may add an explicit `X-Organization-Id` targeting header; this one does not.
- **Cross-org content editing** — no admin endpoints to edit flows, files, deployments, variables, etc. across orgs.
- **Billing, quotas, audit-log tables** — out of scope.
- **Platform-admin management from the UI** — promoting/demoting platform admins is CLI-only in this release.
- **User creation/deletion from the admin UI** — users are still created through the normal signup / auth flow.

## Data Model

### User

Add one column:

```python
is_platform_admin: bool = Field(default=False, nullable=False)
```

Not indexed (cardinality is trivially small). `is_superuser` is left unchanged and retains its existing semantics.

### Organization, Membership

Unchanged. Multi-org membership is already supported by `UniqueConstraint("user_id", "organization_id")`. Admin assignment is **additive**: adding a user to an org creates a new `Membership` row; it does not disturb any existing membership (including the user's personal org).

### Migration

New Alembic revision `xxxx_add_platform_admin_flag.py`:

1. `ALTER TABLE "user" ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE`.
2. Data step: `UPDATE "user" SET is_platform_admin = TRUE WHERE is_superuser = TRUE` — auto-promotes existing superusers so upgraded installs retain admin access.
3. Downgrade drops the column.

## Authorization

New FastAPI dependency in `src/backend/base/langflow/api/utils/core.py`:

```python
PlatformAdmin = Annotated[User, Depends(require_platform_admin)]
```

`require_platform_admin` resolves the current user and raises `HTTPException(403)` if `is_platform_admin` is false. It does **not** resolve or require `CurrentOrg` — admin endpoints are explicitly not org-scoped. `CurrentOrg` behaviour for existing endpoints is unchanged; platform admins have no implicit access to other orgs through the normal API surface.

## API Surface

All endpoints live under `/api/v1/admin/*` in a new router `src/backend/base/langflow/api/v1/admin.py`. Every endpoint depends on `PlatformAdmin`.

### Organizations

- `GET /admin/organizations` — list all orgs. Query params: `q` (name/slug substring search), `limit`, `offset`. Response rows include `id, name, slug, is_personal, member_count, created_at, updated_at`.
- `POST /admin/organizations` — body `{name: str, slug: str}`. Creates a non-personal org (endpoint never sets `is_personal=true`). Returns the created org. `409` on slug collision (enforced by existing unique constraint).
- `GET /admin/organizations/{org_id}` — org detail including member list with role.
- `DELETE /admin/organizations/{org_id}` — body `{confirm_name: str}`.
  - `403` if `is_personal` is true.
  - `400` if `confirm_name` does not exactly match the org's `name`.
  - `404` if not found.
  - Otherwise: inside a single transaction, explicitly delete all rows in tables that carry `organization_id` (flow, file, deployment, deployment_provider_account, variable, job, transaction, vertex_builds, message, folder, flow_version, api_key, membership), then delete the organization. Return a summary object with per-table deleted-row counts for audit.

### Memberships

- `GET /admin/organizations/{org_id}/members` — list members with role.
- `POST /admin/organizations/{org_id}/members` — body `{user_id: UUID, role: MembershipRole = OWNER}`. `404` if user or org unknown. `409` if the (user, org) pair already exists.
- `DELETE /admin/organizations/{org_id}/members/{user_id}` — remove. `403` if the target org is the user's personal org (never orphan a user from their own workspace). Non-personal memberships may always be removed, even if it leaves the user with only their personal org.

### Users (for assignment picker)

- `GET /admin/users?q=...&limit=&offset=` — search users by username or email substring. Returns `id, username, email, is_platform_admin`, plus a list of `{organization_id, organization_name, role}` memberships. Read-only; no mutation endpoints for users in this spec.

## CLI

New command in the existing users CLI:

- `langflow users set-platform-admin <email> [--revoke]` — toggles `is_platform_admin`. Non-zero exit on unknown email.

This is the post-bootstrap mechanism for adding or removing platform admins. The migration-time auto-promote ensures there is always at least one admin immediately after upgrade.

## Frontend

### Navigation

Add a top-level **Admin** entry in the left nav, rendered only when `currentUser.is_platform_admin` is true. The `/users/whoami` response (or whichever endpoint already supplies the logged-in user to the frontend) is extended to include `is_platform_admin`. Admin is distinct from the user-scoped **Settings** area to avoid conflating platform-wide and user-local concerns.

### Routes

- `/admin/organizations` — table of all orgs (name, slug, members, created). Search input bound to `?q=`. "New organization" button opens the create form.
- `/admin/organizations/new` — drawer or modal with `name` and `slug` fields. `slug` auto-derives from `name` with a manual override.
- `/admin/organizations/:orgId` — detail page, two tabs:
  - **Members** — table of members with role and a "Remove" action. "Add member" opens a user-search picker backed by `GET /admin/users?q=`. Selecting a user and confirming posts to `POST /admin/organizations/{orgId}/members`.
  - **Settings** — metadata display and a **Delete organization** button that opens a confirmation dialog requiring the user to type the exact org name to enable the destructive action. Disabled entirely for `is_personal` orgs.

### Frontend plumbing

- New API module `frontend/src/controllers/API/queries/admin/` mirroring existing query patterns.
- If a reusable "confirm by typing" dialog does not exist, add `ConfirmByTypingDialog`. Otherwise reuse.
- No new table/form primitives — reuse the existing component library.

### Error & empty states

- Empty organizations list → illustration + "Create organization" CTA.
- Any `/admin/*` API call returning 403 → redirect to a generic 403 page.
- Loading states follow existing query-based patterns.

## Testing

### Backend

`src/backend/tests/unit/api/v1/test_admin.py`:

- **Auth:** non-admin user receives 403 on every `/admin/*` endpoint; unauthenticated receives 401.
- **Org create:** happy path; duplicate slug → 409; `is_personal` not settable via the endpoint.
- **Org list:** returns all orgs regardless of caller's memberships; search and pagination behave correctly.
- **Org delete:** happy path cascades (assert flows/files/memberships/etc. for that org are gone, and rows for other orgs are untouched); personal org → 403; wrong `confirm_name` → 400; unknown id → 404.
- **Membership add:** happy path; duplicate → 409; unknown user or org → 404.
- **Membership remove:** happy path; removing a user from their own personal org → 403; removing a non-personal membership that leaves the user with only their personal org → allowed.
- **User search:** matches both username and email; returned memberships include role.

### Migration

Apply against a DB seeded with a mix of superuser and non-superuser accounts. Assert `is_platform_admin == is_superuser` post-upgrade. Exercise downgrade and verify the column is dropped cleanly.

### CLI

`langflow users set-platform-admin <email>` flips the flag; `--revoke` unsets it; unknown email yields a non-zero exit.

### Frontend

Smoke-level: nav item is hidden for non-admin, visible for admin; create-org form posts and refetches; delete dialog's action button is only enabled when the typed name matches exactly.

### Out of scope

Load tests, concurrent-delete races (cascade runs in a single transaction).

## Rollout

1. Land migration + model change.
2. Land backend admin router + CLI.
3. Land frontend admin area.
4. Verify on upgrade in a staging environment with existing superusers that `is_platform_admin` is set and the admin UI renders.
