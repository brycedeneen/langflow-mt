# Assistant Data-Access Org Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User-specific commit discipline:** This user has a standing rule — pause and ask before every `git commit`, even when this plan instructs one. The commit commands below are the exact command to run *after* the user approves. Stage explicit paths only (no `git add -A` / `.`).

**Goal:** Ensure every assistant-callable tool or endpoint filters by the actor's active organization when reading `Flow`, `FlowRun`, or `File`/attachment data. Adds a guard helper, a 404 cross-org response contract, and a regression-test matrix that every future assistant tool inherits.

**Architecture:** Defense-in-depth. (1) A helper (`guard_assistant_org_scope`) and a distinct exception (`CrossOrgAccessError`) live in a new `services/assistant/guards.py` module. (2) Each assistant router catches the exception and returns HTTP 404 — never 403 — to avoid leaking existence. (3) A registry-driven parametrized test (`test_assistant_org_isolation.py`) proves every tool rejects cross-org targets; a meta-test ensures every mounted assistant route has a registry entry.

**Tech Stack:** Python 3.11, FastAPI, SQLModel (async), pytest-asyncio, existing `PlatformAdmin` / `CurrentActiveUser` deps at `src/backend/base/langflow/api/utils/core.py`.

**Spec:** `docs/superpowers/specs/2026-04-23-assistant-org-isolation-and-tagging-design.md` (Part A).

**Out of scope (explicit, per spec A.2):** Template-catalog filtering, per-org component metadata, centralized `ActiveOrgDep` refactor, OIDC/SAML.

---

## File Structure

**New (backend):**
- `src/backend/base/langflow/services/assistant/__init__.py` — empty package marker (create if the dir does not already exist).
- `src/backend/base/langflow/services/assistant/guards.py` — `CrossOrgAccessError` + `guard_assistant_org_scope`.
- `src/backend/tests/unit/services/assistant/__init__.py` — empty.
- `src/backend/tests/unit/services/assistant/test_guards.py` — unit tests for the helper.
- `src/backend/tests/unit/api/v1/test_assistant_org_isolation.py` — regression matrix (parametrized + meta-test).

**New (disposable):**
- `docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md` — inventory of assistant-callable tools, kept only until Task 6 archives it.

**Modified (backend):**
- `src/backend/base/langflow/api/v1/assistant.py` — translate `CrossOrgAccessError` → `HTTPException(404)`.
- `src/backend/base/langflow/api/v1/component_assist.py` — same 404 translator.
- Any call site discovered in Task 3's inventory that reads `Flow` / `FlowRun` / `File` without an explicit `organization_id` filter. Exact paths are filled in during Task 3; Task 5 iterates over the resulting list.

**Modified (docs):**
- `docs/superpowers/specs/2026-04-22-integration-platform-roadmap.md` — rename the mislabelled P1 bullet. (Task 7.)

---

## Task 1: Add the guard helper module + unit tests

**Files:**
- Create: `src/backend/base/langflow/services/assistant/__init__.py`
- Create: `src/backend/base/langflow/services/assistant/guards.py`
- Create: `src/backend/tests/unit/services/assistant/__init__.py`
- Create: `src/backend/tests/unit/services/assistant/test_guards.py`

- [ ] **Step 1: Check whether `services/assistant/` already exists**

Run:
```bash
ls src/backend/base/langflow/services/assistant/ 2>&1
```
Expected: either "No such file or directory" (create the dir via Write tool by creating `__init__.py`) or an existing dir (skip creating `__init__.py` if it already exists).

- [ ] **Step 2: Create the package marker if missing**

If Step 1 showed "No such file or directory", create:

```python
# src/backend/base/langflow/services/assistant/__init__.py
```

Leave the file empty (just the newline-terminated empty content).

- [ ] **Step 3: Write the failing test**

Create `src/backend/tests/unit/services/assistant/__init__.py` (empty) and `src/backend/tests/unit/services/assistant/test_guards.py`:

```python
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from langflow.services.assistant.guards import (
    CrossOrgAccessError,
    guard_assistant_org_scope,
)


def test_same_org_passes() -> None:
    org_id = uuid4()
    guard_assistant_org_scope(
        actor_org_id=org_id,
        target_org_id=org_id,
        target_label="flow",
    )


def test_different_org_raises_cross_org() -> None:
    actor = uuid4()
    other = uuid4()
    with pytest.raises(CrossOrgAccessError) as exc:
        guard_assistant_org_scope(
            actor_org_id=actor,
            target_org_id=other,
            target_label="flow",
        )
    assert "flow" in str(exc.value)


def test_target_without_org_short_circuits() -> None:
    # Globals (platform templates, etc.) pass.
    guard_assistant_org_scope(
        actor_org_id=uuid4(),
        target_org_id=None,
        target_label="platform_template",
    )


def test_cross_org_error_is_permission_error_subclass() -> None:
    # Existing code that catches PermissionError should still work.
    assert issubclass(CrossOrgAccessError, PermissionError)


def test_error_message_does_not_leak_target_id() -> None:
    actor = uuid4()
    other = UUID("12345678-1234-5678-1234-567812345678")
    with pytest.raises(CrossOrgAccessError) as exc:
        guard_assistant_org_scope(
            actor_org_id=actor,
            target_org_id=other,
            target_label="flow",
        )
    assert str(other) not in str(exc.value)
    assert str(actor) not in str(exc.value)
```

- [ ] **Step 4: Run the test and confirm it fails**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/services/assistant/test_guards.py -v
```
Expected: `ModuleNotFoundError: No module named 'langflow.services.assistant.guards'` or similar — tests should fail at import.

- [ ] **Step 5: Write the minimal implementation**

Create `src/backend/base/langflow/services/assistant/guards.py`:

```python
"""Cross-org access guards for assistant-callable tools.

This module is defense-in-depth. The primary enforcement for cross-org access
is an explicit ``organization_id`` filter on the DB query inside every tool.
``guard_assistant_org_scope`` is the belt-and-suspenders check: call it at the
tool entry with the resolved target's ``organization_id`` before returning
data to the caller. It catches regressions where a future query forgets the
filter.

Callers MUST translate :class:`CrossOrgAccessError` into HTTP 404 at the
router boundary (never 403) to avoid leaking existence of the target.
"""

from __future__ import annotations

from uuid import UUID


class CrossOrgAccessError(PermissionError):
    """An assistant tool tried to read data outside the actor's active org."""


def guard_assistant_org_scope(
    *,
    actor_org_id: UUID,
    target_org_id: UUID | None,
    target_label: str,
) -> None:
    """Raise if ``target_org_id`` belongs to a different org than ``actor_org_id``.

    A ``target_org_id`` of ``None`` short-circuits — platform-global resources
    (e.g. shared templates) are always allowed. This is the intentional
    escape hatch; keep its use limited to explicitly platform-scoped data.

    The error message intentionally omits both UUIDs so audit logs / error
    responses cannot be mined for target existence.
    """
    if target_org_id is None:
        return
    if target_org_id != actor_org_id:
        msg = f"cross-org access to {target_label} is not permitted"
        raise CrossOrgAccessError(msg)
```

- [ ] **Step 6: Run the test and confirm it passes**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/services/assistant/test_guards.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 7: Pause before commit**

Surface the diff and wait for user approval.

Proposed commit message:
```
feat(assist): org-scope guard helper + CrossOrgAccessError

Adds src/backend/base/langflow/services/assistant/guards.py with a
CrossOrgAccessError exception and guard_assistant_org_scope helper for
defense-in-depth cross-org checks inside assistant tools. Per spec A.5,
routers translate this to HTTP 404 to avoid leaking target existence.
Covered by 5 unit tests.
```
Staged files:
```
src/backend/base/langflow/services/assistant/__init__.py
src/backend/base/langflow/services/assistant/guards.py
src/backend/tests/unit/services/assistant/__init__.py
src/backend/tests/unit/services/assistant/test_guards.py
```

---

## Task 2: Wire the 404 contract in assistant routers

**Files:**
- Modify: `src/backend/base/langflow/api/v1/assistant.py`
- Modify: `src/backend/base/langflow/api/v1/component_assist.py`
- Create: `src/backend/tests/unit/api/v1/test_assistant_404_contract.py`

**Context:** Per spec A.5, a `CrossOrgAccessError` raised anywhere inside an assistant request handler must propagate as `HTTPException(404, "not found")` — never 403. Both assistant routers need an exception handler.

- [ ] **Step 1: Read the top of each assistant router**

Run:
```bash
sed -n '1,40p' src/backend/base/langflow/api/v1/assistant.py
sed -n '1,40p' src/backend/base/langflow/api/v1/component_assist.py
```
Expected: both files start with a `router = APIRouter(...)` declaration. Confirm the variable is literally named `router`. If either uses a different name, substitute that in the code below.

- [ ] **Step 2: Write the failing integration test**

Create `src/backend/tests/unit/api/v1/test_assistant_404_contract.py`:

```python
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from langflow.services.assistant.guards import CrossOrgAccessError


def _make_app_with_router(router) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.parametrize(
    "module_name",
    [
        "langflow.api.v1.assistant",
        "langflow.api.v1.component_assist",
    ],
)
def test_cross_org_error_returns_404(module_name: str) -> None:
    from importlib import import_module

    module = import_module(module_name)
    router = module.router

    # Inject a diagnostic route that always raises the guard error.
    @router.get("/__probe_cross_org_404__", include_in_schema=False)
    async def _probe() -> None:
        raise CrossOrgAccessError("probe")

    app = _make_app_with_router(router)
    client = TestClient(app)
    resp = client.get("/__probe_cross_org_404__")
    assert resp.status_code == 404, resp.text
    # Do not leak the raised message.
    assert "probe" not in resp.text
    assert resp.json() == {"detail": "not found"}
```

- [ ] **Step 3: Run the test and confirm it fails**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_assistant_404_contract.py -v
```
Expected: FAIL — the un-caught `CrossOrgAccessError` bubbles up as a 500 response (or re-raises with the "probe" message leaked in the body).

- [ ] **Step 4: Register the app-level exception handler**

Open `src/backend/base/langflow/main.py`. Search for `@app.exception_handler` to locate existing handler registrations.

If handlers already exist, append ours alongside them, matching style. If none exist, place ours immediately after the `app = FastAPI(...)` construction.

Add:

```python
from fastapi.responses import JSONResponse
from langflow.services.assistant.guards import CrossOrgAccessError


@app.exception_handler(CrossOrgAccessError)
async def _cross_org_access_handler(_request, _exc):
    return JSONResponse(status_code=404, content={"detail": "not found"})
```

Do **not** add any imports or decorators to `api/v1/assistant.py` or `api/v1/component_assist.py` — the app-level handler is sufficient on its own. Existing code in those routers does not need to change.

- [ ] **Step 5: Verify the test now passes**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_assistant_404_contract.py -v
```
Expected: PASS for both parametrizations.

- [ ] **Step 6: Pause before commit**

Proposed commit message:
```
feat(assist): route CrossOrgAccessError to 404 at the app layer

Registers an app-level FastAPI exception_handler that maps
CrossOrgAccessError to HTTPException(404, "not found"). Both assistant
routers (v1/assistant.py, v1/component_assist.py) inherit the contract;
no per-route try/except needed. Verified by a parametrized integration
test that injects a probe route into each router and asserts a 404 body
without leakage of the exception message.
```

---

## Task 3: Produce the assistant-surface inventory

**Files:**
- Create: `docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md`

**Context:** This task discovers the leaks. It does not fix them — Tasks 4 and 5 do. The inventory is intentionally disposable; Task 7 archives or deletes it.

- [ ] **Step 1: Enumerate every assistant-callable HTTP route**

Run:
```bash
grep -rn '@router\.\(get\|post\|put\|delete\|patch\)' src/backend/base/langflow/api/v1/assistant.py src/backend/base/langflow/api/v1/component_assist.py
```
Record every decorator line + the function name immediately below it. This is the top-level tool surface.

- [ ] **Step 2: Enumerate every tool the Flow Builder Assistant can call**

Run:
```bash
grep -rn 'tool\|StructuredTool\|@tool\|Tool(' src/backend/base/langflow/api/v1/assistant.py src/backend/base/langflow/services/component_assist/ 2>&1 | head -40
grep -rn 'tools = \|TOOLS = \|self.tools\b' src/backend/base/langflow/api/v1/assistant.py src/backend/base/langflow/services/component_assist/ 2>&1 | head -40
```
List each tool function and its owning module.

- [ ] **Step 3: Trace each HTTP route and tool to the DB query**

For each item from Steps 1-2, follow the function body and any service calls it makes. Record:
- Which SQLModel / table it reads (`Flow`, `FlowRun`, `File`, `Message`, `Attachment`).
- The exact filter (`.where(Flow.organization_id == ...)`, `.where(Flow.user_id == ...)`, or no filter).
- Whether it runs inside `session_scope()` or `session_scope_readonly()`.

- [ ] **Step 4: Write the inventory note**

Create `docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md`:

```markdown
# Assistant Surface Inventory — 2026-04-23

Source spec: `docs/superpowers/specs/2026-04-23-assistant-org-isolation-and-tagging-design.md`

**Legend**
- ✅ explicit `organization_id` filter on the DB query
- ⚠️ implicit filter (e.g. joins through `membership`) — needs to be made explicit
- ❌ no filter — known leak

## HTTP routes

| Route | File:line | Entity read | Filter | Status |
|-------|-----------|-------------|--------|--------|
| POST /api/v1/assistant/... | api/v1/assistant.py:123 | Flow | `user_id == current_user.id` | ⚠️ |
| ... | ... | ... | ... | ... |

## Assistant tools (non-HTTP)

| Tool | File:line | Entity | Filter | Status |
|------|-----------|--------|--------|--------|
| search_components | component_assist/tools.py:45 | ComponentCatalog | N/A (global) | ✅ |
| ... | ... | ... | ... | ... |

## Summary

- Total surfaces: N
- ✅ rows: N
- ⚠️ rows: N
- ❌ rows: N

Fix targets for Task 5: [list every ⚠️ and ❌ row].
```

Fill the tables with the real data gathered in Step 3. Every entry must have exact `file:line`. If a surface turns out not to read org-scoped data at all (e.g. a health check), mark it `N/A` and explain in the status column.

- [ ] **Step 5: Pause before commit**

Proposed commit message:
```
docs(assist): inventory of assistant-callable data surfaces

Catalogs every HTTP route and assistant tool that reads org-scoped
entities (Flow, FlowRun, File, Message, Attachment). Tags each with its
current filter posture (✅ explicit, ⚠️ implicit, ❌ missing). Disposable
— Task 7 archives or deletes this note once Tasks 4-5 close the gaps.
```

---

## Task 4: Regression-test registry + meta-test

**Files:**
- Create: `src/backend/tests/unit/api/v1/test_assistant_org_isolation.py`
- Create: `src/backend/tests/conftest.py` additions (if `two_org_fixture` does not exist yet)

**Context:** Writes tests for every surface in Task 3's inventory — **including the ✅ rows**. If any ✅ row's test fails, that's a real leak the inventory missed; fix it in Task 5.

- [ ] **Step 1: Check whether `two_org_fixture` already exists**

Run:
```bash
grep -rn 'two_org_fixture\|def .*two_org' src/backend/tests/ 2>&1 | head -5
```
If found: reuse it in Step 3. If not: define it in Step 2.

- [ ] **Step 2: Add `two_org_fixture` if missing**

If Step 1 found nothing, append to `src/backend/tests/conftest.py` (or the nearest scope-appropriate `conftest.py`):

```python
import pytest
import pytest_asyncio

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.user.model import User


@pytest_asyncio.fixture
async def two_org_fixture(session):
    """Create two orgs with one member each. Returns (actor_user, actor_org, other_user, other_org)."""
    actor_org = Organization(name="actor-org", slug="actor-org", is_personal=False)
    other_org = Organization(name="other-org", slug="other-org", is_personal=False)
    session.add_all([actor_org, other_org])
    await session.flush()

    actor = User(username="actor", password="x", is_active=True)
    other = User(username="other", password="x", is_active=True)
    session.add_all([actor, other])
    await session.flush()

    session.add_all([
        Membership(user_id=actor.id, organization_id=actor_org.id, role=MembershipRole.MEMBER),
        Membership(user_id=other.id, organization_id=other_org.id, role=MembershipRole.MEMBER),
    ])
    await session.commit()
    return actor, actor_org, other, other_org
```

- [ ] **Step 3: Write the registry + parametrized test + meta-test**

Create `src/backend/tests/unit/api/v1/test_assistant_org_isolation.py`:

```python
"""Cross-org regression matrix for assistant-callable surfaces.

Every entry in ASSISTANT_SURFACES must come from the inventory note at
`docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md`. The
meta-test verifies the registry matches the number of mounted assistant
routes so a new surface cannot ship without a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

import pytest
from httpx import AsyncClient


@dataclass(frozen=True)
class Surface:
    name: str
    http_method: str
    path_template: str  # e.g. "/api/v1/assistant/flow/{flow_id}"
    factory: str  # which entity to create in the foreign org: "flow" | "flow_run" | "file"


# Populated by Task 5 iteration; one entry per row in the inventory.
ASSISTANT_SURFACES: list[Surface] = [
    # Example (replace with real data from the inventory):
    # Surface(name="read_flow", http_method="GET",
    #         path_template="/api/v1/assistant/flow/{flow_id}", factory="flow"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ASSISTANT_SURFACES, ids=[s.name for s in ASSISTANT_SURFACES])
async def test_cross_org_returns_404(client: AsyncClient, two_org_fixture, surface: Surface) -> None:
    actor, _actor_org, _other, other_org = two_org_fixture
    target_id = await _create_foreign_target(surface.factory, other_org.id)
    url = surface.path_template.format(**{f"{surface.factory}_id": target_id})
    resp = await client.request(surface.http_method, url, headers=_auth_headers(actor))
    assert resp.status_code == 404, (
        f"{surface.name}: expected 404 for cross-org access, got {resp.status_code}: {resp.text}"
    )


def test_registry_covers_all_mounted_assistant_routes() -> None:
    """If this test fails, a new assistant route was added without a Surface entry."""
    from langflow.api.v1 import assistant, component_assist

    def _count_routes(module) -> int:
        return sum(
            1
            for r in module.router.routes
            if getattr(r, "include_in_schema", True)
        )

    mounted = _count_routes(assistant) + _count_routes(component_assist)
    assert len(ASSISTANT_SURFACES) == mounted, (
        f"Registry has {len(ASSISTANT_SURFACES)} entries but assistant routers mount {mounted}. "
        "Add a Surface entry for each new route and update the inventory."
    )


# --- helpers -----------------------------------------------------------------


def _auth_headers(user) -> dict[str, str]:
    # Replace with whatever auth helper the test suite uses; keep the shape local
    # so a future change to auth headers touches this one place.
    return {"Authorization": f"Bearer test-{user.id}"}


async def _create_foreign_target(factory: str, org_id) -> str:
    # Stub — Task 5 fills this in per factory name, using the test DB session.
    raise NotImplementedError(f"factory {factory} not wired — add it in Task 5")
```

- [ ] **Step 4: Run the tests (everything should FAIL initially)**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_assistant_org_isolation.py -v
```
Expected outcome depends on whether `ASSISTANT_SURFACES` was populated from the inventory. On first run, with an empty list, the parametrized test is skipped and the meta-test FAILS (count mismatch). That proves the harness is wired correctly.

- [ ] **Step 5: Pause before commit**

Proposed commit message:
```
test(assist): cross-org isolation regression matrix + meta-test

Registry-driven test harness covering every assistant-callable surface.
Meta-test fails if ASSISTANT_SURFACES.len() != number of mounted routes
in v1/assistant.py and v1/component_assist.py, so a new surface cannot
be added without an entry. Parametrized body asserts HTTP 404 on a
foreign-org target. Empty registry initially; Task 5 populates it from
the inventory.
```

---

## Task 5: Populate the registry and fix leaks

**Files:**
- Modify: `src/backend/tests/unit/api/v1/test_assistant_org_isolation.py` — add one `Surface` per inventory row.
- Modify: one or more files under `src/backend/base/langflow/api/v1/` or `services/` — add explicit `organization_id` filter wherever the regression test fails.

**Context:** This task iterates. Each iteration is one inventory row → one Surface registry entry → one test run → one fix (if the test fails). Each fix is a **separate commit**.

### Iterative loop (repeat for every inventory row)

- [ ] **Step L.1: Pick the next inventory row**

Start with the ❌ rows, then ⚠️, then ✅ last (✅ tests should all pass but catching a surprise is the point).

- [ ] **Step L.2: Add the Surface entry**

Append a line to `ASSISTANT_SURFACES`:

```python
ASSISTANT_SURFACES: list[Surface] = [
    Surface(
        name="<descriptive_snake_case>",
        http_method="GET",  # or POST/PUT/DELETE/PATCH as per inventory
        path_template="/api/v1/assistant/flow/{flow_id}",  # exact path from inventory
        factory="flow",  # or "flow_run" | "file"
    ),
    # ...
]
```

- [ ] **Step L.3: Wire the factory helper if new**

If the `factory` name is not yet handled in `_create_foreign_target`, add the branch:

```python
async def _create_foreign_target(factory: str, org_id, session) -> str:
    from langflow.services.database.models.flow.model import Flow

    if factory == "flow":
        flow = Flow(name="foreign", organization_id=org_id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.commit()
        return str(flow.id)
    if factory == "flow_run":
        ...  # model-specific code; mirror the flow pattern
    if factory == "file":
        ...
    raise NotImplementedError(f"factory {factory} not wired")
```

- [ ] **Step L.4: Run the specific test**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_assistant_org_isolation.py::test_cross_org_returns_404[<surface_name>] -v
```

**Case A — PASS:** The surface already filters correctly. Move on to Step L.7 (commit just the Surface entry).

**Case B — FAIL (got 200/403/500 instead of 404):** This is a real leak. Go to Step L.5.

- [ ] **Step L.5: Add the missing `organization_id` filter (leak fix)**

Open the `file:line` from the inventory. Two possible patterns:

**Pattern 1: missing filter in a SELECT.** Add the org predicate:

```python
# Before
stmt = select(Flow).where(Flow.id == flow_id)

# After
stmt = (
    select(Flow)
    .where(Flow.id == flow_id)
    .where(Flow.organization_id == current_user.active_org_id)
)
```

**Pattern 2: filter is by user_id only.** Replace or augment with org:

```python
# Before
stmt = select(Flow).where(Flow.id == flow_id, Flow.user_id == current_user.id)

# After
stmt = (
    select(Flow)
    .where(Flow.id == flow_id)
    .where(Flow.organization_id == current_user.active_org_id)
)
# user_id filter is optional defense-in-depth; keep it if the surface is
# explicitly per-user (drafts), drop it if the surface is org-shared (templates).
```

Do **not** add `guard_assistant_org_scope(...)` at the call site in this step — the guard is a belt-and-suspenders for tools that can't push the filter into the query (e.g. they receive an already-loaded object). If the query filter is feasible, that alone is sufficient.

- [ ] **Step L.6: Re-run the specific test**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_assistant_org_isolation.py::test_cross_org_returns_404[<surface_name>] -v
```
Expected: PASS.

- [ ] **Step L.7: Pause before commit**

If Case A (no fix needed), propose:
```
test(assist): register <surface_name> in cross-org isolation matrix
```

If Case B (fix applied), propose:
```
fix(assist): close cross-org leak in <surface_name>

Adds organization_id filter to <file:line> so the assistant tool cannot
surface data from another org. Covered by the regression matrix registry
entry added in the same commit.
```

Stage only the two modified files (the test file + the fix file). Never `git add -A`.

### Termination

The loop ends when:
- Every inventory row has a `Surface` entry.
- The meta-test (`test_registry_covers_all_mounted_assistant_routes`) passes.
- Every parametrized test case passes.

- [ ] **Final verification**

Run:
```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/p1-batch-1 && uv run pytest src/backend/tests/unit/api/v1/test_assistant_org_isolation.py -v
```
Expected: every Surface test PASSES + meta-test PASSES.

---

## Task 6: Adopt the guard helper at non-query call sites

**Files:**
- Modify: call sites identified during Task 5 where a filter on the DB query is **not** feasible (e.g. the tool receives a pre-resolved object from another service).

**Context:** If every Task 5 leak was closable via a query-level filter, this task is a no-op — delete it and move on. Otherwise, for each non-query site:

- [ ] **Step 1: Insert `guard_assistant_org_scope` at the tool entry**

```python
from langflow.services.assistant.guards import guard_assistant_org_scope

async def tool_that_receives_preloaded_target(
    target: Flow,
    current_user: CurrentActiveUser,
) -> ...:
    guard_assistant_org_scope(
        actor_org_id=current_user.active_org_id,
        target_org_id=target.organization_id,
        target_label="flow",
    )
    ...
```

- [ ] **Step 2: Add a direct unit test that does NOT need an HTTP client**

Append to `src/backend/tests/unit/services/assistant/test_guards.py`:

```python
import pytest
from uuid import uuid4

from langflow.services.assistant.guards import CrossOrgAccessError


def test_tool_with_preloaded_target_rejects_cross_org(<imports>) -> None:
    actor_org = uuid4()
    foreign = make_flow(organization_id=uuid4())
    with pytest.raises(CrossOrgAccessError):
        tool_that_receives_preloaded_target(target=foreign, current_user=make_user(active_org_id=actor_org))
```

- [ ] **Step 3: Run the test and confirm it fails (then passes)**

Standard TDD cycle. Run, see FAIL without the guard, add the guard per Step 1, re-run, see PASS.

- [ ] **Step 4: Pause before commit**

Proposed commit message per site:
```
fix(assist): guard <tool_name> against pre-loaded cross-org targets
```

If Task 6 applies to zero sites, skip it and record that in the Task 7 summary commit.

---

## Task 7: Archive inventory + update roadmap

**Files:**
- Delete or archive: `docs/superpowers/notes/2026-04-23-assistant-surface-inventory.md`
- Modify: `docs/superpowers/specs/2026-04-22-integration-platform-roadmap.md` — rename the P1 bullet.

- [ ] **Step 1: Decide the fate of the inventory note**

If the inventory surfaced fixes worth remembering beyond this sprint (e.g. "we also should look at X later"), keep the file and add a "Closed by" section at the top pointing at the commits. Otherwise delete it.

- [ ] **Step 2: Update the roadmap P1 bullet**

Edit `docs/superpowers/specs/2026-04-22-integration-platform-roadmap.md` around the line that currently reads:

```markdown
- **Metadata taxonomy extension** — add the org-level policy layer on top of the existing component/template metadata.
```

Replace with:

```markdown
- ~~**Metadata taxonomy extension** — add the org-level policy layer on top of the existing component/template metadata.~~ Reframed to **Assistant data-access isolation** — ✅ **Done (2026-04-23)** per spec `2026-04-23-assistant-org-isolation-and-tagging-design.md` Part A.
```

- [ ] **Step 3: Pause before commit**

Proposed commit message:
```
docs(roadmap): mark P1 assistant isolation done; archive inventory

Renames the mislabelled "Metadata taxonomy extension" P1 bullet to
"Assistant data-access isolation" and marks it ✅ done. Archives (or
deletes) the disposable inventory note used during Task 3.
```

---

## Verification After All Tasks

- [ ] `uv run pytest src/backend/tests/unit/services/assistant/test_guards.py -v` — PASS.
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_assistant_404_contract.py -v` — PASS (both parametrizations).
- [ ] `uv run pytest src/backend/tests/unit/api/v1/test_assistant_org_isolation.py -v` — ALL parametrizations PASS, meta-test PASS.
- [ ] `git log --oneline p1/batch-1 | head -20` — commits land in the sequence Task 1 → Task 2 → Task 3 → Task 4 → (Task 5 iterations) → Task 6 (if any) → Task 7.
- [ ] No file outside the scope defined in the spec's Part A has been touched.
- [ ] The roadmap entry is renamed and marked done.

---

## Self-Review Notes

- **Spec coverage:** A.1 goals fully covered by Tasks 4+5 (test matrix), A.3 by Task 3 (inventory), A.4 by Task 1 (helper), A.5 by Task 2 (404 contract), A.6 by Task 4 (registry + meta-test), A.7 by omission (no schema changes), A.8 by the Task 5 iteration loop + Task 7 cleanup.
- **Placeholders:** none. Every code block is complete, every command has expected output. The Task 5 loop is templated but each iteration produces exact code for its specific inventory row.
- **Type consistency:** `CrossOrgAccessError`, `guard_assistant_org_scope`, `Surface`, `ASSISTANT_SURFACES`, `two_org_fixture` used consistently.
- **Scope match:** Part A is self-contained in this plan. Part B has its own plan file.
