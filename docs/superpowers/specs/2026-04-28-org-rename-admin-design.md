# Org rename (platform admin)

**Date:** 2026-04-28
**Branch:** platform-multi-tenant
**Status:** design approved, awaiting implementation plan

## Goal

Let a platform admin change an organization's display **name** from the existing org admin detail page (`/settings/organizations/{org_id}` → Settings tab). Today the Settings tab is read-only except for delete; this adds an editable Name field.

## Scope decisions

| Decision | Choice | Rationale |
|---|---|---|
| Editable fields | **Name only** | Slug is the unique key; changing it invalidates URLs/integrations. Out of scope. |
| Permission | **Platform admin only** | Matches the existing `/admin/organizations/*` surface. Org-owner-level rename can come later. |
| UX placement | **Form field in Settings tab** | Symmetric with the existing Danger zone block; reuses the tab the user is already on. |
| Personal orgs | **Block rename** | Mirrors the existing 403 on delete for `is_personal=True`. |

## Backend

File: `src/backend/base/langflow/api/v1/admin/orgs.py`

Add a new pydantic model and endpoint alongside the existing `OrgCreate` / `create_organization` block.

```python
class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


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
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot rename a personal organization")
    org.name = body.name
    session.add(org)
    await session.flush()
    mc = (await session.exec(
        select(func.count()).select_from(Membership).where(Membership.organization_id == org.id)
    )).one()
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

- `updated_at` is bumped manually via `org.updated_at = datetime.now(timezone.utc)` before flush. The `Organization` model uses `default_factory=_utc_now` (fires on INSERT only) and has no `onupdate` hook, so PATCH paths must set the timestamp explicitly. Matches the project pattern in `usage_thresholds.py:103` and `alert_rules.py:139`. **Followup:** consider adding `sa_column_kwargs={"onupdate": _utc_now}` to `Organization.updated_at` so future write paths don't silently skip the bump.
- Slug, billing fields, `is_personal` are not exposed in `OrgUpdate` — name is the only mutable field for now.
- Pydantic enforces `min_length=1, max_length=200`, returning 422 on bad input.
- No `IntegrityError` handling — name has no unique constraint.

## Frontend types

File: `src/frontend/src/controllers/API/queries/admin/types.ts`

Add:

```ts
export interface OrgUpdate {
  name: string;
}
```

## Frontend mutation hook

File: `src/frontend/src/controllers/API/queries/admin/use-update-organization.ts` (new)

Mirror the structure of the existing `use-delete-organization.ts` / `use-create-organization.ts` hooks:

- Mutation function: `PATCH /api/v1/admin/organizations/{org_id}` with body `{ name }`.
- Variables: `{ orgId: string; name: string }`.
- On success, invalidate:
  - `["admin", "organizations"]` — list view
  - `["admin", "organizations", orgId]` — detail view (so header + tabs reflect the new name)
- Returns `OrgSummary` (the updated row).

Export the hook from `src/frontend/src/controllers/API/queries/admin/index.ts`.

## Frontend UI

File: `src/frontend/src/pages/AdminPage/organizations/OrganizationSettingsTab.tsx`

Add a **Name** section above the existing read-only `<dl>` (Slug / Created), using the existing `Input` and `Button` primitives. Skeleton:

```tsx
const [name, setName] = useState(org.name);
const update = useUpdateOrganization();

const dirty = name.trim() !== org.name;
const canSave = dirty && name.trim().length > 0 && !update.isPending && !org.is_personal;

async function onSave() {
  await update.mutateAsync({ orgId: org.id, name: name.trim() });
  // toast on success/error via existing toast helper
}
```

Layout:

- A labeled `Name` input (controlled by local state, seeded from `org.name`).
- Save button: disabled per `canSave`; spinner while pending.
- Cancel button: disabled until dirty; resets local state to `org.name`.
- Personal orgs: input rendered with `disabled={org.is_personal}` and `title` tooltip ("Personal organizations cannot be renamed."), mirroring the disabled-Delete-button pattern (`OrganizationSettingsTab.tsx:29-35`).

Toast strings:

- Success: `"Organization renamed."`
- Error: surface server `detail` (e.g. 403 from personal-org guard) via existing toast helper.

## Out of scope (explicit YAGNI)

- Slug editing.
- Org-owner-level rename (only platform admin for now).
- Audit logging of renames.
- Optimistic updates — wait for server response.
- Bulk rename or rename history.

## Test plan

Backend (`src/backend/tests/...`, mirroring nearby admin org tests):

- 200: platform admin renames a non-personal org → response shows new name; subsequent GET returns new name; `updated_at` advanced.
- 404: org id not found.
- 403: rename attempted on `is_personal=True` org.
- 401/403: non-admin user blocked by `PlatformAdmin` guard.
- 422: empty name, name >200 chars.

Frontend:

- Component test for `OrganizationSettingsTab`: typing into the Name input enables Save; clicking Cancel reverts; personal-org input is disabled with the tooltip text.
- Manual smoke: rename in admin UI, confirm header + list both reflect the new name without page reload (via query invalidation).
