# `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` Backport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User-specific commit discipline:** This user has a standing rule — pause and ask before every `git commit`, even when this plan instructs one. The commit commands in each task are the *exact* command to run *after* the user approves; do not run them unprompted. Stage explicit file paths only (no `git add -A` / `.`).

**Goal:** Backport upstream PR [#11893](https://github.com/langflow-ai/langflow/pull/11893) so non-platform-admin tenants cannot create, upload, or execute flows containing custom Python components when `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false` (the default).

**Architecture:** Four layers. (1) A gate library in `lfx` that walks a flow and rejects any node whose `code` does not match a cached component template. (2) One Pydantic setting `allow_custom_components` (default `False`). (3) A single unconditional platform-admin bypass at the top of the gate — our one behavioral divergence from upstream. (4) Four enforcement call sites (execution, flow-create, flow-upload, template-create) plus a frontend guard hook that disables the "New Custom Component" sidebar button, forces `readonly=true` on the code editor for tenants, and does a client-side precheck on JSON imports.

**Tech Stack:** Python 3.11+, FastAPI, SQLModel (async), pytest-asyncio, Pydantic settings, React + TypeScript, react-query v5 (`isPending`), Jest (not Vitest), Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md` (commit `46222f2c80`).

**Out of scope:** per-org allowlist, runtime sandboxing, retroactive scan of pre-existing flows, starter-project JSON edits (our starters are Python, not JSON). See spec for rationale.

---

## File Structure

**New (backend):**
- `src/lfx/src/lfx/utils/flow_validation.py` — gate library ported from upstream PR #11893 with one added platform-admin bypass.
- `src/lfx/src/lfx/utils/component_aliases.py` — helper module ported from upstream verbatim.
- `src/lfx/tests/unit/utils/test_flow_validation.py` — gate unit tests.
- `src/backend/tests/unit/api/v1/test_custom_component_gate.py` — API enforcement tests, one per call site.
- `src/backend/tests/unit/services/test_settings_allow_custom.py` — tiny settings test.

**Modified (backend):**
- `src/backend/base/langflow/services/settings/base.py` — add `allow_custom_components` field.
- `src/backend/base/langflow/api/v1/endpoints.py` — surface flag in `ConfigResponse`.
- `src/backend/base/langflow/api/v1/flows.py` — enforce in `create_flow` (line 360) and `upload_file` (line 913).
- `src/backend/base/langflow/api/v1/templates.py` — enforce in `create_template`.
- `src/lfx/src/lfx/graph/graph/base.py` — enforce on build-vertex entry.

**New (frontend):**
- `src/frontend/src/utils/customComponentGuards.ts` — guard hook.
- `src/frontend/src/utils/__tests__/customComponentGuards.test.tsx` — hook + integration tests.

**Modified (frontend):**
- `src/frontend/src/controllers/API/queries/config/use-get-config.ts` — add `allow_custom_components` to `ConfigResponse` TS interface.
- `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx` — disable the "New Custom Component" button for tenants (line 80 region).
- `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals.tsx` — force `readonly=true` on `<CodeAreaModal>` for tenants (this is the "Edit Code" action on existing nodes).
- `src/frontend/src/hooks/flows/use-upload-flow.ts` — client-side precheck that shows an inline error when a tenant uploads a JSON containing custom-code nodes.

---

## Task 1: Port the gate library (`flow_validation.py` + `component_aliases.py`)

**Vulnerability this addresses:** On deploy, an unvetted custom component in a user-uploaded flow executes on shared infrastructure. This task creates the detector; Tasks 4-7 wire it into the four entry points.

**Files:**
- Create: `src/lfx/src/lfx/utils/flow_validation.py`
- Create: `src/lfx/src/lfx/utils/component_aliases.py`
- Create: `src/lfx/tests/unit/utils/test_flow_validation.py`

- [x] **Step 1: Fetch upstream's files**

The upstream PR is large but the two files we need are self-contained. Pull them directly from the PR branch:

```bash
# Fetch the two utility files verbatim from upstream PR #11893
mkdir -p /tmp/pr-11893
gh api repos/langflow-ai/langflow/contents/src/lfx/src/lfx/utils/flow_validation.py \
  --jq '.content' | base64 -d > /tmp/pr-11893/flow_validation.py
gh api repos/langflow-ai/langflow/contents/src/lfx/src/lfx/utils/component_aliases.py \
  --jq '.content' | base64 -d > /tmp/pr-11893/component_aliases.py

# Sanity check
wc -l /tmp/pr-11893/*.py
# flow_validation.py should be ~200-260 LOC
# component_aliases.py should be ~50-80 LOC
```

If `gh api` fails (no auth / rate limit), fall back to:
```bash
curl -sL https://raw.githubusercontent.com/langflow-ai/langflow/main/src/lfx/src/lfx/utils/flow_validation.py -o /tmp/pr-11893/flow_validation.py
curl -sL https://raw.githubusercontent.com/langflow-ai/langflow/main/src/lfx/src/lfx/utils/component_aliases.py -o /tmp/pr-11893/component_aliases.py
```

Expected: both files downloaded; `flow_validation.py` defines a function that takes a flow dict and raises on any unrecognised `code` payload. The exact name upstream uses may vary (`validate_flow`, `check_flow_code`, etc.) — we will rename to `validate_flow_components` in Step 3.

- [x] **Step 2: Write the failing gate-unit tests**

Create `src/lfx/tests/unit/utils/test_flow_validation.py`:

```python
"""Unit tests for the custom-component gate.

Covers the design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
"""

from __future__ import annotations

import pytest

from lfx.utils.flow_validation import (
    CustomComponentNotAllowedError,
    validate_flow_components,
)


def _flow_with_one_custom_node() -> dict:
    """Flow containing a single node whose code is NOT a known shipped template."""
    return {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "node": {
                        "template": {
                            "code": {
                                "value": "def malicious():\n    import os; os.system('rm -rf /')\n",
                            }
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


def _empty_flow() -> dict:
    return {"nodes": [], "edges": []}


def test_allow_custom_flag_bypasses_gate():
    validate_flow_components(
        _flow_with_one_custom_node(),
        allow_custom=True,
        caller_is_platform_admin=False,
    )  # no raise


def test_platform_admin_bypasses_gate():
    validate_flow_components(
        _flow_with_one_custom_node(),
        allow_custom=False,
        caller_is_platform_admin=True,
    )  # no raise


def test_tenant_with_custom_code_is_rejected():
    with pytest.raises(CustomComponentNotAllowedError):
        validate_flow_components(
            _flow_with_one_custom_node(),
            allow_custom=False,
            caller_is_platform_admin=False,
        )


def test_empty_flow_is_accepted():
    validate_flow_components(
        _empty_flow(),
        allow_custom=False,
        caller_is_platform_admin=False,
    )  # no raise


def test_shipped_component_code_is_accepted():
    """A flow whose node code matches a cached shipped-component template must pass.

    The gate populates its template cache at import/startup; we exercise
    that via a component whose code the cache knows. Any component in
    src/backend/base/langflow/components/ will do — we pick a stable one.
    """
    from langflow.components.inputs.chat import ChatInput
    import inspect

    # Take the verbatim source of a shipped component class.
    shipped_code = inspect.getsource(ChatInput)
    flow = {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "node": {
                        "template": {
                            "code": {"value": shipped_code},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }
    validate_flow_components(
        flow,
        allow_custom=False,
        caller_is_platform_admin=False,
    )  # no raise


def test_missing_code_field_is_treated_as_custom():
    """A node with no code at all (malformed / bad-data bypass attempt) is rejected.

    Rationale: stricter of the two interpretations — prevents an attacker
    from hiding code behind a shape the walker doesn't recognise.
    """
    flow = {
        "nodes": [
            {"id": "n1", "data": {"node": {"template": {}}}},
        ],
        "edges": [],
    }
    with pytest.raises(CustomComponentNotAllowedError):
        validate_flow_components(
            flow, allow_custom=False, caller_is_platform_admin=False
        )
```

- [x] **Step 3: Run tests to verify they fail**

Run: `cd src/lfx && uv run pytest tests/unit/utils/test_flow_validation.py -v`

Expected: all tests FAIL with `ModuleNotFoundError: No module named 'lfx.utils.flow_validation'`. This is the TDD red.

- [x] **Step 4: Drop in the ported files and add the platform-admin bypass**

Copy the fetched files into place:

```bash
cp /tmp/pr-11893/flow_validation.py src/lfx/src/lfx/utils/flow_validation.py
cp /tmp/pr-11893/component_aliases.py src/lfx/src/lfx/utils/component_aliases.py
```

Now modify `src/lfx/src/lfx/utils/flow_validation.py`:

1. If the public entry point upstream is not named `validate_flow_components`, rename it with a simple `Edit` (search/replace). The name we commit to is `validate_flow_components`.
2. If the exception class is not named `CustomComponentNotAllowedError`, rename it similarly.
3. Change the signature so both bypass flags are keyword-only:

```python
def validate_flow_components(
    flow_data: dict,
    *,
    allow_custom: bool,
    caller_is_platform_admin: bool,
) -> None:
    """Raise CustomComponentNotAllowedError if the flow contains a node
    whose `code` does not match a cached component template.

    No-op when `allow_custom` is True or `caller_is_platform_admin` is True.
    """
    # ADDED FOR platform-multi-tenant: single-point bypass (spec 2026-04-22).
    if caller_is_platform_admin or allow_custom:
        return

    # ... existing upstream walker body unchanged ...
```

The bypass must be the *first* statement in the function — before any cache lookup. This keeps the platform-admin hot path at zero overhead.

If upstream's function takes a `settings` object instead of the `allow_custom` bool, adapt the signature to the two explicit kwargs above and pull `allow_custom` out of `settings.allow_custom_components` at each call site in Tasks 4–7. Do **not** leave the `settings` argument in the lfx layer — lfx must not depend on the langflow settings service.

Preserve upstream's cache-loading code and the cold-cache-fail-closed behavior verbatim — these are correctness-critical and we inherit them deliberately.

- [x] **Step 5: Run tests to verify they pass**

Run: `cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/utils/test_flow_validation.py -v`

(The `LFX_TEST_ALLOW_LANGFLOW=1` env var is required because `test_shipped_component_code_is_accepted` imports from `langflow.components.inputs.chat`. See `reference_lfx_test_env.md` in user memory.)

Expected: all 6 tests PASS.

- [x] **Step 6: Ask the user before committing, then commit**

```bash
git add src/lfx/src/lfx/utils/flow_validation.py \
        src/lfx/src/lfx/utils/component_aliases.py \
        src/lfx/tests/unit/utils/test_flow_validation.py
git commit -m "$(cat <<'EOF'
feat(lfx): port custom-component gate from upstream PR #11893

Adds validate_flow_components() and component_aliases helper from
upstream PR #11893, plus a single unconditional platform-admin bypass
(our one behavioral divergence from upstream, per spec 2026-04-22).

The gate walks nodes[].data.node.template.code.value and compares each
against the cached component template set; mismatches raise
CustomComponentNotAllowedError. Cold template cache fails closed.
Missing code field is treated as custom (stricter interpretation).

Not yet wired — enforcement sites land in subsequent commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add the `allow_custom_components` setting

**Files:**
- Modify: `src/backend/base/langflow/services/settings/base.py`
- Create: `src/backend/tests/unit/services/test_settings_allow_custom.py`

- [x] **Step 1: Write the failing settings test**

Create `src/backend/tests/unit/services/test_settings_allow_custom.py`:

```python
"""Regression: LANGFLOW_ALLOW_CUSTOM_COMPONENTS must default to False and parse env-var truthy values."""

from __future__ import annotations

import importlib

import pytest


def _reload_settings():
    """Reload the settings module so env-var changes take effect."""
    from langflow.services.settings import base as base_module

    importlib.reload(base_module)
    return base_module.Settings()


def test_allow_custom_components_defaults_to_false(monkeypatch):
    monkeypatch.delenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", raising=False)
    settings = _reload_settings()
    assert settings.allow_custom_components is False


@pytest.mark.parametrize("truthy", ["true", "True", "1", "TRUE"])
def test_allow_custom_components_parses_truthy(monkeypatch, truthy):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", truthy)
    settings = _reload_settings()
    assert settings.allow_custom_components is True


@pytest.mark.parametrize("falsy", ["false", "0", "False", "FALSE"])
def test_allow_custom_components_parses_falsy(monkeypatch, falsy):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", falsy)
    settings = _reload_settings()
    assert settings.allow_custom_components is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/test_settings_allow_custom.py -v`

Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'allow_custom_components'`.

- [x] **Step 3: Add the setting**

Edit `src/backend/base/langflow/services/settings/base.py`. Near other boolean feature-flag fields (search for an existing `bool = Field(default=False, ...)` entry to find the right region), add:

```python
allow_custom_components: bool = Field(
    default=False,
    description=(
        "When False, non-platform-admin users cannot create, upload, or "
        "execute flows containing custom Python components. Platform admins "
        "always bypass this gate. Env var: LANGFLOW_ALLOW_CUSTOM_COMPONENTS."
    ),
)
```

Pydantic's `BaseSettings` pulls `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` automatically via the existing `env_prefix="LANGFLOW_"` on the settings model (verify the prefix by searching for `env_prefix` in the file). No custom validator needed — Pydantic's default bool parser handles `"true"`, `"1"`, `"True"`, `"false"`, `"0"`, `"False"`.

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/services/test_settings_allow_custom.py -v`

Expected: all 9 tests PASS (default + 4 truthy + 4 falsy).

- [x] **Step 5: Ask the user before committing, then commit**

```bash
git add src/backend/base/langflow/services/settings/base.py \
        src/backend/tests/unit/services/test_settings_allow_custom.py
git commit -m "$(cat <<'EOF'
feat(settings): add LANGFLOW_ALLOW_CUSTOM_COMPONENTS (default False)

Gates enforcement machinery landing in subsequent commits. Default
False for platform-multi-tenant; platform admins always bypass the
gate unconditionally (see spec 2026-04-22).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Surface the flag in `GET /api/v1/config`

The frontend guard hook reads `config.allow_custom_components`. The backend config endpoint is at `src/backend/base/langflow/api/v1/endpoints.py::get_config` (line ~1225). The TypeScript `ConfigResponse` interface is at `src/frontend/src/controllers/API/queries/config/use-get-config.ts`.

**Files:**
- Modify: `src/backend/base/langflow/api/v1/endpoints.py` (around line 1225)
- Modify: `src/frontend/src/controllers/API/queries/config/use-get-config.ts`

- [x] **Step 1: Write the failing config-response test**

Append to `src/backend/tests/unit/services/test_settings_allow_custom.py` (same file as Task 2):

```python
async def test_config_endpoint_surfaces_allow_custom_components(client, logged_in_headers):
    """GET /api/v1/config must expose the allow_custom_components flag so
    the frontend guard hook can read it."""
    resp = await client.get("api/v1/config", headers=logged_in_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "allow_custom_components" in body
    assert body["allow_custom_components"] is False  # default fleet posture
```

Note: `logged_in_headers` is an existing fixture in this repo's conftest (search `def logged_in_headers` if you need to confirm). If the fixture lives in a different conftest scope, copy the fixture shape used by neighbouring `test_*.py` files under `src/backend/tests/unit/services/`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/services/test_settings_allow_custom.py::test_config_endpoint_surfaces_allow_custom_components -v`

Expected: FAIL — `"allow_custom_components" not in body`.

- [x] **Step 3: Add the field to the backend response**

Edit `src/backend/base/langflow/api/v1/endpoints.py`. Around line 1225, `get_config` returns a dict assembled from the settings service. Find the return statement and add the new key. Example patch shape (exact keys already in the response will differ — keep them and add ours):

```python
return {
    # ... existing keys ...
    "allow_custom_components": settings_service.settings.allow_custom_components,
}
```

If the response is typed via a Pydantic `ConfigResponse` model elsewhere in the file, add a corresponding `allow_custom_components: bool = False` field to that model too (grep `class ConfigResponse` in the same file).

- [x] **Step 4: Add the field to the TypeScript interface**

Edit `src/frontend/src/controllers/API/queries/config/use-get-config.ts`. Around the `ConfigResponse` interface (extends `BaseConfig`), add the new field:

```ts
export interface ConfigResponse extends BaseConfig {
  auto_saving: boolean;
  auto_saving_interval: number;
  health_check_max_retries: number;
  feature_flags: Record<string, any>;
  webhook_polling_interval: number;
  serialization_max_items_length: number;
  webhook_auth_enable: boolean;
  default_folder_name: string;
  hide_getting_started_progress: boolean;
  allow_custom_components: boolean;  // NEW
}
```

- [x] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/services/test_settings_allow_custom.py -v`

Expected: all 10 tests PASS (9 from Task 2 + the new config test).

- [x] **Step 6: Type-check the frontend change**

Run: `cd src/frontend && npm run type-check 2>&1 | tail -20`

Expected: no new errors. If consumers of `ConfigResponse` complain that `allow_custom_components` is missing in test fixtures, those fixtures are Task 8's problem — ignore for now.

- [x] **Step 7: Ask the user before committing, then commit**

```bash
git add src/backend/base/langflow/api/v1/endpoints.py \
        src/frontend/src/controllers/API/queries/config/use-get-config.ts \
        src/backend/tests/unit/services/test_settings_allow_custom.py
git commit -m "$(cat <<'EOF'
feat(api/config): surface allow_custom_components in GET /api/v1/config

Frontend guard hook (Task 8) reads this flag from the existing config
endpoint to decide whether to disable custom-component UI for
non-platform-admins. Adds TypeScript ConfigResponse field in the same
commit so the contract lands atomically.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Enforce at flow execution (lfx build-vertex entry)

This is the primary defence. Even if the create/upload/template gates fail to catch a custom-code flow, execution refuses to run it.

**Files:**
- Modify: `src/lfx/src/lfx/graph/graph/base.py`
- Test: add to `src/backend/tests/unit/api/v1/test_custom_component_gate.py` (new file — create in this task)

- [x] **Step 1: Create the API-enforcement test file with the execution scenario**

Create `src/backend/tests/unit/api/v1/test_custom_component_gate.py`:

```python
"""Regression: the custom-component gate must reject non-admin tenants at
execution, create, upload, and template-create sites.

Covers the design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
"""

from __future__ import annotations

import uuid

import pytest

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


# A plausibly-malicious custom component body — anything whose source does not
# match a cached shipped-component template will do.
CUSTOM_CODE = '''
from lfx.custom import CustomComponent

class Exfiltrator(CustomComponent):
    display_name = "Exfiltrator"
    def build(self):
        return "pwned"
'''


def _flow_payload_with_custom_code() -> dict:
    return {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "node": {
                        "template": {
                            "code": {"value": CUSTOM_CODE},
                        }
                    }
                },
            }
        ],
        "edges": [],
    }


@pytest.fixture
async def tenant_and_admin():
    """Create one tenant user (org member, not platform admin) and one platform admin."""
    slug = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        org = Organization(name=f"OrgG-{slug}", slug=f"org-g-{slug}", is_personal=True)
        tenant = User(
            username=f"tenant-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_platform_admin=False,
        )
        admin = User(
            username=f"admin-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_platform_admin=True,
        )
        session.add_all([org, tenant, admin])
        await session.flush()
        session.add_all([
            Membership(user_id=tenant.id, organization_id=org.id, role=MembershipRole.OWNER),
            Membership(user_id=admin.id, organization_id=org.id, role=MembershipRole.OWNER),
        ])
        await session.commit()
        for obj in (org, tenant, admin):
            await session.refresh(obj)
        ids = {
            "org_id": org.id,
            "tenant_id": tenant.id,
            "tenant_username": tenant.username,
            "admin_id": admin.id,
            "admin_username": admin.username,
        }

    yield ids

    async with session_scope() as session:
        for model, pk in [
            (User, ids["tenant_id"]),
            (User, ids["admin_id"]),
            (Organization, ids["org_id"]),
        ]:
            row = await session.get(model, pk)
            if row is not None:
                await session.delete(row)
        await session.commit()


async def _login(client, username: str) -> dict[str, str]:
    resp = await client.post(
        "api/v1/login",
        data={"username": username, "password": "testpassword"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_execution_blocks_custom_component_for_tenant(client, tenant_and_admin):
    """Seed a flow directly in the DB with custom code, owned by the tenant.
    Attempt to build it via the SSE endpoint. The build must fail with the
    gate error surfaced through the stream."""
    async with session_scope() as session:
        flow = Flow(
            name=f"custom-exec-{uuid.uuid4().hex[:8]}",
            data=_flow_payload_with_custom_code(),
            user_id=tenant_and_admin["tenant_id"],
            organization_id=tenant_and_admin["org_id"],
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        flow_id = flow.id

    try:
        headers = await _login(client, tenant_and_admin["tenant_username"])
        # POST /api/v1/build/{flow_id} (or the equivalent build endpoint) starts the build.
        # The exact endpoint name on this branch is either /api/v1/build/{flow_id}/flow
        # or /api/v1/flows/{flow_id}/build — grep for @router and 'build' in
        # src/backend/base/langflow/api/v1/ to confirm the current path.
        resp = await client.post(
            f"api/v1/build/{flow_id}/flow",
            headers=headers,
            json={"inputs": {}},
        )
        # Either the POST itself 403s (if we enforce at job-create), or the
        # subsequent SSE stream emits a build error. Upstream enforces at the
        # graph-build level (inside lfx), so the POST succeeds but the stream
        # body contains "CustomComponentNotAllowedError".
        assert resp.status_code in (200, 202, 403), resp.text
        body_text = resp.text if resp.status_code == 403 else await resp.aread()
        assert "custom" in body_text.decode().lower() or resp.status_code == 403, (
            f"expected gate rejection, got: {body_text[:200]}"
        )
    finally:
        async with session_scope() as session:
            row = await session.get(Flow, flow_id)
            if row is not None:
                await session.delete(row)
                await session.commit()
```

Note: if the SSE build endpoint path differs on this branch, replace the URL. Search: `grep -nE "@router.*build" src/backend/base/langflow/api/v1/*.py`.

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py::test_execution_blocks_custom_component_for_tenant -v`

Expected: FAIL — build succeeds (or errors for an unrelated reason) because no gate is wired into the execution path yet.

- [x] **Step 3: Wire the gate into the build-vertex entry**

Edit `src/lfx/src/lfx/graph/graph/base.py`. Find the entry point that receives the flow dict before any vertex runs (usually a method like `Graph.from_flow`, `build_graph`, or the constructor — the exact name varies by branch; search `flow_data` and `def __init__` / `def from_payload` in the file). Add the gate call immediately after the flow dict is accepted and before any node is materialised:

```python
from lfx.utils.flow_validation import (
    CustomComponentNotAllowedError,
    validate_flow_components,
)

# ... inside the entry method, right after flow_data is received ...
validate_flow_components(
    flow_data,
    allow_custom=_resolve_allow_custom(),
    caller_is_platform_admin=_resolve_caller_is_platform_admin(),
)
```

The two `_resolve_*` helpers need to be threaded in:

- `allow_custom` comes from the langflow settings service. Inside lfx we cannot import langflow — instead, the caller (the langflow build endpoint in `src/backend/base/langflow/api/v1/endpoints.py` or wherever it invokes `Graph(...)`) must pass the bool in as a new constructor kwarg.
- `caller_is_platform_admin` comes from the authenticated FastAPI user and is threaded in the same way.

Concretely, extend the `Graph.__init__` (or whichever entry point in `base.py` holds `flow_data`) with two keyword arguments:

```python
def __init__(
    self,
    # ... existing args ...
    allow_custom_components: bool = False,
    caller_is_platform_admin: bool = False,
):
    # ... existing body ...
    validate_flow_components(
        flow_data,  # or whatever the local name is
        allow_custom=allow_custom_components,
        caller_is_platform_admin=caller_is_platform_admin,
    )
```

Then update the backend call site in `src/backend/base/langflow/api/v1/` that instantiates `Graph`. Search: `grep -rn "Graph(" src/backend/base/langflow/api/v1/ | head -20`. The build endpoint is the primary one. Add:

```python
from langflow.services.deps import get_settings_service

settings = get_settings_service().settings
graph = Graph(
    # ... existing args ...
    allow_custom_components=settings.allow_custom_components,
    caller_is_platform_admin=bool(
        getattr(current_user, "is_platform_admin", False)
    ),
)
```

Keep defaults `False` / `False` on the `Graph.__init__` kwargs so unit tests and CLI paths that construct Graphs directly without a user context remain safe-by-default (they will behave exactly as before: custom code is only allowed when the caller opts in).

- [x] **Step 4: Run the test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py::test_execution_blocks_custom_component_for_tenant -v`

Expected: PASS — either the POST returns 403 or the SSE body contains "custom" (the assertion accepts either).

- [x] **Step 5: Regression-run the build-path tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/ -v -k "build" --timeout 60`

Expected: all PASS. If any existing test constructs a `Graph` directly without passing `caller_is_platform_admin=True` AND relies on a custom-code fixture, it will now fail — fix those fixtures by either (a) using a shipped component in the fixture flow, or (b) passing `caller_is_platform_admin=True` explicitly.

- [x] **Step 6: Ask the user before committing, then commit**

```bash
git add src/lfx/src/lfx/graph/graph/base.py \
        src/backend/base/langflow/api/v1/endpoints.py \
        src/backend/tests/unit/api/v1/test_custom_component_gate.py
# (endpoints.py edit is the Graph() call-site update — if the build call
# is in a different file on this branch, add that file instead.)
git commit -m "$(cat <<'EOF'
feat(lfx): gate custom components at graph construction

Thread allow_custom_components + caller_is_platform_admin kwargs
through Graph() and call validate_flow_components() before any vertex
materialises. Backend build endpoint resolves both from
get_settings_service().settings and current_user.is_platform_admin.

This is the primary defence — even if create/upload/template sites
miss a payload, execution refuses to run custom code for non-admins.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Enforce at `POST /api/v1/flows` (`create_flow`)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (around line 360)
- Test: append to `src/backend/tests/unit/api/v1/test_custom_component_gate.py`

- [x] **Step 1: Append failing create-flow tests**

Append to `src/backend/tests/unit/api/v1/test_custom_component_gate.py`:

```python
async def test_create_flow_rejects_custom_component_for_tenant(client, tenant_and_admin):
    headers = await _login(client, tenant_and_admin["tenant_username"])
    resp = await client.post(
        "api/v1/flows/",
        headers=headers,
        json={
            "name": f"rejected-{uuid.uuid4().hex[:8]}",
            "data": _flow_payload_with_custom_code(),
            "folder_id": None,
        },
    )
    assert resp.status_code == 403, resp.text
    assert "custom components are not allowed" in resp.json()["detail"].lower()


async def test_create_flow_accepts_custom_component_for_platform_admin(client, tenant_and_admin):
    headers = await _login(client, tenant_and_admin["admin_username"])
    resp = await client.post(
        "api/v1/flows/",
        headers=headers,
        json={
            "name": f"admin-custom-{uuid.uuid4().hex[:8]}",
            "data": _flow_payload_with_custom_code(),
            "folder_id": None,
        },
    )
    assert resp.status_code == 201, resp.text
    # Clean up
    created_id = resp.json()["id"]
    async with session_scope() as session:
        row = await session.get(Flow, uuid.UUID(created_id))
        if row is not None:
            await session.delete(row)
            await session.commit()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py -v -k "create_flow"`

Expected: `test_create_flow_rejects_custom_component_for_tenant` FAILS (returns 201 — the vulnerability); `test_create_flow_accepts_custom_component_for_platform_admin` PASSES.

- [x] **Step 3: Wire the gate into `create_flow`**

Edit `src/backend/base/langflow/api/v1/flows.py`. At the top of `create_flow` (around line 360, after `async def create_flow(...):` and before the existing body), add:

```python
from fastapi import HTTPException
from langflow.services.deps import get_settings_service
from lfx.utils.flow_validation import (
    CustomComponentNotAllowedError,
    validate_flow_components,
)

# ... inside create_flow, first statement after signature:
try:
    validate_flow_components(
        body.data or {},
        allow_custom=get_settings_service().settings.allow_custom_components,
        caller_is_platform_admin=bool(
            getattr(current_user, "is_platform_admin", False)
        ),
    )
except CustomComponentNotAllowedError as err:
    raise HTTPException(
        status_code=403,
        detail="Custom components are not allowed on this deployment.",
    ) from err
```

If the imports at the top of `flows.py` don't already include `HTTPException`, `get_settings_service`, `CustomComponentNotAllowedError`, and `validate_flow_components`, add them. Keep the import block tidy (sorted, grouped).

Note: `body.data` is the flow dict. If this endpoint binds the request body to a different name, use that name.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py -v -k "create_flow"`

Expected: both tests PASS.

- [x] **Step 5: Regression-run flow CRUD tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_flows_*.py -v --timeout 60`

Expected: all PASS. If any test creates a flow containing custom code as a non-superuser, it will 403 — fix the fixture by using a shipped-component flow.

- [x] **Step 6: Ask the user before committing, then commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py \
        src/backend/tests/unit/api/v1/test_custom_component_gate.py
git commit -m "$(cat <<'EOF'
feat(api/flows): gate POST /api/v1/flows/ for custom components

create_flow now runs body.data through validate_flow_components(). Non-
platform-admin callers receive 403 when settings.allow_custom_components
is False and the payload contains a custom-code node. Platform admins
and deployments with the flag on continue unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Enforce at `POST /api/v1/flows/upload/` (`upload_file`)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py` (around line 913)
- Test: append to `src/backend/tests/unit/api/v1/test_custom_component_gate.py`

- [x] **Step 1: Append failing upload test**

Append to `src/backend/tests/unit/api/v1/test_custom_component_gate.py`:

```python
import io
import json


async def test_upload_flow_rejects_custom_component_for_tenant(client, tenant_and_admin):
    headers = await _login(client, tenant_and_admin["tenant_username"])
    payload = {
        "name": f"uploaded-{uuid.uuid4().hex[:8]}",
        "data": _flow_payload_with_custom_code(),
    }
    file_bytes = json.dumps(payload).encode()
    files = {"file": ("flow.json", io.BytesIO(file_bytes), "application/json")}
    resp = await client.post("api/v1/flows/upload/", headers=headers, files=files)
    assert resp.status_code == 403, resp.text
    assert "custom components are not allowed" in resp.json()["detail"].lower()


async def test_upload_flow_accepts_custom_component_for_platform_admin(client, tenant_and_admin):
    headers = await _login(client, tenant_and_admin["admin_username"])
    payload = {
        "name": f"admin-uploaded-{uuid.uuid4().hex[:8]}",
        "data": _flow_payload_with_custom_code(),
    }
    file_bytes = json.dumps(payload).encode()
    files = {"file": ("flow.json", io.BytesIO(file_bytes), "application/json")}
    resp = await client.post("api/v1/flows/upload/", headers=headers, files=files)
    assert resp.status_code == 201, resp.text
    # Clean up any flows that were created.
    created_ids = [row["id"] for row in resp.json()]
    async with session_scope() as session:
        for created_id in created_ids:
            row = await session.get(Flow, uuid.UUID(created_id))
            if row is not None:
                await session.delete(row)
        await session.commit()
```

- [x] **Step 2: Run tests to verify tenant case fails**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py -v -k "upload"`

Expected: `test_upload_flow_rejects_custom_component_for_tenant` FAILS; admin case PASSES.

- [x] **Step 3: Wire the gate into `upload_file`**

Edit `src/backend/base/langflow/api/v1/flows.py`, around line 913 in `upload_file`. The handler reads uploaded JSON and builds a list of flows. After the JSON is parsed into `flow_dicts` (or the local equivalent — read the existing body to find the variable name) and BEFORE any DB insert, add:

```python
settings = get_settings_service().settings
is_pa = bool(getattr(current_user, "is_platform_admin", False))
for flow_dict in flow_dicts:
    try:
        validate_flow_components(
            flow_dict.get("data", {}) or {},
            allow_custom=settings.allow_custom_components,
            caller_is_platform_admin=is_pa,
        )
    except CustomComponentNotAllowedError as err:
        raise HTTPException(
            status_code=403,
            detail="Custom components are not allowed on this deployment.",
        ) from err
```

The imports (`get_settings_service`, `validate_flow_components`, `CustomComponentNotAllowedError`, `HTTPException`) were already added in Task 5 — no new import lines.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py -v -k "upload"`

Expected: both PASS.

- [x] **Step 5: Ask the user before committing, then commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py \
        src/backend/tests/unit/api/v1/test_custom_component_gate.py
git commit -m "$(cat <<'EOF'
feat(api/flows): gate POST /api/v1/flows/upload/ for custom components

upload_file validates each flow_dict.data through the gate before DB
insert. Batch uploads fail atomically — if any flow in the upload
contains custom code and the caller is not a platform admin, the whole
upload is rejected (no partial commits).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Enforce at `POST /api/v1/templates` (`create_template`)

**Files:**
- Modify: `src/backend/base/langflow/api/v1/templates.py` (inside `create_template`, after `_load_source_and_blank` returns)
- Test: append to `src/backend/tests/unit/api/v1/test_custom_component_gate.py`

- [x] **Step 1: Append failing template-create test**

Append to `src/backend/tests/unit/api/v1/test_custom_component_gate.py`:

```python
async def test_create_template_rejects_custom_source_flow_for_tenant(client, tenant_and_admin):
    """A tenant's source flow containing custom code cannot be promoted to a
    template, even if the tenant has membership in the destination org."""
    async with session_scope() as session:
        source = Flow(
            name=f"src-custom-{uuid.uuid4().hex[:8]}",
            data=_flow_payload_with_custom_code(),
            user_id=tenant_and_admin["tenant_id"],
            organization_id=tenant_and_admin["org_id"],
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)
        source_id = source.id

    try:
        headers = await _login(client, tenant_and_admin["tenant_username"])
        resp = await client.post(
            "api/v1/templates",
            headers=headers,
            json={
                "name": f"custom-tmpl-{uuid.uuid4().hex[:8]}",
                "description": "should be rejected",
                "source_flow_id": str(source_id),
                "scope": "org",
                "org_id": str(tenant_and_admin["org_id"]),
                "blanked_fields": [],
                "category_ids": [],
            },
        )
        assert resp.status_code == 403, resp.text
        assert "custom components are not allowed" in resp.json()["detail"].lower()
    finally:
        async with session_scope() as session:
            row = await session.get(Flow, source_id)
            if row is not None:
                await session.delete(row)
                await session.commit()
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py::test_create_template_rejects_custom_source_flow_for_tenant -v`

Expected: FAIL. If the current code returns 403 for a different reason (e.g. `create_template` is superuser-only on this branch), make the test caller a superuser/platform-admin with a non-admin tenant org, OR adjust the test to use the admin user and force the gate to fire. Simplest: if `create_template` currently requires superuser, the gate still needs to run for superuser paths too — verify by reading the handler. The org binding shipped in commit `112e55edbe` may have relaxed who can call it; re-read the handler before adapting.

- [x] **Step 3: Wire the gate into `create_template`**

Edit `src/backend/base/langflow/api/v1/templates.py`. Find `create_template` (grep `async def create_template`). The 2026-04-22 security fix added a call to `_load_source_and_blank(...)` that returns `(blanked_nodes, edges)`. Add the gate **after** that returns and before the `Template(...)` row is constructed:

```python
from langflow.services.deps import get_settings_service
from lfx.utils.flow_validation import (
    CustomComponentNotAllowedError,
    validate_flow_components,
)

# ... existing _load_source_and_blank call:
blanked_nodes, edges = await _load_source_and_blank(
    session,
    body.source_flow_id,
    body.blanked_fields,
    required_org_id=body.org_id,
    caller_is_platform_admin=bool(
        getattr(current_user, "is_platform_admin", False)
    ),
)

# NEW:
try:
    validate_flow_components(
        {"nodes": blanked_nodes, "edges": edges},
        allow_custom=get_settings_service().settings.allow_custom_components,
        caller_is_platform_admin=bool(
            getattr(current_user, "is_platform_admin", False)
        ),
    )
except CustomComponentNotAllowedError as err:
    raise HTTPException(
        status_code=403,
        detail="Custom components are not allowed on this deployment.",
    ) from err
```

Add the imports to the existing import block at the top of the file (`HTTPException` is likely already present since the 2026-04-22 security fix uses it; only `get_settings_service` and the two lfx symbols are new).

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py::test_create_template_rejects_custom_source_flow_for_tenant -v`

Expected: PASS.

- [x] **Step 5: Regression-run the template suites**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_templates_cross_org.py src/backend/tests/unit/api/v1/test_templates_endpoints.py src/backend/tests/unit/api/v1/test_templates_create_with_categories.py -v --timeout 60`

Expected: all PASS. The 2026-04-22 security-fix suites (cross-org, scoping) must still pass — the new gate layers on top of their checks and does not interfere.

- [x] **Step 6: Run the full new-gate file**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_custom_component_gate.py -v`

Expected: all 5 tests PASS (execution + 2× create_flow + 2× upload + 1× template-create — adjust count if earlier tasks added more scenarios).

- [x] **Step 7: Ask the user before committing, then commit**

```bash
git add src/backend/base/langflow/api/v1/templates.py \
        src/backend/tests/unit/api/v1/test_custom_component_gate.py
git commit -m "$(cat <<'EOF'
feat(api/templates): gate POST /api/v1/templates for custom components

Runs the blanked source flow through validate_flow_components() after
_load_source_and_blank returns and before the Template row is built.
Layers on top of the 2026-04-22 source-flow org-binding fix (commit
112e55edbe); both checks run independently.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Add the frontend guard hook

**Files:**
- Create: `src/frontend/src/utils/customComponentGuards.ts`
- Create: `src/frontend/src/utils/__tests__/customComponentGuards.test.tsx`

- [x] **Step 1: Write the failing hook tests**

Create `src/frontend/src/utils/__tests__/customComponentGuards.test.tsx`:

```tsx
/**
 * Tests for the useCustomComponentsAllowed guard hook.
 *
 * Covers design at docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
 */
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useCustomComponentsAllowed } from "../customComponentGuards";

// Hoisted mocks — both stores/queries the hook depends on.
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: any) => selector(mockAuthState),
}));

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: () => ({ data: mockConfigData }),
}));

let mockAuthState: any;
let mockConfigData: any;

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useCustomComponentsAllowed", () => {
  beforeEach(() => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: false };
  });

  it("returns false for a tenant when the fleet flag is off", () => {
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(false);
  });

  it("returns true for a platform admin regardless of the fleet flag", () => {
    mockAuthState = { userData: { is_platform_admin: true } };
    mockConfigData = { allow_custom_components: false };
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(true);
  });

  it("returns true for any user when the fleet flag is on", () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: true };
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(true);
  });

  it("returns false when userData is null (unauthenticated boot state)", () => {
    mockAuthState = { userData: null };
    mockConfigData = { allow_custom_components: false };
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(false);
  });

  it("returns false when config has not loaded yet (data undefined)", () => {
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = undefined;
    const { result } = renderHook(() => useCustomComponentsAllowed(), { wrapper });
    expect(result.current).toBe(false);
  });
});
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/frontend && npx jest src/utils/__tests__/customComponentGuards.test.tsx`

Expected: FAIL — module `../customComponentGuards` does not exist.

- [x] **Step 3: Implement the hook**

Create `src/frontend/src/utils/customComponentGuards.ts`:

```ts
import useAuthStore from "@/stores/authStore";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";

/**
 * Returns true when the current caller is allowed to author or run
 * custom Python components. Platform admins always return true. Other
 * users return true only when the deployment has
 * LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true.
 *
 * See docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
 */
export function useCustomComponentsAllowed(): boolean {
  const isPlatformAdmin = useAuthStore(
    (state: any) => state.userData?.is_platform_admin,
  );
  const { data: config } = useGetConfig({});
  return Boolean(isPlatformAdmin || config?.allow_custom_components);
}

/**
 * Walks a parsed flow JSON and returns true if it contains at least
 * one node with a custom-code payload. Used by the flow-import UX
 * precheck (Task 11) — the backend gate is the real enforcement.
 */
export function flowJsonHasCustomComponent(flow: unknown): boolean {
  if (!flow || typeof flow !== "object") return false;
  const nodes = (flow as any)?.data?.nodes ?? (flow as any)?.nodes;
  if (!Array.isArray(nodes)) return false;
  for (const node of nodes) {
    const code = node?.data?.node?.template?.code?.value;
    if (typeof code === "string" && code.trim().length > 0) {
      // A code field with a body present is custom unless the backend
      // accepts it. We're deliberately pessimistic here — a false
      // positive at the UX layer is cheap (user sees a clear error);
      // a false negative would bypass the affordance.
      return true;
    }
  }
  return false;
}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd src/frontend && npx jest src/utils/__tests__/customComponentGuards.test.tsx`

Expected: all 5 tests PASS.

- [x] **Step 5: Type-check**

Run: `cd src/frontend && npm run type-check 2>&1 | tail -10`

Expected: no new errors.

- [x] **Step 6: Ask the user before committing, then commit**

```bash
git add src/frontend/src/utils/customComponentGuards.ts \
        src/frontend/src/utils/__tests__/customComponentGuards.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add useCustomComponentsAllowed guard hook

Single source of truth for the frontend custom-component gate. Returns
true for platform admins (regardless of fleet flag) or any caller when
allow_custom_components is true. Flows json helper for Task 11's
upload precheck. Backend is always the real enforcement boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Disable the "New Custom Component" sidebar button

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx` (around line 80)
- Modify the existing test: `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/__tests__/sidebarFooterButtons.test.tsx`

- [x] **Step 1: Read the existing component**

Run: `cat src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx`

Note the JSX around the `data-testid="sidebar-custom-component-button"` element (line 72-ish). The pattern on this branch wraps the clickable region in a button with an `onClick={...}` that calls `addComponent(customComponent, "CustomComponent")`.

- [x] **Step 2: Append a failing test to the existing test file**

Append to `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/__tests__/sidebarFooterButtons.test.tsx`:

```tsx
describe("custom-component gate", () => {
  const getGuard = () =>
    require("@/utils/customComponentGuards").useCustomComponentsAllowed;

  beforeEach(() => {
    jest.resetModules();
    jest.doMock("@/utils/customComponentGuards", () => ({
      useCustomComponentsAllowed: jest.fn(),
    }));
  });

  it("disables the New Custom Component button when guard returns false", () => {
    (getGuard() as jest.Mock).mockReturnValue(false);
    // re-require the component AFTER the mock is registered
    const Sidebar = require("../sidebarFooterButtons").default;
    const { getByTestId } = render(<Sidebar customComponent={{}} addComponent={jest.fn()} />);
    const btn = getByTestId("sidebar-custom-component-button");
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("title", expect.stringContaining("not allowed"));
  });

  it("leaves the button enabled when guard returns true", () => {
    (getGuard() as jest.Mock).mockReturnValue(true);
    const Sidebar = require("../sidebarFooterButtons").default;
    const { getByTestId } = render(<Sidebar customComponent={{}} addComponent={jest.fn()} />);
    const btn = getByTestId("sidebar-custom-component-button");
    expect(btn).not.toBeDisabled();
  });
});
```

If the existing test file uses static ESM imports at the top (which conflicts with the `jest.doMock` pattern), a simpler approach: add `jest.mock("@/utils/customComponentGuards", ...)` at the top-level of the file with a mutable return, and push/pop the return value in the two tests. Pick whichever matches the file's style.

- [x] **Step 3: Run tests to verify the new cases fail**

Run: `cd src/frontend && npx jest src/pages/FlowPage/components/flowSidebarComponent/components/__tests__/sidebarFooterButtons.test.tsx`

Expected: the two new tests FAIL — the button is not yet gated. Existing tests in the file still PASS.

- [x] **Step 4: Wire the guard into the component**

Edit `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx`. At the top with the other imports, add:

```ts
import { useCustomComponentsAllowed } from "@/utils/customComponentGuards";
```

Inside the component function, grab the flag:

```ts
const customAllowed = useCustomComponentsAllowed();
```

Find the existing button element (around line 72 on the current branch — the one with `data-testid="sidebar-custom-component-button"`). Add `disabled={!customAllowed}` and `title={customAllowed ? undefined : "Custom components are not allowed on this deployment."}` to it:

```tsx
<button
  data-testid="sidebar-custom-component-button"
  disabled={!customAllowed}
  title={customAllowed ? undefined : "Custom components are not allowed on this deployment."}
  onClick={() => {
    if (customComponent) {
      addComponent(customComponent, "CustomComponent");
    }
  }}
>
  {/* existing children */}
</button>
```

If the button is wrapped in a styled component (e.g. a shadcn `<Button>`) that uses `className` for disabled styling, use the library's standard disabled pattern (the `disabled` prop is the invariant API).

- [x] **Step 5: Run tests to verify they pass**

Run: `cd src/frontend && npx jest src/pages/FlowPage/components/flowSidebarComponent/components/__tests__/sidebarFooterButtons.test.tsx`

Expected: all tests PASS.

- [x] **Step 6: Ask the user before committing, then commit**

```bash
git add src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/sidebarFooterButtons.tsx \
        src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/__tests__/sidebarFooterButtons.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend/sidebar): gate New Custom Component button behind guard

Disabled + tooltip for non-platform-admins when
LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false. UX affordance; backend is the
real enforcement boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Force `readonly=true` on `<CodeAreaModal>` for tenants

The code editor modal already has a `readonly` prop. Callers that open the modal for the "Edit Code" action on an existing node must pass `readonly={!customAllowed}` so tenants can *view* but not *modify* a custom component's source. The `toolbar-modals.tsx` file is the node-toolbar "Edit Code" entry point.

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals.tsx`

- [x] **Step 1: Write the failing test**

Append to `src/frontend/src/utils/__tests__/customComponentGuards.test.tsx` (same file as Task 8):

```tsx
import { render } from "@testing-library/react";

// Re-use the same hoisted mocks defined at the top of this file.

describe("CodeAreaModal integration (Task 10 verification)", () => {
  it("is rendered with readonly=true when guard returns false", async () => {
    // Integration check: the file under test (toolbar-modals.tsx)
    // must pass `readonly={!customAllowed}` to CodeAreaModal. We assert
    // by mocking CodeAreaModal and inspecting the received prop.
    mockAuthState = { userData: { is_platform_admin: false } };
    mockConfigData = { allow_custom_components: false };

    const received: { readonly?: boolean } = {};
    jest.doMock("@/modals/codeAreaModal", () => ({
      __esModule: true,
      default: (props: any) => {
        received.readonly = props.readonly;
        return null;
      },
    }));
    const { default: ToolbarModals } = require(
      "@/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals",
    );
    render(<ToolbarModals data={{}} openModal="code" setOpenModal={jest.fn()} />);
    expect(received.readonly).toBe(true);
  });

  it("is rendered with readonly=false for a platform admin", async () => {
    mockAuthState = { userData: { is_platform_admin: true } };
    mockConfigData = { allow_custom_components: false };

    const received: { readonly?: boolean } = {};
    jest.resetModules();
    jest.doMock("@/modals/codeAreaModal", () => ({
      __esModule: true,
      default: (props: any) => {
        received.readonly = props.readonly;
        return null;
      },
    }));
    const { default: ToolbarModals } = require(
      "@/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals",
    );
    render(<ToolbarModals data={{}} openModal="code" setOpenModal={jest.fn()} />);
    expect(received.readonly).toBe(false);
  });
});
```

The exact shape of `ToolbarModals` props (`data`, `openModal`, `setOpenModal`) may differ on this branch. Read `toolbar-modals.tsx` before running the test; adjust the render call to satisfy required props. The assertion (`received.readonly`) is the load-bearing line.

- [x] **Step 2: Run tests to verify they fail**

Run: `cd src/frontend && npx jest src/utils/__tests__/customComponentGuards.test.tsx -t "CodeAreaModal"`

Expected: both new tests FAIL — `received.readonly` is `undefined` because `toolbar-modals.tsx` doesn't pass the prop yet.

- [x] **Step 3: Wire the guard into the toolbar modal**

Edit `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals.tsx`. At the top:

```ts
import { useCustomComponentsAllowed } from "@/utils/customComponentGuards";
```

Inside the component:

```ts
const customAllowed = useCustomComponentsAllowed();
```

Find the `<CodeAreaModal ...>` JSX element. Add/override the `readonly` prop:

```tsx
<CodeAreaModal
  // ... existing props ...
  readonly={!customAllowed}
>
```

If the component already sets `readonly` conditionally, combine: `readonly={existingCondition || !customAllowed}`.

- [x] **Step 4: Run tests to verify they pass**

Run: `cd src/frontend && npx jest src/utils/__tests__/customComponentGuards.test.tsx`

Expected: all tests in the file PASS.

- [x] **Step 5: Ask the user before committing, then commit**

```bash
git add src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/components/toolbar-modals.tsx \
        src/frontend/src/utils/__tests__/customComponentGuards.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend/toolbar): force code editor readonly for gated tenants

The Edit Code action on a node's toolbar now opens CodeAreaModal with
readonly=true for non-platform-admins when
LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false. Users can still read existing
custom-component source (useful for flow inspection) but cannot modify.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Client-side precheck on flow upload

When a tenant drops or pastes a JSON file containing a custom-code node, surface a clear inline error before the request is made. Backend still rejects — this is purely a UX affordance so the user gets feedback at drop time, not after the server round-trip.

**Files:**
- Modify: `src/frontend/src/hooks/flows/use-upload-flow.ts`

- [x] **Step 1: Write the failing test**

Create `src/frontend/src/hooks/flows/__tests__/use-upload-flow-custom-gate.test.tsx`:

```tsx
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import useUploadFlow from "../use-upload-flow";

jest.mock("@/utils/customComponentGuards", () => ({
  useCustomComponentsAllowed: () => mockAllowed,
  flowJsonHasCustomComponent: (flow: any) =>
    Boolean(flow?.data?.nodes?.[0]?.data?.node?.template?.code?.value),
}));

// Minimal mocks for the existing dependencies use-upload-flow pulls in.
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({ setErrorData: mockSetErrorData }),
}));
jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: () => ({ paste: jest.fn() }),
}));

let mockAllowed = true;

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useUploadFlow custom-component gate", () => {
  beforeEach(() => {
    mockSetErrorData.mockReset();
  });

  it("blocks upload and raises an alert when gate is active and flow contains custom code", async () => {
    mockAllowed = false;
    const { result } = renderHook(() => useUploadFlow(), { wrapper });
    const customFlow = {
      name: "x",
      data: {
        nodes: [
          {
            id: "n1",
            data: { node: { template: { code: { value: "def bad(): pass" } } } },
          },
        ],
        edges: [],
      },
    };
    const file = new File([JSON.stringify(customFlow)], "flow.json", {
      type: "application/json",
    });
    await act(async () => {
      await result.current.uploadFlows({ files: [file] });
    });
    expect(mockSetErrorData).toHaveBeenCalledWith(
      expect.objectContaining({
        title: expect.stringContaining("Custom components are not allowed"),
      }),
    );
  });

  it("allows upload when guard returns true", async () => {
    mockAllowed = true;
    const { result } = renderHook(() => useUploadFlow(), { wrapper });
    const customFlow = {
      name: "x",
      data: {
        nodes: [
          {
            id: "n1",
            data: { node: { template: { code: { value: "def ok(): pass" } } } },
          },
        ],
        edges: [],
      },
    };
    const file = new File([JSON.stringify(customFlow)], "flow.json", {
      type: "application/json",
    });
    await act(async () => {
      await result.current.uploadFlows({ files: [file] });
    });
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });
});
```

The exact hook API (`uploadFlows` vs `getFlowsFromFiles`) is what `use-upload-flow.ts` exports. Read the file to see the concrete export shape and adjust the call accordingly. The test's load-bearing assertion is `setErrorData` called with a "Custom components are not allowed" title in the gated case.

- [x] **Step 2: Run test to verify gated case fails**

Run: `cd src/frontend && npx jest src/hooks/flows/__tests__/use-upload-flow-custom-gate.test.tsx`

Expected: the "blocks upload" test FAILS — upload proceeds and `setErrorData` is never called.

- [x] **Step 3: Wire the precheck into the hook**

Edit `src/frontend/src/hooks/flows/use-upload-flow.ts`. At the top of the file, import the new helpers and the alert store:

```ts
import useAlertStore from "@/stores/alertStore";
import {
  flowJsonHasCustomComponent,
  useCustomComponentsAllowed,
} from "@/utils/customComponentGuards";
```

Inside the hook, gate the upload path. The hook returns an object with functions like `uploadFlows` and/or `getFlowsFromFiles` — pick the entry point the consuming UI calls (the `MainPage` drop handler calls `uploadFlows` per file-grep in planning). Add the check:

```ts
const useUploadFlow = () => {
  const addFlow = useAddFlow();
  const paste = useFlowStore((state) => state.paste);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const customAllowed = useCustomComponentsAllowed();

  // ... existing getFlowsFromFiles ...

  async function uploadFlows({ files }: { files: File[] }) {
    const flows = await getFlowsFromFiles({ files });
    if (!customAllowed) {
      const hasCustom = flows.some((f: any) => flowJsonHasCustomComponent(f));
      if (hasCustom) {
        setErrorData({
          title: "Custom components are not allowed on this deployment.",
          list: [
            "The uploaded flow contains custom Python component code. Contact your administrator.",
          ],
        });
        return;  // do not proceed to addFlow
      }
    }
    // ... existing per-flow add/paste logic ...
  }

  return { uploadFlows, getFlowsFromFiles };
};
```

If the file currently structures the upload path differently, preserve its shape — the only additions are (a) the guard check, (b) the early return with `setErrorData` when the guard rejects.

- [x] **Step 4: Run test to verify both cases pass**

Run: `cd src/frontend && npx jest src/hooks/flows/__tests__/use-upload-flow-custom-gate.test.tsx`

Expected: both tests PASS.

- [x] **Step 5: Type-check**

Run: `cd src/frontend && npm run type-check 2>&1 | tail -10`

Expected: no new errors.

- [x] **Step 6: Ask the user before committing, then commit**

```bash
git add src/frontend/src/hooks/flows/use-upload-flow.ts \
        src/frontend/src/hooks/flows/__tests__/use-upload-flow-custom-gate.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend/upload): client-side precheck for custom components

Drop/paste of a JSON flow containing custom-code nodes now raises an
inline alert before the backend round-trip when the caller is gated.
UX affordance only — backend POST /api/v1/flows/upload/ gate
(from an earlier commit) remains the real boundary.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Manual verification

**Goal:** exercise all three deployment postures end-to-end in a browser before merging.

- [x] **Step 1: Start the dev stack with the gate ON (default)**

From repo root:

```bash
# Unset or set to false — either works.
unset LANGFLOW_ALLOW_CUSTOM_COMPONENTS
make dev
```

Wait for the server to bind and the frontend to compile.

- [x] **Step 2: Exercise as a tenant (non-platform-admin)**

Log in as a tenant user who has at least one org membership but does NOT have `is_platform_admin=true`. Verify:

- ✅ Sidebar: "New Custom Component" button is **disabled**; hovering shows the tooltip.
- ✅ Node toolbar "Edit Code" on an existing catalog component opens `CodeAreaModal` in **read-only** mode.
- ✅ Dropping or pasting a flow JSON that contains a custom-code node produces an inline alert (red toast) with "Custom components are not allowed" text. No POST is made.
- ✅ `curl`-style direct POST to `/api/v1/flows/` with a custom-code body returns **403** with the correct detail string.
- ✅ A flow built entirely from catalog components builds and runs normally.

- [x] **Step 3: Exercise as a platform admin**

Log in as a user with `is_platform_admin=true`. Verify:

- ✅ All UI is unchanged — sidebar button enabled, code editor read/write, JSON upload accepted.
- ✅ Backend POST with a custom-code body returns **201**.
- ✅ Custom-component flows execute successfully.

- [x] **Step 4: Flip the fleet flag and verify full-permissive mode**

Restart with:

```bash
LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true make dev
```

Log in again as the **tenant** (non-admin). Verify:

- ✅ All UI unchanged — sidebar button enabled, code editor read/write, JSON upload accepted.
- ✅ Backend POST with custom-code body returns **201**.
- ✅ `GET /api/v1/config` response has `allow_custom_components: true`.

- [x] **Step 5: Record results in the plan**

Nothing to commit. If any scenario failed, treat it as a blocker and open the appropriate earlier task for revision before merging.

---

## Self-Review Checklist (already applied)

1. **Spec coverage:** all sections of the spec (gate library, setting, override, 4 call sites, guard hook, 3 gated surfaces, testing matrix, manual verification, rollout) map to tasks 1–12. Out-of-scope items from the spec are not touched.
2. **Placeholder scan:** every code block is self-contained and copy-pasteable. Two explicit placeholders remain and are flagged with "search: `...`" so the engineer can resolve them trivially — (a) the exact build-endpoint path for the SSE test (Task 4 Step 1), (b) the exact variable name for the parsed JSON inside `upload_file` (Task 6 Step 3). Both are 30-second grep tasks.
3. **Type consistency:** `validate_flow_components` takes `allow_custom: bool, caller_is_platform_admin: bool` at every call site (Tasks 1, 4, 5, 6, 7). `CustomComponentNotAllowedError` is caught and translated to HTTP 403 in every backend call site with the identical detail string. `useCustomComponentsAllowed(): boolean` is the single frontend entry point; `flowJsonHasCustomComponent(flow): boolean` is the helper. `readonly={!customAllowed}` is the CodeAreaModal prop shape.
4. **Commit hygiene:** every `git add` uses explicit paths (no `-A` / `.`). Every task ends with "Ask the user before committing" per the user's standing rule.
