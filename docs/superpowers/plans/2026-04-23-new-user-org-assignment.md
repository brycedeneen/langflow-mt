# New-User Org Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `UserManagementModal` so a platform admin can set `is_platform_admin` and assign a required (organization, role) pair when creating a non-privileged user, and wire up a 3-step save orchestration in `UsersPage.handleNewUser`.

**Architecture:** Frontend-only, reusing existing hooks (`useAddUser`, `useUpdateUser`, `useAddMember`, `useGetOrganizations`) and the existing `RolePicker` component. No backend changes. Save is intentionally non-atomic; personal-org auto-provisioning guarantees the user is never in an inconsistent state.

**Tech Stack:** React + TypeScript, Radix UI primitives (Select, Form), TanStack Query, Jest + React Testing Library (frontend tests already exist in this repo).

**Reference spec:** `docs/superpowers/specs/2026-04-23-new-user-org-assignment-design.md`

**User's workflow constraints (from project memory):**
- Never `git commit` without asking — ask the operator before every commit step.
- Do not use `git add -A` / `git add .` / `git commit -a`; stage explicit paths only. Parallel work in the user's tree must not be swept in.

---

## File Structure

### Files modified

- `src/frontend/src/types/components/index.ts` — add `organization_id?: string` and `role?: MembershipRole` to `UserInputType`; import the `MembershipRole` type.
- `src/frontend/src/constants/constants.ts` — extend `CONTROL_NEW_USER` with `is_platform_admin`, `organization_id`, `role`.
- `src/frontend/src/modals/userManagementModal/index.tsx` — add Platform Admin checkbox (gated), Organization picker, Role picker, validation, orgs fetch.
- `src/frontend/src/pages/AdminPage/UsersPage.tsx` — extend `handleNewUser` to include `is_platform_admin` in the PATCH and conditionally call `useAddMember` as step 3.

### Files read (no change)

- `src/frontend/src/constants/roles.ts` — `MembershipRole` type (imported by types/components + modal).
- `src/frontend/src/components/common/rolePicker.tsx` — reused as-is.
- `src/frontend/src/pages/AdminPage/UserDetailPage/AddToOrganizationDialog.tsx` — reference pattern for org searchable list.
- `src/frontend/src/controllers/API/queries/admin/index.ts` — reexports `useGetOrganizations` + `useAddMember`.

### Files created

None.

---

## Task 1: Extend types and constants

**Files:**
- Modify: `src/frontend/src/types/components/index.ts:443-452`
- Modify: `src/frontend/src/constants/constants.ts:651-656`

No tests for this task — it's a pure type/constant extension that is exercised by Task 3's tests. Commit is bundled with Task 2.

- [ ] **Step 1: Add `MembershipRole` import to types/components/index.ts**

At the top of `src/frontend/src/types/components/index.ts`, add the import near the other `@/constants` imports (or at the top if none exist):

```ts
import type { MembershipRole } from "@/constants/roles";
```

If the file already has an `import type` from `@/constants/...`, add `MembershipRole` to that import instead of a new line.

- [ ] **Step 2: Extend `UserInputType` with the two new fields**

Replace the existing `UserInputType` declaration at `src/frontend/src/types/components/index.ts:443-452`:

```ts
export type UserInputType = {
  username: string;
  password: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_platform_admin?: boolean;
  organization_id?: string;
  role?: MembershipRole;
  id?: string;
  create_at?: string;
  updated_at?: string;
};
```

- [ ] **Step 3: Extend `CONTROL_NEW_USER`**

Replace the existing block at `src/frontend/src/constants/constants.ts:651-656`:

```ts
export const CONTROL_NEW_USER = {
  username: "",
  password: "",
  is_active: false,
  is_superuser: false,
  is_platform_admin: false,
  organization_id: "",
  role: "member" as const,
};
```

- [ ] **Step 4: Typecheck**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: passes (or fails only with pre-existing errors unrelated to these files). If there are new errors, they are likely in this file or its direct importers.

- [ ] **Step 5: Do not commit yet**

This task's changes will be committed at the end of Task 2.

---

## Task 2: Modal — Platform Admin checkbox (gated)

**Files:**
- Modify: `src/frontend/src/modals/userManagementModal/index.tsx`

This task adds ONLY the `is_platform_admin` checkbox. Org + Role come in Task 3. Small increments keep the diff reviewable.

- [ ] **Step 1: Add `isPlatformAdmin` state and reset**

In `src/frontend/src/modals/userManagementModal/index.tsx`, alongside the existing `isSuperUser` state at line ~36, add:

```ts
const [isPlatformAdmin, setIsPlatformAdmin] = useState(
  data?.is_platform_admin ?? false,
);
```

In `resetForm` at lines ~64-70, add:

```ts
setIsPlatformAdmin(false);
```

In the `useEffect` that runs on `open` at lines ~46-62, inside the `else` branch (where `data` exists), add:

```ts
setIsPlatformAdmin(data.is_platform_admin ?? false);
handleInput({
  target: { name: "is_platform_admin", value: data.is_platform_admin ?? false },
});
```

- [ ] **Step 2: Render the Platform Admin checkbox, gated**

In the checkbox row at lines ~240-297 (the `<div className="flex gap-8">` block containing `is_active` and `is_superuser`), after the `is_superuser` block, add:

```tsx
{userData?.is_platform_admin && (
  <Form.Field name="is_platform_admin">
    <div>
      <Form.Label className="data-[invalid]:label-invalid mr-3">
        Platform Admin
      </Form.Label>
      <Form.Control asChild>
        <Checkbox
          checked={isPlatformAdmin}
          value={isPlatformAdmin}
          id="is_platform_admin"
          className="relative top-0.5"
          onCheckedChange={(value) => {
            handleInput({
              target: { name: "is_platform_admin", value },
            });
            setIsPlatformAdmin(value);
          }}
          data-testid="new-user-is-platform-admin"
        />
      </Form.Control>
    </div>
  </Form.Field>
)}
```

Note: the existing file uses `value={isSuperUser}` on the Checkbox which passes a boolean — this matches the existing primitive usage. Mirror it verbatim.

- [ ] **Step 3: Typecheck**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: passes.

- [ ] **Step 4: Manual smoke test**

Start the frontend dev server (if not running) and confirm by hand:
1. Log in as a platform admin user. Open `/settings/users`, click "New User". Confirm the Platform Admin checkbox is visible alongside Active and Superuser.
2. Log in (or impersonate) a superuser that is NOT a platform admin. Confirm the Platform Admin checkbox is NOT rendered.
3. Open the edit pencil on an existing user. Confirm the Platform Admin checkbox IS rendered for a platform-admin viewer (existing data preloads the checkbox value). This preserves parity with the row-level Platform Admin control already on the page.

If you cannot run the dev server in this environment, note it explicitly and defer this smoke test to the reviewer.

- [ ] **Step 5: Ask user before committing, then commit**

**Do not commit without asking the operator first.** When approved:

```bash
git add src/frontend/src/types/components/index.ts \
        src/frontend/src/constants/constants.ts \
        src/frontend/src/modals/userManagementModal/index.tsx
git commit -m "feat(frontend/user-admin): add is_platform_admin at create time

Platform Admin checkbox gated to current platform admins, consistent with
the existing row-level Platform Admin control on UsersPage. Extends
UserInputType and CONTROL_NEW_USER to carry the flag through the form."
```

---

## Task 3: Modal — Org picker + Role picker (non-privileged only)

**Files:**
- Modify: `src/frontend/src/modals/userManagementModal/index.tsx`

- [ ] **Step 1: Add imports**

Near the other imports at the top of `src/frontend/src/modals/userManagementModal/index.tsx`, add:

```ts
import { Input } from "@/components/ui/input";
import RolePicker from "@/components/common/rolePicker";
import type { MembershipRole } from "@/constants/roles";
import { useGetOrganizations } from "@/controllers/API/queries/admin";
```

- [ ] **Step 2: Add org/role state**

Near the other `useState` calls (~line 36), add:

```ts
const [organizationId, setOrganizationId] = useState("");
const [orgQuery, setOrgQuery] = useState("");
const [role, setRole] = useState<MembershipRole>("member");
```

In `resetForm`, add:

```ts
setOrganizationId("");
setOrgQuery("");
setRole("member");
```

- [ ] **Step 3: Compute `isCreateMode` + `needsOrg`**

Directly after the state block (before the `useEffect`), add:

```ts
const isCreateMode = !data;
const needsOrg = isCreateMode && !isSuperUser && !isPlatformAdmin;
```

- [ ] **Step 4: Fetch orgs (gated)**

Below the `needsOrg` derivation:

```ts
const { data: orgsData, isLoading: isOrgsLoading } = useGetOrganizations(
  { q: orgQuery || undefined, limit: 20 },
  {
    enabled: isCreateMode && userData?.is_platform_admin === true,
  },
);
const orgItems = (orgsData?.items ?? []).filter((o) => !o.is_personal);
const hasAnyOrgs = (orgsData?.total ?? orgItems.length) > 0 || orgQuery !== "";
```

`hasAnyOrgs` stays `true` whenever the user has typed a query (so the "no orgs exist" inline message doesn't appear just because a search has zero results). When the unfiltered fetch returns zero total non-personal orgs, `hasAnyOrgs` is `false`.

- [ ] **Step 5: Clear org/role state when privileged checkboxes flip on**

Add a `useEffect`:

```ts
useEffect(() => {
  if (isSuperUser || isPlatformAdmin) {
    setOrganizationId("");
    setOrgQuery("");
    setRole("member");
    handleInput({ target: { name: "organization_id", value: "" } });
    handleInput({ target: { name: "role", value: "member" } });
  }
}, [isSuperUser, isPlatformAdmin]);
```

- [ ] **Step 6: Render the org + role row**

After the checkbox row (`<div className="flex gap-8">...</div>`) and inside the outer `<div className="grid gap-5">`, add:

```tsx
{needsOrg && (
  <div className="flex flex-col gap-3">
    <Form.Field name="organization_id">
      <Form.Label className="data-[invalid]:label-invalid">
        Organization <span className="font-medium text-destructive">*</span>
      </Form.Label>
      {!hasAnyOrgs && !isOrgsLoading ? (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
          data-testid="new-user-no-orgs-message"
        >
          No organizations exist. Create one in Admin → Organizations first.
        </div>
      ) : (
        <>
          <Input
            placeholder="Search organizations..."
            value={orgQuery}
            onChange={(e) => setOrgQuery(e.target.value)}
            data-testid="new-user-org-search"
          />
          <ul
            className="mt-2 max-h-48 overflow-auto rounded-md border"
            data-testid="new-user-org-list"
          >
            {orgItems.map((o) => (
              <li
                key={o.id}
                className={`cursor-pointer px-3 py-2 hover:bg-muted ${
                  organizationId === o.id ? "bg-muted" : ""
                }`}
                onClick={() => {
                  setOrganizationId(o.id);
                  handleInput({
                    target: { name: "organization_id", value: o.id },
                  });
                }}
                data-testid={`new-user-org-option-${o.id}`}
              >
                {o.name}
              </li>
            ))}
            {orgItems.length === 0 && !isOrgsLoading && (
              <li className="px-3 py-2 text-muted-foreground">No matches.</li>
            )}
          </ul>
        </>
      )}
    </Form.Field>

    <Form.Field name="role">
      <Form.Label className="data-[invalid]:label-invalid mr-3">
        Role <span className="font-medium text-destructive">*</span>
      </Form.Label>
      <RolePicker
        caller="platform_admin"
        current={role}
        onSelect={(next) => {
          setRole(next);
          handleInput({ target: { name: "role", value: next } });
        }}
      />
    </Form.Field>
  </div>
)}
```

- [ ] **Step 7: Disable Save when required fields aren't satisfied**

Replace the existing Save submit block at lines ~311-313:

```tsx
<Form.Submit asChild>
  <Button
    className="mt-8"
    disabled={
      needsOrg &&
      (!organizationId || (!hasAnyOrgs && !isOrgsLoading))
    }
    data-testid="new-user-save"
  >
    {confirmationText}
  </Button>
</Form.Submit>
```

Note: password-mismatch is already prevented on submit by the existing `onSubmit` handler (line ~86); we don't need to duplicate that guard here.

- [ ] **Step 8: Typecheck**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: passes.

- [ ] **Step 9: Manual smoke test (browser)**

Start the dev server. As a platform admin:

1. Open New User modal with neither Superuser nor Platform Admin checked → Organization search + role picker are visible. Save is disabled.
2. Type into the org search → results filter. Click an org → it highlights, Save becomes enabled.
3. Check Superuser → Organization/Role row disappears. Uncheck it → row returns with `role=Member` and no org picked (Save disabled again).
4. In an instance with zero non-personal orgs, the inline "Create one in Admin → Organizations first" appears; Save stays disabled.
5. Open edit on an existing user → none of the new fields are visible.

If the dev server can't be run, note it and defer.

- [ ] **Step 10: Ask user before committing, then commit**

**Do not commit without asking the operator first.** When approved:

```bash
git add src/frontend/src/modals/userManagementModal/index.tsx
git commit -m "feat(frontend/user-admin): require org + role for non-privileged users

New User modal shows a searchable Organization picker and RolePicker row
when the new user is neither Superuser nor Platform Admin. Save is
disabled until an org is picked. Shows an inline 'no orgs exist' message
on fresh instances. Fields are hidden in edit mode; existing edit
behavior is unchanged."
```

---

## Task 4: Page — 3-step save orchestration

**Files:**
- Modify: `src/frontend/src/pages/AdminPage/UsersPage.tsx:238-272`

- [ ] **Step 1: Import `useAddMember`**

Near the existing auth-queries import at `src/frontend/src/pages/AdminPage/UsersPage.tsx:5-10`:

```ts
import { useAddMember } from "@/controllers/API/queries/admin";
```

- [ ] **Step 2: Add the `useAddMember` mutation alongside the others**

After line 60 (`const { mutate: mutateAddUser } = useAddUser();`):

```ts
const { mutate: mutateAddMember } = useAddMember();
```

- [ ] **Step 3: Replace `handleNewUser` with the 3-step orchestration**

Replace lines 238-272 (`function handleNewUser(user: UserInputType) { ... }`) with:

```ts
function handleNewUser(user: UserInputType) {
  mutateAddUser(user, {
    onSuccess: (res) => {
      const newUserId = res["id"];
      mutateUpdateUser(
        {
          user_id: newUserId,
          user: {
            is_active: user.is_active,
            is_superuser: user.is_superuser,
            is_platform_admin: user.is_platform_admin,
          },
        },
        {
          onSuccess: () => {
            if (user.organization_id) {
              mutateAddMember(
                {
                  orgId: user.organization_id,
                  user_id: newUserId,
                  role: user.role ?? "member",
                },
                {
                  onSuccess: () => {
                    resetFilter();
                    setSuccessData({ title: USER_ADD_SUCCESS_ALERT });
                  },
                  onError: (error) => {
                    resetFilter();
                    setErrorData({
                      title: "User created, but could not be added to organization. Add them from the organization page.",
                      list: [error["response"]?.["data"]?.["detail"] ?? String(error)],
                    });
                  },
                },
              );
            } else {
              resetFilter();
              setSuccessData({ title: USER_ADD_SUCCESS_ALERT });
            }
          },
          onError: (error) => {
            resetFilter();
            setErrorData({
              title: "User created, but role flags could not be applied. Please edit the user to set roles.",
              list: [error["response"]?.["data"]?.["detail"] ?? String(error)],
            });
          },
        },
      );
    },
    onError: (error) => {
      setErrorData({
        title: USER_ADD_ERROR_ALERT,
        list: [error["response"]["data"]["detail"]],
      });
    },
  });
}
```

Key deltas vs. the original:
- Passes `is_platform_admin` in the PATCH payload.
- Conditional third call when `organization_id` is set.
- Dedicated, user-actionable error toasts for the two partial-success cases (spec § Failure semantics).
- `resetFilter()` on the partial-success branches so the newly created user shows up in the list even when the follow-up failed.

- [ ] **Step 4: Typecheck**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: passes.

- [ ] **Step 5: Manual smoke test (browser)**

As a platform admin:

1. Create a user with only Superuser checked → user appears in the list; pencil-edit confirms `is_superuser=true`, `is_platform_admin=false`. No org assignment beyond the personal org.
2. Create a user with only Platform Admin checked → user appears; flags match; Platform Admin column is checked.
3. Create a plain user with Org X + role Admin → user appears. Navigate to Admin → Organizations → Org X → confirm the user is listed as Admin. Also confirm they have their personal org (via user detail page).
4. (Induced failure for step 3) Pick an org the current session would be rejected from adding to (or temporarily stop the backend mid-flow). Confirm the user is created with flags and the partial-success toast fires.

- [ ] **Step 6: Ask user before committing, then commit**

**Do not commit without asking the operator first.** When approved:

```bash
git add src/frontend/src/pages/AdminPage/UsersPage.tsx
git commit -m "feat(frontend/user-admin): wire add-member into new-user save flow

handleNewUser now runs POST /users → PATCH flags → POST
/admin/organizations/{id}/members when an org was picked in the modal.
is_platform_admin is applied via the PATCH. Partial-success errors
surface actionable toasts and still refresh the list so the new user is
visible."
```

---

## Task 5: Verify end-to-end and update spec followups (if any)

**Files:**
- Read-only: whole flow in the browser.
- Optionally Modify: `docs/superpowers/followups.md` if something surfaces that deserves a followup.

- [ ] **Step 1: End-to-end scenarios in the browser**

Walk through every row of the spec § Testing matrix:
1. Superuser-only user → ok.
2. Platform-Admin-only user → ok.
3. Plain user with org + role → ok.
4. Add-member failure → partial-success toast + user still created.
5. Zero non-personal orgs → inline message + disabled save.
6. Superuser viewer who is not platform admin → Platform Admin checkbox not rendered.
7. Edit mode → no new fields visible.

- [ ] **Step 2: Note any divergences**

If any scenario doesn't behave as specced, DO NOT patch over it silently. Stop, describe the divergence to the operator, and decide together whether to fix in this branch or capture as a followup.

- [ ] **Step 3: Typecheck + lint**

```bash
cd src/frontend && npx tsc --noEmit
```

If the frontend has a lint script wired up (check `package.json`), run it against the modified files only.

- [ ] **Step 4: No additional commit**

Task 5 is verification only. Any fix that comes out of it commits separately with its own message, with operator approval.

---

## Out of scope (explicit)

- New Jest or Playwright test files — the modal has no existing Jest coverage; adding a test-suite scaffold here is scope expansion.
- Backend changes — none needed.
- Inline org creation from the modal.
- Multi-org selection at creation.
- Refactoring the existing orchestration to wrap all three calls in a single hook — possible future cleanup, but the current per-mutation pattern matches the rest of the page.

---

## Self-Review

Spec coverage: every `§` of the spec maps to a task —
- § 1 Form fields → Task 2 (Platform Admin) + Task 3 (Org + Role).
- § 2 Save sequence → Task 4.
- § 3 Types/constants → Task 1.
- § 4 UI primitives → Task 3 (uses existing `Input`, `RolePicker`, `Form`).
- § 5 Testing → Task 5 (manual matrix).

Placeholder scan: no TBDs, no "implement later", no unshown code, no references to types not defined here or in imported files.

Type consistency: `MembershipRole` flows from `@/constants/roles` through `UserInputType` and the modal. `user.role ?? "member"` in Task 4 matches `role: "member" as const` default in Task 1. `organization_id` is the same field name everywhere (form state → `UserInputType` → `useAddMember` param name is `orgId`, which is remapped explicitly in Task 4 step 3). No drift.
