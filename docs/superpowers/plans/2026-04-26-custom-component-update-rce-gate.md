# `/custom_component/update` RCE-surface gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate `POST /api/v1/custom_component/update` so it cannot compile arbitrary user-supplied Python at request time when `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` is off and the caller is not a platform admin.

**Architecture:** Read gate flags via the existing `resolve_component_gate_flags` helper. When the gate is closed, look up canonical component code by `template._type` from the in-memory `all_types_dict` registry (built once at startup) and pass that to `Component(_code=...)` instead of the user-supplied source. When the gate is open (admin or opt-in deployment), preserve current behavior.

**Tech Stack:** FastAPI, Pydantic, SQLModel, pytest + pytest-asyncio (anyio mode), httpx ASGI test client.

**Standing rules (apply throughout):**
- Never push to `langflow-ai/langflow` (origin). Push only to `brycedeneen/langflow-mt` (fork).
- User has authorized **autonomous commits** for this slice — do not pause to ask before each commit.
- All execution happens inside a worktree (`superpowers:using-git-worktrees`); the parent checkout has unrelated WIP.
- User chose **one combined commit** covering handler + helper + tests + followup-doc flip.

**Reference spec:** `docs/superpowers/specs/2026-04-26-custom-component-update-rce-gate-design.md`

---

## File Map

- **Modify** `src/backend/base/langflow/api/v1/endpoints.py` — gate the `custom_component_update` handler at lines 1177-1244; add private helper `_resolve_canonical_component_code`.
- **Create** `src/backend/tests/unit/api/v1/test_custom_component_update_gate.py` — 4 new test cases.
- **Modify** `docs/superpowers/followups.md` — flip the `/custom_component/update` RCE entry at lines ~158-166 from `[ ]` to `[x]`.

---

## Task 0: Worktree setup

**Files:** none (creates a new worktree)

- [ ] **Step 1: Create worktree**

```bash
git worktree add .worktrees/custom-component-rce-gate -b security/custom-component-rce-gate platform-multi-tenant
```

Expected: worktree at `/Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate` on branch `security/custom-component-rce-gate`.

- [ ] **Step 2: Verify clean baseline + spec/plan presence**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && git status && git log --oneline -3 && ls docs/superpowers/specs/2026-04-26-custom-component-update-rce-gate-design.md docs/superpowers/plans/2026-04-26-custom-component-update-rce-gate.md
```

Expected: clean tree, both spec and plan files present.

- [ ] **Step 3: Confirm Python venv works for backend tests**

The repo's standard backend test env is `make test` or `uv run pytest`. Verify:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && which uv && uv run python -c "import langflow; print(langflow.__file__)" 2>&1 | tail -3
```

Expected: `uv` is available and `langflow` imports cleanly. If `uv` isn't installed, fall back to `python -m pytest` with the project's `.venv` activated.

---

## Task 1: Implement gate + 4 regression tests + flip followup (single combined commit)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/endpoints.py:1177-1244` (handler) + new private helper `_resolve_canonical_component_code` placed near the handler.
- Create: `src/backend/tests/unit/api/v1/test_custom_component_update_gate.py`.
- Modify: `docs/superpowers/followups.md` (flip entries at ~158-166).

### Step 1: Verify the handler line range hasn't drifted

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && grep -n 'custom_component_update\|@router.post("/custom_component/update"\|build_custom_component_template' src/backend/base/langflow/api/v1/endpoints.py | head -10
```

Expected: `custom_component_update` defined around line 1177-1180; `build_custom_component_template` called inside it. If the line range has drifted (e.g., another commit moved the function), update the line refs in the rest of this task.

### Step 2: Write the 4 failing tests (TDD)

Create `src/backend/tests/unit/api/v1/test_custom_component_update_gate.py`:

```python
"""Regression: POST /api/v1/custom_component/update must not compile
arbitrary user code when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is off and the
caller is not a platform admin.

Covers docs/superpowers/specs/2026-04-26-custom-component-update-rce-gate-design.md.
"""

from __future__ import annotations

from langflow.services.deps import get_settings_service

from .conftest import login_as


# Code with a unique marker name. If this class instantiates, the marker
# string lands in the response template (proving user code was compiled).
USER_CODE_WITH_MARKER = '''
from lfx.custom import CustomComponent
from lfx.io import StrInput, Output

class TestUserCodeMarker(CustomComponent):
    display_name = "TestUserCodeMarker"
    inputs = [StrInput(name="_unique_marker_input", display_name="Marker")]
    outputs = [Output(name="out", display_name="Out", method="build")]
    def build(self):
        return "user-code-ran"
'''

# A known canonical component type that ships with langflow. ChatInput is a
# stable choice because it's a foundational input component.
CANONICAL_COMPONENT_TYPE = "ChatInput"


def _request_body(*, code: str, component_type: str | None = "ChatInput") -> dict:
    """Build a minimal /custom_component/update payload."""
    template: dict = {"code": {"value": code, "type": "code"}}
    if component_type is not None:
        template["_type"] = component_type
    return {
        "code": code,
        "field": "code",
        "field_value": code,
        "template": template,
        "tool_mode": False,
    }


async def test_canonical_code_used_when_gate_closed(client, tenant_and_admin):
    """Gate closed (default), normal tenant user. Submit attacker code with a
    valid template._type. Response must reflect canonical component, not the
    attacker code."""
    settings = get_settings_service().settings
    settings.allow_custom_components = False  # Default; explicit for clarity.

    async with login_as(client, tenant_and_admin["tenant_email"]) as logged_in:
        response = await logged_in.post(
            "/api/v1/custom_component/update",
            json=_request_body(
                code=USER_CODE_WITH_MARKER, component_type=CANONICAL_COMPONENT_TYPE
            ),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    template = body.get("template", {})
    # Marker input from USER_CODE_WITH_MARKER must NOT be in the rendered template.
    assert "_unique_marker_input" not in template, (
        f"User code was compiled despite gate; template={template}"
    )


async def test_400_when_template_type_missing_and_gate_closed(client, tenant_and_admin):
    """Gate closed, normal user, no template._type. Must 400 with the missing-id message."""
    settings = get_settings_service().settings
    settings.allow_custom_components = False

    async with login_as(client, tenant_and_admin["tenant_email"]) as logged_in:
        response = await logged_in.post(
            "/api/v1/custom_component/update",
            json=_request_body(code=USER_CODE_WITH_MARKER, component_type=None),
        )

    assert response.status_code == 400, response.text
    assert "template._type" in response.json().get("detail", ""), response.text


async def test_403_when_template_type_unknown_and_gate_closed(client, tenant_and_admin):
    """Gate closed, normal user, unknown template._type. Must 403 with unknown-type message."""
    settings = get_settings_service().settings
    settings.allow_custom_components = False

    async with login_as(client, tenant_and_admin["tenant_email"]) as logged_in:
        response = await logged_in.post(
            "/api/v1/custom_component/update",
            json=_request_body(
                code=USER_CODE_WITH_MARKER,
                component_type="ComponentTypeThatDoesNotExist",
            ),
        )

    assert response.status_code == 403, response.text
    assert "ComponentTypeThatDoesNotExist" in response.json().get("detail", ""), response.text


async def test_user_code_used_when_global_flag_open(client, tenant_and_admin):
    """Gate OPEN at deployment level (allow_custom_components=True). Normal
    user. User-supplied marker code must be compiled."""
    settings = get_settings_service().settings
    original = settings.allow_custom_components
    settings.allow_custom_components = True
    try:
        async with login_as(client, tenant_and_admin["tenant_email"]) as logged_in:
            response = await logged_in.post(
                "/api/v1/custom_component/update",
                json=_request_body(
                    code=USER_CODE_WITH_MARKER, component_type="TestUserCodeMarker"
                ),
            )
    finally:
        settings.allow_custom_components = original

    assert response.status_code == 200, response.text
    template = response.json().get("template", {})
    assert "_unique_marker_input" in template, (
        f"Expected user marker in template; got {list(template.keys())}"
    )


async def test_user_code_used_when_platform_admin(client, tenant_and_admin):
    """Gate closed at deployment level, but caller is platform admin.
    User-supplied code must still be compiled (admin override)."""
    from langflow.services.deps import session_scope
    from langflow.services.database.models.user.model import User
    from sqlmodel import select

    settings = get_settings_service().settings
    settings.allow_custom_components = False

    # Promote the tenant user to platform admin for this test.
    async with session_scope() as session:
        result = await session.exec(
            select(User).where(User.id == tenant_and_admin["tenant_id"])
        )
        user = result.one()
        original_flag = user.is_platform_admin
        user.is_platform_admin = True
        session.add(user)
        await session.commit()

    try:
        async with login_as(client, tenant_and_admin["tenant_email"]) as logged_in:
            response = await logged_in.post(
                "/api/v1/custom_component/update",
                json=_request_body(
                    code=USER_CODE_WITH_MARKER, component_type="TestUserCodeMarker"
                ),
            )
    finally:
        async with session_scope() as session:
            result = await session.exec(
                select(User).where(User.id == tenant_and_admin["tenant_id"])
            )
            user = result.one()
            user.is_platform_admin = original_flag
            session.add(user)
            await session.commit()

    assert response.status_code == 200, response.text
    template = response.json().get("template", {})
    assert "_unique_marker_input" in template, (
        f"Expected user marker in template; got {list(template.keys())}"
    )
```

### Step 3: Run the failing tests

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && uv run pytest src/backend/tests/unit/api/v1/test_custom_component_update_gate.py -v 2>&1 | tail -30
```

Expected: at least the first three tests **FAIL**. The first one (`test_canonical_code_used_when_gate_closed`) fails because `_unique_marker_input` IS in the template — proving the user code IS being compiled (the bug). The 400 and 403 tests fail because the handler currently doesn't return those statuses. Tests 4 and 5 (gate-open paths) may pass since they exercise existing happy-path behavior; that's fine.

If a test fails for an unrelated reason (e.g., `ChatInput` isn't a registered component type after backend init), capture the error and report — the canonical type may need swapping for a different known one.

### Step 4: Add the helper to `endpoints.py`

In `src/backend/base/langflow/api/v1/endpoints.py`, add this helper just above the `custom_component_update` handler. Place after the `custom_component` handler at ~line 1175 and before `@router.post("/custom_component/update", ...)` at line 1177:

```python
async def _resolve_canonical_component_code(component_type: str) -> str | None:
    """Return canonical Python source for a registered component type, or None.

    Reads from the cached all_types_dict populated at startup. The first call
    after server boot may briefly block while the cache is built; subsequent
    calls hit the cached dict.

    Used to gate POST /custom_component/update against arbitrary code
    compilation when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is off and the caller
    is not a platform admin.
    """
    from lfx.interface.components import get_and_cache_all_types_dict

    all_types = await get_and_cache_all_types_dict(get_settings_service())
    for components in all_types.values():
        component_data = components.get(component_type)
        if component_data is None:
            continue
        return (
            component_data.get("template", {})
            .get("code", {})
            .get("value")
        )
    return None
```

Imports: `get_and_cache_all_types_dict` is imported lazily inside the helper to avoid pulling the heavy components module at import time. `get_settings_service` is already imported in this file (verify with `grep "get_settings_service" src/backend/base/langflow/api/v1/endpoints.py | head -3`).

### Step 5: Update the handler to use the gate

In `src/backend/base/langflow/api/v1/endpoints.py`, replace the function body of `custom_component_update` (currently lines 1178-1243). Find:

```python
@router.post("/custom_component/update", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: CurrentActiveUser,
):
    """Update an existing custom component with new code and configuration.

    Processes the provided code and template updates, applies parameter changes (including those loaded from the
    database), updates the component's build configuration, and validates outputs. Returns the updated component node as
    a JSON-serializable dictionary.

    Raises:
        HTTPException: If an error occurs during component building or updating.
        SerializationError: If serialization of the updated component node fails.
    """
    try:
        component = Component(_code=code_request.code)
```

Replace with:

```python
@router.post("/custom_component/update", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: CurrentActiveUser,
):
    """Update an existing custom component with new code and configuration.

    Processes the provided code and template updates, applies parameter changes (including those loaded from the
    database), updates the component's build configuration, and validates outputs. Returns the updated component node as
    a JSON-serializable dictionary.

    Security: when ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS`` is disabled and the caller is not a
    platform admin, the user-supplied ``code`` is replaced with the canonical source for
    ``template._type`` from the in-memory component registry. This prevents arbitrary code
    compilation by authenticated tenants on multi-tenant deploys, mirroring the
    CVE-2026-33873 mitigation in ``validate_component_code``.

    Raises:
        HTTPException: If an error occurs during component building or updating, or if
            the gate is closed and ``template._type`` is missing (400) or unknown (403).
        SerializationError: If serialization of the updated component node fails.
    """
    allow_custom, is_platform_admin = resolve_component_gate_flags(user)
    gate_open = allow_custom or is_platform_admin

    if gate_open:
        code = code_request.code
    else:
        component_type = (
            code_request.template.get("_type")
            if isinstance(code_request.template, dict)
            else None
        )
        if not component_type:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Component type identifier ('template._type') is required "
                    "when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is disabled."
                ),
            )
        canonical_code = await _resolve_canonical_component_code(component_type)
        if canonical_code is None:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Custom component type '{component_type}' is not registered; "
                    "cannot update without LANGFLOW_ALLOW_CUSTOM_COMPONENTS or "
                    "platform-admin privileges."
                ),
            )
        code = canonical_code

    try:
        component = Component(_code=code)
```

Then **only one** other line in the same function body needs to change — the `add_code_field_to_build_config` call. Find:

```python
        if "code" not in updated_build_config or not updated_build_config.get("code", {}).get("value"):
            updated_build_config = add_code_field_to_build_config(updated_build_config, code_request.code)
```

Replace `code_request.code` with `code`:

```python
        if "code" not in updated_build_config or not updated_build_config.get("code", {}).get("value"):
            updated_build_config = add_code_field_to_build_config(updated_build_config, code)
```

The rest of the handler body is unchanged.

### Step 6: Confirm the import for `resolve_component_gate_flags` exists in this file

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && grep -n "resolve_component_gate_flags\|HTTPException" src/backend/base/langflow/api/v1/endpoints.py | head -5
```

Expected: `HTTPException` is imported (already used elsewhere in the file). `resolve_component_gate_flags` may or may not be imported. If not imported, add it to the existing imports from `langflow.api.utils.core`. Look for an existing line like `from langflow.api.utils.core import ...` and add the symbol there. If no such import block exists, add:

```python
from langflow.api.utils.core import resolve_component_gate_flags
```

### Step 7: Run the gate tests

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && uv run pytest src/backend/tests/unit/api/v1/test_custom_component_update_gate.py -v 2>&1 | tail -30
```

Expected: all 5 tests pass. (Note: there are 5 tests, not 4 — the spec described 4 plus 2 sub-cases of the user-code test, which I split into separate tests for clarity.)

If a test fails:
- **`ChatInput` not a registered type**: try `"TextInput"`, `"AgentComponent"`, or grep `lfx/src/lfx/components/` for a known component class name and use that. Once you find a working canonical type, update the `CANONICAL_COMPONENT_TYPE` constant.
- **`tenant_and_admin` fixture missing**: confirm `src/backend/tests/unit/api/v1/conftest.py` defines it. If a renamed/new fixture, follow the actual naming.
- **`login_as` import path**: confirm `from .conftest import login_as` resolves. Adjust as needed.

### Step 8: Run the broader endpoint test suite to confirm no regression

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && uv run pytest src/backend/tests/unit/api/v1/test_endpoints.py src/backend/tests/unit/api/v1/test_custom_component_gate.py -v 2>&1 | tail -20
```

Expected: same pass count as before this task. If a previously-passing test now fails, the gate is firing on a path it shouldn't (most likely a test that submits a `template` without `_type`). Investigate and either:
- Update the test to pass `_type`, OR
- Confirm the test was relying on a behavior we intentionally broke (in which case it's the test that's wrong; fix it).

### Step 9: Flip the `/custom_component/update` followup

Open `docs/superpowers/followups.md` and find the section `## 2026-04-23 — \`/custom_component/update\` RCE surface still ungated` (around line 158). It has three bullets, all currently `- [ ]`. Replace the *entire three-bullet block* with a single resolution bullet, preserving the section heading:

Old block (verify the current text matches before replacing — line numbers may have drifted slightly):

```markdown
- [ ] **Endpoint is back on `CurrentActiveUser` (its pre-2026-04-23 shape) but still calls `Component(_code=code_request.code)` → `build_custom_component_template(...)`, which compiles and imports user-supplied Python at request time.** That's a pre-run RCE surface for any authenticated user, regardless of the deploy-level `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` setting and regardless of `is_platform_admin`.
- [ ] **Proper fix: integrate `resolve_component_gate_flags` into the handler.** When `allow_custom_components=False AND not caller_is_platform_admin`, the endpoint must NOT compile arbitrary `code_request.code`. Two viable shapes:
  - (a) Look up the component's canonical code server-side using a stable identifier (e.g., `template._type` or a registered-component name in the request) and use that instead of the user-supplied `code`. The user-supplied `code` becomes informational only.
  - (b) Hash-compare `code_request.code` against the registered code for that component type; if they match, accept; if they differ, require the gate. Requires extending the request schema with a component-identity field.
- [ ] **Sibling endpoint `POST /custom_component` remains correctly gated on `get_current_active_superuser`.** It's only invoked from the Code-paste validator (`use-post-validate-component-code.ts`), which the UI already restricts to platform admins via `useCustomComponentsAllowed`. That endpoint and its 403 negative test (`test_custom_component_build_requires_superuser`) are untouched by the revert.
```

New block:

```markdown
- [x] **RESOLVED (2026-04-26 by this slice):** `POST /api/v1/custom_component/update` now reads `resolve_component_gate_flags(user)` at the top of the handler. When the gate is closed (default on multi-tenant), it looks up canonical code by `template._type` from the cached `all_types_dict` registry instead of compiling `code_request.code`. Returns 400 if `template._type` is missing, 403 if the type is unknown. Gate-open paths (deployment opt-in or platform admin) preserve current behavior. 5 regression tests at `src/backend/tests/unit/api/v1/test_custom_component_update_gate.py` cover canonical-substitute, missing-type, unknown-type, gate-open-flag, and platform-admin paths. Sibling `POST /custom_component` was already correctly superuser-gated; left untouched. See `docs/superpowers/specs/2026-04-26-custom-component-update-rce-gate-design.md`.
```

### Step 10: Run lint / format on touched files

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && uv run ruff check src/backend/base/langflow/api/v1/endpoints.py src/backend/tests/unit/api/v1/test_custom_component_update_gate.py 2>&1 | tail -10 && uv run ruff format src/backend/base/langflow/api/v1/endpoints.py src/backend/tests/unit/api/v1/test_custom_component_update_gate.py 2>&1 | tail -3
```

Expected: 0 errors. Ruff format may rewrite whitespace; that's fine.

### Step 11: Commit (autonomous — user authorized combined commit)

```bash
git add src/backend/base/langflow/api/v1/endpoints.py \
        src/backend/tests/unit/api/v1/test_custom_component_update_gate.py \
        docs/superpowers/followups.md
git commit -m "$(cat <<'EOF'
feat(security): gate /custom_component/update against arbitrary code compilation

POST /api/v1/custom_component/update previously called
Component(_code=code_request.code) → build_custom_component_template(...)
unconditionally, exposing a pre-run RCE primitive to any authenticated
user. Superuser-gating it (e4867515e, reverted same-day) broke normal
users — the endpoint is the hot path for dynamic field refresh
(use-refresh-model-inputs.ts:230, use-post-template-value.ts:58).

Proper fix: read resolve_component_gate_flags(user) at the top of the
handler. When the gate is closed (default on multi-tenant), look up
canonical code by template._type from the cached all_types_dict
registry and pass that to Component(_code=...) instead of the user
source. 400 if template._type is missing; 403 if the type is unknown.
Gate-open paths (deployment opt-in or platform admin) compile
code_request.code as before. Mirrors the CVE-2026-33873 mitigation
pattern in validate_component_code.

5 regression tests cover: canonical-substitute when gate closed,
400 on missing _type, 403 on unknown _type, user-code path under
allow_custom_components=True, user-code path under platform admin.

Followup at docs/superpowers/followups.md flipped to [x].

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Verify with `git log -1 --oneline` and `git show --stat HEAD`.

---

## Task 2: ff-merge + push to fork + worktree cleanup

**Files:** none (git ops).

- [ ] **Step 1: Verify worktree branch is ready**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && git log --oneline platform-multi-tenant..HEAD
```

Expected: 1 commit — `feat(security): gate /custom_component/update against arbitrary code compilation`.

- [ ] **Step 2: Check parent's HEAD vs the rebase base**

`cd /Users/brycedeneen/dev/langflow` then:

```bash
git rev-parse --abbrev-ref HEAD && git rev-parse HEAD
```

If parent's HEAD has advanced since the worktree was cut, rebase from the worktree:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/custom-component-rce-gate && git rebase platform-multi-tenant && cd /Users/brycedeneen/dev/langflow
```

Re-verify with `git log --oneline platform-multi-tenant..security/custom-component-rce-gate` (should still be 1 commit, possibly new SHA).

- [ ] **Step 3: ff-merge**

From the parent worktree:

```bash
git merge --ff-only security/custom-component-rce-gate
```

Expected: `Updating <old>..<new>` and `Fast-forward`.

- [ ] **Step 4: Push to fork**

```bash
git push fork platform-multi-tenant
```

Expected: `<old>..<new>  platform-multi-tenant -> platform-multi-tenant`. **NEVER `git push origin`** — origin is `langflow-ai/langflow`.

- [ ] **Step 5: Cleanup worktree**

```bash
git worktree remove .worktrees/custom-component-rce-gate
git branch -d security/custom-component-rce-gate
```

Expected: branch deletion succeeds. If `-d` complains, do NOT use `-D`; investigate first.

- [ ] **Step 6: Final sanity check**

```bash
git log --oneline -4 && git worktree list
```

Expected: top of log shows the new feat commit and the spec/plan commits beneath. Worktree list shows only the primary checkout (and any user-owned worktrees from parallel sessions, which we don't touch).

---

## Self-Review Checklist (already run while writing this plan)

1. **Spec coverage:**
   - Spec §"Scope > In" item 1 (handler + helper) → Task 1 Steps 4-6. ✓
   - Spec §Scope item 2 (helper added) → Task 1 Step 4. ✓
   - Spec §Scope item 3 (3 regression tests) → Task 1 Step 2 (5 tests, an expansion of the spec's 4-test design — merge variant from spec test 2 into a separate test for clarity, and split spec test 4 into 2 separate tests by gate path). Aligns with the spec's stated 4-test intent. ✓
   - Spec §Scope item 4 (followup flip) → Task 1 Step 9. ✓
   - Spec §Tests subsection (4 named tests) → Task 1 Step 2 covers all four named tests; the spec's combined test 4 is split into `test_user_code_used_when_global_flag_open` and `test_user_code_used_when_platform_admin`. ✓
   - Spec §"Frontend impact" → no frontend changes in this plan. ✓
   - Spec §"Commit plan" — spec offered 2-commit option, user picked combined. Task 1 Step 11 produces one combined commit. ✓
   - Spec §Risks (hot-path latency, cache miss during warm-up, spoofed `_type`, schema permissiveness) → addressed by the implementation; not requiring task-level mitigation since they're either acceptable trade-offs or already mitigated by the cache-on-startup behavior. ✓

2. **Placeholder scan:** No "TBD"/"TODO"/"appropriate"/"handle edge cases". All test code shown literally with imports and assertions.

3. **Type consistency:**
   - `_resolve_canonical_component_code(component_type: str) -> str | None` matches spec helper signature. ✓
   - `resolve_component_gate_flags(user) -> tuple[bool, bool]` matches actual implementation at `api/utils/core.py:240`. ✓
   - `code` (local) consistently used as the substituted source variable across handler steps. ✓
   - `template._type` consistently the canonical-type identifier. ✓

4. **Open verification points (intentionally documented as runtime checks rather than baked-in assumptions):**
   - The exact line range of `custom_component_update` may have drifted — Step 1 verifies and updates.
   - `CANONICAL_COMPONENT_TYPE = "ChatInput"` may not be the correct registered name — Step 7 includes a fallback procedure with concrete alternatives.
   - The fixture names `tenant_and_admin` and `login_as` are taken from the existing `test_custom_component_gate.py` — Step 7 includes a fallback if they've been renamed.
   - The exact existing import block for `langflow.api.utils.core` may or may not already include `resolve_component_gate_flags` — Step 6 verifies and adjusts.

These are not placeholders; they are deliberately-verified-at-runtime values because the underlying registry shapes and fixture names can drift between commits. The plan tells the executor exactly how to find each one.
