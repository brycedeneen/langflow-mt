# Org Rename (Platform Admin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a platform admin rename an organization (display `name` only) from the existing admin Settings tab. Personal orgs are blocked, mirroring delete.

**Architecture:** New `PATCH /api/v1/admin/organizations/{org_id}` endpoint accepting `{ name }`, gated by `PlatformAdmin`, returning `OrgSummary`. Frontend gets a typed `useUpdateOrganization` mutation hook and an inline editable Name section in `OrganizationSettingsTab.tsx`. Slug, billing fields, and `is_personal` are immutable through this endpoint.

**Tech Stack:** FastAPI + SQLModel (backend), pydantic v2, pytest+httpx async tests, React + TanStack Query v5 + Zod (frontend), `validatedQueryFn` schema-validated client.

**Spec:** `docs/superpowers/specs/2026-04-28-org-rename-admin-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/backend/base/langflow/api/v1/admin/orgs.py` | modify | add `OrgUpdate` body model + `update_organization` PATCH route |
| `src/backend/tests/unit/api/v1/test_admin.py` | modify | add 5 tests covering happy path, 404, 403 (personal), validation, auth |
| `src/frontend/src/schemas/api/_generated.ts` | regenerate | adds `OrgUpdate` Zod schema (auto via `make gen_frontend_schemas`) |
| `src/frontend/src/controllers/API/queries/admin/types.ts` | modify | add `OrgUpdate` interface |
| `src/frontend/src/controllers/API/queries/admin/use-update-organization.ts` | create | TanStack mutation hook calling PATCH |
| `src/frontend/src/controllers/API/queries/admin/index.ts` | modify | export the new hook |
| `src/frontend/src/pages/AdminPage/organizations/OrganizationSettingsTab.tsx` | modify | add editable Name section above existing read-only fields |

---

## Task 1: Backend — `OrgUpdate` model + PATCH endpoint

**Files:**
- Modify: `src/backend/base/langflow/api/v1/admin/orgs.py` (insert after the existing `create_organization` block at lines 133-153)

- [ ] **Step 1: Add `OrgUpdate` body model**

In `src/backend/base/langflow/api/v1/admin/orgs.py`, immediately above the existing `OrgDeleteBody` class (around line 156), add:

```python
class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
```

- [ ] **Step 2: Add the PATCH endpoint**

Immediately after the `create_organization` function (around line 154, before `class OrgDeleteBody`), add:

```python
@router.patch("/organizations/{org_id}", response_model=OrgSummary)
async def update_organization(
    org_id: UUID,
    body: OrgUpdate,
    _admin: PlatformAdmin,
    session: DbSession,
) -> OrgSummary:
    org = await session.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    if org.is_personal:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Cannot rename a personal organization"
        )
    org.name = body.name
    session.add(org)
    await session.flush()
    await session.refresh(org)
    mc = (
        await session.exec(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == org.id)
        )
    ).one()
    return OrgSummary(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_personal=org.is_personal,
        member_count=int(mc),
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )
```

Notes:
- Reuses imports already in this file (`HTTPException`, `status`, `BaseModel`, `Field`, `select`, `func`, `Membership`, `Organization`, `PlatformAdmin`, `DbSession`).
- `await session.refresh(org)` ensures `updated_at` reflects the post-flush value.

- [ ] **Step 3: Sanity-check imports**

Run: `cd /Users/brycedeneen/dev/langflow && uv run --no-sync python -c "from langflow.api.v1.admin.orgs import update_organization, OrgUpdate; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/backend/base/langflow/api/v1/admin/orgs.py
git commit -m "feat(admin): add PATCH endpoint for renaming organizations"
```

> **NOTE for executor:** The repo owner has a standing rule that requires asking permission before every commit. **Pause and ask the user before running `git commit`.** Do not run it autonomously.

---

## Task 2: Backend — Tests (5 cases)

**Files:**
- Modify: `src/backend/tests/unit/api/v1/test_admin.py` (append after the existing `test_delete_personal_org_forbidden` test at line 207, before the membership tests divider)

- [ ] **Step 1: Add five tests in a single block**

Append the following just before the `# Membership tests` divider comment (around line 209):

```python
# ---------------------------------------------------------------------------
# Org rename (PATCH) tests
# ---------------------------------------------------------------------------


async def test_rename_org_happy(client: AsyncClient, admin_headers):
    """Platform admin can rename a non-personal org; GET returns the new name."""
    slug = f"rename-org-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Old Name", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"api/v1/admin/organizations/{org_id}",
        json={"name": "New Name"},
        headers=admin_headers,
    )
    assert patch_resp.status_code == status.HTTP_200_OK
    data = patch_resp.json()
    assert data["id"] == org_id
    assert data["name"] == "New Name"
    assert data["slug"] == slug  # slug unchanged

    get_resp = await client.get(
        f"api/v1/admin/organizations/{org_id}", headers=admin_headers
    )
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["name"] == "New Name"


async def test_rename_org_not_found(client: AsyncClient, admin_headers):
    """PATCH a non-existent org → 404."""
    missing_id = str(uuid4())
    resp = await client.patch(
        f"api/v1/admin/organizations/{missing_id}",
        json={"name": "Whatever"},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_rename_personal_org_forbidden(client: AsyncClient, admin_headers):
    """PATCH a personal org → 403."""
    personal_id = None
    async with session_scope() as session:
        personal = Organization(
            name="Personal",
            slug=f"user-rename-{uuid4()}",
            is_personal=True,
        )
        session.add(personal)
        await session.flush()
        await session.refresh(personal)
        personal_id = str(personal.id)

    try:
        resp = await client.patch(
            f"api/v1/admin/organizations/{personal_id}",
            json={"name": "Renamed Personal"},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        from uuid import UUID as _UUID
        async with session_scope() as session:
            org = await session.get(Organization, _UUID(personal_id))
            if org:
                await session.delete(org)


async def test_rename_org_validates_name(client: AsyncClient, admin_headers):
    """Empty name and >200 chars → 422."""
    slug = f"rename-bad-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Renamable", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    for bad_name in ["", "a" * 201]:
        resp = await client.patch(
            f"api/v1/admin/organizations/{org_id}",
            json={"name": bad_name},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            f"Expected 422 for name {bad_name!r}, got {resp.status_code}"
        )


async def test_rename_org_requires_platform_admin(
    client: AsyncClient, admin_headers, logged_in_headers
):
    """Non-admin user → 403."""
    slug = f"rename-auth-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Auth Test", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    resp = await client.patch(
        f"api/v1/admin/organizations/{org_id}",
        json={"name": "Should Fail"},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
```

- [ ] **Step 2: Run the new tests, expect them to pass**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/api/v1/test_admin.py -k "rename" -v`
Expected: 5 passed.

If any test fails, fix the implementation in `orgs.py` (Task 1) — not the test — and re-run.

- [ ] **Step 3: Run the full admin org test file to confirm no regressions**

Run: `cd /Users/brycedeneen/dev/langflow && uv run pytest src/backend/tests/unit/api/v1/test_admin.py -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/backend/tests/unit/api/v1/test_admin.py
git commit -m "test(admin): cover PATCH org rename happy path, 404, 403, validation, auth"
```

> **NOTE for executor:** Pause and ask the user before running `git commit`.

---

## Task 3: Regenerate frontend OpenAPI schemas

**Files:**
- Regenerate: `src/frontend/src/schemas/api/_generated.ts` (auto-generated; do not hand-edit)

- [ ] **Step 1: Run the schema generator**

Run: `cd /Users/brycedeneen/dev/langflow && make gen_frontend_schemas`
Expected: `_generated.ts` updated; new `OrgUpdate` Zod schema appears around the existing `OrgCreate` block.

- [ ] **Step 2: Verify the new schema is present**

Run: `grep -n "^export const OrgUpdate" /Users/brycedeneen/dev/langflow/src/frontend/src/schemas/api/_generated.ts`
Expected: one match showing the generated `OrgUpdate` definition.

- [ ] **Step 3: Verify the operation id is registered**

Run: `grep -n "update_organization_api_v1_admin_organizations__org_id__patch" /Users/brycedeneen/dev/langflow/src/frontend/src/schemas/api/generated.meta.ts`
Expected: at least one match. If `generated.meta.ts` doesn't exist or doesn't list operation ids by name, skip — Task 4 references the operation id by string and will fail at runtime if the backend route isn't wired up; the backend tests in Task 2 already cover that.

- [ ] **Step 4: Commit the regenerated schema**

```bash
git add src/frontend/src/schemas/api/_generated.ts src/frontend/src/schemas/api/generated.meta.ts
git commit -m "chore(frontend): regenerate API schemas for OrgUpdate"
```

> **NOTE for executor:** Pause and ask the user before running `git commit`.

---

## Task 4: Frontend — `OrgUpdate` TS interface

**Files:**
- Modify: `src/frontend/src/controllers/API/queries/admin/types.ts`

- [ ] **Step 1: Add `OrgUpdate` interface**

In `types.ts`, append at the bottom of the file (after the existing `UserDetail` interface):

```ts
export interface OrgUpdate {
  name: string;
}
```

- [ ] **Step 2: Verify TS compiles**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | head -20`
Expected: no errors referencing `OrgUpdate` or `types.ts`.

(Note: the project may have pre-existing TS errors elsewhere; only fail this step if the errors involve files you're modifying in this plan.)

---

## Task 5: Frontend — `useUpdateOrganization` mutation hook

**Files:**
- Create: `src/frontend/src/controllers/API/queries/admin/use-update-organization.ts`

- [ ] **Step 1: Create the hook file**

Create the new file with this content:

```ts
import { validatedQueryFn } from "@/lib/validated-fetch";
import { OrgSummary as OrgSummarySchema } from "@/schemas/api/_generated";
import type { useMutationFunctionType } from "@/types/api";
import type { z } from "zod";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateOrganizationParams {
  orgId: string;
  name: string;
}

export const useUpdateOrganization: useMutationFunctionType<
  undefined,
  UpdateOrganizationParams,
  z.infer<typeof OrgSummarySchema>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateOrganizationFn = async ({
    orgId,
    name,
  }: UpdateOrganizationParams): Promise<z.infer<typeof OrgSummarySchema>> => {
    const data = await validatedQueryFn(
      "api.admin.update_organization_api_v1_admin_organizations__org_id__patch",
      OrgSummarySchema,
      async () =>
        (
          await api.patch<unknown>(`${getURL("ADMIN_ORGS")}/${orgId}`, {
            name,
          })
        ).data,
    )();
    return data;
  };

  const mutation = mutate(["useUpdateOrganization"], updateOrganizationFn, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "organizations"] });
      queryClient.invalidateQueries({
        queryKey: ["admin", "organizations", variables.orgId],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
```

- [ ] **Step 2: Export from `index.ts`**

Modify `src/frontend/src/controllers/API/queries/admin/index.ts` — add a new line after `export * from "./use-delete-organization";`:

```ts
export * from "./use-update-organization";
```

The complete relevant section should read:
```ts
export * from "./use-create-organization";
export * from "./use-delete-organization";
export * from "./use-update-organization";
```

- [ ] **Step 3: Verify TS compiles**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "use-update-organization|useUpdateOrganization" | head`
Expected: no output (no errors mentioning the new hook).

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/controllers/API/queries/admin/types.ts src/frontend/src/controllers/API/queries/admin/use-update-organization.ts src/frontend/src/controllers/API/queries/admin/index.ts
git commit -m "feat(frontend): add useUpdateOrganization mutation hook"
```

> **NOTE for executor:** Pause and ask the user before running `git commit`.

---

## Task 6: Frontend — Editable Name section in Settings tab

**Files:**
- Modify: `src/frontend/src/pages/AdminPage/organizations/OrganizationSettingsTab.tsx`

- [ ] **Step 1: Replace the entire file with the rename-aware version**

Replace the contents of `OrganizationSettingsTab.tsx` with:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ConfirmByTypingDialog from "@/components/common/confirmByTypingDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useDeleteOrganization,
  useUpdateOrganization,
} from "@/controllers/API/queries/admin";
import type { OrgDetail } from "@/controllers/API/queries/admin";
import useAlertStore from "@/stores/alertStore";

export default function OrganizationSettingsTab({ org }: { org: OrgDetail }) {
  const [confirming, setConfirming] = useState(false);
  const [name, setName] = useState(org.name);
  const nav = useNavigate();
  const del = useDeleteOrganization();
  const update = useUpdateOrganization();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const trimmed = name.trim();
  const dirty = trimmed !== org.name;
  const canSave =
    dirty && trimmed.length > 0 && !update.isPending && !org.is_personal;

  function handleSave() {
    update.mutate(
      { orgId: org.id, name: trimmed },
      {
        onSuccess: (updated) => {
          setName(updated.name);
          setSuccessData({ title: "Organization renamed." });
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to rename organization",
            list: [
              error?.response?.data?.detail ??
                "An unexpected error occurred.",
            ],
          });
        },
      },
    );
  }

  function handleCancel() {
    setName(org.name);
  }

  return (
    <div className="space-y-6">
      <div className="flex max-w-md flex-col gap-2">
        <label className="text-sm font-medium" htmlFor="org-name">
          Name
        </label>
        <Input
          id="org-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={org.is_personal || update.isPending}
          title={
            org.is_personal
              ? "Personal organizations cannot be renamed"
              : undefined
          }
          maxLength={200}
        />
        <div className="flex gap-2">
          <Button
            variant="primary"
            disabled={!canSave}
            onClick={handleSave}
          >
            {update.isPending ? "Saving..." : "Save"}
          </Button>
          <Button
            variant="outline"
            disabled={!dirty || update.isPending}
            onClick={handleCancel}
          >
            Cancel
          </Button>
        </div>
      </div>

      <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Slug</dt>
        <dd>{org.slug}</dd>
        <dt className="text-muted-foreground">Created</dt>
        <dd>{new Date(org.created_at).toLocaleString()}</dd>
      </dl>

      <div className="border-t pt-4">
        <h3 className="font-medium">Danger zone</h3>
        <p className="my-2 text-sm text-muted-foreground">
          Deleting an organization permanently removes it along with all of its
          flows, files, deployments, and memberships. This cannot be undone.
        </p>
        <Button
          variant="destructive"
          disabled={org.is_personal}
          onClick={() => setConfirming(true)}
          title={
            org.is_personal
              ? "Personal organizations cannot be deleted"
              : undefined
          }
        >
          Delete organization
        </Button>
      </div>
      <ConfirmByTypingDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete organization"
        description="This permanently deletes the organization and all flows, files, deployments, and memberships inside it."
        confirmText={org.name}
        onConfirm={async () => {
          await del.mutateAsync({ orgId: org.id, confirm_name: org.name });
          setConfirming(false);
          nav("/settings/organizations");
        }}
      />
    </div>
  );
}
```

Key behavior:
- Input is seeded from `org.name` and updated to the server's response on success.
- Save is disabled unless: name changed, non-empty, not pending, not a personal org.
- Cancel resets to `org.name` and is disabled when nothing's dirty.
- Personal orgs render the input as disabled with the same `title` tooltip pattern as the Delete button.
- Toasts use the same `useAlertStore` pattern as `CreateOrganizationDrawer.tsx`.
- The `Input` import path matches other admin org files (`@/components/ui/input`).
- `maxLength={200}` mirrors the backend `Field(max_length=200)` constraint as a UX guard; backend still validates.

- [ ] **Step 2: Verify TS compiles**

Run: `cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "OrganizationSettingsTab" | head`
Expected: no output.

- [ ] **Step 3: Manual smoke test (run dev server)**

Run: `cd /Users/brycedeneen/dev/langflow && make backend &` then in another terminal: `cd /Users/brycedeneen/dev/langflow/src/frontend && npm run start`

Open `/settings/organizations`, click into a non-personal org, go to the Settings tab. Verify:
1. Name field is pre-filled with the current org name.
2. Save and Cancel are disabled until you edit.
3. After typing a new name and clicking Save, success toast appears, header in the detail page reflects the new name (it's driven by the same query, which gets invalidated).
4. Navigate back to the org list — the renamed org shows the new name.
5. Click into a personal org → Name input is disabled with the tooltip; Delete button still disabled too.
6. Try saving an empty name → Save stays disabled.

If any step fails, debug rather than skipping. Report manual smoke as "tested" only after all 6 are confirmed.

- [ ] **Step 4: Commit**

```bash
git add src/frontend/src/pages/AdminPage/organizations/OrganizationSettingsTab.tsx
git commit -m "feat(admin-ui): allow renaming organization from settings tab"
```

> **NOTE for executor:** Pause and ask the user before running `git commit`.

---

## Self-review notes

- **Spec coverage:**
  - Backend PATCH endpoint → Task 1. ✓
  - Personal-org block → Task 1 (403 path) + Task 2 (test). ✓
  - Name length 1–200 → Task 1 (`Field(min_length=1, max_length=200)`) + Task 2 (validation test). ✓
  - PlatformAdmin gate → Task 1 + Task 2 (auth test). ✓
  - Frontend hook + types → Tasks 4, 5. ✓
  - UI Name section + personal-org-disabled + toasts → Task 6. ✓
  - Query invalidation (list + detail) → Task 5. ✓
  - Out-of-scope: slug editing, owner-level rename, audit log, optimistic update — none implemented. ✓
- **No placeholders:** every code block is complete; every command has an expected output.
- **Type consistency:**
  - Backend `OrgUpdate.name` is `str` length 1–200; frontend `OrgUpdate.name` is `string`; mutation hook `UpdateOrganizationParams.name` is `string`. Aligned.
  - Mutation invalidation keys match `useGetOrganization` query key shape (`["admin", "organizations", orgId]`) verified in `use-get-organization.ts:31`.
  - Operation id `api.admin.update_organization_api_v1_admin_organizations__org_id__patch` follows FastAPI's auto-generated `<function_name>_<path>_<method>` convention (compare with `create_organization_api_v1_admin_organizations_post`).
