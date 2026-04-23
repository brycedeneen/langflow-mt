# New-User Org Assignment in User Admin Modal

## Problem

In the current User Admin → "New User" modal (`UserManagementModal` opened from `UsersPage`), a platform admin can create a user with only a username, password, Active flag, and Superuser flag. The user is auto-assigned to a newly minted *personal* organization (`ensure_personal_organization`), but never to any real tenant org. Every non-privileged user must belong to at least one non-personal org — today the platform admin has to create the user here and then navigate to a different admin page to add them to an org.

Additionally, the `is_platform_admin` flag already exists on the User record and is editable from the row-level Platform Admin column on `UsersPage`, but it cannot be set at user-creation time.

## Goals

1. Let a platform admin set `is_platform_admin` at create time.
2. Require a real org assignment (with a role) at create time for any user who isn't a Superuser or Platform Admin.
3. Do not change edit-mode behavior. Membership management for existing users stays on the org detail page.
4. Do not change any backend endpoints. Reuse existing hooks.

## Non-goals

- Multi-org assignment at creation (a user can be added to multiple orgs, but only one at creation time — the rest happen on the org detail page).
- Inline org creation from the modal.
- Changes to any endpoint schema, backend validation, or migration.
- New Jest coverage for `UserManagementModal` (it currently has none; expanding it is out of scope).
- Playwright coverage for user admin flows.

## Form design (create mode only)

The modal gains three fields, added below the existing Active/Superuser row:

| Field | Primitive | Visible when | Required |
|---|---|---|---|
| Platform Admin | Checkbox | `userData.is_platform_admin === true` | No |
| Organization | Searchable list (Input `q` + scrollable `<ul>`, populated from `useGetOrganizations`; mirrors `AddToOrganizationDialog`) | `isCreateMode && !isSuperUser && !isPlatformAdmin` | Yes when visible |
| Role | `RolePicker` (`src/components/common/rolePicker.tsx`, `caller="platform_admin"`, default `member`) | same as Organization | Yes when visible |

Derived state:

```ts
const isCreateMode = !data;
const needsOrg = isCreateMode && !isSuperUser && !isPlatformAdmin;
```

When either privileged checkbox flips on, the Organization + Role row unmounts and its state clears (`organizationId = ""`, `role = "member"`). No lingering state is submitted.

**Save button disabled when:**

- passwords don't match (existing behavior), OR
- `needsOrg && !organizationId` (required-field behavior), OR
- `needsOrg && organizations list is empty` (see edge case i below).

**Edit mode:** all three new fields are hidden. The modal only touches User fields (username, password, is_active, is_superuser, is_platform_admin). Existing edit behavior is unchanged.

## Save orchestration (in `UsersPage.handleNewUser`)

The current flow is POST `/users/` + PATCH `/users/{id}` (for Active/Superuser). It gains a third conditional call and extends the PATCH payload:

```
1. POST /api/v1/users/                { username, password }
   → returns { id, ... }; backend auto-creates personal org + owner membership.

2. PATCH /api/v1/users/{new_id}       { is_active, is_superuser, is_platform_admin }
   → existing call; is_platform_admin is the only added field.

3. (conditional) POST /api/v1/admin/organizations/{organization_id}/members
                                      { user_id: new_id, role }
   → runs iff `organization_id` was picked in the form.
```

Ordering rationale: need the user's id before steps 2 and 3. Step 2 before step 3 so the user is Active before appearing in the org roster.

### Failure semantics

No rollback; personal-org provisioning in step 1 keeps the user in a coherent state even if steps 2 and 3 fail.

| Step | Fails → |
|---|---|
| 1 | Nothing created. Existing error toast (e.g. "This username is unavailable"). |
| 2 | User exists with default flags. Toast: *"User created but role flags could not be applied. Please edit the user to set roles."* |
| 3 | User exists with flags but no membership in the picked org. Toast: *"User created but could not be added to {org_name}. Add them from the organization page."* User can retry from the org detail page without recreating the user. |

## Edge cases

- **Zero non-personal orgs exist (fresh instance).** The Organization select renders a disabled state with inline message *"No organizations exist. Create one in Admin → Organizations first."* Save is disabled.
- **Non-privileged user + no org picked.** Save is disabled by the required-field rule; no submit-time toast.
- **Platform admin untoggles their own `is_platform_admin`.** Out of scope; this spec covers create only, and the checkbox is not shown in edit mode beyond today's row-level control (which is unchanged).

## Types and constants

`src/frontend/src/types/components/index.ts`:

```ts
export type UserInputType = {
  username: string;
  password: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_platform_admin?: boolean;
  organization_id?: string;   // new — create only; ignored in edit mode
  role?: MembershipRole;      // new — create only; imported from @/constants/roles
  id?: string;
  create_at?: string;
  updated_at?: string;
};
```

`src/frontend/src/constants/constants.ts`:

```ts
export const CONTROL_NEW_USER = {
  username: "",
  password: "",
  is_active: false,
  is_superuser: false,
  is_platform_admin: false,
  organization_id: "",
  role: "member",
};
```

Role values come from the existing `MembershipRole` type in `src/frontend/src/constants/roles.ts`, which mirrors the backend `langflow.services.database.models.membership.model.MembershipRole` enum. The `RolePicker` component in `src/frontend/src/components/common/rolePicker.tsx` is reused as-is; the Platform Admin caller gets every role enabled.

## Data fetching

The modal calls `useGetOrganizations({ limit: 200 })` with `enabled: isCreateMode && userData?.is_platform_admin === true`. 200 matches the backend's `Query(ge=1, le=200)` ceiling. Instances with more than 200 orgs are not a near-term concern; `q`-based server-side search can be added later without changing this spec.

## Visibility rules (summary)

| Actor | Platform Admin checkbox | Org + Role row |
|---|---|---|
| Platform admin (create mode) | visible | visible iff neither priv flag is set |
| Superuser but NOT platform admin (create mode) | hidden | hidden |
| Edit mode (any actor) | hidden (row-level control unchanged) | hidden |

Note: `UsersPage` itself is superuser-gated at the API level today (`get_current_active_superuser`). This spec adds no page-level gating changes. A superuser who is not also a platform admin will see the modal but will not see the Platform Admin checkbox or the Org/Role row — they can still create privileged (superuser) users, matching the shape of today's flow.

## Files touched

All changes are frontend-only:

- `src/frontend/src/modals/userManagementModal/index.tsx` — add fields, visibility logic, state, disabled-save rule, orgs fetch.
- `src/frontend/src/pages/AdminPage/UsersPage.tsx` — extend `handleNewUser` to pass `is_platform_admin` in the PATCH and conditionally invoke `useAddMember`.
- `src/frontend/src/types/components/index.ts` — add `organization_id` and `role` to `UserInputType`.
- `src/frontend/src/constants/constants.ts` — extend `CONTROL_NEW_USER`, add `MEMBERSHIP_ROLES`.

No backend changes. No new files.

## Testing

Manual (primary), run in a real browser:

1. Platform admin creates a Superuser-only user → no org row; save succeeds; flags applied.
2. Platform admin creates a Platform-Admin-only user → no org row; save succeeds; flags applied.
3. Platform admin creates a plain user → org row required; save disabled until picked; after save the user is a member of both their personal org (owner) and the picked org (`role`).
4. Add-member step 3 induced failure (e.g. org the caller can't admin on a non-superuser session) → user exists with flags; toast names the failure; retry from org detail page works.
5. Instance with zero non-personal orgs → combobox shows inline "Create one in Admin → Organizations first"; save disabled.
6. Superuser who is not a platform admin → Platform Admin checkbox not rendered; existing Superuser behavior unchanged.
7. Pencil-icon edit on existing user → none of the new fields visible; existing behavior unchanged.

No new unit or Playwright tests.

## Open questions

None.
