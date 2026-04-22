# User Detail Page & Role Expansion — Design Spec

**Date:** 2026-04-22
**Status:** Approved for implementation planning
**Scope:** Introduce an admin-facing User Detail Page, expand `MembershipRole` from single-value (`OWNER`) to a five-tier hierarchy (Owner/Admin/Member/Operator/Viewer), transition flows and folders from per-user ownership to org-owned access with role-based authorization, and document the enforcement surfaces knowingly left for a later pass.

## Motivation

The `/settings/organizations/:orgId` detail page gives operators a rich view *from the org's perspective* — members, settings, roles. There is no mirror *from the user's perspective*: a platform admin has no single place to see which orgs a given user belongs to, what role they hold in each, or toggle account status (`is_active`, `is_platform_admin`).

In parallel, the `MembershipRole` enum is a placeholder — only `OWNER` exists, so every member is functionally equivalent. The multi-tenant foundation has already reached the data layer (flows, folders, variables, api_keys, etc. all have `organization_id`), but *access control* is still dominated by per-user ownership checks (`user_id == current_user.id`). Until a real role hierarchy is enforced, "adding a member to an org" has no meaningful distinction from giving them Owner-level access.

This spec tackles both together because the UI and the role model need to co-evolve: a detail page that surfaces a single meaningless role would be cosmetic; a role hierarchy without a place to see and change roles would be invisible.

## Non-Goals

- **Full Option 3 authorization enforcement.** This spec gates flow/folder CRUD and flow execution on org role. It does **not** gate API keys, variables, files, deployments, flow runs, messages, jobs, vertex builds, or transactions. See [Known Gaps](#known-gaps).
- **Platform-level role tiers.** `User.is_platform_admin` stays a boolean. No platform-owner / platform-auditor stratification in this release.
- **Org impersonation** for platform admins remains out of scope (per the platform-admin spec).
- **Per-flow sharing** (flow-level collaborators independent of org role) is explicitly deferred.
- **Immediate session revocation** on `is_active=false`. Sessions invalidate on next request, not instantly.
- **Soft-deletion / "terminated" lifecycle state.** Status is a single `is_active` boolean. Reversible.
- **Billing-related roles or gates.** No billing system exists today.

## Data Model

### `MembershipRole` enum (extended, not renamed)

```python
class MembershipRole(str, Enum):
    OWNER = "owner"      # exists today
    ADMIN = "admin"      # new
    MEMBER = "member"    # new
    OPERATOR = "operator" # new
    VIEWER = "viewer"    # new
```

Existing `OWNER` rows stay Owner. No backfill. Hierarchy is defined in backend code as a single source of truth:

```python
ROLE_ORDER: dict[MembershipRole, int] = {
    MembershipRole.OWNER:    5,
    MembershipRole.ADMIN:    4,
    MembershipRole.MEMBER:   3,
    MembershipRole.OPERATOR: 2,
    MembershipRole.VIEWER:   1,
}
```

### Membership invariants

- At least one `OWNER` per org at all times. Enforced on member removal and on role change (cannot demote the last Owner).
- Personal orgs (`is_personal=true`) remain Owner-locked — role cannot be changed, membership cannot be removed. The existing remove-member guard is extended to cover PATCH role.

### `Flow.user_id` and `Folder.user_id` — semantic change, no column rename

`Flow.user_id` and `Folder.user_id` stay on the table and stay populated by the current user on create. Their **semantic role changes to `created_by` attribution only**. They are never consulted by authorization code after this change.

- FK is changed from the current cascade behavior to `ON DELETE SET NULL` so deleting a user preserves their flows and folders; the creator attribution simply becomes "deleted user" in the UI.
- The column name is preserved to avoid churning downstream queries.

### `User` model

Unchanged. `is_active` and `is_platform_admin` remain booleans. No lifecycle enum, no `terminated_at` column.

### Migrations (Alembic)

Two revisions, both additive / non-destructive:

1. **`xxxx_extend_membership_role_enum.py`**
   - `ALTER TYPE membershiprole ADD VALUE 'admin'` / `'member'` / `'operator'` / `'viewer'` (Postgres).
   - SQLite picks up new enum values via the CHECK regeneration performed when SQLAlchemy rebuilds the enum type.
   - Downgrade is a no-op (Postgres does not support `ALTER TYPE DROP VALUE`; rollback via forward-compatible deploy).
2. **`xxxx_flow_folder_user_id_set_null.py`**
   - Alter `flow.user_id` FK to `ON DELETE SET NULL`.
   - Alter `folder.user_id` FK to `ON DELETE SET NULL`.
   - Downgrade restores prior FK behavior.

No data migration — existing memberships all remain `OWNER`; existing flows/folders keep their current `user_id`.

## Authorization

### New helpers (`src/backend/base/langflow/api/utils/core.py`)

Two entry points — a FastAPI dep factory (for endpoints where `org_id` is a path param) and an imperative helper (for endpoints that resolve the org from a resource).

```python
def require_org_role(min_role: MembershipRole) -> Callable:
    """Dep factory. Returns a FastAPI dependency that resolves `org_id` from
    the path (`/.../{org_id}/...`) and raises 403 unless the caller has at
    least `min_role`. Platform admins bypass. Returns the caller's Membership.
    """

def assert_org_role(user: User, org_id: UUID, min_role: MembershipRole) -> Membership | None:
    """Imperative check. Used after resolving a resource (e.g. fetch flow,
    then check its organization_id). Raises HTTPException(403) on failure.
    Returns the caller's Membership (None for platform-admin bypass).
    """
```

Typical usage on admin endpoints:

```python
OrgRoleOwner    = Annotated[Membership, Depends(require_org_role(MembershipRole.OWNER))]
OrgRoleAdmin    = Annotated[Membership, Depends(require_org_role(MembershipRole.ADMIN))]
OrgRoleMember   = Annotated[Membership, Depends(require_org_role(MembershipRole.MEMBER))]
OrgRoleOperator = Annotated[Membership, Depends(require_org_role(MembershipRole.OPERATOR))]
OrgRoleViewer   = Annotated[Membership, Depends(require_org_role(MembershipRole.VIEWER))]
```

Typical usage on resource endpoints (flow, folder):

```python
@router.patch("/flows/{flow_id}")
async def update_flow(flow_id: UUID, current_user: CurrentUser, ...):
    flow = await get_flow(flow_id)
    assert_org_role(current_user, flow.organization_id, MembershipRole.MEMBER)
    ...
```

### Capability matrix

| Capability                                    | Owner | Admin | Member | Operator | Viewer |
| --------------------------------------------- | :---: | :---: | :----: | :------: | :----: |
| Delete / transfer org                         |   ✓   |       |        |          |        |
| Manage members (invite / remove / change role)|   ✓   |  ✓¹   |        |          |        |
| Edit org settings                             |   ✓   |   ✓   |        |          |        |
| Create / edit / delete flows and folders      |   ✓   |   ✓   |   ✓    |          |        |
| Execute flows (run, build)                    |   ✓   |   ✓   |   ✓    |    ✓     |        |
| View flows and folders                        |   ✓   |   ✓   |   ✓    |    ✓     |   ✓    |

¹ **Escalation guard:** Admin cannot *assign* or *revoke* roles at the Admin or Owner level. An Admin may only change roles where **both the source and the target role are Member, Operator, or Viewer.** Only Owners can promote anyone to Admin/Owner, demote an Admin/Owner, or transfer ownership. Enforced on both the add-member (POST) and change-role (PATCH) endpoints; personal-org memberships are locked for everyone.

### Flow & folder CRUD gates (applies to Option 2 scope)

After this spec, the `user_id == current_user.id` ownership check is **removed** from flow and folder endpoints. Access is purely role-based:

| Endpoint family                              | Required role                 |
| -------------------------------------------- | ----------------------------- |
| `GET /flows`, `GET /flows/{id}`              | Viewer+ (in the flow's org)   |
| `POST /flows`, `PATCH /flows/{id}`, `DELETE` | Member+                       |
| `POST /build/{flow_id}`, `POST /run/{id}`    | Operator+                     |
| Folder list/read                             | Viewer+                       |
| Folder create/rename/delete/move             | Member+                       |

Execution endpoints covered by "Operator+" include the build, run, stream, and any cancel/kill-run endpoints. The precise endpoint list is enumerated during implementation by grepping `user_id == current_user`; every such site is replaced with `require_org_role` using the resource's `organization_id`.

### `is_active = false` side effects

When a platform admin flips `is_active` to false:

- Login endpoint rejects (already checks `is_active`; verify).
- API-key authentication rejects (API key auth path checks the owning user's `is_active`; verify).
- Existing session cookies expire on their next authenticated request (no active session sweep).
- Flows, memberships, api_keys, variables, deployments — all rows untouched. Deployed flows continue to run.
- Re-activation is simply flipping the flag back; no state restoration needed.

### Platform admin bypass

`is_platform_admin=true` bypasses `require_org_role` unconditionally. Platform admins still are not members of an org they don't belong to — `Membership` lookup returns None — but the authorization check short-circuits to success. Where an endpoint needs the caller's concrete role (e.g. role-escalation validation), platform admins are treated as Owner-equivalent.

## API Surface

### New endpoints

#### `GET /api/v1/admin/users/{user_id}` *(platform admin)*

Response:

```json
{
  "id": "uuid",
  "username": "ava.chen",
  "is_active": true,
  "is_platform_admin": false,
  "is_superuser": false,
  "create_at": "...",
  "updated_at": "...",
  "last_login_at": "...",
  "memberships": [
    {
      "organization_id": "uuid",
      "organization_name": "ADP Platform",
      "is_personal": false,
      "role": "admin",
      "joined_at": "2025-11-03T..."
    }
  ]
}
```

`memberships` is sorted personal org first, then alphabetically by name.

#### `PATCH /api/v1/admin/organizations/{org_id}/members/{user_id}` *(platform admin or org Owner/Admin)*

Body: `{ "role": "owner" | "admin" | "member" | "operator" | "viewer" }`

Guards:
- Caller is platform admin **or** has `require_org_role(org_id, min_role=ADMIN)`.
- Admin cannot assign Owner or Admin (403).
- Cannot demote the last Owner (409).
- Personal-org memberships locked (409).

Response is the updated `MemberRow`.

### Extended endpoints

#### `POST /api/v1/admin/organizations/{org_id}/members` *(now: platform admin or org Owner/Admin)*

- Gate relaxed from platform-admin-only.
- Admins cannot add someone as Owner or Admin (same escalation guard as PATCH).
- Response shape unchanged.

#### `DELETE /api/v1/admin/organizations/{org_id}/members/{user_id}` *(now: platform admin or org Owner/Admin)*

- Gate relaxed the same way.
- Adds "cannot remove last Owner" check (409).
- Existing personal-org guard retained.

#### `GET /api/v1/admin/organizations/{org_id}` — response shape

- `MemberRow` grows an `is_active` field so the org-admin scoped view can render the status pill without a separate fetch.

#### `PATCH /api/v1/users/{user_id}` — verify coverage

- Already used by `UsersPage` for editing users. Verify it accepts `is_active` and `is_platform_admin` in the body; extend the request schema if not. Platform-admin gate is retained. Org admins never hit this endpoint.

### No new endpoint for the org-admin scoped view

The org-admin scoped detail view (`/settings/organizations/:orgId/members/:userId`) sources its data from the existing `GET /admin/organizations/{org_id}` response. The frontend finds the target user by `user_id` in the returned `members` array. No extra round-trip.

## Frontend

### Routes (`src/frontend/src/routes.tsx`)

- `/admin/users/:userId` → `UserDetailPage` — gated on `is_platform_admin`
- `/settings/organizations/:orgId/members/:userId` → `OrgMemberDetailPage` — gated on platform admin **or** Owner/Admin of `:orgId`

### Components

**Platform-admin page** (`src/frontend/src/pages/AdminPage/UserDetailPage/`)
- `index.tsx` — page shell: breadcrumb, identity header (avatar, username, user-id, Active pill, Platform-Admin pill), tab bar
- `AccountTab.tsx` — status toggles (`is_active`, `is_platform_admin`), identity facts (created, updated, last login), danger zone (delete user)
- `MembershipsTab.tsx` — table of orgs with inline `RolePicker` and Remove action; personal org row is read-only
- `AddToOrganizationDialog.tsx` — org search + role selection; posts to existing `POST /admin/organizations/{org_id}/members`

**Org-admin scoped page** (`src/frontend/src/pages/AdminPage/organizations/OrgMemberDetailPage.tsx`)
- Single panel: identity header (avatar, username, Active pill — display only), role picker scoped to this org, remove-from-org action
- Does not render: the Platform-Admin pill, other orgs, the danger zone, identity toggles

**Shared components** (`src/frontend/src/components/common/`)
- `RoleBadge` — color-coded pill with role label and description tooltip; reused in `OrganizationMembersTab` and both new detail pages
- `RolePicker` — dropdown `{ currentRole, callerRole, onSelect, orgId }`; disables options the caller cannot assign (client-side enforcement mirrors the backend escalation guard; backend is still the source of truth)

### Updates to existing pages

- `UsersPage.tsx` — each row becomes clickable, navigating to `/admin/users/:userId`. Inline edit/delete actions retained.
- `OrganizationMembersTab.tsx` — each row becomes clickable, navigating to `/settings/organizations/:orgId/members/:userId`. Role column swaps plain text → `RoleBadge`. The current inline role-edit control moves into the scoped detail page.

### API hooks (`src/frontend/src/controllers/API/queries/admin/`)

- `useGetUser(userId)` — new
- `useUpdateMemberRole({ orgId, userId, role })` — new
- `useAddMember({ orgId, userId, role })` — existing; reused
- `useRemoveMember({ orgId, userId })` — existing; reused
- `useUpdateUser(userId, patch)` — existing; reused for `is_active` / `is_platform_admin` toggles

### Role metadata (`src/frontend/src/constants/roles.ts`)

```ts
export const ROLE_METADATA: Record<MembershipRole, {
  label: string;
  description: string;
  color: string;
  order: number;
}> = {
  owner:    { label: "Owner",    description: "Full access. Manages members and org settings. Can delete the organization.", color: "...", order: 5 },
  admin:    { label: "Admin",    description: "Manages members and org settings. Cannot delete the organization or create other Admins or Owners.", color: "...", order: 4 },
  member:   { label: "Member",   description: "Creates, edits, and runs flows. Cannot manage members or org settings.", color: "...", order: 3 },
  operator: { label: "Operator", description: "Runs flows and views results. Cannot edit flows or manage the organization.", color: "...", order: 2 },
  viewer:   { label: "Viewer",   description: "Views flows and their configuration. Cannot run or edit anything.", color: "...", order: 1 },
};
```

The `order` values mirror the backend `ROLE_ORDER` and are used by the escalation guard in `RolePicker`.

### Zustand v5 note

Per the repo's migration guidance, any new store selector that returns an object/array literal must be wrapped with `useShallow` to avoid render loops. Applies to any new hook that subscribes to store-derived data on the detail pages.

## Testing

### Backend

- `require_org_role` + `ROLE_ORDER` unit tests — each role against each threshold; platform-admin bypass.
- Enum migration test — existing `OWNER` rows load; new values insertable.
- Per-endpoint tests:
  - `GET /admin/users/{user_id}` — success, 404, 403 for non-platform-admin callers.
  - `PATCH /admin/organizations/{org_id}/members/{user_id}` — escalation/de-escalation matrix, last-Owner demotion blocked, personal-org locked, 403 for Viewer/Operator/Member callers.
  - `POST /admin/organizations/{org_id}/members` — relaxed gate allows Org Admin; escalation guard holds.
  - `DELETE /admin/organizations/{org_id}/members/{user_id}` — last-Owner removal blocked; personal-org blocked.
- Flow CRUD + execution gate tests — parametrize over (caller role) × (action) asserting 200/403.
- `is_active=false` — login denied; API key auth denied; existing session fails on next request.

### Frontend (Jest; react-query v5 uses `isPending`)

- `RoleBadge` — renders correct label, color, tooltip text per role.
- `RolePicker` — options disabled correctly given `(callerRole, currentRole)`; emits `onSelect`.
- `UserDetailPage` — tabs switch; identity header renders; toggles call the correct mutations; danger-zone confirmation flow.
- `MembershipsTab` — role change round-trip via hook mock; remove confirmation; personal-org row renders as locked.
- `AddToOrganizationDialog` — org search + role assignment.
- `OrgMemberDetailPage` — scoped rendering; Platform-Admin and other-org data hidden for org-admin audience.

## Rollout

### Migration safety

- Both Alembic revisions are additive. Enum expansion is zero-downtime. FK change is metadata-only.
- No data backfill.
- Deploy order:
  1. Backend: migrations + new/extended endpoints + authorization helpers.
  2. Frontend: detail pages, `RoleBadge`/`RolePicker`, route registration.
  3. Flow/folder ownership transition (remove `user_id == current_user`): gated on the new `require_org_role` helper existing server-side. This is the largest user-visible behavior change; ship last so it can be reverted independently.

### No feature flag

The role expansion is additive. Existing frontend behaves the same when only `OWNER` memberships exist. Old frontend clients receiving new role values gracefully render them as strings — no crashes. Dual-deployment safe.

### Migration concerns to verify before merging

- Any "My Flows" / "Recent Flows" filter in the flow list that currently queries `user_id == current_user` must be updated to "flows in orgs I'm a member of." This is a UI-level concern; identify during implementation by grepping the flow list page(s).
- Any flow detail view that labels the creator should use `created_by_id` (= the existing `user_id` column) rather than an ownership label.

## Known Gaps

The following surfaces are **intentionally** not gated by org role in this spec. They remain with their current access model and are tracked as future work for an Option 3 enforcement pass:

| Resource               | Today's enforcement   | Post-spec enforcement  |
| ---------------------- | --------------------- | ---------------------- |
| API keys               | Per-user              | Per-user (unchanged)   |
| Variables              | Per-user              | Per-user (unchanged)   |
| Files                  | Per-user              | Per-user (unchanged)   |
| Deployments            | Per-user              | Per-user (unchanged)   |
| Deployment provider accounts | Per-user        | Per-user (unchanged)   |
| Flow runs / logs       | Per-user              | Per-user (unchanged)   |
| Messages (chat history)| Per-user              | Per-user (unchanged)   |
| Transactions           | Per-user              | Per-user (unchanged)   |
| Jobs                   | Per-user              | Per-user (unchanged)   |
| Vertex builds          | Per-user              | Per-user (unchanged)   |

Additional gaps:

- **Active session revocation** on `is_active=false` — sessions invalidate on next request, not immediately. Full kickout would require a session-store sweep or token-version bump.
- **Org transfer** (changing sole ownership of an org from one user to another) — no endpoint; workaround is to add the new owner, then have the old owner demote themselves.
- **Platform-level role tiers** — `is_platform_admin` remains a single boolean.
- **Per-flow sharing / explicit collaborators** beyond org role.
- **Billing-role gating** — no billing system exists.

Each row above is deliberate: the org-role model is extensible to any of these surfaces without schema change. A follow-up spec can add `require_org_role` to each endpoint family as needed.
