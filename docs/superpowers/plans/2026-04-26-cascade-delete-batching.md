# Cascade-Delete Batching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-flow `cascade_delete_flow` loops at `api/v1/projects.py:530` and `api/v1/flows.py:1135` with a single `cascade_delete_flows` helper that issues one `DELETE WHERE flow_id IN (:ids)` per child table — collapsing N-flow deletes from O(N) round-trips down to a fixed O(1) per child table.

**Architecture:** Add `cascade_delete_flows(session, flow_ids: Sequence[UUID])` next to the existing `cascade_delete_flow` in `src/backend/base/langflow/api/utils/core.py`. Single-id callers keep using `cascade_delete_flow` (now a thin wrapper around the batched helper). Bulk callers (`projects.delete_project`, `flows.delete_multiple_flows`) switch to the new helper. Order, table list, and SQLite-cascade caveats are preserved verbatim from the existing helper.

**Tech Stack:** Python 3.12, SQLModel + SQLAlchemy 2.x async, asyncpg / aiosqlite, pytest-asyncio.

**Spec:** None — this plan is the design. Source motivation captured below in the Problem Statement.

**Standing constraints (carry from project memory):**
- No upstream PR; local `platform-multi-tenant` only.
- **No git commits without explicit user approval** — every "Commit" step must pause and ask. Do not use `git add -A` / `git add .` / `git commit -a`. Stage explicit paths only.
- Working directory for all commands: `.worktrees/perf-cascade-batch/` unless noted.

---

## Problem Statement

Two endpoints today loop over flows and issue a full cascade per flow.

**`src/backend/base/langflow/api/v1/projects.py:523-531`** — project deletion:

```python
flows = (
    await session.exec(
        select(Flow).where(
            Flow.folder_id == project_id, Flow.organization_id == current_org.id
        )
    )
).all()
for flow in flows:
    await cascade_delete_flow(session, flow.id)
```

**`src/backend/base/langflow/api/v1/flows.py:1128-1136`** — bulk flow delete:

```python
flows_to_delete = (
    await db.exec(
        select(Flow)
        .where(col(Flow.id).in_(flow_ids))
        .where(Flow.organization_id == current_org.id)
    )
).all()
for flow in flows_to_delete:
    await cascade_delete_flow(db, flow.id)
```

`cascade_delete_flow` (at `src/backend/base/langflow/api/utils/core.py:442-466`) issues **6–7 DELETEs + 1 SELECT** per flow:

1. `DELETE FROM message WHERE flow_id = :id`
2. `DELETE FROM transaction WHERE flow_id = :id`
3. `DELETE FROM vertex_build WHERE flow_id = :id`
4. `DELETE FROM flow_version WHERE flow_id = :id`
5. `SELECT trace.id FROM trace WHERE flow_id = :id` (gathers `trace_ids`)
6. `DELETE FROM span WHERE trace_id IN :trace_ids` (only when traces exist)
7. `DELETE FROM trace WHERE flow_id = :id`
8. `DELETE FROM flow WHERE id = :id`

So a project with **N** flows triggers **7N–8N** database round-trips just for cascade. For N=100, that is ~750 awaited round-trips inside a single HTTP request — visibly slow on Postgres-over-network and the dominant cost of project deletion. The flows themselves carry no per-flow side effects beyond what `cascade_delete_flow` does, so the fix is purely a SQL-shape change.

---

## Inventory of Cascades

The current `cascade_delete_flow` body is the source of truth for what gets deleted and in what order. Reproduced here so the batched plan can be verified against it line-for-line:

```python
async def cascade_delete_flow(session: AsyncSession, flow_id: uuid.UUID) -> None:
    try:
        # TODO: Verify if deleting messages is safe in terms of session id relevance
        # If we delete messages directly, rather than setting flow_id to null,
        # it might cause unexpected behaviors because the session id could still be
        # used elsewhere to search for these messages.
        await session.exec(delete(MessageTable).where(MessageTable.flow_id == flow_id))
        await session.exec(delete(TransactionTable).where(TransactionTable.flow_id == flow_id))
        await session.exec(delete(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id))
        # Explicit delete despite FK CASCADE — SQLite doesn't enforce FK cascades
        # by default (requires PRAGMA foreign_keys = ON), and this function follows
        # the existing pattern of explicitly deleting all child records.
        await session.exec(delete(FlowVersion).where(FlowVersion.flow_id == flow_id))
        # Spans must go before traces because span.trace_id lacked CASCADE in the
        # original migration (3478f0bd6ccb); migration c8a5f32e9b74 retrofits it.
        trace_ids = (
            await session.exec(select(TraceTable.id).where(TraceTable.flow_id == flow_id))
        ).all()
        if trace_ids:
            await session.exec(delete(SpanTable).where(col(SpanTable.trace_id).in_(trace_ids)))
        await session.exec(delete(TraceTable).where(TraceTable.flow_id == flow_id))
        await session.exec(delete(Flow).where(Flow.id == flow_id))
    except Exception as e:
        msg = f"Unable to cascade delete flow: {flow_id}"
        raise RuntimeError(msg, e) from e
```

**Tables touched (in delete order):**

| # | Table              | Filter             | Why before parent           |
|---|--------------------|--------------------|-----------------------------|
| 1 | `message`          | `flow_id`          | child of `flow`             |
| 2 | `transaction`      | `flow_id`          | child of `flow`             |
| 3 | `vertex_build`     | `flow_id`          | child of `flow`             |
| 4 | `flow_version`     | `flow_id`          | child of `flow` (SQLite)    |
| 5 | `span`             | `trace_id IN ...`  | grandchild via `trace`      |
| 6 | `trace`            | `flow_id`          | child of `flow`             |
| 7 | `flow`             | `id`               | parent — last               |

**Order constraints (verified from comments in the helper):**

- `span` strictly before `trace`. Migration `3478f0bd6ccb` did not add CASCADE on `span.trace_id`; `c8a5f32e9b74` retrofitted it but the helper still does an explicit pre-delete because the pattern is uniform across the file. Keep the explicit pre-delete in the batched version.
- `flow` strictly last. Even on Postgres where FK CASCADE works, the helper does explicit child deletes because SQLite does not enforce CASCADE without `PRAGMA foreign_keys = ON`. Keep the same belt-and-suspenders approach in the batched version — the win comes from collapsing N round-trips per child table, not from relying on FK CASCADE.
- The order between `message` / `transaction` / `vertex_build` / `flow_version` is irrelevant — none reference each other. Preserve the existing order anyway for review-diff cleanliness.

**Side effects beyond DELETEs (audit by reading the helper + both call sites):**

- **None inside `cascade_delete_flow`**. The helper is pure SQL: no file system cleanup, no telemetry/audit emission, no cache invalidation. Errors are re-raised as `RuntimeError`.
- **At the call sites:** neither `delete_project` nor `delete_multiple_flows` emits per-flow events. `delete_project` emits one project-level audit event after the loop (via `audit_ctx`); `delete_multiple_flows` returns a `{"deleted": N}` count with no event emission at all. **No fan-out logic to preserve** — the cleanup is entirely in-database.
- **Caches:** `chat_service.set_cache(flow_id, ...)` is populated by build paths but is in-process and TTL-bound; deletion does not currently invalidate it. Out of scope here — file a follow-up if the existing per-flow path doesn't either (it doesn't).
- **MCP composer:** `delete_project` separately calls `mcp_composer_service.stop_project_composer(project_id)` once per project (not per flow). Untouched by this change.

**Other callers of `cascade_delete_flow` (must keep working after refactor):**

- `src/backend/base/langflow/services/flow/flow_runner.py:225` — `clear_state` deletes a single flow.
- `src/backend/base/langflow/services/flow/flow_runner.py:233` — `clear_user_state` loops over a user's flows. **Bonus opportunity** — collect IDs and call the new batched helper in one go. Mark as Task 6.
- `src/backend/base/langflow/api/v1/flows.py:1006` — single-flow `delete_flow` endpoint. Stays on `cascade_delete_flow`.

---

## Proposed Batched Approach

Define a new helper alongside `cascade_delete_flow`:

```python
async def cascade_delete_flows(
    session: AsyncSession, flow_ids: Sequence[uuid.UUID]
) -> None:
    """Cascade-delete a batch of flows in a single sequence of DELETEs.

    Equivalent to calling cascade_delete_flow() in a loop, but issues one
    DELETE per child table (with `flow_id IN :ids`) instead of one DELETE
    per (flow, table) pair. For N flows that is ~7 round-trips total
    instead of ~7*N.

    Order, table list, and SQLite-cascade caveats are identical to
    cascade_delete_flow — see that function for the rationale on each step.
    """
    if not flow_ids:
        return
    ids = list(flow_ids)  # tolerate generators; SQLAlchemy needs a sequence
    try:
        await session.exec(delete(MessageTable).where(col(MessageTable.flow_id).in_(ids)))
        await session.exec(delete(TransactionTable).where(col(TransactionTable.flow_id).in_(ids)))
        await session.exec(delete(VertexBuildTable).where(col(VertexBuildTable.flow_id).in_(ids)))
        await session.exec(delete(FlowVersion).where(col(FlowVersion.flow_id).in_(ids)))
        # Spans go before traces — see cascade_delete_flow for the migration history.
        trace_ids = (
            await session.exec(
                select(TraceTable.id).where(col(TraceTable.flow_id).in_(ids))
            )
        ).all()
        if trace_ids:
            await session.exec(delete(SpanTable).where(col(SpanTable.trace_id).in_(trace_ids)))
        await session.exec(delete(TraceTable).where(col(TraceTable.flow_id).in_(ids)))
        await session.exec(delete(Flow).where(col(Flow.id).in_(ids)))
    except Exception as e:
        msg = f"Unable to cascade delete flows: {ids!r}"
        raise RuntimeError(msg, e) from e
```

And rewrite `cascade_delete_flow` as a one-line shim:

```python
async def cascade_delete_flow(session: AsyncSession, flow_id: uuid.UUID) -> None:
    """Single-flow convenience wrapper. See cascade_delete_flows."""
    await cascade_delete_flows(session, [flow_id])
```

**SQL shape produced (Postgres flavor; SQLite is identical modulo bind-param syntax):**

```sql
DELETE FROM message     WHERE flow_id IN ($1, $2, ..., $N);
DELETE FROM transaction WHERE flow_id IN ($1, $2, ..., $N);
DELETE FROM vertex_build WHERE flow_id IN ($1, $2, ..., $N);
DELETE FROM flow_version WHERE flow_id IN ($1, $2, ..., $N);
SELECT id FROM trace    WHERE flow_id IN ($1, $2, ..., $N);
DELETE FROM span        WHERE trace_id IN ($T1, $T2, ..., $TM);  -- only if any traces
DELETE FROM trace       WHERE flow_id IN ($1, $2, ..., $N);
DELETE FROM flow        WHERE id IN ($1, $2, ..., $N);
```

**`IN`-list size guard.** Postgres allows up to 32,767 bind params per statement; SQLite's default `SQLITE_LIMIT_VARIABLE_NUMBER` is 999 in older builds and 32,766 in builds since 3.32. A pathological "delete project with 10,000 flows" call could hit either limit. Add a chunking helper and chunk at **500 ids per statement** — well under both limits, and well above any realistic project size:

```python
_BATCH_SIZE = 500

async def cascade_delete_flows(session, flow_ids):
    if not flow_ids:
        return
    ids = list(flow_ids)
    for chunk_start in range(0, len(ids), _BATCH_SIZE):
        chunk = ids[chunk_start : chunk_start + _BATCH_SIZE]
        await _cascade_delete_flow_chunk(session, chunk)
```

`_cascade_delete_flow_chunk` is the body shown above. The outer loop is fine because each chunk still produces a constant number of round-trips regardless of `len(chunk)`.

---

## Hidden Side Effects to Handle

Audit findings (verified by Grep over the helper, both call sites, and downstream code paths):

| Side effect category        | Per-flow today? | Action under batched path                      |
|-----------------------------|-----------------|------------------------------------------------|
| File-system cleanup         | No              | None                                           |
| Per-flow audit/telemetry    | No              | None                                           |
| Cache invalidation          | No (existing bug — out of scope)               | None                                           |
| MCP composer stop           | No (project-level, post-loop)                  | None                                           |
| FK CASCADE reliance         | No (explicit deletes for SQLite parity)        | Preserve explicit deletes in batched form      |
| Pydantic / SQLModel hooks   | No (raw `delete()` statements bypass ORM events) | None                                       |

In short: **no per-flow side effects exist** that would force a fan-out. The full per-flow loop today is pure SQL, so a pure SQL batch is behavior-preserving. If a future change adds a per-flow event emitter, it should be added at the call sites (around the `cascade_delete_flows` call), not inside the helper — same shape as the current call sites.

---

## Transaction Boundaries

**Today:** Both call sites run inside a `DbSession`-injected `AsyncSession` whose `injectable_session_scope` auto-commits on success and rolls back on exception. The N-flow loop is therefore one big transaction already — partial failure (e.g., DB error halfway through the loop) rolls back the whole batch. Behavior is **all-or-nothing** in practice, even though it doesn't look that way at first glance.

**Recommended for batched path:** Keep the same all-or-nothing semantics — the batched helper runs inside the same session, so the existing scope handles commit/rollback correctly. **No explicit `session.begin()` needed**; `injectable_session_scope` already wraps the request handler.

**Trade-off considered and rejected — per-flow autonomous transactions.** Switching to per-flow savepoints (`SAVEPOINT sp; DELETE ... ; RELEASE sp;` or `IsolationLevel.READ_COMMITTED` with explicit commits) would let one corrupted flow not block the rest of a bulk delete. **Rejected because:**

- Cascade DELETEs against valid `flow_id`s do not raise — there is no realistic data scenario where flow A's cleanup fails mid-batch but flow B's would succeed if retried separately. The helper today re-raises any error as `RuntimeError`; production has no observed instances of partial-success requirements.
- Per-flow savepoints would re-introduce N round-trips for the SAVEPOINT/RELEASE handshake, defeating the win.
- The bulk-delete endpoint already returns a single integer count, not per-flow status. There is no API contract to honor for partial success.

If a future requirement emerges (e.g., admin "force-delete corrupted flows" tool), wrap the call site in a per-flow loop with try/except and call the single-flow shim. Don't bake partial-success into the helper.

---

## Estimated Win

Concrete numbers, per call (assuming the trace SELECT returns no rows for half the flows so the span DELETE is skipped — typical for production where most flows are never traced):

| Scenario                                       | Round-trips today  | Round-trips after  | Speedup            |
|-----------------------------------------------|---------------------|---------------------|--------------------|
| `delete_project` with 1 flow                  | 7–8                 | 7–8                 | 1.0× (no change)   |
| `delete_project` with 10 flows                | 70–80               | 7–8                 | 10×                |
| `delete_project` with 100 flows               | 700–800             | 7–8                 | ~100×              |
| `delete_project` with 1000 flows              | 7000–8000           | 14–16 (2 chunks)    | ~500×              |
| `delete_multiple_flows` of 50 flows           | 350–400             | 7–8                 | ~50×               |
| `clear_user_state` for a user with 200 flows  | 1400–1600           | 7–8                 | ~200×              |

In wall-clock terms on a Postgres-over-network deployment with ~2ms RTT, a 100-flow project delete drops from ~1.5s of pure round-trip latency to ~16ms — frequently-cited UX cliff for "delete project" feeling slow.

---

## Rollout / Test Plan

### Tests to add

**Unit (new file `src/backend/tests/unit/api/utils/test_cascade_delete_flows.py`):**

- `test_empty_input_is_noop` — pass `[]`, assert no SQL executed (use `sqlalchemy.event` listener or mock `session.exec`).
- `test_single_flow_delegates_through_shim` — call `cascade_delete_flow(session, id)`, assert it produces the same DELETE sequence as the batched helper with `[id]`.
- `test_batch_deletes_in_correct_order` — fixture builds 3 flows with attached `MessageTable`, `TransactionTable`, `VertexBuildTable`, `FlowVersion`, `TraceTable`, `SpanTable` rows. After `cascade_delete_flows(session, [f1, f2, f3])`, assert `select(count()).from(...)` returns 0 for each child table and the `flow` table.
- `test_batch_with_partial_traces` — only some flows have traces; spans for those traces are deleted, traceless flows still cleaned up.
- `test_chunking_at_batch_boundary` — pass 501 ids; assert the helper issues 2 chunks (use a wrapper that counts `session.exec` calls per table).
- `test_chunking_preserves_dependency_order` — within a chunk, span DELETE strictly precedes trace DELETE; across chunks, each chunk completes its own dependency order before the next chunk starts.
- `test_partial_failure_rolls_back_whole_batch` — monkey-patch the trace DELETE to raise; assert flow rows are still present (rollback fired) and the original `RuntimeError` propagates.
- `test_unrelated_flows_untouched` — set up flow A in scope and flow B out of scope; delete A only; assert B and B's children still exist.

**Integration (extend `src/backend/tests/integration/api/v1/test_projects.py` and `test_flows.py`):**

- Project-deletion test: create a project with 5 flows, each with messages/transactions/vertex_builds/traces/spans, call `DELETE /api/v1/projects/{id}`, assert post-delete row count is 0 across all child tables for those flow_ids and exactly preserved for sibling flows in another project.
- Bulk flow delete: same matrix using `DELETE /api/v1/flows/` with body `[id1, id2, id3]`.

**Performance smoke (no assertion, manual reproduction):**

- Create a project with 100 flows + populated children. Capture wall-clock for `DELETE /api/v1/projects/{id}` before and after the change. Document the numbers in `docs/superpowers/plans/notes/cascade-batch-perf-2026-04-26.md`.

### Verification commands

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests/unit/api/utils/test_cascade_delete_flows.py -v
uv run pytest src/backend/tests/integration/api/v1/test_projects.py -k "cascade or delete" -v
uv run pytest src/backend/tests/integration/api/v1/test_flows.py -k "delete_multiple" -v
```

---

## Tasks

### Task 1: Failing unit tests for `cascade_delete_flows`

**Files:**
- Create: `src/backend/tests/unit/api/utils/test_cascade_delete_flows.py`

**Purpose:** Strict TDD — write the test file referencing the not-yet-created helper. Confirm the suite fails at import.

- [ ] **Step 1: Write the test file** with the cases listed under "Tests to add → Unit" above. Skeleton:

```python
import uuid

import pytest
from sqlmodel import select

from langflow.api.utils import cascade_delete_flow, cascade_delete_flows
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable


@pytest.mark.asyncio
async def test_empty_input_is_noop(session_with_flows):
    # ... see plan for full case list
    ...
```

- [ ] **Step 2: Run the suite, verify import-error failure**

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests/unit/api/utils/test_cascade_delete_flows.py -v 2>&1 | tail -20
```

Expected: failure with `ImportError: cannot import name 'cascade_delete_flows'`.

- [ ] **Step 3: Commit (PAUSE)**

```bash
git add src/backend/tests/unit/api/utils/test_cascade_delete_flows.py
git commit -m "test(perf): failing tests for cascade_delete_flows batched helper"
```

---

### Task 2: Implement `cascade_delete_flows` and shim `cascade_delete_flow`

**Files:**
- Modify: `src/backend/base/langflow/api/utils/core.py`
- Modify: `src/backend/base/langflow/api/utils/__init__.py` (export `cascade_delete_flows`)

**Purpose:** Add the batched helper and reduce `cascade_delete_flow` to a one-line wrapper. Behavior preserved exactly.

- [ ] **Step 1: Add `cascade_delete_flows` and `_BATCH_SIZE` constant** to `core.py` immediately above the existing `cascade_delete_flow`. Body as shown in "Proposed Batched Approach" — including the chunking outer loop.

- [ ] **Step 2: Replace `cascade_delete_flow` body** with:

```python
async def cascade_delete_flow(session: AsyncSession, flow_id: uuid.UUID) -> None:
    """Single-flow convenience wrapper. See cascade_delete_flows."""
    await cascade_delete_flows(session, [flow_id])
```

- [ ] **Step 3: Add the export** in `src/backend/base/langflow/api/utils/__init__.py` so call sites can import the new name. Find the existing `cascade_delete_flow` re-export and add `cascade_delete_flows` to the same line.

- [ ] **Step 4: Run unit tests, verify all pass**

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests/unit/api/utils/test_cascade_delete_flows.py -v 2>&1 | tail -20
```

Expected: 8 tests pass.

- [ ] **Step 5: Run the full unit suite to confirm no regressions in callers**

```bash
uv run pytest src/backend/tests/unit -q 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 6: Commit (PAUSE)**

```bash
git add \
  src/backend/base/langflow/api/utils/core.py \
  src/backend/base/langflow/api/utils/__init__.py
git commit -m "perf(db): cascade_delete_flows — single-statement batched cascade"
```

---

### Task 3: Switch `delete_project` to the batched helper

**Files:**
- Modify: `src/backend/base/langflow/api/v1/projects.py`

**Purpose:** Replace the per-flow loop at lines 530–531 with one call.

- [ ] **Step 1: Update the import** at line 21:

```python
from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    cascade_delete_flow,
    cascade_delete_flows,
    custom_params,
    remove_api_keys,
)
```

(Keep the existing `cascade_delete_flow` import in case other code in this file uses it — Grep first to confirm, drop if not.)

- [ ] **Step 2: Replace the loop** at lines 523–531:

```python
flow_ids = (
    await session.exec(
        select(Flow.id).where(
            Flow.folder_id == project_id, Flow.organization_id == current_org.id
        )
    )
).all()
await cascade_delete_flows(session, flow_ids)
```

(Note: the original selected the full `Flow` object only to read `.id`. The replacement selects only `Flow.id` — a small extra win.)

- [ ] **Step 3: Run integration tests**

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests/integration/api/v1/test_projects.py -k "delete" -v 2>&1 | tail -20
```

Expected: all delete-path tests pass.

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add src/backend/base/langflow/api/v1/projects.py
git commit -m "perf(api): batch cascade-delete in delete_project"
```

---

### Task 4: Switch `delete_multiple_flows` to the batched helper

**Files:**
- Modify: `src/backend/base/langflow/api/v1/flows.py`

**Purpose:** Replace the per-flow loop at lines 1135–1136.

- [ ] **Step 1: Update the import** at line 33 to include `cascade_delete_flows`.

- [ ] **Step 2: Replace the loop** at lines 1128–1138:

```python
flow_ids_in_org = (
    await db.exec(
        select(Flow.id)
        .where(col(Flow.id).in_(flow_ids))
        .where(Flow.organization_id == current_org.id)
    )
).all()
await cascade_delete_flows(db, flow_ids_in_org)
await db.flush()
return {"deleted": len(flow_ids_in_org)}
```

The org-scoped SELECT remains so cross-org flow IDs in the request body are silently filtered (existing behavior).

- [ ] **Step 3: Run integration tests**

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests/integration/api/v1/test_flows.py -k "delete_multiple" -v 2>&1 | tail -20
```

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add src/backend/base/langflow/api/v1/flows.py
git commit -m "perf(api): batch cascade-delete in delete_multiple_flows"
```

---

### Task 5: Switch `clear_user_state` to the batched helper

**Files:**
- Modify: `src/backend/base/langflow/services/flow/flow_runner.py`

**Purpose:** Lines 230–233 today loop `cascade_delete_flow` over every flow owned by a user. Same shape as the other two call sites — replace with a single call.

- [ ] **Step 1: Update the import** at line 13 to include `cascade_delete_flows`.

- [ ] **Step 2: Rewrite the loop**

Find:

```python
flows = await session.exec(select(Flow.id).where(Flow.user_id == user_id))
flow_ids: list[UUID] = [fid for fid in flows.scalars().all() if fid is not None]
for flow_id in flow_ids:
    await cascade_delete_flow(session, flow_id)
await session.exec(delete(Variable).where(Variable.user_id == user_id))
await session.exec(delete(User).where(User.id == user_id))
```

Replace the loop with:

```python
flows = await session.exec(select(Flow.id).where(Flow.user_id == user_id))
flow_ids: list[UUID] = [fid for fid in flows.scalars().all() if fid is not None]
await cascade_delete_flows(session, flow_ids)
await session.exec(delete(Variable).where(Variable.user_id == user_id))
await session.exec(delete(User).where(User.id == user_id))
```

- [ ] **Step 3: Run the relevant tests**

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests -k "clear_user_state or clear_state" -v 2>&1 | tail -10
```

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add src/backend/base/langflow/services/flow/flow_runner.py
git commit -m "perf(db): batch cascade-delete in clear_user_state"
```

---

### Task 6: Performance smoke + capture before/after

**Files:**
- Create: `docs/superpowers/plans/notes/cascade-batch-perf-2026-04-26.md`

**Purpose:** Document the wall-clock impact concretely.

- [ ] **Step 1: Pre-stage `git stash`** the changes from Tasks 2–5 (keeping Task 1's tests). Restore the original loop-based code as the baseline.

- [ ] **Step 2: Set up a fixture project** with 100 flows, each with 5 messages, 5 transactions, 5 vertex_builds, 5 flow_versions, 1 trace + 3 spans. A small Python script run via `uv run python` against the dev Postgres works.

- [ ] **Step 3: Time the baseline**

```bash
time curl -X DELETE -H "Cookie: ..." http://localhost:7860/api/v1/projects/<project_id>
```

Record the wall-clock.

- [ ] **Step 4: `git stash pop`** to restore the batched code. Recreate the fixture (since the previous request deleted it). Re-run the timing.

- [ ] **Step 5: Write the notes file**

```markdown
# Cascade-delete batching — perf capture (2026-04-26)

## Setup
- Postgres 16 over loopback, ~0.5ms RTT
- Project with 100 flows; each flow: 5 messages, 5 transactions, 5 vertex_builds, 5 flow_versions, 1 trace + 3 spans

## Results

| Variant   | Wall-clock | Round-trips (estimate) |
|-----------|-----------|------------------------|
| Baseline  | <X> s     | ~750                   |
| Batched   | <Y> s     | ~7                     |
| Speedup   | <X/Y>×    | ~100×                  |

## Observations

- ...
```

- [ ] **Step 6: Commit (PAUSE)**

```bash
git add docs/superpowers/plans/notes/cascade-batch-perf-2026-04-26.md
git commit -m "docs(perf): cascade-delete batching — before/after capture"
```

---

### Task 7: Final verification

**Files:** None modified.

- [ ] **Step 1: Full unit suite**

```bash
cd .worktrees/perf-cascade-batch
uv run pytest src/backend/tests/unit -q 2>&1 | tail -10
```

- [ ] **Step 2: Full integration suite (slow — run only the relevant subset first)**

```bash
uv run pytest src/backend/tests/integration -k "delete or cascade or project or flow" -q 2>&1 | tail -10
```

- [ ] **Step 3: Lint**

```bash
uv run ruff check src/backend/base/langflow/api/utils/core.py \
                  src/backend/base/langflow/api/v1/projects.py \
                  src/backend/base/langflow/api/v1/flows.py \
                  src/backend/base/langflow/services/flow/flow_runner.py
```

Expected: 0 errors.

- [ ] **Step 4: Manual smoke**

In the running app:
1. Create a project with 3 flows; populate one flow with messages by running it.
2. Delete the project via the UI.
3. Verify in Postgres: `SELECT count(*) FROM message WHERE flow_id IN (...)` → 0; same for `transaction`, `vertex_build`, `flow_version`, `trace`, `span`, `flow`.
4. Repeat for "select multiple flows → delete" in the flows list.

- [ ] **Step 5: Final pause**

Ask the user: "All cascade-delete batching tasks complete and verified. Ready to consolidate / merge, or keep as-is?"

---

## Open Questions / Risks

- **`MessageTable` vs `Message` deletion semantics.** The `cascade_delete_flow` source comment flags an unresolved concern: "Verify if deleting messages is safe in terms of session id relevance." The batched helper inherits this exactly — same TODO, same risk. Out of scope for this change; the batched helper does not introduce any new behavior here. Surface to whoever owns chat/session-id semantics as a separate item if it is still open after this lands.
- **`flow_run` table.** The `flow_run` table (model at `services/database/models/flow_run/model.py:34`) has `flow_id: UUID = Field(foreign_key="flow.id", index=True)` — a child of `flow` that the existing `cascade_delete_flow` does **not** delete. Either the FK CASCADE is being relied on (Postgres-only) and SQLite parity is broken today, or this is an existing bug. The batched helper preserves the existing behavior — including the omission. Flag as a follow-up: should `flow_run` be added to the cascade list, and if so, was it always missing or did a recent migration introduce it without the helper update?
- **`tag.flow_id`, `flow_usage_daily.flow_id`, `pro_service_quote.flow_id`, `jobs.flow_id`.** Same shape — `flow_id` columns that may or may not be in the cascade. Quick audit before commit: are these tables expected to be cleaned on flow delete, or are they intentionally orphaned (e.g., for billing/audit retention)? Don't expand the cascade scope in this change — surface the question in the plan-completion message and let the owner decide.
- **`IN`-list chunk size of 500.** Picked conservatively to stay under SQLite 3.31's 999-param limit with margin. If the deployment target is exclusively Postgres, the chunk size could go to ~10000 with no real risk — minor speedup for the 1000+ flow case. Leave at 500 for safety; revisit if a perf-oriented project deletion benchmark surfaces it.
- **Index on `transaction.flow_id` and `vertex_build.flow_id`.** Both DELETEs use `flow_id IN (...)`. Confirm indexes exist (a quick `\d transaction` / `\d vertex_build` in psql). If they don't, large-batch DELETEs degrade to seq-scans and the win shrinks. Flag during Task 6's perf capture.

---

## Deferred / Out of Scope

- Adding `flow_run` (and friends) to the cascade — see Open Questions.
- Cache invalidation on flow delete (`chat_service` cache currently leaks past delete; a separate fix).
- Per-flow audit events on bulk delete — none today; if added, they go at the call site, not in the helper.
- Switching from `delete()` statements to FK CASCADE-only (Postgres) — would require fixing SQLite first; not worth the complexity for marginal additional gain.
