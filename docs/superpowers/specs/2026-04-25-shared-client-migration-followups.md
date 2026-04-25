# shared_client Migration Followups

## Status as of 2026-04-25

- `shared_client` fixture exists in `src/backend/tests/conftest.py`.
- Validated on `src/backend/tests/unit/api/v1/test_monitor_auth.py` (Task C.4):
  wallclock dropped from 57.71s to 30.94s (1.86x speedup) for 9 tests total
  (6 migrated to `shared_client`, 3 remain on `client`).
- Existing function-scoped `client` fixture remains as-is for tests using
  the `noclient` or `load_flows` keywords.

## Architecture: what was built

- `shared_app_db_path` (session-scoped sync): one on-disk sqlite file for the
  whole pytest session.
- `shared_app_env` (session-scoped sync): sets `LANGFLOW_DATABASE_URL` etc.
  env vars once.
- `shared_app` (session-scoped async, `loop_scope="session"`): calls
  `create_app()` + `LifespanManager` once. Requires
  `@pytest_asyncio.fixture(scope="session", loop_scope="session")`.
- `shared_client` (function-scoped async, `loop_scope="session"`): yields an
  `AsyncClient` against the shared app. NO per-test rollback (see blocker
  below).

## SAVEPOINT rollback blocker

**Root cause:** `shared_app` runs on the session event loop. `shared_client`
is function-scoped and in pytest-asyncio 1.x with
`asyncio_default_fixture_loop_scope=function`, test coroutines run on the
function event loop. An `AsyncEngine` is bound to a specific event loop —
SQLAlchemy async connections cannot cross event-loop boundaries.

Attempting to `await engine.connect()` from the function loop while the
engine is bound to the session loop causes `SAWarning: non-checked-in
connection` and `AttributeError` on fixture value propagation.

**Fix path (two options):**

1. **Upgrade pytest-asyncio to 0.24+** and set
   `asyncio_default_fixture_loop_scope = session` in `pyproject.toml`. This
   makes all async fixtures share one event loop, eliminating the cross-loop
   issue. The SAVEPOINT pattern then works as described in the plan.

2. **Use a synchronous HTTPX client** for `shared_client` with a synchronous
   SQLAlchemy SAVEPOINT. `httpx.Client` (sync) + `with engine.sync_engine.connect()`
   avoids the async event-loop crossing entirely.

## Mixed-scope teardown warning

When a file mixes `shared_client` tests and `client` tests (different event
loop scopes), the last `client`-based test's teardown triggers:

```
Task exception was never retrieved
asyncio:base_events.py:1833
```

This is a cosmetic warning — all tests PASS, but the shared app's session-loop
is shutting down while the function-loop's `active_user` cleanup runs. To avoid
it, keep `shared_client` tests in separate files from `client` tests.

## Required follow-ups before mass migration

### 1. Resolve SAVEPOINT blocker (pick one option above)

Without per-test rollback, `shared_client` tests must be read-only or clean
up their own writes. Read-only auth/security tests are ideal candidates now.

### 2. Add `shared_*` variants of fixtures that depend on `client`

The following fixtures in `conftest.py` take `client` as a dependency
and therefore force any test using them onto the slow function-scoped path:

- `test_user` (line ~434)
- `active_user` (line ~448)
- `active_super_user` (line ~492)
- `logged_in_headers` (line ~483)
- `logged_in_headers_super_user` (line ~524)
- `logged_in_headers_platform_admin` (line ~554)

Add `shared_test_user`, `shared_active_user`, `shared_active_super_user`,
`shared_logged_in_headers` etc. variants. Each takes `shared_client` instead
of `client`. Body is otherwise identical, but cleanup must happen within the
rolled-back transaction (once SAVEPOINT is implemented) so it's free.

### 3. Segregate migrated files

Do NOT mix `shared_client` and `client` in the same test file until the
teardown issue is resolved. Migration candidates for first wave:

- All auth/security tests that only check status codes without creating DB
  state (like the 6 migrated tests in `test_monitor_auth.py`).
- Read-only GET endpoint tests with no `logged_in_headers` dependency.

### 4. Mass migration strategy

Two options:
- **Codemod-style sweep:** rename `client` -> `shared_client` (and fixture
  deps) across all eligible test files in a single PR. Fast but reviewer-heavy.
- **Per-file gradual:** migrate one subdirectory at a time (start with
  `unit/api`, then `unit/services`, then `unit/components`).

The codemod approach is safe if every test file in scope has been audited for
`noclient`/`load_flows` use and for any side-effects that assume a fresh app
per test (e.g. tests that monkeypatch a setting and expect `create_app()` to
re-read it).

### 5. Once all files are migrated

- Delete the original `client` fixture.
- Rename `shared_client` to `client`.
- Drop the `noclient`/`load_flows` keyword paths if no remaining test uses them
  (some integration tests may still need them).
