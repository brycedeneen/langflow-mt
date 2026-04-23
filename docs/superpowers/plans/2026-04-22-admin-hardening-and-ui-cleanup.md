# Admin Hardening & UI Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-04-22-admin-hardening-and-ui-cleanup-design.md`

**Goal:** Restrict the component "Code" editor — both the UI affordances and the backend endpoints that accept raw Python code — to platform super admins, and delete the Share → Embed link + every piece of dead code it holds up.

**Architecture:** Two independent surfaces. (1) Backend: add `get_current_active_superuser` to the two existing endpoints that accept raw component Python code (`POST /custom_component` and `POST /custom_component/update`). (2) Frontend: tighten the role gate on the Code button from "org admin OR superuser" to superuser-only in two render sites (`nodeToolbarComponent/index.tsx`, `InspectionPanel/components/InspectionPanelHeader.tsx`), then delete the Embed menu item, `EmbedModal`, `get-widget-code`, the `getWidgetCode` entry in `types/tweaks`, and the `ENABLE_WIDGET` feature flag.

**Tech Stack:** FastAPI + SQLModel (backend), Jest + React (frontend), pytest + `httpx.AsyncClient` (backend tests).

---

## File Structure

**Backend — modify:**
- `src/backend/base/langflow/api/v1/endpoints.py` — swap `CurrentActiveUser` → `get_current_active_superuser` on two endpoints (lines 1135-1137 and 1156-1159).
- `src/backend/tests/unit/api/v1/test_endpoints.py` — two existing tests (`test_update_component_outputs`, `test_update_component_model_name_options`) use the plain `logged_in_headers` fixture; they'll need to switch to `logged_in_headers_super_user` and gain two new negative-case tests (403 for non-super).

**Frontend — create:**
- `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/can-view-code-button.ts` — tiny pure helper: `canViewCodeButton(hasCode, isSuperuser)`. Extracted so we can unit-test the tightened rule without rendering the full toolbar.
- `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts`.

**Frontend — modify:**
- `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx` — line 115-127: drop `isAdmin` from the `useAuthStore` selector and replace the `canViewCode` line with a call to the new helper.
- `src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelHeader.tsx` — line 30-57, 198-212: read `is_superuser` from `useAuthStore`; gate the `CodeAreaModal` render on superuser; the unused `handleOpenCode` callback gets the same gate for defense-in-depth.
- `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx` — remove the `ENABLE_WIDGET` import (line 20), the `openEmbedModal` state (line 45), the menu item block (lines 161-169), and the `<EmbedModal>` render + import (line 23, lines 235-243).
- `src/frontend/src/customization/feature-flags.ts` — delete line 13 (`export const ENABLE_WIDGET = true;`).
- `src/frontend/src/types/tweaks/index.ts` — delete line 7 (`getWidgetCode?: (GetCodeType) => string;`).

**Frontend — delete:**
- `src/frontend/src/modals/EmbedModal/embed-modal.tsx`
- `src/frontend/src/modals/apiModal/utils/get-widget-code.tsx`
- `src/frontend/src/modals/apiModal/utils/__tests__/get-widget-code.test.ts`

---

## Task 0: Audit — confirm coverage of Python-code-accepting endpoints

Already done during planning. Findings:

- **Two** endpoints accept raw Python component code: `POST /custom_component` (endpoints.py:1134) and `POST /custom_component/update` (endpoints.py:1156). Both take `CustomComponentRequest.code: str` and instantiate `Component(_code=raw_code.code)`.
- **Two** frontend render sites: `nodeToolbarComponent/index.tsx:522-533` (the toolbar Code button) and `InspectionPanelHeader.tsx:198-212` (the `CodeAreaModal` render — wired via the `handleOpenCode` callback; appears unused today but guard it anyway).
- **`ENABLE_WIDGET`** is referenced only in `feature-flags.ts:13` and `deploy-dropdown.tsx:20,161`.
- **`getWidgetCode`** is imported only by `embed-modal.tsx:11`. The `GetCodeType` type is shared with other api-code utilities (curl, python, js) and must stay.
- **Backend fixtures:** `logged_in_headers` authenticates a non-super user (`active_user`, defaults `is_superuser=False`). `logged_in_headers_super_user` authenticates `active_super_user` which has `is_superuser=True`. The fork's `get_current_active_superuser` (in `langflow.services.auth.utils`) checks `is_superuser` — matches the frontend `userData?.is_superuser` gate. Use `get_current_active_superuser`, not `require_platform_admin` (which checks the distinct `is_platform_admin` field).

No further audit required. Proceed to Task 1.

---

## Task 1: Backend — write the failing test for P0-1 (`/custom_component/update`)

**Files:**
- Test: `src/backend/tests/unit/api/v1/test_endpoints.py` (add a new test alongside the existing ones).

- [ ] **Step 1: Write the failing test**

Append to the bottom of `src/backend/tests/unit/api/v1/test_endpoints.py` (it can live after `test_update_component_model_name_options`):

```python
async def test_update_component_requires_superuser(
    client: AsyncClient, logged_in_headers: dict
):
    """Non-superuser users get 403 from POST /custom_component/update."""
    path = Path(__file__).parent.parent.parent.parent / "data" / "dynamic_output_component.py"
    code = await path.read_text(encoding="utf-8")
    frontend_node: dict[str, Any] = {"outputs": []}
    request = UpdateCustomComponentRequest(
        code=code,
        frontend_node=frontend_node,
        field="show_output",
        field_value=True,
        template={},
    )

    response = await client.post(
        "api/v1/custom_component/update",
        json=request.model_dump(),
        headers=logged_in_headers,  # plain non-super user
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN, response.text


async def test_custom_component_build_requires_superuser(
    client: AsyncClient, logged_in_headers: dict
):
    """Non-superuser users get 403 from POST /custom_component."""
    path = Path(__file__).parent.parent.parent.parent / "data" / "dynamic_output_component.py"
    code = await path.read_text(encoding="utf-8")
    request = CustomComponentRequest(code=code, frontend_node=None)

    response = await client.post(
        "api/v1/custom_component",
        json=request.model_dump(),
        headers=logged_in_headers,  # plain non-super user
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN, response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_endpoints.py::test_update_component_requires_superuser tests/unit/api/v1/test_endpoints.py::test_custom_component_build_requires_superuser -v`

Expected: both tests FAIL with `AssertionError: assert 200 == 403` (non-super users currently get through).

Do **not** commit yet.

---

## Task 2: Backend — add superuser gate on both endpoints

**Files:**
- Modify: `src/backend/base/langflow/api/v1/endpoints.py:1128-1160`

- [ ] **Step 1: Add the import and the dependency**

At the top of `src/backend/base/langflow/api/v1/endpoints.py`, find the existing `from langflow.services.auth.utils import …` line (it already imports `get_current_active_user`) and add `get_current_active_superuser` to the same import:

Before:
```python
from langflow.services.auth.utils import get_current_active_user
```

After:
```python
from langflow.services.auth.utils import get_current_active_superuser, get_current_active_user
```

*(If the existing import line doesn't exist because `CurrentActiveUser` is imported from `langflow.api.utils.core`, instead add the new import next to that one.)*

Confirm with:

Run: `grep -n "get_current_active_superuser" src/backend/base/langflow/api/v1/endpoints.py`

Expected output includes a line with the import and later the two `Depends(...)` usages.

- [ ] **Step 2: Swap the dependency on `POST /custom_component`**

In `endpoints.py`, replace lines 1134-1137:

Before:
```python
@router.post("/custom_component", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component(
    raw_code: CustomComponentRequest,
    user: CurrentActiveUser,
) -> CustomComponentResponse:
```

After:
```python
@router.post("/custom_component", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component(
    raw_code: CustomComponentRequest,
    user: User = Depends(get_current_active_superuser),
) -> CustomComponentResponse:
```

If `User` and `Depends` are not already imported at the top of the file, add them (they are likely already present; check with `grep -n "from fastapi import" src/backend/base/langflow/api/v1/endpoints.py` and `grep -n "from langflow.services.database.models.user" src/backend/base/langflow/api/v1/endpoints.py`).

- [ ] **Step 3: Swap the dependency on `POST /custom_component/update`**

Same file, replace lines 1156-1160:

Before:
```python
@router.post("/custom_component/update", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: CurrentActiveUser,
):
```

After:
```python
@router.post("/custom_component/update", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: User = Depends(get_current_active_superuser),
):
```

- [ ] **Step 4: Run the failing tests — expect pass**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_endpoints.py::test_update_component_requires_superuser tests/unit/api/v1/test_endpoints.py::test_custom_component_build_requires_superuser -v`

Expected: both PASS.

- [ ] **Step 5: Fix the two existing tests that previously used `logged_in_headers`**

The existing `test_update_component_outputs` (around line 37) and `test_update_component_model_name_options` (around line 57) both call `POST /custom_component/update` with `logged_in_headers` (non-super). They will now fail with 403. Switch them to use `logged_in_headers_super_user`:

In `test_update_component_outputs`, replace the function signature and the header argument:

Before:
```python
async def test_update_component_outputs(client: AsyncClient, logged_in_headers: dict):
    # ...
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers)
```

After:
```python
async def test_update_component_outputs(client: AsyncClient, logged_in_headers_super_user: dict):
    # ...
    response = await client.post("api/v1/custom_component/update", json=request.model_dump(), headers=logged_in_headers_super_user)
```

Apply the same change to `test_update_component_model_name_options` (both the signature and the single `headers=logged_in_headers` call).

- [ ] **Step 6: Run the full endpoints test module**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_endpoints.py -v`

Expected: all PASS (the two new negative tests, the two existing tests on the super fixture, plus the rest of the module).

- [ ] **Step 7: Commit**

```bash
git add src/backend/base/langflow/api/v1/endpoints.py src/backend/tests/unit/api/v1/test_endpoints.py
git commit -m "feat(api): require superuser for custom component endpoints

POST /custom_component and POST /custom_component/update execute arbitrary
Python. Gate both on get_current_active_superuser so only platform super
admins can update component code. Add negative tests for 403, switch the
two existing update-flow tests to the superuser fixture.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Remember:** do not commit without explicit user approval if that rule is in effect. Ask first.

---

## Task 3: Frontend — extract `canViewCodeButton` helper with failing test

**Files:**
- Create: `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/can-view-code-button.ts`
- Create: `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts`:

```typescript
import { canViewCodeButton } from "../can-view-code-button";

describe("canViewCodeButton", () => {
  it("returns false when the component has no code field", () => {
    expect(canViewCodeButton({ hasCode: false, isSuperuser: true })).toBe(false);
  });

  it("returns false for a non-superuser even if the component has code", () => {
    expect(canViewCodeButton({ hasCode: true, isSuperuser: false })).toBe(false);
  });

  it("returns true for a superuser on a component with code", () => {
    expect(canViewCodeButton({ hasCode: true, isSuperuser: true })).toBe(true);
  });

  it("ignores an undefined superuser flag (treated as non-super)", () => {
    expect(canViewCodeButton({ hasCode: true, isSuperuser: undefined })).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd src/frontend && npx jest src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts`

Expected: FAIL with "Cannot find module '../can-view-code-button'".

- [ ] **Step 3: Write the helper**

Create `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/can-view-code-button.ts`:

```typescript
export type CanViewCodeButtonInput = {
  hasCode: boolean;
  isSuperuser: boolean | undefined;
};

export function canViewCodeButton({
  hasCode,
  isSuperuser,
}: CanViewCodeButtonInput): boolean {
  return hasCode && isSuperuser === true;
}
```

- [ ] **Step 4: Run the test — expect pass**

Run: `cd src/frontend && npx jest src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts`

Expected: all 4 tests PASS.

---

## Task 4: Frontend — wire `canViewCodeButton` into `nodeToolbarComponent/index.tsx`

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx:115-127`

- [ ] **Step 1: Add the helper import**

Near the other relative imports at the top of `nodeToolbarComponent/index.tsx`, add:

```typescript
import { canViewCodeButton } from "./utils/can-view-code-button";
```

- [ ] **Step 2: Drop `isAdmin` from the store selector and replace the `canViewCode` line**

Replace lines 115-127:

Before:
```typescript
const { isAdmin, userData } = useAuthStore(
  useShallow((state) => ({
    isAdmin: state.isAdmin,
    userData: state.userData,
  })),
);

const nodeLength = useMemo(() => getNodeLength(data), [data]);
const hasCode = useMemo(
  () => Object.keys(data.node!.template).includes("code"),
  [data.node],
);
const canViewCode = hasCode && (isAdmin || !!userData?.is_superuser);
```

After:
```typescript
const userData = useAuthStore((state) => state.userData);

const nodeLength = useMemo(() => getNodeLength(data), [data]);
const hasCode = useMemo(
  () => Object.keys(data.node!.template).includes("code"),
  [data.node],
);
const canViewCode = useMemo(
  () => canViewCodeButton({ hasCode, isSuperuser: userData?.is_superuser }),
  [hasCode, userData?.is_superuser],
);
```

Note: since there's only one value left, the `useShallow` wrapper is unnecessary — a plain selector avoids the memoization overhead.

- [ ] **Step 3: Verify `useShallow` is still referenced in the file**

Run: `grep -n "useShallow" src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx`

If no matches remain, remove the `import { useShallow } from "zustand/react/shallow";` line (or equivalent). If matches remain, leave the import alone.

- [ ] **Step 4: Type-check & run the helper's tests**

Run: `cd src/frontend && npx jest src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts`

Expected: PASS.

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors in the modified file.

---

## Task 5: Frontend — gate the `CodeAreaModal` in `InspectionPanelHeader`

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelHeader.tsx:30-57, 198-212`

- [ ] **Step 1: Add the auth store import and superuser read**

At the top of `InspectionPanelHeader.tsx`, next to the existing store imports (around line 12), add:

```typescript
import useAuthStore from "@/stores/authStore";
```

Inside the component body, immediately after the existing hook calls (around line 30, just after `const [openCodeModal, setOpenCodeModal] = useState(false);`), add:

```typescript
const isSuperuser =
  useAuthStore((state) => state.userData?.is_superuser) === true;
```

- [ ] **Step 2: Tighten the `handleOpenCode` callback**

Replace lines 53-57:

Before:
```typescript
const handleOpenCode = useCallback(() => {
  if (hasCode) {
    setOpenCodeModal(true);
  }
}, [hasCode]);
```

After:
```typescript
const handleOpenCode = useCallback(() => {
  if (hasCode && isSuperuser) {
    setOpenCodeModal(true);
  }
}, [hasCode, isSuperuser]);
```

- [ ] **Step 3: Tighten the `CodeAreaModal` render gate**

Replace the conditional around line 198:

Before:
```typescript
{hasCode && openCodeModal && (
```

After:
```typescript
{hasCode && openCodeModal && isSuperuser && (
```

- [ ] **Step 4: Type-check**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no new errors.

---

## Task 6: Frontend — commit the Code-button tightening

- [ ] **Step 1: Stage and commit**

```bash
git add \
  src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/can-view-code-button.ts \
  src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/utils/__tests__/can-view-code-button.test.ts \
  src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx \
  src/frontend/src/pages/FlowPage/components/InspectionPanel/components/InspectionPanelHeader.tsx

git commit -m "feat(ui): restrict component Code editor to superusers

Tighten the Code-button gate from (orgAdmin OR superuser) to superuser
only. Extract the predicate into canViewCodeButton so the rule is
unit-tested, and apply the same gate to the InspectionPanel's
CodeAreaModal render path for defense-in-depth.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause and confirm with the user before running this commit if the no-commit-without-permission rule is active.**

---

## Task 7: Frontend — remove Share → Embed menu item

**Files:**
- Modify: `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`

- [ ] **Step 1: Remove the `ENABLE_WIDGET` import**

Replace line 20:

Before:
```typescript
import { ENABLE_PUBLISH, ENABLE_WIDGET } from "@/customization/feature-flags";
```

After:
```typescript
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
```

- [ ] **Step 2: Remove the `EmbedModal` import**

Delete line 23:

```typescript
import EmbedModal from "@/modals/EmbedModal/embed-modal";
```

- [ ] **Step 3: Remove the `openEmbedModal` state**

Delete line 45:

```typescript
const [openEmbedModal, setOpenEmbedModal] = useState(false);
```

- [ ] **Step 4: Remove the menu item block**

Delete lines 161-169 (the `{ENABLE_WIDGET && (…)}` block):

```typescript
{ENABLE_WIDGET && (
  <DropdownMenuItem
    onClick={() => setOpenEmbedModal(true)}
    className="deploy-dropdown-item group"
  >
    <IconComponent name="Columns2" className={`icon-size mr-2`} />
    <span>Embed into site</span>
  </DropdownMenuItem>
)}
```

- [ ] **Step 5: Remove the `<EmbedModal>` render**

Delete lines 235-243 (the `<EmbedModal … />` block):

```typescript
<EmbedModal
  open={openEmbedModal}
  setOpen={setOpenEmbedModal}
  flowId={flowId ?? ""}
  flowName={flowName ?? ""}
  isAuth={isAuth}
  tweaksBuildedObject={{}}
  activeTweaks={false}
></EmbedModal>
```

- [ ] **Step 6: Check whether `isAuth` is still referenced**

Run: `grep -n "isAuth" src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`

If no matches remain besides the `const isAuth = useAuthStore(...)` declaration (around line 57), delete the declaration and the `useAuthStore` import if it has no other reference. If any match remains, leave everything alone.

- [ ] **Step 7: Verify the file still compiles**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors in `deploy-dropdown.tsx`.

---

## Task 8: Frontend — delete `EmbedModal`, `get-widget-code`, and test

**Files:**
- Delete: `src/frontend/src/modals/EmbedModal/embed-modal.tsx`
- Delete: `src/frontend/src/modals/apiModal/utils/get-widget-code.tsx`
- Delete: `src/frontend/src/modals/apiModal/utils/__tests__/get-widget-code.test.ts`
- Modify: `src/frontend/src/types/tweaks/index.ts:7`

- [ ] **Step 1: Delete the three files**

```bash
rm src/frontend/src/modals/EmbedModal/embed-modal.tsx
rmdir src/frontend/src/modals/EmbedModal
rm src/frontend/src/modals/apiModal/utils/get-widget-code.tsx
rm src/frontend/src/modals/apiModal/utils/__tests__/get-widget-code.test.ts
```

If `rmdir` fails, it means the directory has other files — `ls src/frontend/src/modals/EmbedModal/` to investigate, then remove what's orphaned.

- [ ] **Step 2: Remove `getWidgetCode` from `GetCodeType` consumers**

Open `src/frontend/src/types/tweaks/index.ts` and delete the `getWidgetCode` line (line 7):

Before:
```typescript
  getWidgetCode?: (GetCodeType) => string;
```

After:
*(line removed)*

Leave the other `get*Code` entries intact; `GetCodeType` itself stays.

- [ ] **Step 3: Ensure nothing else imports the removed modules**

Run: `grep -rn "get-widget-code\|EmbedModal\|getWidgetCode\|embed-modal" src/frontend/src`

Expected: no results (zero hits).

- [ ] **Step 4: Type-check**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors.

---

## Task 9: Frontend — remove the `ENABLE_WIDGET` feature flag

**Files:**
- Modify: `src/frontend/src/customization/feature-flags.ts:13`

- [ ] **Step 1: Delete the flag**

Open `src/frontend/src/customization/feature-flags.ts` and delete line 13:

Before:
```typescript
export const ENABLE_WIDGET = true;
```

After:
*(line removed)*

- [ ] **Step 2: Confirm no residual references**

Run: `grep -rn "ENABLE_WIDGET" src/frontend/src`

Expected: no results.

- [ ] **Step 3: Type-check**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json`

Expected: no errors.

---

## Task 10: Frontend — commit the Embed removal

- [ ] **Step 1: Stage and commit**

```bash
git add \
  src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx \
  src/frontend/src/customization/feature-flags.ts \
  src/frontend/src/types/tweaks/index.ts

git add -u src/frontend/src/modals/EmbedModal/ \
  src/frontend/src/modals/apiModal/utils/get-widget-code.tsx \
  src/frontend/src/modals/apiModal/utils/__tests__/get-widget-code.test.ts

git commit -m "refactor(ui): remove Share → Embed link + widget embed support

Remove the 'Embed into site' menu item, the EmbedModal component, the
getWidgetCode utility + test, the getWidgetCode entry in GetCodeType,
and the now-unused ENABLE_WIDGET feature flag. Chat-widget embed is
not a supported deployment model; the broader builder-embed story will
be reintroduced as a separate project.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**Pause and confirm with the user before running this commit if the no-commit-without-permission rule is active.**

---

## Task 11: Full verification pass

- [ ] **Step 1: Run the full frontend test suite**

Run: `cd src/frontend && npm test`

Expected: all PASS. No "Cannot find module" errors for the deleted files.

- [ ] **Step 2: Run the full frontend lint + type-check**

Run: `cd src/frontend && npx tsc --noEmit --pretty --project tsconfig.json && npx @biomejs/biome check --diagnostic-level=error`

Expected: exit 0.

- [ ] **Step 3: Run the focused backend tests**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_endpoints.py -v`

Expected: all PASS.

- [ ] **Step 4: Manual smoke test checklist**

Start the backend + frontend dev servers. Then, as each role:

| Role | Expected on a component with a `code` field |
|---|---|
| Regular member | No Code button in toolbar. No CodeAreaModal from InspectionPanel. |
| Org admin | No Code button (tightened — was visible before this change). |
| Super admin | Code button visible; opens modal; save persists. |

For each role, open the Share menu on a flow:

| Role | Expected |
|---|---|
| Any | No "Embed into site" option. |

Direct API test with a non-super session token:

```
POST /api/v1/custom_component       → 403
POST /api/v1/custom_component/update → 403
```

With a super session token:

```
POST /api/v1/custom_component       → 200
POST /api/v1/custom_component/update → 200
```

If anything diverges, stop and investigate before calling this plan done.

---

## Self-review notes

1. **Spec coverage:**
   - P0-1 frontend gate → Tasks 3, 4, 5, 6.
   - P0-1 backend gate (both endpoints) → Tasks 1, 2.
   - P0-1 research for other Python-code endpoints → Task 0 (done during planning; documented).
   - P0-2 menu removal → Task 7.
   - P0-2 orphan cleanup (EmbedModal, get-widget-code, types/tweaks entry, ENABLE_WIDGET) → Tasks 8, 9.
   - Commits — three logical commits: backend, Code-button tightening, Embed removal.

2. **Placeholder scan:** no TBDs or "add error handling" stubs. Each code block is complete.

3. **Type consistency:** `canViewCodeButton` signature matches between the helper file, the test file, and the `index.tsx` call site (`{ hasCode, isSuperuser }` object input).

4. **Risks captured in the spec:**
   - Existing org admins lose Code access silently — intended.
   - Safety check for `/custom_component/update` in the hot path — confirmed by inspection: it's edit-only (no flow-load codepath invokes it; only the custom component editor and model-field reactions do).

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-04-22-admin-hardening-and-ui-cleanup.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using the executing-plans skill, batch execution with checkpoints.

**Which approach?**
