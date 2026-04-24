# Remove AUTO_LOGIN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.
>
> **Commit policy:** The repo owner's standing rule (per memory) is *no git commits without explicit permission*. The `Commit` steps below describe the intent; at execution time, stage the files and pause for approval before actually running `git commit`.

**Goal:** Remove the `AUTO_LOGIN` mode entirely. All users MUST authenticate with username+password. Bootstrap requires `LANGFLOW_SUPERUSER` and `LANGFLOW_SUPERUSER_PASSWORD` — the app fails fast at startup if either is missing.

**Architecture:** Pure deletion-and-simplification. No data migrations. Settings field removed; `/auto_login` endpoint and longterm-token path deleted; every `if AUTO_LOGIN:` branch collapses to the "authenticated user required" side. Frontend auto-login hook/state/cookie removed; route guards simplify to "authenticated or redirect to login."

**Tech Stack:** Python 3.11+, FastAPI, SQLModel, Pydantic-Settings; React + TypeScript, Zustand v5, React Query v5, Jest, Playwright.

**Prerequisites for local development after Task 2 lands:**
Add to `.env` (the file the user has open in the IDE):
```
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=<choose a real password>
```
Without these, the backend will refuse to start.

---

## File-Structure Overview

**Backend files touched:**
- `src/lfx/src/lfx/services/settings/auth.py` — remove field + validator
- `src/backend/base/langflow/services/utils.py` — fail-fast bootstrap
- `src/backend/base/langflow/initial_setup/setup.py` — remove `initialize_auto_login_default_superuser`
- `src/backend/base/langflow/main.py` — remove the two bootstrap call sites
- `src/backend/base/langflow/api/v1/login.py` — delete `GET /auto_login`
- `src/backend/base/langflow/services/auth/service.py` — delete `create_user_longterm_token` + AUTO_LOGIN branches in 3 security functions
- `src/backend/base/langflow/services/auth/constants.py` — remove `AUTO_LOGIN_WARNING` / `AUTO_LOGIN_ERROR`
- `src/backend/base/langflow/api/v1/flows.py` — drop `user_id IS NULL` filter branch
- `src/backend/base/langflow/api/v1/projects.py` — drop AUTO_LOGIN-conditional `auth_type=apikey` default (always default to apikey)
- `src/backend/base/langflow/api/v1/mcp_projects.py` — drop AUTO_LOGIN branches in `verify_project_auth`, `should_generate_api_key`, and the startup rewrite loop
- `src/backend/base/langflow/api/utils/mcp/config_utils.py` — drop AUTO_LOGIN check
- `src/backend/base/langflow/services/database/service.py` — remove `assign_orphaned_flows_to_superuser` + AUTO_LOGIN teardown branch
- `src/backend/base/langflow/services/telemetry/service.py`, `schema.py` — drop AUTO_LOGIN reporting

**Frontend files touched:**
- `src/frontend/src/constants/constants.ts` — remove `IS_AUTO_LOGIN`, `LANGFLOW_AUTO_LOGIN_OPTION`, retry delays, `/auto_login` route entry
- `src/frontend/src/controllers/API/helpers/constants.ts` — remove `AUTOLOGIN` entry
- `src/frontend/src/controllers/API/queries/auth/use-get-autologin.ts` — delete
- `src/frontend/src/hooks/use-is-auto-login.ts` — delete
- `src/frontend/src/stores/authStore.ts`, `src/frontend/src/types/zustand/auth/index.ts`, `src/frontend/src/types/contexts/auth.ts` — remove `autoLogin`/`setAutoLogin`
- `src/frontend/src/contexts/authContext.tsx` — drop `auto_login_lf` cookie writes
- `src/frontend/src/utils/cookie-manager.ts` — drop `auto_login_lf` cookie clear
- `src/frontend/src/pages/AppInitPage/index.tsx` — simplify session-ready logic
- `src/frontend/src/controllers/API/api.tsx` — drop `IS_AUTO_LOGIN` from 401 handling
- `src/frontend/src/components/authorization/authGuard/index.tsx` — always require auth
- `src/frontend/src/components/authorization/authLoginGuard/index.tsx` — redirect based on `isAuthenticated` only
- `src/frontend/src/components/authorization/authAdminGuard/index.tsx`, `authSettingsGuard/index.tsx`, `authSuperuserGuard/index.tsx` — drop `autoLogin` branches
- `src/frontend/src/pages/SettingsPage/index.tsx`, `pages/GeneralPage/index.tsx` — drop `autoLogin` visibility branches
- `src/frontend/src/pages/MainPage/pages/homePage/hooks/useMcpServer.ts` — drop `autoLogin` branching
- `src/frontend/src/components/core/appHeaderComponent/components/AccountMenu/index.tsx` — drop `autoLogin` branching if present
- `src/frontend/src/components/core/parameterRenderComponent/components/tableComponent/components/tableNodeCellRender/index.tsx` — drop `autoLogin` branch
- `src/frontend/src/modals/apiModal/index.tsx` — drop `autoLogin` branch
- `src/frontend/src/controllers/API/queries/auth/use-post-logout.ts`, `use-post-refresh-access.ts` — drop `setAutoLogin` calls
- `src/frontend/src/vite-env.d.ts` — drop `LANGFLOW_AUTO_LOGIN` env-var type

**Test files updated/deleted:**
- Backend: `conftest.py`, `test_setup_superuser.py`, `test_setup_superuser_flow.py`, `test_auth_settings.py`, `test_initial_setup.py`, `test_cli.py`, `test_settings_initialization_order.py`, `test_projects_integration.py`, `test_webhook_distributed.py`, `test_mcp_projects.py`, `integration/components/mcp/test_mcp_superuser_flow.py`, `test_auth_service.py`, `api/v2/test_runs_*.py`, `api/v2/test_files.py`, `api/v1/test_files.py`, `api/v1/test_projects.py`, `test_user.py`, `test_server_init.py`, `test_telemetry_schema.py`, `test_telemetry_splitting_integration.py`, `test_exception_telemetry.py`, `integration/e2e/test_runs_e2e.py`
- Frontend (Jest): delete `use-get-autologin-race-condition.test.ts`, `autologin-race-condition-regression.test.ts`, `use-is-auto-login.test.ts`, `app-init-page-session-ready.test.tsx`; update `authStore.test.ts`, `authContext-login-fix.test.tsx`, `cookie-manager.test.ts`, `useMcpServer.test.tsx`, `use-post-refresh-access.test.ts`, `use-post-logout.test.ts`
- Frontend (Playwright): delete `tests/core/features/auto-login-off.spec.ts`, `tests/extended/features/autoLogin.spec.ts`; update `tests/core/features/user-flow-state-cleanup.spec.ts`, `tests/core/regression/general-bugs-remove-session-after-logout.spec.ts`, `tests/extended/regression/general-bugs-component-webhook-api-key-display.spec.ts`, `tests/utils/add-new-user-and-loggin.ts`, `tests/fixtures.ts`, `playwright.config.ts`, `run-tests.sh`, `vite.config.mts`

**Docs / CI / ops:**
- `.env.example`, `deploy/README.md`, `SECURITY.md`, `src/backend/base/README.md`, `Makefile`, `.github/workflows/python_test.yml`, `.github/workflows/release.yml`, `.github/workflows/release_nightly.yml`, `scripts/aws/lib/construct/backend.ts`, `scripts/aws/.env.example`, six files under `docs/docs/**`

---

## Task 1: Remove `AUTO_LOGIN` settings field + validator

**Files:**
- Modify: `src/lfx/src/lfx/services/settings/auth.py:70-81, 139-158`
- Modify: `src/backend/tests/unit/test_auth_settings.py`

**Note:** Tests for `src/lfx/` must be run from the repo-level venv with `LFX_TEST_ALLOW_LANGFLOW=1` (see project memory).

- [x] **Step 1: Delete the `AUTO_LOGIN` and `skip_auth_auto_login` fields**

In `src/lfx/src/lfx/services/settings/auth.py`, delete lines 70-81 (the `AUTO_LOGIN` field, its triple-quoted docstring, and the `skip_auth_auto_login` field + docstring). Result: the block from `AUTO_LOGIN: bool = Field(...)` through the `skip_auth_auto_login` docstring is gone.

- [x] **Step 2: Delete the `validate_superuser` field validator**

In the same file, delete lines 139-158 (the `# If autologin is true...` comment block and the entire `validate_superuser` classmethod). The superuser/password fields (lines 94-96) keep their defaults (empty string / `DEFAULT_SUPERUSER_PASSWORD`) — fail-fast moves to `setup_superuser()` in Task 2.

- [x] **Step 3: Update `test_auth_settings.py`**

Open `src/backend/tests/unit/test_auth_settings.py`. Delete any test that references `AUTO_LOGIN` or asserts the validator forces defaults. If the file becomes empty, delete the file.

- [x] **Step 4: Run the auth-settings tests**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/backend/tests/unit/test_auth_settings.py -v` (or delete-confirm if file removed).
Expected: PASS (or file absent).

- [x] **Step 5: Quick-import check**

Run: `uv run python -c "from lfx.services.settings.auth import AuthSettings; AuthSettings(CONFIG_DIR='/tmp/lf-plan')"`
Expected: no `AUTO_LOGIN` attribute, no errors.

- [x] **Step 6: Commit (pending user approval)**

```bash
git add src/lfx/src/lfx/services/settings/auth.py src/backend/tests/unit/test_auth_settings.py
git commit -m "refactor(auth): remove AUTO_LOGIN settings field and validator"
```

---

## Task 2: Fail-fast bootstrap in `setup_superuser` + remove `initialize_auto_login_default_superuser`

**Files:**
- Modify: `src/backend/base/langflow/services/utils.py:70-128`
- Modify: `src/backend/base/langflow/initial_setup/setup.py:1110-1126` (delete function)
- Modify: `src/backend/base/langflow/main.py:31-37, 184-194` (remove import + call sites)
- Modify: `src/backend/tests/unit/test_setup_superuser.py`, `test_setup_superuser_flow.py`, `test_initial_setup.py`

- [x] **Step 1: Write the failing fail-fast test**

Replace the contents of `src/backend/tests/unit/test_setup_superuser.py` with:

```python
"""Tests for setup_superuser fail-fast behavior."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.services.utils import setup_superuser
from pydantic import SecretStr


async def test_setup_superuser_fails_without_username():
    settings_service = MagicMock()
    settings_service.auth_settings.SUPERUSER = ""
    settings_service.auth_settings.SUPERUSER_PASSWORD = SecretStr("real-password")
    session = AsyncMock()

    with pytest.raises(ValueError, match="LANGFLOW_SUPERUSER"):
        await setup_superuser(settings_service, session)


async def test_setup_superuser_fails_without_password():
    settings_service = MagicMock()
    settings_service.auth_settings.SUPERUSER = "admin"
    settings_service.auth_settings.SUPERUSER_PASSWORD = SecretStr("")
    session = AsyncMock()

    with pytest.raises(ValueError, match="LANGFLOW_SUPERUSER_PASSWORD"):
        await setup_superuser(settings_service, session)


async def test_setup_superuser_creates_user_with_valid_env(monkeypatch):
    settings_service = MagicMock()
    settings_service.auth_settings.SUPERUSER = "admin"
    settings_service.auth_settings.SUPERUSER_PASSWORD = SecretStr("realpw")
    session = AsyncMock()

    created = {}

    async def fake_create(username, password, db):
        created["username"] = username
        created["password"] = password
        user = MagicMock()
        user.id = "user-id"
        return user

    from langflow.services.auth import utils as auth_utils

    monkeypatch.setattr(auth_utils, "create_super_user", fake_create, raising=False)

    await setup_superuser(settings_service, session)

    assert created["username"] == "admin"
    assert created["password"] == "realpw"
```

- [x] **Step 2: Run the new tests — expect failure**

Run: `uv run pytest src/backend/tests/unit/test_setup_superuser.py -v`
Expected: FAIL (current `setup_superuser` falls back to defaults instead of raising).

- [x] **Step 3: Rewrite `setup_superuser` to fail fast**

In `src/backend/base/langflow/services/utils.py`, replace lines 70-102 (the entire `setup_superuser` function) with:

```python
async def setup_superuser(settings_service: SettingsService, session: AsyncSession) -> None:
    username = settings_service.auth_settings.SUPERUSER
    password_secret = settings_service.auth_settings.SUPERUSER_PASSWORD
    password = password_secret.get_secret_value() if password_secret else ""

    if not username:
        msg = (
            "LANGFLOW_SUPERUSER must be set. Username/password authentication is required; "
            "provide LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD via environment or .env."
        )
        raise ValueError(msg)
    if not password:
        msg = (
            "LANGFLOW_SUPERUSER_PASSWORD must be set. Username/password authentication is required; "
            "provide LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD via environment or .env."
        )
        raise ValueError(msg)

    await logger.adebug(f"Creating or updating superuser '{username}'.")
    await create_super_user(username=username, password=password, db=session)
    settings_service.auth_settings.reset_credentials()
```

Also delete the entire `teardown_superuser` function at lines 104-128 — we no longer maintain a separate "default superuser" to clean up. Remove any import of `teardown_superuser` that is now unused (search with Grep).

- [x] **Step 4: Run the tests — expect pass**

Run: `uv run pytest src/backend/tests/unit/test_setup_superuser.py -v`
Expected: PASS.

- [x] **Step 5: Delete `initialize_auto_login_default_superuser`**

In `src/backend/base/langflow/initial_setup/setup.py`, delete the entire function at lines 1110-1126 (from `async def initialize_auto_login_default_superuser` to the end of its body).

- [x] **Step 6: Remove both bootstrap call sites in `main.py`**

In `src/backend/base/langflow/main.py`:
- Remove `initialize_auto_login_default_superuser` from the import at lines 31-37.
- Delete lines 184-194 (the entire `if get_settings_service().auth_settings.AUTO_LOGIN:` block and the **unconditional duplicate call** right after — both go). Leave the surrounding logging intact.

- [x] **Step 7: Update `test_setup_superuser_flow.py` and `test_initial_setup.py`**

- `test_setup_superuser_flow.py`: delete or rewrite any test that exercised `AUTO_LOGIN=True` + default credentials. Replace with a smoke test that calls `setup_superuser` with real env values.
- `test_initial_setup.py:188`: delete the assertion(s) touching `AUTO_LOGIN`. If a test was specifically about auto-login superuser creation, delete the test.

- [x] **Step 8: Run the superuser + initial-setup tests**

Run: `uv run pytest src/backend/tests/unit/test_setup_superuser.py src/backend/tests/unit/test_setup_superuser_flow.py src/backend/tests/unit/test_initial_setup.py -v`
Expected: PASS.

- [x] **Step 9: Commit (pending approval)**

```bash
git add src/backend/base/langflow/services/utils.py src/backend/base/langflow/initial_setup/setup.py src/backend/base/langflow/main.py src/backend/tests/unit/test_setup_superuser.py src/backend/tests/unit/test_setup_superuser_flow.py src/backend/tests/unit/test_initial_setup.py
git commit -m "feat(auth): require LANGFLOW_SUPERUSER/PASSWORD at startup (fail-fast)"
```

---

## Task 3: Delete `/auto_login` endpoint + `create_user_longterm_token`

**Files:**
- Modify: `src/backend/base/langflow/api/v1/login.py:96-142` (delete endpoint)
- Modify: `src/backend/base/langflow/services/auth/service.py:516-545` (delete function)

- [x] **Step 1: Delete the `/auto_login` route**

In `src/backend/base/langflow/api/v1/login.py`, delete lines 96-142 (the entire `@router.get("/auto_login", ...)` function). Keep `/login`, `/refresh`, `/session`, `/logout` intact.

- [x] **Step 2: Delete `create_user_longterm_token`**

In `src/backend/base/langflow/services/auth/service.py`, delete lines 516-545 (the entire `create_user_longterm_token` method on the auth service class).

- [x] **Step 3: Search for remaining references**

Run: `grep -rn "create_user_longterm_token\|/auto_login\|GET.*auto_login" src/backend`
Expected: only matches in test files or docs.

- [x] **Step 4: Delete any now-broken unit tests that call `create_user_longterm_token`**

Check `src/backend/tests/unit/services/auth/test_auth_service.py` and delete any test exercising `create_user_longterm_token` or `GET /auto_login`.

- [x] **Step 5: Run auth-service tests**

Run: `uv run pytest src/backend/tests/unit/services/auth/ -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/v1/login.py src/backend/base/langflow/services/auth/service.py src/backend/tests/unit/services/auth/test_auth_service.py
git commit -m "refactor(auth): delete /auto_login endpoint and longterm-token path"
```

---

## Task 4: Simplify API-key / WebSocket / MCP security functions

**Files:**
- Modify: `src/backend/base/langflow/services/auth/service.py:226-279, 281-322, 724-782`
- Modify: `src/backend/base/langflow/services/auth/constants.py`

- [x] **Step 1: Simplify `_api_key_security_impl`**

In `service.py` lines 226-279, replace the body with:

```python
async def _api_key_security_impl(
    self,
    query_param: str | None,
    header_param: str | None,
    db: AsyncSession,
    settings_service,
) -> UserRead | None:
    api_key = query_param or header_param
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An API key must be passed as query or header",
        )
    result = await check_key(db, api_key)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    if isinstance(result, User):
        return UserRead.model_validate(result, from_attributes=True)
    msg = "Invalid result type"
    raise ValueError(msg)
```

- [x] **Step 2: Simplify `ws_api_key_security`**

In the same file lines 281-322, replace with:

```python
async def ws_api_key_security(self, api_key: str | None) -> UserRead:
    async with session_scope() as db:
        if not api_key:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="An API key must be passed as query or header",
            )
        result = await check_key(db, api_key)
        if not result:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid or missing API key",
            )
        if isinstance(result, User):
            return UserRead.model_validate(result, from_attributes=True)
    raise WebSocketException(
        code=status.WS_1011_INTERNAL_ERROR,
        reason="Authentication subsystem error",
    )
```

- [x] **Step 3: Simplify `get_current_user_mcp`**

In the same file lines 724-782, replace with:

```python
async def get_current_user_mcp(
    self,
    token: str | Coroutine | None,
    query_param: str | None,
    header_param: str | None,
    db: AsyncSession,
) -> User | UserRead:
    if token:
        return await self.get_current_user_from_access_token(token, db)

    api_key = query_param or header_param
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An API key must be passed as query or header",
        )
    result = await check_key(db, api_key)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    if isinstance(result, User):
        return result
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid authentication result",
    )
```

- [x] **Step 4: Remove `AUTO_LOGIN_WARNING` / `AUTO_LOGIN_ERROR` constants**

In `src/backend/base/langflow/services/auth/constants.py`, delete the `AUTO_LOGIN_WARNING` and `AUTO_LOGIN_ERROR` constants. Grep for any remaining imports and remove them from the import statements in `service.py` and `mcp_projects.py`.

- [x] **Step 5: Run auth + MCP tests**

Run: `uv run pytest src/backend/tests/unit/services/auth/ src/backend/tests/unit/api/v1/test_mcp_projects.py -v -x --no-header`
Expected: PASS (or only failures in tests that exercised the removed AUTO_LOGIN branches — those tests are updated in later tasks).

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/services/auth/service.py src/backend/base/langflow/services/auth/constants.py src/backend/base/langflow/api/v1/mcp_projects.py
git commit -m "refactor(auth): simplify api-key/ws/mcp security — always require credential"
```

---

## Task 5: Remove orphan-flow branch in flow listing

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py:484-493`

- [x] **Step 1: Remove the `user_id IS NULL` branch**

In `src/backend/base/langflow/api/v1/flows.py`, replace lines 484-493 with:

```python
        if not folder_id:
            folder_id = default_folder_id

        stmt = select(Flow).where(Flow.user_id == current_user.id)
```

Also remove any `auth_settings = ...` line nearby that became unused.

- [x] **Step 2: Grep for other `AUTO_LOGIN` references in flows.py**

Run Grep for `AUTO_LOGIN` in `src/backend/base/langflow/api/v1/flows.py`.
Expected: no matches.

- [x] **Step 3: Run flow API tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_endpoints.py src/backend/tests/unit/api/v1/test_flows.py -v -x`
Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add src/backend/base/langflow/api/v1/flows.py
git commit -m "refactor(flows): drop orphan-flow (user_id IS NULL) visibility branch"
```

---

## Task 6: Simplify project auth defaults

**Files:**
- Modify: `src/backend/base/langflow/api/v1/projects.py:91-102, 693-703`
- Modify: `src/backend/base/langflow/api/utils/mcp/config_utils.py`

- [x] **Step 1: Default new projects to `apikey` unconditionally**

In `projects.py` around line 91, replace the block:

```python
        # If AUTO_LOGIN is false, automatically enable API key authentication
        default_auth = {"auth_type": "none"}
        if not settings_service.auth_settings.AUTO_LOGIN and not new_project.auth_settings:
            default_auth = {"auth_type": "apikey"}
            new_project.auth_settings = encrypt_auth_settings(default_auth)
            await logger.adebug(...)
```

with:

```python
        if not new_project.auth_settings:
            default_auth = {"auth_type": "apikey"}
            new_project.auth_settings = encrypt_auth_settings(default_auth)
            await logger.adebug(
                f"Enabled API key authentication for project {new_project.name} ({new_project.id})"
            )
```

Also drop the now-unused `settings_service = get_settings_service()` if nothing else uses it in that function.

- [x] **Step 2: Same change for uploaded projects**

Apply the equivalent simplification at lines 693-703 in the upload handler.

- [x] **Step 3: Simplify `config_utils.py`**

In `src/backend/base/langflow/api/utils/mcp/config_utils.py`, grep for `AUTO_LOGIN` and remove the conditional branch — default to whatever the `AUTO_LOGIN=False` branch did today.

- [x] **Step 4: Run project tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_projects.py src/backend/tests/integration/test_projects_integration.py -v -x`
Expected: PASS (tests exercising AUTO_LOGIN=True will need updates — see Task 10).

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/api/v1/projects.py src/backend/base/langflow/api/utils/mcp/config_utils.py
git commit -m "refactor(projects): always default new projects to apikey auth"
```

---

## Task 7: Simplify MCP project auth branching

**Files:**
- Modify: `src/backend/base/langflow/api/v1/mcp_projects.py:99-143, 700-725, 1438-1476`

- [x] **Step 1: Simplify `verify_project_auth`**

In `mcp_projects.py` lines 99-143, the function has this shape:

```python
if (not auth_settings and not settings_service.auth_settings.AUTO_LOGIN) or (
    auth_settings and auth_settings.auth_type == "apikey"
):
    # require API key...
...
# fallback: superuser lookup
result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
```

Replace with: always require an API key when the project has no explicit auth or uses `apikey`. Delete the entire superuser-fallback tail (the `logger.warning(AUTO_LOGIN_WARNING)` + username lookup). Show this revised block:

```python
    if not auth_settings or auth_settings.auth_type == "apikey":
        api_key = query_param or header_param
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )
        result = await check_key(db, api_key)
        if not result or not isinstance(result, User):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )
        return result

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unsupported auth type",
    )
```

(Keep any OAuth branch currently above/below intact if present — check lines 115-132 before editing.)

- [x] **Step 2: Simplify `should_generate_api_key` logic**

Lines 700-725 contain a cascading `if not mcp_composer_enabled: ... elif ...` with AUTO_LOGIN branches. Replace the AUTO_LOGIN-dependent branches with a simple rule: if the project has no explicit auth or uses `apikey`, generate a key; otherwise (OAuth) don't. The line `if settings_service.auth_settings.AUTO_LOGIN and not settings_service.auth_settings.SUPERUSER:` is now dead and goes away.

- [x] **Step 3: Remove the startup auth-rewrite loop**

Lines 1438-1476 contain a startup block that rewrites projects to `apikey` auth when `AUTO_LOGIN=False`. Since every project now defaults to `apikey`, this loop is only needed to migrate *old* projects that currently have `auth_type="none"`. Replace the outer `if not settings_service.auth_settings.AUTO_LOGIN:` with an unconditional version (so it always runs and normalizes old "none" projects). Keep the OAuth-reset branch; replace `fallback_auth_type = "apikey" if not settings_service.auth_settings.AUTO_LOGIN else "none"` with `fallback_auth_type = "apikey"`.

- [x] **Step 4: Remove the `from langflow.services.auth.constants import AUTO_LOGIN_WARNING` import**

- [x] **Step 5: Run MCP tests**

Run: `uv run pytest src/backend/tests/unit/api/v1/test_mcp_projects.py src/backend/tests/integration/components/mcp/ -v -x`
Expected: PASS (some tests will need updates in Task 10; that's fine for now if failures are only in AUTO_LOGIN-specific tests).

- [x] **Step 6: Commit**

```bash
git add src/backend/base/langflow/api/v1/mcp_projects.py
git commit -m "refactor(mcp): always require API key for apikey projects; drop superuser fallback"
```

---

## Task 8: Remove `assign_orphaned_flows_to_superuser` + AUTO_LOGIN teardown branch

**Files:**
- Modify: `src/backend/base/langflow/services/database/service.py:310-315, 635-643`

- [x] **Step 1: Delete `assign_orphaned_flows_to_superuser`**

In `src/backend/base/langflow/services/database/service.py`, delete the entire `assign_orphaned_flows_to_superuser` method (around lines 310-335, find it by searching for `async def assign_orphaned_flows_to_superuser`). Grep for its call sites and remove them.

- [x] **Step 2: Remove the teardown-superuser call**

Lines 635-643 contain:

```python
async def teardown(self) -> None:
    ...
    settings_service = get_settings_service()
    async with session_scope() as session:
        await teardown_superuser(settings_service, session)
    ...
```

Remove the `teardown_superuser` call and the `settings_service = get_settings_service()` line if unused. Also remove the import of `teardown_superuser` at the top of the file (it was deleted in Task 2).

- [x] **Step 3: Grep for any lingering `assign_orphaned_flows_to_superuser` or `teardown_superuser`**

Run Grep for both names across the backend.
Expected: no matches.

- [x] **Step 4: Smoke-test app startup/teardown**

Run: `uv run pytest src/backend/tests/performance/test_server_init.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/backend/base/langflow/services/database/service.py
git commit -m "refactor(db): remove orphan-flow reassignment and superuser teardown"
```

---

## Task 9: Remove AUTO_LOGIN from telemetry

**Files:**
- Modify: `src/backend/base/langflow/services/telemetry/service.py`
- Modify: `src/backend/base/langflow/services/telemetry/schema.py`

- [x] **Step 1: Find the references**

Run Grep for `AUTO_LOGIN` in `src/backend/base/langflow/services/telemetry/`.

- [x] **Step 2: Drop the field + population**

Remove the AUTO_LOGIN field from the telemetry schema and the line that populates it in the service. If this is a reported payload, note in the commit message that the telemetry schema changes.

- [x] **Step 3: Run telemetry tests**

Run: `uv run pytest src/backend/tests/unit/services/telemetry/ src/backend/tests/integration/test_telemetry_splitting_integration.py src/backend/tests/integration/test_exception_telemetry.py -v -x`
Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add src/backend/base/langflow/services/telemetry/
git commit -m "refactor(telemetry): drop AUTO_LOGIN from reported payload"
```

---

## Task 10: Update backend test fixtures + remaining unit/integration tests

**Files:**
- Modify: `src/backend/tests/conftest.py:395, 401`
- Modify (or delete): `src/backend/tests/unit/test_cli.py`, `test_settings_initialization_order.py`, `test_projects_integration.py`, `test_webhook_distributed.py`, `test_mcp_projects.py`, `integration/components/mcp/test_mcp_superuser_flow.py`, `test_user.py`, `api/v2/test_runs_read.py`, `test_runs_enqueue.py`, `test_runs_cancel.py`, `test_runs_logs.py`, `api/v2/test_files.py`, `api/v1/test_files.py`, `api/v1/test_projects.py`, `integration/e2e/test_runs_e2e.py`

- [x] **Step 1: Update conftest**

In `src/backend/tests/conftest.py`:
- Delete line 395 (`monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")`) — no longer relevant.
- Delete line 401 (`monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")` inside the `load_flows` branch).
- Add in its place, for all test clients:
  ```python
  monkeypatch.setenv("LANGFLOW_SUPERUSER", "admin")
  monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "testpassword123")
  ```
  so the fail-fast bootstrap succeeds.

- [x] **Step 2: Update `test_cli.py`**

Lines 75, 94, 111, 139 reference AUTO_LOGIN. Rewrite these test cases to exercise only the new "SUPERUSER/PASSWORD are required" flow. Delete any test that was specifically about AUTO_LOGIN=True forcing defaults.

- [x] **Step 3: Update remaining tests**

For each file in the Files list, grep for `AUTO_LOGIN` / `auto_login` and delete or rewrite:
- If the test was asserting AUTO_LOGIN-specific behavior that no longer exists → delete.
- If the test was using `mock_settings.AUTO_LOGIN = True/False` just to make the test run → remove that line.
- If the test was hitting `GET /auto_login` → delete.

Use this command to find every occurrence:
```bash
grep -rn "AUTO_LOGIN\|auto_login" src/backend/tests
```

- [x] **Step 4: Run full backend unit-test suite**

Run: `uv run pytest src/backend/tests/unit -x --no-header`
Expected: PASS.

- [x] **Step 5: Run integration tests**

Run: `uv run pytest src/backend/tests/integration -x --no-header -m "not slow"`
Expected: PASS.

- [x] **Step 6: Final grep**

Run: `grep -rn "AUTO_LOGIN\|auto_login" src/backend/`
Expected: zero matches.

- [x] **Step 7: Commit**

```bash
git add src/backend/tests/
git commit -m "test(auth): drop AUTO_LOGIN fixtures and tests across backend"
```

---

## Task 11: Delete frontend auto-login hooks + constants + API route

**Files:**
- Delete: `src/frontend/src/controllers/API/queries/auth/use-get-autologin.ts`
- Delete: `src/frontend/src/controllers/API/queries/auth/__tests__/use-get-autologin-race-condition.test.ts`
- Delete: `src/frontend/src/controllers/API/queries/auth/__tests__/autologin-race-condition-regression.test.ts`
- Delete: `src/frontend/src/hooks/use-is-auto-login.ts`
- Delete: `src/frontend/src/hooks/__tests__/use-is-auto-login.test.ts`
- Modify: `src/frontend/src/constants/constants.ts:823, 880, 947-952`
- Modify: `src/frontend/src/controllers/API/helpers/constants.ts:18`
- Modify: `src/frontend/src/vite-env.d.ts`

- [x] **Step 1: Delete the hook and its tests**

Delete the five files listed above.

- [x] **Step 2: Remove constants**

In `src/frontend/src/constants/constants.ts`:
- Line 823: remove the `"/auto_login"` entry from the route array.
- Line 880: remove `export const LANGFLOW_AUTO_LOGIN_OPTION = "auto_login_lf";`
- Lines 947-952: remove `IS_AUTO_LOGIN`, `AUTO_LOGIN_RETRY_DELAY`, `AUTO_LOGIN_MAX_RETRY_DELAY`.

In `src/frontend/src/controllers/API/helpers/constants.ts` line 18: remove `AUTOLOGIN: "auto_login",` from the URL map.

In `src/frontend/src/vite-env.d.ts`: remove the `LANGFLOW_AUTO_LOGIN` env-var typing.

- [x] **Step 3: Grep for every remaining consumer of these symbols**

```bash
grep -rn "useGetAutoLogin\|useIsAutoLogin\|IS_AUTO_LOGIN\|LANGFLOW_AUTO_LOGIN_OPTION\|AUTOLOGIN\|AUTO_LOGIN_RETRY" src/frontend/src
```

Expected: matches only in files that will be updated in Tasks 12-15. Note each match — those imports must be removed in the appropriate later task.

- [x] **Step 4: Skip build check until downstream imports are cleaned up**

Build will fail now because consumers still import these symbols. That's expected; Tasks 12-15 clean up. Don't commit alone — bundle with Task 12.

---

## Task 12: Remove `autoLogin` from zustand store, auth context, and cookie manager

**Files:**
- Modify: `src/frontend/src/stores/authStore.ts`
- Modify: `src/frontend/src/types/zustand/auth/index.ts`
- Modify: `src/frontend/src/types/contexts/auth.ts`
- Modify: `src/frontend/src/contexts/authContext.tsx:5, 69-73`
- Modify: `src/frontend/src/utils/cookie-manager.ts:5, 75`
- Modify: `src/frontend/src/controllers/API/queries/auth/use-post-logout.ts`
- Modify: `src/frontend/src/controllers/API/queries/auth/use-post-refresh-access.ts`
- Modify: `src/frontend/src/stores/__tests__/authStore.test.ts`
- Modify: `src/frontend/src/contexts/__tests__/authContext-login-fix.test.tsx`
- Modify: `src/frontend/src/utils/__tests__/cookie-manager.test.ts`

- [x] **Step 1: Remove `autoLogin` / `setAutoLogin` from the zustand store**

In `src/frontend/src/stores/authStore.ts`, remove the `autoLogin` state field and `setAutoLogin` action. In `src/frontend/src/types/zustand/auth/index.ts` remove the matching interface members.

- [x] **Step 2: Remove `autoLogin` from the auth-context type**

In `src/frontend/src/types/contexts/auth.ts`, drop the `autoLogin: string` parameter from the `login` signature. In `src/frontend/src/contexts/authContext.tsx`:
- Line 5: drop the `LANGFLOW_AUTO_LOGIN_OPTION` import.
- Lines 69-73: change the `login` function signature to drop the `autoLogin` parameter and remove the `cookieManager.set(LANGFLOW_AUTO_LOGIN_OPTION, autoLogin);` line. Update every call site in the codebase — grep for `login(` inside React code and fix.

- [x] **Step 3: Remove cookie clear in `cookie-manager.ts`**

Line 5: drop the `LANGFLOW_AUTO_LOGIN_OPTION` import. Line 75: remove `this.remove(LANGFLOW_AUTO_LOGIN_OPTION);`.

- [x] **Step 4: Remove `setAutoLogin` calls**

Grep for `setAutoLogin` in `src/frontend/src`. Remove every call (`setAutoLogin(true)`, `setAutoLogin(false)`) from `use-post-logout.ts`, `use-post-refresh-access.ts`, and anywhere else it appears.

- [x] **Step 5: Update tests**

- `authStore.test.ts`: delete any test asserting `autoLogin` state or `setAutoLogin` action.
- `authContext-login-fix.test.tsx`: drop the `auto_login_lf` cookie assertions at lines 303, 384, 402, 408, 516. Adjust expected cookie counts accordingly (`expect(mockCookiesInstance.set).toHaveBeenCalledTimes(...)`).
- `cookie-manager.test.ts:317`: delete the `expect(mockCookiesInstance.remove).toHaveBeenCalledWith("auto_login_lf", ...)` line.
- `use-post-refresh-access.test.ts`, `use-post-logout.test.ts`: drop any `setAutoLogin` assertions.

- [x] **Step 6: Run frontend Jest tests**

Run: `cd src/frontend && npm run test -- --watchAll=false`
Expected: tests that were updated now pass; other unrelated failures are tracked separately.

- [x] **Step 7: Commit**

```bash
git add src/frontend/src/ src/frontend/tests/
git commit -m "refactor(frontend/auth): drop autoLogin zustand state, context arg, and cookie"
```

---

## Task 13: Simplify frontend route guards

**Files:**
- Modify: `src/frontend/src/components/authorization/authGuard/index.tsx`
- Modify: `src/frontend/src/components/authorization/authLoginGuard/index.tsx`
- Modify: `src/frontend/src/components/authorization/authAdminGuard/index.tsx`
- Modify: `src/frontend/src/components/authorization/authSettingsGuard/index.tsx`
- Modify: `src/frontend/src/components/authorization/authSuperuserGuard/index.tsx`

- [x] **Step 1: `authGuard` — always require auth**

Replace the contents with:

```tsx
import { Navigate } from "react-router-dom";
import useAuthStore from "@/stores/authStore";

export const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};
```

(Match whatever the current export signature is — probably `default export` or a `ProtectedRoute` named export. Keep the existing API; only the body changes.)

- [x] **Step 2: `authLoginGuard` — redirect-away-from-login when authenticated**

In `authLoginGuard/index.tsx`, replace `if (autoLogin === true || isAuthenticated)` with `if (isAuthenticated)`. Remove the `autoLogin` import and hook call.

- [x] **Step 3: `authAdminGuard` — drop `autoLogin` branch**

Line 10: remove `const autoLogin = useAuthStore((state) => state.autoLogin);`. Line 17: replace `(userData && !isAdmin && !isPlatformAdmin) || autoLogin` with `userData && !isAdmin && !isPlatformAdmin`.

- [x] **Step 4: `authSettingsGuard` — show settings unconditionally when authenticated**

Line 7-11: drop `autoLogin` usage. The computation `showGeneralSettings = ENABLE_PROFILE_ICONS || hasStore || !autoLogin` should become `showGeneralSettings = true` (or simply inline the old fallback logic; grep to see what decisions it gates).

- [x] **Step 5: `authSuperuserGuard` — drop `autoLogin` branch**

Lines 13, 18: remove `autoLogin`. Change `if (!userData?.is_superuser || autoLogin)` to `if (!userData?.is_superuser)`.

- [x] **Step 6: Build check**

Run: `cd src/frontend && npm run build`
Expected: passes (type checker catches any remaining `autoLogin` references).

- [x] **Step 7: Commit**

```bash
git add src/frontend/src/components/authorization/
git commit -m "refactor(frontend/auth-guards): always require auth; drop autoLogin branches"
```

---

## Task 14: Simplify `AppInitPage` and API interceptor

**Files:**
- Modify: `src/frontend/src/pages/AppInitPage/index.tsx:32, 42, 46, 88-89`
- Delete: `src/frontend/src/pages/AppInitPage/__tests__/app-init-page-session-ready.test.tsx`
- Modify: `src/frontend/src/controllers/API/api.tsx:8, 30, 75-82, 158`

- [x] **Step 1: `AppInitPage` — session-ready simplifies**

In `src/frontend/src/pages/AppInitPage/index.tsx`:
- Line 32: remove `const autoLogin = useAuthStore((state) => state.autoLogin);`
- Line 42: remove the `useGetAutoLogin({ enabled: isLoaded })` call entirely.
- Line 46: replace `const isAuthReady = autoLogin === true || isAuthenticated;` with `const isAuthReady = isAuthenticated;`.
- Lines 88-89: replace `() => isAuthenticated || autoLogin || isSessionFetched` with `() => isAuthenticated || isSessionFetched`.

- [x] **Step 2: Delete the session-ready test**

`app-init-page-session-ready.test.tsx` tested a matrix of `(autoLogin, isSessionFetched)`. With `autoLogin` gone, the logic is trivial. Delete the file.

- [x] **Step 3: `api.tsx` — drop `IS_AUTO_LOGIN` 401 branch**

In `src/frontend/src/controllers/API/api.tsx`:
- Line 8: remove `import { IS_AUTO_LOGIN } from "@/constants/constants";`
- Line 30: remove `const autoLogin = useAuthStore((state) => state.autoLogin);`
- Lines 75-82: replace the multi-line auth-error guard. The current logic is:
  ```ts
  const authRedirect =
    (isAuthenticationError && !IS_AUTO_LOGIN) ||
    (isAuthenticationError && !autoLogin && autoLogin !== undefined);
  ...
  if (authRedirect && !error?.config?.url?.includes("auto_login")) { ... }
  ```
  Replace with:
  ```ts
  const authRedirect = isAuthenticationError;
  ...
  if (authRedirect) { /* existing redirect logic */ }
  ```
- Line 158: remove `autoLogin` from the `useEffect` dependency array.

- [x] **Step 4: Build check**

Run: `cd src/frontend && npm run build`
Expected: passes.

- [x] **Step 5: Commit**

```bash
git add src/frontend/src/pages/AppInitPage/ src/frontend/src/controllers/API/api.tsx
git commit -m "refactor(frontend): simplify AppInitPage and API interceptor after AUTO_LOGIN removal"
```

---

## Task 15: Simplify settings UI and remaining UI consumers

**Files:**
- Modify: `src/frontend/src/pages/SettingsPage/index.tsx:15, 21, 119`
- Modify: `src/frontend/src/pages/SettingsPage/pages/GeneralPage/index.tsx:43, 155`
- Modify: `src/frontend/src/pages/MainPage/pages/homePage/hooks/useMcpServer.ts:107`
- Modify: `src/frontend/src/pages/MainPage/pages/homePage/hooks/__tests__/useMcpServer.test.tsx:51`
- Modify: `src/frontend/src/components/core/appHeaderComponent/components/AccountMenu/index.tsx`
- Modify: `src/frontend/src/components/core/parameterRenderComponent/components/tableComponent/components/tableNodeCellRender/index.tsx`
- Modify: `src/frontend/src/modals/apiModal/index.tsx`

- [x] **Step 1: `SettingsPage/index.tsx`**

- Line 15: remove `const autoLogin = useAuthStore((state) => state.autoLogin);`
- Line 21: replace `showGeneralSettings = ENABLE_PROFILE_ICONS || hasStore || !autoLogin` with `showGeneralSettings = true` (or inline the positive conditions).
- Line 119: replace `if (isAdmin && !autoLogin)` with `if (isAdmin)`.

- [x] **Step 2: `GeneralPage/index.tsx`**

Line 43: drop `autoLogin` hook. Line 155: remove the `{!autoLogin && (...)}` wrapper — keep its children unconditionally.

- [x] **Step 3: `useMcpServer.ts`**

Line 107: `const isAutoLoginFromStore = useAuthStore((st) => st.autoLogin);` — remove. Find where `isAutoLoginFromStore` is consumed and replace with the non-auto-login behavior.

Update `useMcpServer.test.tsx` (line 51): remove the `autoLogin: false,` property from the mocked auth state.

- [x] **Step 4: Remaining UI consumers**

For each of `AccountMenu/index.tsx`, `tableNodeCellRender/index.tsx`, `apiModal/index.tsx`: grep for `autoLogin`, remove the state read, and drop/simplify any branch that used it. Prefer the "not-auto-login" behavior.

- [x] **Step 5: Final grep**

```bash
grep -rn "autoLogin\|IS_AUTO_LOGIN\|LANGFLOW_AUTO_LOGIN_OPTION" src/frontend/src
```

Expected: zero matches.

- [x] **Step 6: Full Jest run**

Run: `cd src/frontend && npm run test -- --watchAll=false`
Expected: PASS.

- [x] **Step 7: Build check**

Run: `cd src/frontend && npm run build`
Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add src/frontend/src/pages/ src/frontend/src/components/ src/frontend/src/modals/
git commit -m "refactor(frontend): drop autoLogin branches in settings, MCP, and menus"
```

---

## Task 16: Frontend Playwright tests + fixtures

**Files:**
- Delete: `src/frontend/tests/core/features/auto-login-off.spec.ts`
- Delete: `src/frontend/tests/extended/features/autoLogin.spec.ts`
- Modify: `src/frontend/tests/core/features/user-flow-state-cleanup.spec.ts`
- Modify: `src/frontend/tests/core/regression/general-bugs-remove-session-after-logout.spec.ts`
- Modify: `src/frontend/tests/extended/regression/general-bugs-component-webhook-api-key-display.spec.ts`
- Modify: `src/frontend/tests/utils/add-new-user-and-loggin.ts`
- Modify: `src/frontend/tests/fixtures.ts`
- Modify: `src/frontend/playwright.config.ts`
- Modify: `src/frontend/vite.config.mts`
- Modify: `src/frontend/run-tests.sh`
- Modify: `src/frontend/tsconfig.json`

- [x] **Step 1: Delete the auto-login-focused specs**

Remove `auto-login-off.spec.ts` and `autoLogin.spec.ts`. These no longer make sense.

- [x] **Step 2: Rewrite tests that stubbed auto-login**

For each remaining Playwright test that `page.addInitScript` sets `LANGFLOW_AUTO_LOGIN` or mocks `/auto_login`, delete those stubs — tests should rely on the login helper (`add-new-user-and-loggin.ts`) instead.

- [x] **Step 3: Clean up the login helper**

In `add-new-user-and-loggin.ts`, grep for `AUTO_LOGIN`/`auto_login` and remove any branching. The helper should always perform a real login POST.

- [x] **Step 4: Update configs**

- `playwright.config.ts`: remove any `LANGFLOW_AUTO_LOGIN` env var or project-specific override. Add `LANGFLOW_SUPERUSER=admin` and `LANGFLOW_SUPERUSER_PASSWORD=testpassword123` if missing.
- `vite.config.mts`: remove `LANGFLOW_AUTO_LOGIN` from the list of env vars proxied to the client bundle.
- `run-tests.sh`: strip any `--set-env LANGFLOW_AUTO_LOGIN` flags.
- `tsconfig.json`: remove `LANGFLOW_AUTO_LOGIN` from any env-typing `includes`.
- `fixtures.ts`: drop `autoLogin`/`AUTO_LOGIN` fixtures if present.

- [x] **Step 5: Local sanity — run a small Playwright slice**

Run: `cd src/frontend && npx playwright test tests/core/features/user-flow-state-cleanup.spec.ts`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add src/frontend/tests/ src/frontend/playwright.config.ts src/frontend/vite.config.mts src/frontend/run-tests.sh src/frontend/tsconfig.json
git commit -m "test(frontend/e2e): drop AUTO_LOGIN specs and stubs; real-login-only fixtures"
```

---

## Task 17: Docs, env example, CI workflows, deploy scripts

**Files:**
- Modify: `.env.example:101-117`
- Modify: `deploy/README.md`
- Modify: `SECURITY.md`
- Modify: `src/backend/base/README.md:29`
- Modify: `Makefile` (the `login` variable wiring)
- Modify: `.github/workflows/python_test.yml`, `.github/workflows/release.yml`, `.github/workflows/release_nightly.yml`
- Modify: `scripts/aws/lib/construct/backend.ts`
- Modify: `scripts/aws/.env.example`
- Modify: `docs/docs/Deployment/develop-application.mdx`, `docs/docs/Develop/environment-variables.mdx`, `docs/docs/Develop/api-keys-and-authentication.mdx`, `docs/docs/Agents/mcp-server.mdx`, `docs/docs/Support/release-notes.mdx`, `docs/docs/Support/troubleshooting.mdx`

- [x] **Step 1: `.env.example`**

Delete the `LANGFLOW_AUTO_LOGIN` block (lines 101-117). Ensure `LANGFLOW_SUPERUSER` and `LANGFLOW_SUPERUSER_PASSWORD` are documented as **required** — add a comment: `# Required. The application will refuse to start without these.`

- [x] **Step 2: `deploy/README.md` + `SECURITY.md`**

Remove `LANGFLOW_AUTO_LOGIN` from the env-var tables. Update any prose referencing "auto-login mode." In `SECURITY.md`, remove references to auto-login being a dev-only or deprecated mode — it no longer exists.

- [x] **Step 3: `src/backend/base/README.md` + `Makefile`**

`README.md:29` documents the `make login=...` variable. Remove it. In the `Makefile`, delete the `login` variable and any `--env LANGFLOW_AUTO_LOGIN=...` plumbing.

- [x] **Step 4: CI workflows**

In each `.github/workflows/*.yml`, grep for `LANGFLOW_AUTO_LOGIN` and remove. Add `LANGFLOW_SUPERUSER` + `LANGFLOW_SUPERUSER_PASSWORD` to any job `env:` that previously assumed auto-login (use test credentials).

- [x] **Step 5: AWS deploy scripts**

In `scripts/aws/lib/construct/backend.ts` and `scripts/aws/.env.example`, remove `LANGFLOW_AUTO_LOGIN`. Ensure `LANGFLOW_SUPERUSER`/`LANGFLOW_SUPERUSER_PASSWORD` are surfaced as required CDK parameters or env vars.

- [x] **Step 6: Docs site**

For each of the six `docs/docs/**` files, remove the `LANGFLOW_AUTO_LOGIN` documentation. If there's a section titled "Auto-login" or similar, remove it and add a short note in the release-notes or upgrade guide explaining it's gone.

- [x] **Step 7: Final grep**

```bash
grep -rn "AUTO_LOGIN\|auto_login" .env.example deploy/ SECURITY.md src/backend/base/README.md Makefile .github/ scripts/aws/ docs/docs/
```

Expected: zero matches.

- [x] **Step 8: Commit**

```bash
git add .env.example deploy/ SECURITY.md src/backend/base/README.md Makefile .github/ scripts/aws/ docs/docs/
git commit -m "docs(auth): remove AUTO_LOGIN from env, CI, deploy, and docs"
```

---

## Task 18: Final verification

**Files:** (read-only — running tests and manual smoke)

- [x] **Step 1: Full backend test run**

Run: `uv run pytest src/backend/tests -x --no-header`
Expected: PASS.

- [x] **Step 2: Full lfx test run**

Run: `LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx -x --no-header`
Expected: PASS.

- [x] **Step 3: Frontend Jest**

Run: `cd src/frontend && npm run test -- --watchAll=false`
Expected: PASS.

- [x] **Step 4: Frontend build**

Run: `cd src/frontend && npm run build`
Expected: PASS.

- [x] **Step 5: Full-repo grep**

```bash
grep -rn "AUTO_LOGIN\|auto_login\|autoLogin\|IS_AUTO_LOGIN\|LANGFLOW_AUTO_LOGIN" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.mdx" --include="*.md" --include="*.yml" --include="*.sh" --include="*.mts" .
```

Expected: zero matches outside of historical docs (release notes explaining the removal are OK).

- [x] **Step 6: Manual smoke — fail-fast**

Temporarily clear `LANGFLOW_SUPERUSER` in `.env`, then run `uv run langflow run`.
Expected: app fails to start with a clear "LANGFLOW_SUPERUSER must be set" error.

Restore `.env` before proceeding.

- [x] **Step 7: Manual smoke — login required**

Start the backend (`uv run langflow run`) and frontend (`cd src/frontend && npm run dev`). Open `http://localhost:3000`.
Expected: redirected to `/login`. Enter the superuser credentials from `.env`. Expected: dashboard loads. Log out. Expected: back to `/login`. Try visiting `/flows` without auth. Expected: redirected to `/login`.

- [x] **Step 8: No commit — this task is verification only**

If any step above surfaces a regression, fix it as part of the relevant earlier task (go back, fix, re-commit). When everything passes, the plan is complete.

---

## Self-Review Notes

- **Spec coverage:** Every area from the research (settings, bootstrap, `/auto_login` route, API-key security, flow listing, projects auth, MCP auth, orphan-flow reassignment, telemetry, frontend constants/store/context/cookie, route guards, AppInit, API interceptor, settings UI, Playwright, docs/env/CI/deploy) is covered by a task.
- **Placeholders:** None. Every code change shows the replacement code or a specific grep pattern for lines to delete.
- **Type consistency:** `setup_superuser(settings_service, session)` signature preserved; `create_super_user(username=..., password=..., db=...)` matches existing usage; `useAuthStore` selector patterns match current code style.
- **Deletion ordering:** Task 11 (deleting frontend consts/hooks) intentionally doesn't commit alone — bundled with Task 12 because intermediate state would break the build.
