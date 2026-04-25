# Per-Flow Audit History + Dropdown Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User commit policy:** Per `feedback_no_git_commits.md`, pause and ask before every `git commit`. The commit steps below are real intent, but you must request approval before running them.

**Goal:** Surface audit-log history at the per-flow level for any org member, give org admins a way to query their org's audit logs, and rename the flow editor's "Share" dropdown to "More" with a new "Flow history" entry that opens the per-flow drawer.

**Architecture:**
- Two new non-admin REST endpoints reuse `AuditService.query()` but enforce org-scoped authz instead of platform-admin: `GET /api/v1/flows/{flow_id}/audit-logs` (org viewer+ on the flow's org) and `GET /api/v1/orgs/{org_id}/audit-logs` (org admin+).
- A new flow-page side drawer (`FlowAuditDrawer`) lists entries returned by the per-flow endpoint, mirroring the visual style of the existing `AuditLogDrawer`. It is opened from the renamed "More" dropdown via a new "Flow history" item.
- The org-admin endpoint ships with tests but no dedicated frontend page in this plan; an org-admin audit page is left as a follow-up.

**Tech Stack:** FastAPI + SQLModel (backend), pytest-asyncio (tests), React + React Query v5 + shadcn/ui (frontend), Jest (frontend tests). Per-flow drawer uses the same custom fixed-position pattern as `AuditLogDrawer.tsx` (no shadcn Sheet).

---

## File Structure

**Created:**
- `src/backend/base/langflow/api/v1/audit_logs.py` — non-admin audit router with org-scoped endpoint
- `src/backend/tests/unit/api/v1/test_flows_audit.py` — pytest for per-flow endpoint
- `src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py` — pytest for org-scoped endpoint
- `src/frontend/src/controllers/API/queries/flows/use-get-flow-audit-logs.ts` — React Query hook
- `src/frontend/src/components/core/flowToolbarComponent/components/flow-audit-drawer.tsx` — per-flow drawer

**Modified:**
- `src/backend/base/langflow/api/v1/flows.py` — add per-flow audit-logs endpoint (lives with other flow routes)
- `src/backend/base/langflow/api/v1/__init__.py` — export new `audit_logs_router`
- `src/backend/base/langflow/main.py` (or wherever v1 routers are included) — mount `audit_logs_router` (engineer must locate the router-include site if not in main.py)
- `src/frontend/src/controllers/API/helpers/constants.ts` — add `FLOW_AUDIT_LOGS` URL constant
- `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx` — rename "Share" → "More", add "Flow history" item, wire drawer state

---

## Task 1: Per-flow audit-logs endpoint (backend, TDD)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (add new route at end of file)
- Test: `src/backend/tests/unit/api/v1/test_flows_audit.py` (create)

The endpoint forces `target_type=FLOW` and `target_id={flow_id}` server-side, ignoring any client overrides. Authz: viewer+ on the flow's `organization_id`. Returns the same `AuditLogListResponse` shape as the admin endpoint to maximize frontend reuse.

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_flows_audit.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.deps import session_scope


async def _seed_flow_audit(flow_id, org_id) -> None:
    async with session_scope() as session:
        session.add(
            AuditLog(
                actor_user_id=uuid4(),
                actor_email="a@b.com",
                actor_is_super=False,
                org_id=org_id,
                target_type=AuditTargetType.FLOW,
                target_id=flow_id,
                action=AuditAction.UPDATE,
                diff={"changed": {"name": ["old", "new"]}},
                diff_hash="abc",
                request_metadata={},
            )
        )


@pytest.mark.asyncio
async def test_flow_audit_requires_org_membership(
    client: AsyncClient, logged_in_headers: dict, created_flow
):
    # logged_in_headers user has no membership in created_flow.organization_id
    resp = await client.get(
        f"api/v1/flows/{created_flow.id}/audit-logs",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_flow_audit_returns_only_target_flow_entries(
    client: AsyncClient, org_member_headers: dict, created_flow
):
    other_flow_id = uuid4()
    await _seed_flow_audit(created_flow.id, created_flow.organization_id)
    await _seed_flow_audit(other_flow_id, created_flow.organization_id)

    resp = await client.get(
        f"api/v1/flows/{created_flow.id}/audit-logs",
        headers=org_member_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["target_type"] == "flow"
        assert item["target_id"] == str(created_flow.id)


@pytest.mark.asyncio
async def test_flow_audit_404_when_flow_missing(
    client: AsyncClient, org_member_headers: dict
):
    resp = await client.get(
        f"api/v1/flows/{uuid4()}/audit-logs",
        headers=org_member_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
```

If `org_member_headers` / `created_flow` fixtures don't yet exist, follow the patterns used in `src/backend/tests/unit/api/v1/test_flows.py` and the `conftest.py` siblings; fixtures may already exist there. Reuse, don't reinvent.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_flows_audit.py -v`
Expected: FAIL — endpoint does not exist (404 on the route, not 403/200).

- [ ] **Step 3: Implement the endpoint**

Append to `src/backend/base/langflow/api/v1/flows.py` (use the same import/dependency style as the existing `read_flow` route — see lines 551-564 for the pattern):

```python
from langflow.api.utils.authz import assert_org_role
from langflow.services.audit.service import get_audit_service
from langflow.services.database.models.audit_log import AuditTargetType
from langflow.services.database.models.audit_log.model import AuditAction
# Reuse response models from the admin module rather than redefining
from langflow.api.v1.admin.audit_logs import AuditLogListResponse, AuditLogRead


@router.get("/{flow_id}/audit-logs", response_model=AuditLogListResponse)
async def list_flow_audit_logs(
    *,
    session: DbSession,
    flow_id: UUID,
    current_user: CurrentActiveUser,
    current_org: CurrentOrg,
    action: Annotated[AuditAction | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    """List audit log entries for a single flow (Viewer+ on the flow's organization)."""
    flow = await _read_flow(session, flow_id, current_org.id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    await assert_org_role(current_user, flow.organization_id, MembershipRole.VIEWER, session=session)

    service = get_audit_service()
    rows, total = await service.query(
        org_id=flow.organization_id,
        target_type=AuditTargetType.FLOW,
        target_id=flow_id,
        action=action,
        from_=from_,
        to=to,
        page=page,
        size=size,
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(r, from_attributes=True) for r in rows],
        total=total,
        page=page,
        size=size,
    )
```

If `AuditLogListResponse` / `AuditLogRead` aren't importable cross-module without circular issues, lift them into `src/backend/base/langflow/services/audit/schemas.py` as a small refactor and import from both call sites.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_flows_audit.py -v`
Expected: PASS — 3 tests pass.

- [ ] **Step 5: Commit (ASK FIRST per user policy)**

```bash
git add src/backend/base/langflow/api/v1/flows.py src/backend/tests/unit/api/v1/test_flows_audit.py
git commit -m "feat(audit): add GET /flows/{flow_id}/audit-logs (org viewer+)"
```

---

## Task 2: Org-scoped audit-logs endpoint (backend, TDD)

**Files:**
- Create: `src/backend/base/langflow/api/v1/audit_logs.py`
- Modify: `src/backend/base/langflow/api/v1/__init__.py`
- Modify: router-include site (likely `src/backend/base/langflow/main.py`)
- Test: `src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py` (create)

Endpoint: `GET /api/v1/orgs/{org_id}/audit-logs`. Authz: org admin+. The endpoint forces `org_id={org_id}` server-side; client cannot override.

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.deps import session_scope


async def _seed(org_id) -> None:
    async with session_scope() as session:
        session.add(
            AuditLog(
                actor_user_id=uuid4(),
                actor_email="a@b.com",
                actor_is_super=False,
                org_id=org_id,
                target_type=AuditTargetType.FLOW,
                target_id=uuid4(),
                action=AuditAction.CREATE,
                diff={},
                diff_hash="x",
                request_metadata={},
            )
        )


@pytest.mark.asyncio
async def test_org_audit_requires_admin_role(
    client: AsyncClient, org_member_headers: dict, created_org
):
    # org_member_headers user is a MEMBER, not ADMIN
    resp = await client.get(
        f"api/v1/orgs/{created_org.id}/audit-logs",
        headers=org_member_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_org_audit_returns_only_caller_org_entries(
    client: AsyncClient, org_admin_headers: dict, created_org
):
    other_org = uuid4()
    await _seed(created_org.id)
    await _seed(other_org)

    resp = await client.get(
        f"api/v1/orgs/{created_org.id}/audit-logs",
        headers=org_admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["org_id"] == str(created_org.id)


@pytest.mark.asyncio
async def test_org_audit_rejects_non_member_admin(
    client: AsyncClient, org_admin_headers: dict
):
    foreign_org = uuid4()
    resp = await client.get(
        f"api/v1/orgs/{foreign_org}/audit-logs",
        headers=org_admin_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
```

If `org_admin_headers` / `created_org` fixtures don't exist, locate the existing org-scoped test patterns (e.g., in `test_memberships.py` or `tests/unit/api/v1/admin/test_role_changes.py`) and reuse/extend their fixtures.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py -v`
Expected: FAIL — route does not exist.

- [ ] **Step 3: Create the new router module**

Create `src/backend/base/langflow/api/v1/audit_logs.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from langflow.api.utils.authz import assert_org_role
from langflow.api.utils.core import CurrentActiveUser
from langflow.api.v1.admin.audit_logs import AuditLogListResponse, AuditLogRead
from langflow.services.audit.service import get_audit_service
from langflow.services.database.models.audit_log.model import AuditAction, AuditTargetType
from langflow.services.database.models.membership.model import MembershipRole
from langflow.services.deps import DbSession

router = APIRouter(tags=["AuditLogs"])


@router.get("/orgs/{org_id}/audit-logs", response_model=AuditLogListResponse)
async def list_org_audit_logs(
    *,
    session: DbSession,
    org_id: UUID,
    current_user: CurrentActiveUser,
    actor_user_id: Annotated[UUID | None, Query()] = None,
    target_type: Annotated[AuditTargetType | None, Query()] = None,
    target_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditLogListResponse:
    """List audit log entries scoped to a single organization (Admin+ in that org)."""
    await assert_org_role(current_user, org_id, MembershipRole.ADMIN, session=session)

    service = get_audit_service()
    rows, total = await service.query(
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        action=action,
        from_=from_,
        to=to,
        page=page,
        size=size,
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(r, from_attributes=True) for r in rows],
        total=total,
        page=page,
        size=size,
    )
```

- [ ] **Step 4: Export the router from v1 `__init__.py`**

Edit `src/backend/base/langflow/api/v1/__init__.py`:

```python
from langflow.api.v1.audit_logs import router as audit_logs_router
```

Add `"audit_logs_router"` to the `__all__` list (keep alphabetical placement).

- [ ] **Step 5: Mount the router**

Find where v1 routers are included (likely `src/backend/base/langflow/main.py` or a sibling of `api/v1/__init__.py`). Search for `flows_router` in the codebase to locate the include site, then add `app.include_router(audit_logs_router, prefix="/api/v1")` next to the others.

Run: `Grep flows_router glob='**/*.py' output_mode=files_with_matches` to find the include site if unclear.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py -v`
Expected: PASS — 3 tests pass.

- [ ] **Step 7: Run the full audit test suite to catch regressions**

Run: `uv run pytest src/backend/tests/unit/api/v1/admin/test_audit_logs.py src/backend/tests/unit/api/v1/test_flows_audit.py src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py -v`
Expected: PASS — all green.

- [ ] **Step 8: Commit (ASK FIRST per user policy)**

```bash
git add src/backend/base/langflow/api/v1/audit_logs.py src/backend/base/langflow/api/v1/__init__.py src/backend/base/langflow/main.py src/backend/tests/unit/api/v1/test_audit_logs_org_scoped.py
git commit -m "feat(audit): add GET /orgs/{org_id}/audit-logs (org admin+)"
```

(Adjust the file list if the router-include lives outside main.py.)

---

## Task 3: Frontend query hook for per-flow audit logs

**Files:**
- Modify: `src/frontend/src/controllers/API/helpers/constants.ts`
- Create: `src/frontend/src/controllers/API/queries/flows/use-get-flow-audit-logs.ts`

- [ ] **Step 1: Add the URL constant**

Edit `src/frontend/src/controllers/API/helpers/constants.ts` near the existing `ADMIN_AUDIT_LOGS` entry (line 45):

```ts
FLOW_AUDIT_LOGS: (flowId: string) => `flows/${flowId}/audit-logs`,
```

If the existing URL map only supports static strings, follow whatever pattern is already used for path-parameterized URLs in the same file (e.g. there will be siblings building paths like `flows/{id}/...`). Match the dominant style.

- [ ] **Step 2: Create the query hook**

Create `src/frontend/src/controllers/API/queries/flows/use-get-flow-audit-logs.ts`. Mirror `src/frontend/src/controllers/API/queries/admin/use-get-audit-logs.ts` but parameterize by `flow_id` and reuse the same `AuditLogListResponseSchema`:

```ts
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { validatedQueryFn } from "../utils/validated-query-fn";
import {
  AuditLogListResponse,
  AuditLogListResponseSchema,
} from "../admin/use-get-audit-logs"; // re-use type/schema

export type FlowAuditLogParams = {
  flow_id: string;
  action?: string;
  from?: string;
  to?: string;
  page?: number;
  size?: number;
};

export const useGetFlowAuditLogs: useQueryFunctionType<
  FlowAuditLogParams,
  AuditLogListResponse
> = ({ flow_id, ...params }, options) => {
  const { query } = UseRequestProcessor();
  const fn = validatedQueryFn(
    "api.flows.list_flow_audit_logs",
    AuditLogListResponseSchema,
    async () =>
      (await api.get<unknown>(getURL("FLOW_AUDIT_LOGS", { flowId: flow_id }), {
        params,
      })).data,
  );
  return query(["flows", flow_id, "audit-logs", params], fn, { ...options });
};
```

If `AuditLogListResponseSchema` is not exported from `use-get-audit-logs.ts`, export it from there first and import here. If `getURL` does not accept a path-args object, switch to whatever signature the codebase uses (e.g. `` `${getURL("FLOWS_BASE")}${flow_id}/audit-logs` ``).

- [ ] **Step 3: Type-check**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Commit (ASK FIRST per user policy)**

```bash
git add src/frontend/src/controllers/API/helpers/constants.ts src/frontend/src/controllers/API/queries/flows/use-get-flow-audit-logs.ts
git commit -m "feat(audit): add useGetFlowAuditLogs hook"
```

---

## Task 4: FlowAuditDrawer component

**Files:**
- Create: `src/frontend/src/components/core/flowToolbarComponent/components/flow-audit-drawer.tsx`

A side drawer that opens from the flow toolbar. Visual style mirrors `src/frontend/src/pages/AdminPage/AdminAuditLogsPage/AuditLogDrawer.tsx` but lists multiple entries (a list view), with each row expandable to show the diff and request metadata.

- [ ] **Step 1: Create the component**

Create `src/frontend/src/components/core/flowToolbarComponent/components/flow-audit-drawer.tsx`:

```tsx
import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetFlowAuditLogs } from "@/controllers/API/queries/flows/use-get-flow-audit-logs";

type Props = {
  flowId: string;
  open: boolean;
  onClose: () => void;
};

const PAGE_SIZE = 50;

export default function FlowAuditDrawer({ flowId, open, onClose }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { data, isPending, isError } = useGetFlowAuditLogs(
    { flow_id: flowId, size: PAGE_SIZE, page: 1 },
    { enabled: open },
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-y-0 right-0 w-[480px] bg-background border-l shadow-xl flex flex-col z-50"
      data-testid="flow-audit-drawer"
    >
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="font-semibold">Flow history</h2>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
          <IconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-4 text-sm">
        {isPending && <div className="text-muted-foreground">Loading…</div>}
        {isError && <div className="text-destructive">Failed to load history.</div>}
        {!isPending && !isError && data && data.items.length === 0 && (
          <div className="text-muted-foreground">No history yet.</div>
        )}
        {!isPending && !isError && data && data.items.length > 0 && (
          <ul className="flex flex-col gap-2">
            {data.items.map((entry) => {
              const expanded = expandedId === entry.id;
              const changedFields = Object.keys(
                (entry.diff as { changed?: Record<string, unknown> })?.changed ?? {},
              );
              const summary =
                entry.action === "create"
                  ? "Created"
                  : entry.action === "delete"
                    ? "Deleted"
                    : changedFields.length > 0
                      ? `Updated: ${changedFields.join(", ")}`
                      : entry.action;
              return (
                <li
                  key={entry.id}
                  className="border rounded p-2 cursor-pointer hover:bg-muted"
                  onClick={() => setExpandedId(expanded ? null : entry.id)}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      {new Date(entry.occurred_at).toLocaleString()}
                    </span>
                    <span className="text-xs">{entry.action}</span>
                  </div>
                  <div className="text-sm">{entry.actor_email}</div>
                  <div className="text-xs text-muted-foreground">{summary}</div>
                  {expanded && (
                    <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-auto">
                      {JSON.stringify(entry.diff, null, 2)}
                    </pre>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit (ASK FIRST per user policy)**

```bash
git add src/frontend/src/components/core/flowToolbarComponent/components/flow-audit-drawer.tsx
git commit -m "feat(audit): add FlowAuditDrawer component"
```

---

## Task 5: Rename "Share" → "More" + add "Flow history" item

**Files:**
- Modify: `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`

- [ ] **Step 1: Read the current file to find the exact label and item layout**

Read `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx` start-to-end, then make the edits below.

- [ ] **Step 2: Rename the trigger label**

Change the trigger button content from `Share` to `More` (the literal lives at line ~105):

```tsx
<Button
  variant="ghost"
  size="md"
  className="!px-2.5 font-normal"
  data-testid="publish-button"
>
  More
  <IconComponent name="ChevronDown" className="!h-5 !w-5" />
</Button>
```

Leave `data-testid="publish-button"` unchanged to avoid breaking any e2e tests. If e2e/Cypress tests reference the literal "Share" text, update them in the same edit.

- [ ] **Step 3: Add drawer state and import**

At the top of the component file, add:

```tsx
import FlowAuditDrawer from "./flow-audit-drawer";
```

Inside the component body, near other `useState` hooks (search for `setOpenApiModal`):

```tsx
const [openAuditDrawer, setOpenAuditDrawer] = useState(false);
```

- [ ] **Step 4: Add the "Flow history" dropdown item**

Add this `DropdownMenuItem` between the existing "Export" and "Save as Template" items (or wherever it reads naturally — placement is not load-bearing):

```tsx
<DropdownMenuItem
  className="deploy-dropdown-item group"
  onClick={() => setOpenAuditDrawer(true)}
  data-testid="flow-history-item"
>
  <IconComponent name="History" className="icon-size mr-2" />
  <span>Flow history</span>
</DropdownMenuItem>
```

- [ ] **Step 5: Mount the drawer at the bottom of the component's JSX**

Just before the component's closing tag (next to the other modal renders), add:

```tsx
<FlowAuditDrawer
  flowId={currentFlowId}
  open={openAuditDrawer}
  onClose={() => setOpenAuditDrawer(false)}
/>
```

`currentFlowId` should already be available in this component (the API/Export modals use a flow id). If the variable name differs (e.g. `flow.id`, `flowId`), use whatever name the existing modals use.

- [ ] **Step 6: Type-check + run frontend tests touching this component**

Run:
```
cd src/frontend && npx tsc --noEmit
cd src/frontend && npx jest src/components/core/flowToolbarComponent
```
Expected: PASS. If any test asserts the literal "Share", update it to "More" in the same change.

- [ ] **Step 7: Commit (ASK FIRST per user policy)**

```bash
git add src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx
git commit -m "feat(flow-toolbar): rename Share→More and add Flow history entry"
```

---

## Task 6: Manual verification in the browser

Type-checking and Jest cover code correctness; this step covers feature correctness.

- [ ] **Step 1: Start the backend and frontend dev servers**

Use whatever the project's standard dev commands are (check `package.json` and `Makefile` / `pyproject.toml`). Confirm both are running.

- [ ] **Step 2: Verify the per-flow audit drawer**

1. Open an existing flow in the editor.
2. Confirm the top-right dropdown trigger reads **More** (not "Share").
3. Open the dropdown and click **Flow history**.
4. Confirm the drawer slides in from the right and lists at least one entry (the flow's most recent update). Verify time, actor email, and a sensible summary render.
5. Click an entry to expand the diff JSON; click again to collapse.
6. Close the drawer with the X button.

- [ ] **Step 3: Verify the per-flow endpoint authz**

Sign in as a user who is *not* a member of the flow's org and confirm the dropdown either hides "Flow history" or that opening it surfaces an error state cleanly (don't leave a 403 echoing as a stack trace).

- [ ] **Step 4: Smoke-test the org-scoped endpoint via curl**

Even though there's no UI yet, confirm the endpoint works:

```bash
curl -H "Authorization: Bearer $ORG_ADMIN_TOKEN" \
  http://localhost:7860/api/v1/orgs/$ORG_ID/audit-logs?size=5
```

Expected: 200 with audit entries scoped to that org.

- [ ] **Step 5: Note any UI regressions**

Confirm the other dropdown items (API access, Export, Save as Template, MCP Server, Shareable Playground) still work after the rename. Briefly open each.

---

## Follow-ups (out of scope for this plan)

- **Extract audit-log schemas to `services/audit/schemas.py`.** `AuditLogListResponse` and `AuditLogRead` now live in `api/v1/admin/audit_logs.py` but are imported by both `api/v1/flows.py` (Task 1) and `api/v1/audit_logs.py` (Task 2). That inverts the dependency direction (non-admin modules reaching into `admin/`). Lifting the schemas to `services/audit/schemas.py` straightens the graph and creates a natural home for a `query_audit_logs(...)` helper that dedupes the 3-way-duplicated `AuditLogListResponse(items=[...], total, page, size)` assembly across all three endpoints.
- **Org-admin audit page UI.** Task 2's endpoint is callable but has no dedicated frontend. A future plan should add an `/organization/audit-logs` page that uses `GET /api/v1/orgs/{org_id}/audit-logs` and is gated on org-admin role. Likely small refactor to extract a shared `<AuditLogTable>` component reusable by both that page and the existing `AdminAuditLogsPage`.
- **Filtering controls in `FlowAuditDrawer`.** Action filter and date range are accepted by the endpoint but not exposed in the drawer UI. Add when users ask for them.
- **Pagination in `FlowAuditDrawer`.** Currently fixed at first 50 entries. Add infinite scroll or page controls if flows accumulate enough audit history to need it.
