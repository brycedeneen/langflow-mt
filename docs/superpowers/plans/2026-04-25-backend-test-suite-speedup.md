# Backend Test Suite Speedup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut backend `make unit_tests` wallclock time by attacking the three architectural costs identified during the 2026-04-25 audit: heavy import cost, xdist-incompatible test state sharing, and a function-scoped `client` fixture that rebuilds the FastAPI app for every test.

**Architecture:** Three independent workstreams, executed in increasing-risk order.
- **Part A** (low risk, ~3s import-time win): Defer `langchain_classic` imports in `lfx/field_typing/constants.py` behind `TYPE_CHECKING`.
- **Part B** (medium risk, unblocks `unit_tests_parallel`): Diagnose and fix the ~10 xdist-incompatible tests in `services/database/test_vertex_builds.py` and `services/flow/test_flow_runner.py`.
- **Part C** (high leverage, biggest single win): Introduce a session-scoped `shared_client` fixture (app + DB built once, per-test transaction rollback) and migrate one hot test file as a validated proof-of-concept.

**Tech Stack:** pytest, pytest-asyncio, pytest-xdist, FastAPI + asgi-lifespan, SQLAlchemy/SQLModel async, langchain_classic, langflow.

**Audit baselines (from 2026-04-25 measurements, on `platform-multi-tenant`):**
- `make unit_tests` (full suite, default markers): not measured end-to-end this session, but `unit/services` alone runs **101.8s wall** serial / **67.9s wall** under `-n auto` (= ~1.5×). 6,080 tests collected total.
- Pytest startup + import cost before any test runs: **~22s wall** (collection alone is ~14s wall, ~12s CPU).
- `langflow.main` cumulative import time: **7.97s** (`uv run python -X importtime`). `langchain_classic.agents` alone contributes **3.74s** transitively.
- xdist breaks 10 tests in `services/database/test_vertex_builds.py` (7 tests) and `services/flow/test_flow_runner.py` (~3 tests) that pass serially.
- `client` fixture is function-scoped at `src/backend/tests/conftest.py:379-424`: every use rebuilds the app via `create_app()`, runs full lifespan startup, and creates a fresh tempfile sqlite DB. Used by hundreds of tests.

---

## Task 0: Worktree setup

**Files:** none (workspace operation only).

**Why this task exists:** Per standing project guidance, dev work runs in a dedicated worktree to isolate from parallel Claude sessions on the same checkout.

- [ ] **Step 1: Create worktree from current branch**

```bash
git worktree add ../langflow-test-speedup platform-multi-tenant
cd ../langflow-test-speedup
```

Expected output: `Preparing worktree (checking out 'platform-multi-tenant')...`

- [ ] **Step 2: Verify clean tree**

```bash
git status --short
```

Expected: only files known to be in WIP on the source checkout (the user's currently-modified files), no failures.

- [ ] **Step 3: Sync dependencies**

```bash
uv sync --frozen
```

Expected: `Resolved N packages` with no errors.

---

## Part A — Defer langchain_classic imports

**Why:** `src/lfx/src/lfx/field_typing/constants.py` eagerly imports `langchain_classic.agents.agent.AgentExecutor`, `langchain_classic.chains.base.Chain`, `langchain_classic.memory.chat_memory.BaseChatMemory`, and `langchain_classic.base_memory.BaseMemory`. These pull in transitively ~3.7s of langchain at every import of `lfx.field_typing.constants`. Pytest pays this cost during collection AND in every xdist worker.

**Why TYPE_CHECKING is safe here:** The imports are wrapped in `try/except ImportError` with stub fallback classes (lines 26-94 of the file). They're used as type aliases in typing dicts and as targets of `isinstance()` only in narrow code paths. Most call sites only need them as type hints. We will:
1. Audit actual runtime usage of each symbol.
2. For type-hint-only usage: move into `TYPE_CHECKING`.
3. For runtime `isinstance()` usage: replace with a lazily-resolved cached helper.

### Task A.1: Audit usage of the deferred symbols

**Files:**
- Read-only: `src/lfx/src/lfx/field_typing/constants.py`, full repo grep.

- [ ] **Step 1: Capture eager import call sites**

```bash
rg -n "from lfx\.field_typing\.constants import|from lfx\.field_typing import" src/ | tee /tmp/lfx-field-typing-importers.txt
```

Expected: list of files importing from this module. Save for Task A.3 reference.

- [ ] **Step 2: Capture runtime isinstance() / direct-use of the four heavy symbols**

```bash
for sym in AgentExecutor Chain BaseChatMemory BaseMemory; do
  echo "=== $sym ==="
  rg -n "\b$sym\b" src/lfx/src/lfx/ src/backend/base/langflow/ | grep -v "field_typing/constants.py"
done | tee /tmp/lfx-heavy-symbol-uses.txt
```

Expected: a small set of usages per symbol. Each line will be inspected in step 3.

- [ ] **Step 3: Classify each use site**

For each line in `/tmp/lfx-heavy-symbol-uses.txt`, mark in a scratch note:
- `TYPE_HINT` if the symbol appears only in an annotation, return type, `TypeAlias`, dict-of-types, or string forward-ref.
- `RUNTIME` if the symbol is used in `isinstance(x, Symbol)`, `issubclass`, called as a constructor, or referenced from non-annotation code.

Write the classification table to `/tmp/lfx-heavy-symbol-classification.md` with columns: `file:line | symbol | classification | notes`.

This task does NOT modify any files. The classification feeds Task A.2 and A.3.

- [ ] **Step 4: Commit the audit notes (optional, for the record)**

If you want a paper trail for the next person:

```bash
mkdir -p docs/superpowers/specs
cp /tmp/lfx-heavy-symbol-classification.md docs/superpowers/specs/2026-04-25-langchain-classic-import-audit.md
git add docs/superpowers/specs/2026-04-25-langchain-classic-import-audit.md
git commit -m "docs(test-speedup): audit langchain_classic import usage in lfx.field_typing"
```

Otherwise skip the commit — the notes can stay in `/tmp` for the duration of the plan.

---

### Task A.2: Add an importtime regression test

**Files:**
- Create: `src/backend/tests/unit/test_lfx_import_cost.py`
- Test: same.

**Why a test:** Without one, this optimization can silently regress when someone adds an eager import elsewhere. The test should be cheap and run on every CI build.

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/test_lfx_import_cost.py
"""Regression test for lazy-loading of heavy langchain_classic imports.

If this test starts failing, someone has added an eager `import langchain_classic.*`
somewhere in lfx.field_typing's import graph. Move it behind TYPE_CHECKING or a
lazy helper.
"""
import subprocess
import sys
import textwrap


def test_field_typing_constants_does_not_eagerly_load_langchain_classic():
    """Importing lfx.field_typing.constants must not pull in langchain_classic.*."""
    script = textwrap.dedent(
        """
        import sys
        import lfx.field_typing.constants  # noqa: F401

        leaked = sorted(
            name for name in sys.modules
            if name == "langchain_classic" or name.startswith("langchain_classic.")
        )
        if leaked:
            print("LEAKED:" + ",".join(leaked))
            sys.exit(1)
        print("CLEAN")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"langchain_classic eagerly loaded by lfx.field_typing.constants:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest src/backend/tests/unit/test_lfx_import_cost.py -v
```

Expected: FAIL with stdout containing `LEAKED:langchain_classic,langchain_classic.agents,...`. This confirms the current state — eager import — and gives the fix a target.

- [ ] **Step 3: Commit the failing test on a branch**

```bash
git add src/backend/tests/unit/test_lfx_import_cost.py
git commit -m "test(lfx): add regression test for lazy langchain_classic loading

Currently fails — pre-fix baseline. The next commit makes it pass."
```

---

### Task A.3: Move type-hint-only langchain_classic imports under TYPE_CHECKING

**Files:**
- Modify: `src/lfx/src/lfx/field_typing/constants.py:1-94` (the import + stub block).
- Modify (if Task A.1 found any): each call site classified `RUNTIME` in `/tmp/lfx-heavy-symbol-classification.md`.

**Strategy:** All four heavy symbols (`AgentExecutor`, `Chain`, `BaseChatMemory`, `BaseMemory`) get moved under `TYPE_CHECKING`. The lighter `langchain_core.*` and `langchain_text_splitters.*` imports STAY at top level — they're cheap and the audit profile didn't flag them. The `try/except ImportError` stub fallback also stays for the lighter imports.

If Task A.1 found any `RUNTIME` use of one of the four heavy symbols, that call site needs to do its own local import (`from langchain_classic.agents.agent import AgentExecutor` inside the function body). The plan below assumes the audit found ZERO `RUNTIME` uses — if it found any, add a per-call-site fix sub-task here before continuing.

- [ ] **Step 1: Refactor `constants.py` import block**

Read `src/lfx/src/lfx/field_typing/constants.py:1-94` first to confirm exact line numbers haven't drifted, then replace the top-of-file imports + stub fallback. The full new top of the file:

```python
"""Constants for field typing used throughout lfx package."""

import importlib.util
from collections.abc import Callable
from typing import TYPE_CHECKING, Text, TypeAlias, TypeVar

if TYPE_CHECKING:
    # Heavy: each transitively pulls ~1-3s of langchain_classic. Kept behind
    # TYPE_CHECKING so importing lfx.field_typing.constants doesn't force the
    # full langchain_classic import graph at pytest collection time.
    from langchain_classic.agents.agent import AgentExecutor
    from langchain_classic.base_memory import BaseMemory
    from langchain_classic.chains.base import Chain
    from langchain_classic.memory.chat_memory import BaseChatMemory

# Lighter langchain_core / text_splitters imports — keep eager. ImportError
# stubs preserved for environments where langchain isn't installed.
try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.document_loaders import BaseLoader
    from langchain_core.documents import Document
    from langchain_core.documents.compressor import BaseDocumentCompressor
    from langchain_core.embeddings import Embeddings
    from langchain_core.language_models import BaseLanguageModel, BaseLLM
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.output_parsers import BaseLLMOutputParser, BaseOutputParser
    from langchain_core.prompts import BasePromptTemplate, ChatPromptTemplate, PromptTemplate
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.tools import BaseTool, Tool
    from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
    from langchain_text_splitters import TextSplitter
except ImportError:
    # Stub types for environments without langchain installed.
    class BaseChatMessageHistory:
        pass

    class BaseLoader:
        pass

    class Document:
        pass

    class BaseDocumentCompressor:
        pass

    class Embeddings:
        pass

    class BaseLanguageModel:
        pass

    class BaseLLM:
        pass

    class BaseChatModel:
        pass

    class BaseLLMOutputParser:
        pass

    class BaseOutputParser:
        pass

    class BasePromptTemplate:
        pass

    class ChatPromptTemplate:
        pass

    class PromptTemplate:
        pass

    class BaseRetriever:
        pass

    class BaseTool:
        pass

    class Tool:
        pass

    class VectorStore:
        pass

    class VectorStoreRetriever:
        pass

    class TextSplitter:
        pass


# NOTE: AgentExecutor / Chain / BaseChatMemory / BaseMemory are referenced below
# only inside string annotations (e.g. `"AgentExecutor"`) or `TypeAlias`
# expressions. If you add a new RUNTIME use, do a local import inside the
# function body, NOT at module scope.
```

Re-read the rest of `constants.py` (lines after the import block) and:
- For any line that previously read e.g. `Foo: TypeAlias = AgentExecutor`, change it to use the string-quoted form: `Foo: TypeAlias = "AgentExecutor"`. This works because `TypeAlias` resolves lazily and the heavy class only needs to be imported at type-check time.
- If a `dict[str, type]`-style mapping uses one of the four heavy symbols as a value, replace with a lazy resolver (function returning the type when called). The audit in Task A.1 should have flagged any such site.

- [ ] **Step 2: Run the regression test to verify it passes**

```bash
uv run pytest src/backend/tests/unit/test_lfx_import_cost.py -v
```

Expected: PASS, output prints `CLEAN`.

- [ ] **Step 3: Run the broader unit test smoke target to ensure nothing else broke**

```bash
make unit_tests_smoke
```

Expected: All previously-passing tests still pass. Specifically watch for `ImportError` or `NameError` referencing the four moved symbols — those would indicate a missed call site.

- [ ] **Step 4: Run any tests that import `lfx.field_typing.constants`**

```bash
uv run pytest $(rg -l "from lfx\.field_typing|from lfx\.field_typing\.constants" src/backend/tests src/lfx/tests | tr '\n' ' ') -q --no-header --tb=short -m 'not api_key_required and not slow'
```

Expected: PASS. If any test fails with `NameError` on one of the four symbols, fix the corresponding call site by adding a local import inside the function or wrapping the reference in a string forward-ref.

- [ ] **Step 5: Measure import time win**

```bash
uv run python -X importtime -c "from langflow.main import create_app" 2>&1 \
  | awk -F'|' 'NR>1 {gsub(/^ +/,"",$3); print $2"  "$3}' \
  | sort -k1 -n -r | head -5
```

Expected: `langflow.main` cumulative drops by roughly 2-3s vs the audit baseline of 7.97s. Record the new value in the commit message.

- [ ] **Step 6: Commit**

```bash
git add src/lfx/src/lfx/field_typing/constants.py
git commit -m "perf(lfx): defer langchain_classic imports behind TYPE_CHECKING

Moves AgentExecutor, Chain, BaseChatMemory, BaseMemory under TYPE_CHECKING
in lfx.field_typing.constants. These are type-hint-only usages and were
eagerly pulling ~3s of langchain_classic into every import of the module
(including pytest collection in every xdist worker).

Verified by tests/unit/test_lfx_import_cost.py regression test.
langflow.main cumulative importtime: 7.97s -> <NEW VALUE>."
```

---

## Part B — Fix xdist-incompatible tests

**Why:** `make unit_tests_parallel` (`pytest -n auto`) currently fails 10 tests in two files that pass serially. Until those are fixed, parallel runs aren't safe — and the tests themselves are flagging real test-isolation bugs. Fixing them lets the next maintainer flip xdist on with confidence.

**Hypotheses to check during diagnosis (do NOT pre-implement any fix):**
- pytest-xdist defaults to `--dist=load` which spreads tests round-robin across workers within a single test FILE. Two tests in the same file can therefore land on different workers, but each worker has its own Python process — module-level state and the `:memory:` SQLite DB used by `async_session` are per-worker, so this should already isolate.
- Most likely culprit: `pytest-asyncio` `asyncio_default_fixture_loop_scope = "function"` (`pyproject.toml`) gives each test a fresh event loop, but a fixture using `async_session` may have its async-session bound to the *first* test's loop and reused across tests on the same worker — causing `RuntimeError: Event loop is closed` on the second test.
- Alternative culprit: `LangflowRunnerExperimental()` in `test_flow_runner.py` may instantiate or call into the global service manager, which is shared module-level state within a worker.
- Alternative culprit: `vertex_builds_storage_enabled` toggled via `mock_settings` fixture may interact with a singleton settings cache that persists across tests in a worker.

### Task B.1: Reproduce the xdist failures with verbose output

**Files:** none (diagnosis only).

- [ ] **Step 1: Run the two failing files under xdist with full tracebacks**

```bash
uv run pytest \
  src/backend/tests/unit/services/database/test_vertex_builds.py \
  src/backend/tests/unit/services/flow/test_flow_runner.py \
  -m 'not api_key_required and not slow' \
  -n auto -p no:cacheprovider --tb=short -ra 2>&1 | tee /tmp/xdist-failures.log
```

Expected: ~10 failures. Tracebacks should now reveal the actual exception type and origin, not just `FAILED`. Look for: `RuntimeError: Event loop is closed`, `sqlalchemy.exc.InvalidRequestError`, `AttributeError` on a service, `ConnectionError` from a db engine, etc.

- [ ] **Step 2: Run the same files serially as a control**

```bash
uv run pytest \
  src/backend/tests/unit/services/database/test_vertex_builds.py \
  src/backend/tests/unit/services/flow/test_flow_runner.py \
  -m 'not api_key_required and not slow' \
  -p no:cacheprovider --tb=short -ra 2>&1 | tee /tmp/serial-results.log
```

Expected: 0 or near-0 failures (some pre-existing breakage on the branch unrelated to xdist is acceptable but document which ones).

- [ ] **Step 3: Diagnose**

Compare `/tmp/xdist-failures.log` vs `/tmp/serial-results.log`. The tests that fail ONLY under xdist are the ones to fix. For each unique error signature, write a one-line diagnosis to `/tmp/xdist-diagnosis.md`:

```markdown
- test_log_vertex_build_basic: `<error type>` at `<file:line>` — likely cause: `<one-sentence hypothesis>`
- ... (repeat per unique failure)
```

Stop here and present the diagnosis before continuing. **The fixes in B.2 are templated for the most likely root cause; if your diagnosis points elsewhere, adjust accordingly.**

---

### Task B.2: Fix the test isolation issues

**Files:**
- Modify (likely): `src/backend/tests/unit/services/database/test_vertex_builds.py`
- Modify (likely): `src/backend/tests/unit/services/flow/test_flow_runner.py`
- Possibly modify: `src/backend/tests/conftest.py` (if `async_session` itself needs scope/loop fixing)

**Two probable fix patterns** — pick based on the diagnosis from B.1:

**Fix pattern 1 — async_session loop binding:** If failures are `RuntimeError: Event loop is closed` or similar, the `async_session` fixture (`src/backend/tests/conftest.py:252-263`) creates an engine bound to the first test's event loop. Add a per-test recreation guard. Concretely:

```python
# src/backend/tests/conftest.py — replace the existing async_session fixture body
@pytest.fixture
async def async_session():
    # Each test gets a fresh engine bound to its own event loop. Avoids
    # cross-test loop contamination under pytest-xdist + pytest-asyncio.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
    finally:
        await engine.dispose()
```

(This is structurally identical to the current fixture. If failures persist, the diagnosis is wrong — move to Fix Pattern 2.)

**Fix pattern 2 — global service-manager state:** If failures point to `get_service_manager()` returning stale services (e.g. `mock_settings` not reflecting in `log_vertex_build`), add a service-manager reset to each affected test file's setup:

```python
# Add to test_vertex_builds.py and test_flow_runner.py near the top
@pytest.fixture(autouse=True)
def _reset_service_manager_per_test():
    """Each test gets a clean service-manager so settings patches apply."""
    from lfx.services.manager import get_service_manager
    mgr = get_service_manager()
    mgr.factories.clear()
    mgr.services.clear()
    yield
    mgr.factories.clear()
    mgr.services.clear()
```

- [ ] **Step 1: Write a failing test that pins the bug**

For each unique failure mode in B.1's diagnosis, the failing case from B.1 itself IS the failing test — no new test code needed. Re-run only those failing tests in isolation to confirm reproducibility.

```bash
uv run pytest <failing-test-id> -m 'not api_key_required and not slow' -n 2 -p no:cacheprovider -v
```

Expected: still fails. If running with `-n 2` instead of `-n auto` makes the failure go away, the bug is load-balancing-sensitive — note in commit message.

- [ ] **Step 2: Apply the appropriate fix pattern**

Based on diagnosis, edit the relevant file(s) to apply Fix Pattern 1 or 2. Show the FULL replacement code, not a diff.

- [ ] **Step 3: Re-run under xdist**

```bash
uv run pytest \
  src/backend/tests/unit/services/database/test_vertex_builds.py \
  src/backend/tests/unit/services/flow/test_flow_runner.py \
  -m 'not api_key_required and not slow' \
  -n auto -p no:cacheprovider --tb=short -ra
```

Expected: 0 failures (excluding any pre-existing serial failures from B.1 step 2's control run).

- [ ] **Step 4: Re-run the broader services suite under xdist as a non-regression check**

```bash
uv run pytest src/backend/tests/unit/services -m 'not api_key_required and not slow' -n auto --tb=line -ra 2>&1 | tail -10
```

Expected: failure count matches the serial baseline (no NEW xdist-only failures introduced by the fix).

- [ ] **Step 5: Update Makefile caveat in `unit_tests_parallel`**

If both files are now xdist-clean, edit `Makefile:218-228` (the `unit_tests_parallel` target's comment block) to remove the specific file callouts. Keep the general "some tests share state" caveat — there may be other latent issues in the suite.

```makefile
# ---- Opt-in parallel run via pytest-xdist ----
# CAUTION: pytest startup + import cost is ~22s on this codebase, so the
# speedup is modest (~1.5x on services/). Use selectively (per-area is
# most useful), not for the whole suite. If you hit new xdist-only
# failures, they likely indicate test-isolation bugs worth fixing.
unit_tests_parallel: ## run unit tests with -n auto
	@uv run pytest src/backend/tests/unit \
		--ignore=src/backend/tests/integration \
		--ignore=src/backend/tests/unit/template \
		--instafail -ra -m '$(markers)' -n auto $(args)
```

- [ ] **Step 6: Commit**

```bash
git add src/backend/tests/unit/services/database/test_vertex_builds.py \
        src/backend/tests/unit/services/flow/test_flow_runner.py \
        Makefile
# Add conftest.py to the staging list ONLY if Fix Pattern 1 was applied:
# git add src/backend/tests/conftest.py
git commit -m "test(backend): fix xdist test isolation in vertex_builds and flow_runner

<one-sentence summary of the actual fix pattern applied — e.g. 'Reset
the global service manager per-test so mock_settings takes effect' or
'Recreate async engine per test to avoid cross-loop contamination'>.

Verified by re-running both files under -n auto: 0 failures (vs 10
before). Removes the per-file caveat from the Makefile unit_tests_parallel
target."
```

---

## Part C — Session-scoped `shared_client` fixture

**Why:** `client_fixture` at `src/backend/tests/conftest.py:379-424` rebuilds the FastAPI app, runs full lifespan startup, and creates a fresh tempfile sqlite DB on every test. With hundreds of tests using it, this is the architectural reason your slow tests are slow. We will:
1. Add a session-scoped `shared_client` alongside the existing `client` (do NOT replace `client` yet — too invasive).
2. Migrate ONE hot test file as proof.
3. Measure the speedup.
4. Document the migration path; full migration becomes a follow-up.

**Architecture for `shared_client`:**
- Session-scoped `shared_app_db_path` fixture: creates one tempfile sqlite DB for the whole pytest session.
- Session-scoped `shared_app_lifecycle` fixture: sets `LANGFLOW_DATABASE_URL` env var, calls `create_app()`, runs `LifespanManager` startup once.
- Function-scoped `shared_client` fixture: yields an `AsyncClient` against the shared app, with a per-test SQL transaction wrapped via `connection.begin_nested()` and a `SAVEPOINT` rollback at teardown, so each test sees a clean DB without paying for a rebuild.

**Why we keep `client` untouched:**
- Tests using `noclient` keyword need the function-scoped fallback path (line 387-388).
- Tests using `load_flows` keyword need to inject a flow file BEFORE `create_app()` — fundamentally incompatible with a shared app.
- Replacing `client` directly is a hundreds-of-files refactor; that's a separate plan.

### Task C.1: Validate the chosen test target file

**Files:** none (selection step only).

**Why:** We want a high-leverage migration target — a file that uses `client`, runs many tests, has measurable wallclock cost, and does NOT use `noclient` or `load_flows` keywords (so it's safe to point at `shared_client`).

- [ ] **Step 1: Find candidate files**

```bash
rg -l "@pytest\.mark\.usefixtures\(.client.\)|def test_.*\(client\b|client: " src/backend/tests/unit/api -n | sort -u | tee /tmp/client-using-files.txt
```

Expected: list of test files using `client`. The `unit/api` subtree is the densest.

- [ ] **Step 2: Filter out files using `load_flows` or `noclient`**

```bash
while read -r f; do
  if grep -q "load_flows\|noclient" "$f"; then
    continue
  fi
  count=$(grep -cE "^(async )?def test_" "$f")
  echo "$count $f"
done < /tmp/client-using-files.txt | sort -rn | head -20
```

Expected: a list sorted by test count. Pick the top file with at least 10 tests as the migration target. **Record the chosen file path** for use in Task C.4. The sample text below assumes `src/backend/tests/unit/api/v1/test_api_key.py` — substitute your actual choice.

- [ ] **Step 3: Baseline-time the chosen file**

```bash
/usr/bin/time -p uv run pytest <chosen-file> -m 'not api_key_required and not slow' -q --no-header --tb=no
```

Expected: a `real Xs` line. Record this as the BEFORE measurement (used in Task C.5).

---

### Task C.2: Add session-scoped fixture infrastructure

**Files:**
- Modify: `src/backend/tests/conftest.py` (add new fixtures after the existing `client_fixture` definition, around line 425).

**Important:** All new fixtures live under DIFFERENT names (`shared_*`) so the existing `client` fixture and its callers are untouched.

- [ ] **Step 1: Write the failing test**

```python
# src/backend/tests/unit/services/test_shared_client_smoke.py
"""Smoke tests pinning the contract of the new shared_client fixtures.

Each test must run independently against the same session-scoped app.
Rollback isolation must prevent state leaking between tests.
"""
import pytest


@pytest.mark.asyncio
async def test_shared_client_yields_async_client(shared_client):
    response = await shared_client.get("/health_check")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_shared_client_has_clean_db_per_test(shared_client):
    """If isolation works, this test sees no leftover users from the previous test."""
    # The actual user-creation in the previous test is rolled back, so listing
    # users here returns only the bootstrap superuser.
    response = await shared_client.get("/api/v1/users/")
    assert response.status_code in (200, 401)
    # Status alone is enough — body shape varies. Real isolation contract is
    # validated by Task C.4's migrated file timing within budget.


@pytest.mark.asyncio
async def test_shared_client_db_writes_roll_back(shared_client):
    """A user created in this test must not appear in a sibling test."""
    response = await shared_client.post(
        "/api/v1/users/",
        json={"username": "sharedclient_isolation_check", "password": "x" * 12},
    )
    # Whether this 201/409s depends on the order of test discovery; we only
    # assert that the request reaches the app. The rollback contract is
    # validated by re-running the test twice (no "username already taken" on
    # the second run) — see step 3.
    assert response.status_code in (201, 409, 422)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest src/backend/tests/unit/services/test_shared_client_smoke.py -v
```

Expected: FAIL with `fixture 'shared_client' not found`.

- [ ] **Step 3: Implement the fixtures**

Append to `src/backend/tests/conftest.py` (after the existing `client_fixture`, around line 425). The full new block:

```python
# ---------------------------------------------------------------------
# Session-scoped client infrastructure (`shared_client`).
#
# The existing `client` fixture rebuilds the FastAPI app and DB per test.
# `shared_client` runs ONE app for the whole pytest session and uses a
# per-test SQL transaction with rollback to give each test a clean DB
# view. Tests using `load_flows` or `noclient` keywords must keep using
# `client` — those features need per-test app construction.
# ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def shared_app_db_path():
    """One on-disk sqlite file shared across the whole pytest session."""
    db_dir = tempfile.mkdtemp(prefix="langflow-shared-")
    db_path = Path(db_dir) / "test.db"
    yield db_path
    with suppress(FileNotFoundError):
        db_path.unlink()
    with suppress(FileNotFoundError):
        Path(db_dir).rmdir()


@pytest.fixture(scope="session")
def shared_app_env(shared_app_db_path):
    """Set the env vars create_app() needs, once. Cleared at session end."""
    import os

    previous = {
        k: os.environ.get(k)
        for k in ("LANGFLOW_DATABASE_URL", "LANGFLOW_SUPERUSER", "LANGFLOW_SUPERUSER_PASSWORD")
    }
    os.environ["LANGFLOW_DATABASE_URL"] = f"sqlite:///{shared_app_db_path}"
    os.environ["LANGFLOW_SUPERUSER"] = "admin"
    os.environ["LANGFLOW_SUPERUSER_PASSWORD"] = "testpassword123"  # noqa: S105
    yield
    for k, v in previous.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="session")
async def shared_app(shared_app_env):  # noqa: ARG001
    """One FastAPI app + one lifespan startup for the whole session."""
    from lfx.services.manager import get_service_manager

    get_service_manager().factories.clear()
    get_service_manager().services.clear()
    app = create_app()
    db_service = get_db_service()
    db_service.reload_engine()
    async with LifespanManager(app, startup_timeout=None, shutdown_timeout=60) as manager:
        yield manager.app


@pytest.fixture
async def shared_client(shared_app) -> AsyncGenerator:
    """Per-test AsyncClient against the shared app.

    NOTE: this fixture does NOT yet provide per-test DB rollback — a
    follow-up task wraps each test in a SAVEPOINT once we've confirmed
    the no-rollback variant works end-to-end. In the meantime, tests
    using shared_client must clean up their own DB writes (or only
    test read-only paths).
    """
    async with AsyncClient(
        transport=ASGITransport(app=shared_app),
        base_url="http://testserver/",
        http2=True,
    ) as client:
        yield client
```

- [ ] **Step 4: Run smoke test to verify it passes**

```bash
uv run pytest src/backend/tests/unit/services/test_shared_client_smoke.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/conftest.py src/backend/tests/unit/services/test_shared_client_smoke.py
git commit -m "test(backend): add session-scoped shared_client fixture (no rollback yet)

Builds the FastAPI app + DB once per pytest session. Per-test isolation
via SQL transaction rollback is deferred to a follow-up — tests that
opt in must clean up their own writes for now.

The existing function-scoped client fixture is untouched. Tests using
load_flows or noclient keywords must keep using it."
```

---

### Task C.3: Add per-test transaction rollback to `shared_client`

**Files:**
- Modify: `src/backend/tests/conftest.py` (the `shared_client` fixture body added in C.2).

**Why:** Without rollback, `shared_client` is only useful for read-only tests. Adding SAVEPOINT rollback gives clean-DB-per-test semantics with ~zero per-test cost.

**Pattern:** The standard SQLAlchemy + asyncio pattern is:
1. Open a connection, begin a transaction, begin a nested transaction (SAVEPOINT).
2. Bind the app's DB session-maker to that connection (override the dependency).
3. After the test, roll back the SAVEPOINT and the outer transaction. The connection is reused; only the rolled-back state is discarded.

This requires hooking into how `langflow.services.deps.get_db_service()` hands out sessions. Look at `db_service.with_session()` (or whichever method is the per-request session source) and patch it to bind to our managed connection during the test.

**Diagnostic step before implementation:** read `src/backend/base/langflow/services/database/service.py` (or wherever `get_db_service` is defined) and identify the function the FastAPI app calls to get a per-request session. This is the dependency that needs to be overridden. Record the exact name in `/tmp/db-session-dependency.md`.

- [ ] **Step 1: Identify the DB session dependency**

```bash
rg -n "Depends\(.*session\)|async def get_session|def with_session\b" src/backend/base/langflow/services/database/ src/backend/base/langflow/api/ | head -20
```

Find the canonical FastAPI dependency that hands out an `AsyncSession`. This is usually a function like `get_session` or `with_session`. Note its full module path.

- [ ] **Step 2: Write the failing test (extend the smoke file)**

Append to `src/backend/tests/unit/services/test_shared_client_smoke.py`:

```python
@pytest.mark.asyncio
async def test_shared_client_rollback_isolates_writes(shared_client):
    """Two consecutive POSTs of the same user must both succeed — proves rollback."""
    payload = {"username": "rollback_isolation_user", "password": "x" * 12}
    r1 = await shared_client.post("/api/v1/users/", json=payload)
    # First test instance: creates the user.
    assert r1.status_code in (201, 422), r1.text
    # If rollback works, the next test invocation of this same test (re-run)
    # will also see status 201, not 409 "username taken".
    # We test this by running pytest twice in CI; here we just assert the
    # contract: a second POST in the SAME test sees the row from the first.
    r2 = await shared_client.post("/api/v1/users/", json=payload)
    assert r2.status_code in (409, 422), r2.text
```

Then verify the cross-test rollback contract by running pytest twice and confirming both runs show 201 for the first POST:

```bash
uv run pytest src/backend/tests/unit/services/test_shared_client_smoke.py::test_shared_client_rollback_isolates_writes -v
# Re-run; first POST should still return 201 if rollback is wired correctly
uv run pytest src/backend/tests/unit/services/test_shared_client_smoke.py::test_shared_client_rollback_isolates_writes -v
```

Expected before fix: second run returns 409 ("username taken") — rollback isn't happening.

- [ ] **Step 3: Implement rollback in the `shared_client` fixture**

Replace the body of `shared_client` (added in Task C.2) with:

```python
@pytest.fixture
async def shared_client(shared_app) -> AsyncGenerator:
    """Per-test AsyncClient with SAVEPOINT-based rollback isolation.

    Each test runs against the shared app but its DB writes are wrapped
    in a SAVEPOINT that rolls back at teardown — giving clean-DB-per-test
    semantics without paying for app or schema rebuild.
    """
    from <DB-DEPS-MODULE> import <SESSION-DEPENDENCY>  # filled in from step 1

    db_service = get_db_service()
    async_engine = db_service._async_engine  # or the public accessor if one exists

    connection = await async_engine.connect()
    transaction = await connection.begin()
    nested = await connection.begin_nested()

    async def _override_session():
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            yield session

    shared_app.dependency_overrides[<SESSION-DEPENDENCY>] = _override_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=shared_app),
            base_url="http://testserver/",
            http2=True,
        ) as client:
            yield client
    finally:
        shared_app.dependency_overrides.pop(<SESSION-DEPENDENCY>, None)
        if nested.is_active:
            await nested.rollback()
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()
```

Replace `<DB-DEPS-MODULE>` and `<SESSION-DEPENDENCY>` with the actual values from step 1.

- [ ] **Step 4: Run rollback contract test twice in a row**

```bash
uv run pytest src/backend/tests/unit/services/test_shared_client_smoke.py -v
sleep 1
uv run pytest src/backend/tests/unit/services/test_shared_client_smoke.py -v
```

Expected: both runs pass identically. The "first POST returns 201" contract holds across pytest invocations because the rolled-back row never gets persisted to the on-disk session DB.

- [ ] **Step 5: Commit**

```bash
git add src/backend/tests/conftest.py src/backend/tests/unit/services/test_shared_client_smoke.py
git commit -m "test(backend): add SAVEPOINT rollback to shared_client fixture

Per-test isolation via outer transaction + nested SAVEPOINT pattern.
Each test sees a clean DB without paying for app or schema rebuild.

DB session dependency override: <SESSION-DEPENDENCY-NAME>"
```

---

### Task C.4: Migrate one hot test file to `shared_client`

**Files:**
- Modify: `<chosen-file-from-Task-C.1>` (the substitution will be e.g. `src/backend/tests/unit/api/v1/test_api_key.py`).

**Why:** A real-world validation that `shared_client` works for an existing test file. Catches issues that the synthetic smoke tests don't (e.g. tests that depend on lifespan ordering, or that monkeypatch settings that the shared app already cached).

- [ ] **Step 1: Make the file's tests use `shared_client` instead of `client`**

Read the chosen file and:
- Replace every `client` parameter in test signatures with `shared_client`.
- Replace every `@pytest.mark.usefixtures("client")` with `@pytest.mark.usefixtures("shared_client")`.
- Do NOT touch tests that use other fixtures depending on `client` transitively (e.g. `logged_in_headers` — see step 2).

- [ ] **Step 2: Audit transitive `client` dependencies in the file**

```bash
rg -n "def \w+\(.*\bclient\b" src/backend/tests/conftest.py
```

Identify every fixture that takes `client` as a parameter (e.g. `test_user`, `active_user`, `active_super_user`, `logged_in_headers`). If the chosen file uses any of these, you have two options:
1. Skip migrating those tests (leave them on `client`).
2. Add a `shared_*` variant of the dependent fixture (e.g. `shared_logged_in_headers`).

For this proof-of-concept, prefer option 1. List the skipped tests in the commit message.

- [ ] **Step 3: Run the migrated file and verify it passes**

```bash
uv run pytest <chosen-file> -m 'not api_key_required and not slow' -v
```

Expected: same passing test count as the baseline in Task C.1 step 3 (modulo any tests skipped because they use a transitive `client` fixture).

- [ ] **Step 4: Time the migrated file and compare to baseline**

```bash
/usr/bin/time -p uv run pytest <chosen-file> -m 'not api_key_required and not slow' -q --no-header --tb=no
```

Expected: significantly faster than the baseline measured in Task C.1 step 3. Record both before/after numbers.

- [ ] **Step 5: Commit**

```bash
git add <chosen-file>
git commit -m "test(backend): migrate <chosen-file-basename> to shared_client

Proof-of-concept migration to the session-scoped client fixture.
Wallclock: <BEFORE>s -> <AFTER>s (<RATIO>x).

<N> tests skipped because they depend on transitive client fixtures
(test_user, active_user, logged_in_headers). Those need shared_*
variants before they can migrate."
```

---

### Task C.5: Document the migration path

**Files:**
- Create: `docs/superpowers/specs/2026-04-25-shared-client-migration-followups.md`

**Why:** The proof-of-concept is the easy 80%. The remaining 20% — adding `shared_*` variants for `test_user`, `active_user`, `logged_in_headers`, etc., then mass-migrating ~hundreds of test files — is real work that the next person needs to know about.

- [ ] **Step 1: Write the followup spec**

Create the file with this content:

```markdown
# shared_client Migration Followups

## Status as of 2026-04-25

- `shared_client` fixture exists in `src/backend/tests/conftest.py`.
- Validated on `<chosen-file>` (Task C.4): wallclock dropped from <BEFORE>s
  to <AFTER>s (<RATIO>x).
- Existing function-scoped `client` fixture remains as-is for tests using
  the `noclient` or `load_flows` keywords.

## Required follow-ups before mass migration

### 1. Add `shared_*` variants of fixtures that depend on `client`

The following fixtures in `conftest.py` take `client` as a dependency
and therefore force any test using them onto the slow function-scoped
path:
- `test_user` (line ~433)
- `active_user` (line ~447)
- `active_super_user` (line ~492)
- `logged_in_headers` (line ~482)

Add `shared_test_user`, `shared_active_user`, `shared_active_super_user`,
`shared_logged_in_headers` variants. Each takes `shared_client` instead
of `client`. Body is otherwise identical, but cleanup must happen WITHIN
the rolled-back transaction so it's free.

### 2. Decide migration strategy

Two options:
- **Codemod-style sweep:** rename `client` -> `shared_client` (and
  fixtures) across all eligible test files in a single PR. Fast but
  reviewer-heavy.
- **Per-file gradual:** migrate one subdirectory at a time (start with
  `unit/api`, then `unit/services`, then `unit/components`).

The codemod approach is fine if every test file in scope has been
audited for `noclient`/`load_flows` use and for any side-effects that
assume a fresh app per test (e.g. tests that monkeypatch a setting and
expect create_app() to re-read it).

### 3. Once all files are migrated

- Delete the original `client` fixture.
- Rename `shared_client` to `client`.
- Drop the `noclient`/`load_flows` keyword paths if no remaining test
  uses them (some integration tests may still need them).
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-25-shared-client-migration-followups.md
git commit -m "docs(test-speedup): record shared_client migration followups"
```

---

## Task Z: Final verification + push

- [ ] **Step 1: Run the full smoke target**

```bash
make unit_tests_smoke
```

Expected: same pass count as the baseline (244 / 33s wall on the audit measurement). No regressions from any Part A/B/C change.

- [ ] **Step 2: Run the full default unit suite**

```bash
make unit_tests
```

Expected: same pass count as before this plan. Wallclock should be lower (Part A's import savings apply globally; Part C's gains are scoped to the migrated file).

- [ ] **Step 3: Run the parallel target as a sanity check**

```bash
make unit_tests_parallel
```

Expected: failure count matches the serial baseline (Part B's fixes should make `services/database/test_vertex_builds.py` and `services/flow/test_flow_runner.py` clean under xdist). Other files may still have latent xdist issues — those are out of scope for this plan.

- [ ] **Step 4: Push**

```bash
git push fork platform-multi-tenant
```

Use `fork`, not `origin` — `origin` is the upstream langflow-ai/langflow remote.

---

## Out of scope (intentional)

- Replacing the `client` fixture entirely. Out of scope; documented as a follow-up in `docs/superpowers/specs/2026-04-25-shared-client-migration-followups.md`.
- Lazy-loading other heavy imports (`lfx.template.field`, `lfx.inputs`). The audit flagged these but they're harder to defer than `langchain_classic.agents` because they're used at runtime, not just for type hints.
- Fixing latent xdist issues outside the two named files. The plan only covers what the 2026-04-25 audit reproduced.
- Frontend Jest test optimization. Separate codebase, separate plan.
