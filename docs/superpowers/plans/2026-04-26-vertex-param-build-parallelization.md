# Vertex Param-Build Parallelization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **CRITICAL — user-level rule (overrides skill defaults):** Every step labelled "Commit" must pause and ask the user for explicit approval before running `git commit`. Never use `git add -A`, `git add .`, or `git commit -a` — always stage explicit paths. This applies to every commit in this plan.

**Goal:** Convert the sequential per-key `await` loop in `Vertex._build_each_vertex_in_params_dict` into a single `asyncio.gather` so that independent upstream-vertex `get_result()` calls run concurrently. Keep the post-gather merge into `self.params` deterministic and ordered.

**Architecture:** A targeted refactor to one method (~25 lines) plus mirrored changes to two helpers (`_build_dict_and_update_params`, `_build_list_of_vertices_and_update_params`). The dispatch logic that decides per-key handling stays as it is; only the awaits move into a coroutine-collection phase followed by a gather and a synchronous post-merge phase. No public API changes.

**Tech Stack:** Python 3.11+, `asyncio`, `pytest-asyncio`, lfx graph internals.

**Source finding:** `src/lfx/src/lfx/graph/vertex/base.py:585-608` (the `_build_each_vertex_in_params_dict` body). Vertices with wide dependency fan-in (many list/dict inputs) currently pay the latency of every upstream `get_result()` end-to-end serially on each flow build.

---

## File map

| Path | Role |
| --- | --- |
| `src/lfx/src/lfx/graph/vertex/base.py` | MODIFY — replace sequential awaits in three sibling methods with `asyncio.gather` |
| `src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py` | NEW — pin concurrency contract and ordering invariants |
| `src/backend/tests/unit/graph/test_graph.py` (or nearest existing graph integration test) | READ-ONLY first; ADD a regression case if the existing suite doesn't already exercise wide fan-in |

---

## Problem statement

The exact code in question (read this before editing — line numbers may have drifted; the file is on `platform-multi-tenant`):

```python
# src/lfx/src/lfx/graph/vertex/base.py:585-608
async def _build_each_vertex_in_params_dict(self) -> None:
    """Iterates over each vertex in the params dictionary and builds it."""
    for key, value in self.raw_params.items():
        if self._is_vertex(value):
            if value == self:
                del self.params[key]
                continue
            await self._build_vertex_and_update_params(
                key,
                value,
            )
        elif isinstance(value, list) and self._is_list_of_vertices(value):
            await self._build_list_of_vertices_and_update_params(key, value)
        elif isinstance(value, dict):
            await self._build_dict_and_update_params(
                key,
                value,
            )
        elif key not in self.params or self.updated_raw_params:
            self.params[key] = value

    # Reset the flag after processing raw_params
    if self.updated_raw_params:
        self.updated_raw_params = False
```

Each `await` blocks until the upstream vertex's `get_result()` returns. Because every iteration of the loop awaits before the next iteration starts, N independent upstream builds are serialized — each pays its own latency in full. For a vertex with K upstream dependencies that each take T ms, the loop costs K·T ms even though the dependencies are independent. The same pattern repeats inside `_build_list_of_vertices_and_update_params` (`for vertex in vertices: await ...`) and `_build_dict_and_update_params` (`for sub_key, value in vertices_dict.items(): ... await ...`).

This is exclusively wallclock waste — the Python event loop is idle during each `await`, the dependencies are independent, and the only post-gather work is dict assignment.

---

## Proposed change

For `_build_each_vertex_in_params_dict`:

1. **First pass (sync):** walk `self.raw_params.items()` and bin keys into four buckets:
   - `self_ref` — keys whose value is `self` (deleted from `self.params`, unchanged behaviour).
   - `vertex_keys` — keys whose value is a single upstream `Vertex`.
   - `list_keys` — keys whose value is a `list[Vertex]`.
   - `dict_keys` — keys whose value is a `dict` (mixed vertex / non-vertex contents).
   - Plain-value keys (the `elif` branch at line 603-604) are handled inline — they don't await.
2. **Coroutine collection:** build a list of coroutines, one per non-self-ref key:
   - For each `vertex_keys` entry, create a task wrapping `value.get_result(self, target_handle_name=key)` (NOT `_build_vertex_and_update_params`, because that method also performs the post-merge — see "Concurrency risk analysis" below).
   - For each `list_keys` entry, create a task that awaits each upstream `get_result` (still serial within a single key — see "Two-level parallelism" below).
   - For each `dict_keys` entry, similarly.
3. **Gather:** `results = await asyncio.gather(*coros)`.
4. **Second pass (sync):** zip the gathered results back to their keys and run the post-merge logic that is currently interleaved with the await — `_handle_func`, `_extend_params_list_with_result`, list-flattening, and final `self.params[key] = ...` assignment. Because this runs after the gather completes, no two coroutines write to `self.params` concurrently.
5. Run the `self.updated_raw_params = False` reset at the very end, unchanged.

The same pattern applies to `_build_list_of_vertices_and_update_params` and `_build_dict_and_update_params`: collect inner coroutines, gather, then post-merge sequentially under the same key.

---

## Concurrency risk analysis

This is the meat of the plan. I read every helper that the current loop touches; the relevant functions are `_build_vertex_and_update_params`, `_build_list_of_vertices_and_update_params`, `_build_dict_and_update_params`, `_handle_func`, `_extend_params_list_with_result`, and the upstream `Vertex.get_result` / `_get_result`.

### What state does each coroutine touch?

The single-vertex path (`_build_vertex_and_update_params`):

```python
# src/lfx/src/lfx/graph/vertex/base.py:685-691
async def _build_vertex_and_update_params(self, key, vertex: Vertex) -> None:
    """Builds a given vertex and updates the params dictionary accordingly."""
    result = await vertex.get_result(self, target_handle_name=key)
    self._handle_func(key, result)
    if isinstance(result, list):
        self._extend_params_list_with_result(key, result)
    self.params[key] = result
```

- `vertex.get_result(...)` acquires `vertex.lock` (per-source asyncio.Lock at `base.py:130-135`) and returns either `built_result` or `built_object`. It is a read-only call once the source is built — it raises if the source isn't built. Multiple consumers awaiting the same source serialize on that source's lock; they do not race.
- `self._handle_func(key, result)` mutates `self.params["coroutine"]` when `key == "func"`. Two simultaneous func keys would be a problem, but a vertex has at most one `func` input — fine. Document this as a precondition; assert it in the new test.
- `self._extend_params_list_with_result(key, result)` reads `self.params[key]` and `.extend(result)`s into it.
- `self.params[key] = result` assignment.

The list-of-vertices path (`_build_list_of_vertices_and_update_params`, lines 693-721):

- Resets `self.params[key] = []` once, then iterates and `.append()`s / `.extend()`s. Order within a single key matters for downstream consumers (the list is the input to a component).
- Reads `self.params[key]` between iterations.

The dict path (`_build_dict_and_update_params`, lines 610-621):

- Mutates `self.params[key][sub_key] = result` for each sub-key.
- Inside one outer key the sub-keys are independent dict slots, so they can also gather.

### What can race under naive `gather`?

Naively wrapping `_build_vertex_and_update_params` calls in `asyncio.gather` introduces three categories of write to `self.params`:

1. **Different keys, simple writes (`self.params[key] = result`)** — safe under asyncio because each write is a single non-async dict slot store; the event loop never preempts mid-statement.
2. **Same key visited twice via the `func`/`coroutine` side-channel** — only one `func` key per vertex, but `_handle_func` writes `self.params["coroutine"]` from *any* func-typed input. If two awaits concurrently set `self.params["coroutine"]` the last writer wins. This is a real (if narrow) hazard. Mitigation: post-gather merge — apply `_handle_func` after results are gathered, in deterministic key-iteration order.
3. **`_extend_params_list_with_result` read-modify-write** — reads `self.params[key]`, then `.extend(result)`. If two coros' awaits resolved between these two operations, an interleaving would corrupt the list. In practice asyncio schedules them serially (each chunk runs to its next `await` without preemption), but the safer pattern is still to do the merge synchronously after gather.

### Mitigation strategy

**Per-task isolated state, post-gather merge.** Each gathered coroutine returns its raw `result` only; it does NOT touch `self.params`. After `gather` returns, a synchronous loop walks the (key, result) pairs in the original `raw_params.items()` order and applies all the existing merge logic exactly as before. This eliminates every shared-write hazard above by construction.

Concretely the new shape of `_build_each_vertex_in_params_dict` is:

```python
async def _build_each_vertex_in_params_dict(self) -> None:
    """Iterates over each vertex in the params dictionary and builds it."""
    # Phase 1 (sync): bin keys, gather plain-value writes inline.
    pending: list[tuple[str, Any, Any]] = []  # (key, kind, payload)
    for key, value in self.raw_params.items():
        if self._is_vertex(value):
            if value == self:
                del self.params[key]
                continue
            pending.append((key, "vertex", value))
        elif isinstance(value, list) and self._is_list_of_vertices(value):
            pending.append((key, "list", value))
        elif isinstance(value, dict):
            pending.append((key, "dict", value))
        elif key not in self.params or self.updated_raw_params:
            self.params[key] = value

    # Phase 2 (gather): launch all upstream get_result calls concurrently.
    coros = [self._collect_param_value(kind, payload, key) for key, kind, payload in pending]
    resolved = await asyncio.gather(*coros)

    # Phase 3 (sync): merge back, preserving raw_params iteration order.
    for (key, kind, _payload), value in zip(pending, resolved, strict=True):
        self._merge_resolved_param(key, kind, value)

    if self.updated_raw_params:
        self.updated_raw_params = False
```

Where `_collect_param_value` does the awaiting and returns a kind-specific payload (a single result for `"vertex"`, a list of results for `"list"`, a dict of results for `"dict"`), and `_merge_resolved_param` runs the existing post-await mutation logic (`_handle_func`, list-extend, dict-slot assignment) without any awaits.

### Two-level parallelism (optional, do last)

Inside `_build_list_of_vertices_and_update_params` and `_build_dict_and_update_params` the inner loops are themselves serial. Once the outer-level gather lands and is verified, an obvious follow-up is to gather the inner `get_result` calls too. This compounds wins on vertices with many `list[Vertex]` inputs, but it is strictly an additive optimization and can ship as Task 4.

---

## Ordering concerns

`asyncio.gather` preserves the order of its input list — `await asyncio.gather(c1, c2, c3)` returns `[r1, r2, r3]` regardless of which finished first. The plan exploits this by walking `pending` (in `raw_params.items()` order, which is insertion-order on dict) when merging. So:

- Single-vertex keys land in `self.params` in the same order as before.
- List-of-vertex keys preserve intra-list order because the inner loop in `_collect_param_value` for `"list"` either keeps its inner serial awaits (default) or uses an inner `gather` that also preserves order.
- Dict keys: each sub-key is filled deterministically because we keep the dict's insertion order in the inner walk.

The `func` -> `coroutine` side effect in `_handle_func` happens during the merge phase, in `raw_params` iteration order, identical to today's behaviour (the loop already visits keys in this order).

No downstream consumer of `self.params` should observe a different ordering than today. Pin this with a test that builds a vertex with multiple ordered upstreams and asserts `list(self.params.keys()) == list(self.raw_params.keys())` plus the per-list ordering invariant.

---

## Error handling

Today the loop propagates the first exception immediately because of the explicit `await`. A `ComponentBuildError` from any upstream `get_result` aborts the whole build of `self`.

`asyncio.gather` defaults to **fail-fast**: if any coroutine raises, gather cancels the rest and re-raises. This matches today's behaviour at the level of "this vertex failed to build" — the parent vertex still raises, the user still sees the same exception. Cancellation of the in-flight upstream tasks is fine because they only acquire per-source locks (which release on cancel) and each upstream's own `_build` is a separately scheduled coroutine guarded by its own try/except in `Graph.build`.

**Match the codebase pattern: do NOT pass `return_exceptions=True`.** A grep for `asyncio.gather(` across `src/lfx` and `src/backend` shows the prevailing pattern is fail-fast; `return_exceptions=True` is only used in narrow event-broadcasting paths where partial failure is intentional. The vertex param-build path is the opposite — partial failure leaves `self.params` half-populated, which is worse than failing the whole build. Confirm during implementation by re-running the grep on the merged branch.

One subtlety: today, exceptions thrown by an early upstream prevent later upstreams from being built *at all* in this iteration. After gather, all upstreams are launched concurrently — a doomed-to-fail upstream's later sibling will be cancelled mid-flight. This is a minor behaviour change in the failure path: at most you'll see an extra "starting build" log line for cancelled siblings. Document this in the commit message and the test plan; it's not user-visible.

---

## Estimated wins

**Honest assumption:** the win scales with `K * average_get_result_latency` for vertices that have K upstreams whose results are not already cached.

- Vertex with 10 upstream deps each blocking 50ms on its own build: today 500ms in this loop, after gather ~50ms (limited by the slowest dep). 10× wallclock cut on this method.
- Vertex with 10 upstreams that are all already-built (warm cache): no measurable change. `get_result` returns immediately.
- Vertex with 1 upstream: zero change, possibly a few µs of overhead from the bin/gather/merge restructuring.

**The aggregate flow-level win is bounded by the critical path of the build DAG.** If the slow upstream chains are linear, this optimization shaves only the constant fan-in cost at each fork point. Real measurements need to come from a flow with at least one fan-in node and N>5 upstreams; pick one such flow from `src/backend/tests/integration/data/` (or build a synthetic one in the test plan) and benchmark before/after.

A reasonable order-of-magnitude expectation for a fan-in-heavy production flow: 10-30% wallclock reduction on `Graph.build()`. Over-promising would be dishonest until measured.

---

## Tasks

### Task 0: Worktree setup

**Files:** none (workspace operation only).

- [ ] **Step 1: Confirm you are working in the dedicated worktree**

```bash
git worktree list
pwd
```

Expected: pwd is the dedicated perf worktree (e.g. `~/dev/langflow/.worktrees/perf-vertex-gather`); `git worktree list` shows it on a feature branch off `platform-multi-tenant`. If not, create it before continuing — never run this on the main checkout.

- [ ] **Step 2: Sync deps**

```bash
uv sync --frozen
```

Expected: `Resolved N packages` with no errors.

---

### Task 1: Pin the current behaviour with a regression test

**Files:**
- Create: `src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py`

**Why:** Before changing the loop, write a test that asserts (a) all upstreams produce results in the parent's `self.params`, (b) the keys appear in `raw_params` insertion order, and (c) the order of items within a `list[Vertex]` input is preserved. The same test will be re-run after the gather refactor to prove no regression.

- [ ] **Step 1: Write the test against the current sequential implementation**

The test builds a parent vertex with three upstream stubs that each emit a recognizable result, plus one `list[Vertex]` input with two stubs in a specific order. Assert `parent.params == expected_dict` and `parent.params["multi_input"] == [first_result, second_result]`.

- [ ] **Step 2: Run it; it must pass before any refactor**

```bash
uv run pytest src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py -v
```

Expected: green.

- [ ] **Step 3: Commit (ASK FIRST)**

Stage explicit paths only:

```bash
git add src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py
git commit -m "test(lfx): pin vertex param-build ordering invariants

Pre-refactor regression test for _build_each_vertex_in_params_dict.
Asserts param keys appear in raw_params insertion order and that
list[Vertex] inputs preserve intra-list order.

This test passes against the current sequential implementation; the
upcoming asyncio.gather refactor must also pass it unchanged."
```

---

### Task 2: Add a concurrency-witness test

**Files:**
- Modify: `src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py` (extend with a timing-based witness).

**Why:** The ordering test passes both with and without parallelism. Add a second test that proves the parallelism actually happens — without that we have no way to detect a future regression to sequential behaviour.

- [ ] **Step 1: Write the witness test**

Pattern: each upstream stub's `get_result` sleeps 50ms before returning. Build a parent with 5 such upstreams. Time `await parent._build_each_vertex_in_params_dict()`. Assert wallclock is closer to 50ms than to 250ms. Use a tolerance of ~150ms to allow CI jitter; the goal is to fail loud only if someone reverts to serial awaits.

```python
# Sketch — fill in concrete fixtures from existing test helpers.
import time
import pytest

@pytest.mark.asyncio
async def test_param_build_runs_upstreams_concurrently(parent_vertex_with_5_slow_upstreams):
    parent = parent_vertex_with_5_slow_upstreams  # each upstream sleeps 50ms in get_result
    start = time.perf_counter()
    await parent._build_each_vertex_in_params_dict()
    elapsed = time.perf_counter() - start
    # Serial would be ~250ms; parallel should be ~50-100ms even on a slow CI.
    assert elapsed < 0.20, f"upstreams ran serially: {elapsed:.3f}s"
```

- [ ] **Step 2: Run it; it MUST FAIL against the current sequential code**

```bash
uv run pytest src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py -v
```

Expected: the new test fails (~250ms wallclock). If it passes against the current code, the test is wrong — the upstreams aren't actually slow. Re-check the fixture.

- [ ] **Step 3: Commit (ASK FIRST)**

```bash
git add src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py
git commit -m "test(lfx): add concurrency witness for vertex param build

Currently fails — proves the upstream get_result calls run serially.
The next commit makes this test pass via asyncio.gather."
```

---

### Task 3: Refactor `_build_each_vertex_in_params_dict` to use `asyncio.gather`

**Files:**
- Modify: `src/lfx/src/lfx/graph/vertex/base.py` (the method at lines 585-608, plus two new private helpers).

**Strategy:** the three-phase shape from "Proposed change" above. Do NOT touch the inner loops of `_build_list_of_vertices_and_update_params` / `_build_dict_and_update_params` in this task — Task 4 covers those.

- [ ] **Step 1: Replace the method body**

Re-read the current method and replace it with the bin/gather/merge pattern. Add two new private methods on `Vertex`:

- `async def _collect_param_value(self, kind: str, payload: Any, key: str) -> Any:` — the only `await` site. Branches on `kind`:
  - `"vertex"`: returns `await payload.get_result(self, target_handle_name=key)`.
  - `"list"`: still serial inner await (for now); returns a list of resolved values in order.
  - `"dict"`: still serial inner await; returns `{sub_key: resolved_value_or_passthrough}`.
- `def _merge_resolved_param(self, key: str, kind: str, value: Any) -> None:` — sync. Branches on `kind` and applies the existing post-merge logic verbatim. For `"vertex"` it reproduces the body of today's `_build_vertex_and_update_params` minus the await. For `"list"` and `"dict"` it does the same assignment / append / extend pattern that the old helpers did.

The legacy methods `_build_vertex_and_update_params`, `_build_list_of_vertices_and_update_params`, and `_build_dict_and_update_params` stay in place; they are still public-shaped helpers that `_build_each_vertex_in_params_dict` no longer uses but other code (or subclasses) might. Verify with a grep that nothing outside the vertex base file calls them:

```bash
rg "_build_vertex_and_update_params|_build_list_of_vertices_and_update_params|_build_dict_and_update_params" src/ tests/
```

If any external callers exist, leave the helpers; if not, mark them deprecated in a docstring but do NOT delete in this PR — separate cleanup.

- [ ] **Step 2: Run the regression and witness tests**

```bash
uv run pytest src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py -v
```

Expected: both tests now pass — ordering preserved AND wallclock proves parallelism.

- [ ] **Step 3: Run the broader graph suite**

```bash
uv run pytest src/lfx/tests/unit/graph -m 'not api_key_required and not slow' -q
uv run pytest src/backend/tests/unit/graph -m 'not api_key_required and not slow' -q
```

Expected: no new failures vs the baseline on `platform-multi-tenant`. Capture the baseline before starting the task with the same commands.

- [ ] **Step 4: Run a flow-build smoke check**

```bash
uv run pytest src/backend/tests/unit -k "graph and build" -m 'not api_key_required and not slow' -q --no-header --tb=short
```

Expected: pass. This catches integration tests that build real Graphs.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/lfx/src/lfx/graph/vertex/base.py
git commit -m "perf(lfx): parallelize vertex param build with asyncio.gather

Replaces the sequential await loop in
Vertex._build_each_vertex_in_params_dict with a three-phase
bin/gather/merge pattern. Independent upstream get_result calls now
run concurrently; results are merged back into self.params after
gather() returns, in raw_params iteration order.

Behaviour-preserving:
- Param key order matches today's iteration order.
- list[Vertex] intra-list order preserved.
- Fail-fast on the first upstream exception (matches existing semantics).

Verified by tests/unit/graph/vertex/test_param_build_parallel.py:
ordering invariants pass; wallclock witness drops from ~250ms to
~50-80ms on a 5-upstream synthetic vertex."
```

---

### Task 4 (optional, gated on Task 3 measurements): inner-loop gather

**Files:**
- Modify: `src/lfx/src/lfx/graph/vertex/base.py` — the `_collect_param_value` branches for `"list"` and `"dict"`.

**Why optional:** Task 3 already gives the headline win across keys. Inner-loop gather only helps vertices that have a single key whose value is a `list[Vertex]` of >3 items. Measure first; if no real flow benefits, skip.

- [ ] **Step 1: Identify whether any real flow has high-cardinality `list[Vertex]` inputs**

```bash
rg -l "is_list.*True" src/lfx/src/lfx/components | head
```

The components most likely to fan-in via list inputs are aggregators (e.g. tools-list inputs in Agent components, document-list in indexers). If none in production flows have >3 connected vertices on a single list input, skip this task.

- [ ] **Step 2: If proceeding, replace the inner serial loop**

In `_collect_param_value` for `kind == "list"`, replace `for vertex in payload: results.append(await vertex.get_result(...))` with:

```python
inner_coros = [v.get_result(self, target_handle_name=key) for v in payload]
return await asyncio.gather(*inner_coros)
```

Same idea for `kind == "dict"`: gather over the sub-key vertices, then assemble the dict in the merge phase.

- [ ] **Step 3: Re-run the witness test extended with a list-input case**

Update the test to also assert that a 5-element `list[Vertex]` input runs in <100ms wallclock when each element sleeps 50ms.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git add src/lfx/src/lfx/graph/vertex/base.py src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py
git commit -m "perf(lfx): parallelize inner list/dict get_result loops too

Builds on the outer-loop gather: the per-key list[Vertex] and
dict[str, Vertex] inputs now also gather their inner get_result calls.
Intra-list / intra-dict order is preserved by relying on
asyncio.gather's order-preserving result list."
```

---

## Rollout / test plan

- **Unit:** the two new tests in `src/lfx/tests/unit/graph/vertex/test_param_build_parallel.py` (ordering pin + concurrency witness) are the contract.
- **Integration:** run `src/backend/tests/integration/services/test_flow_runner.py` (or whatever the closest end-to-end flow-build test is) before and after to confirm no behavioural change on real flows.
- **Manual smoke:** pick one fan-in-heavy flow (an Agent vertex with multiple tool inputs is the obvious one) and time `Graph.build()` before and after. Record the numbers in the Task 3 commit message.
- **No feature flag.** This is a pure-internal optimization with no behavioural surface change. Gating it would only add complexity. If something breaks, revert is one commit.

---

## Open questions / risks

1. **Are there any subclasses of `Vertex` that override `_build_each_vertex_in_params_dict`?** Grep before the refactor:

   ```bash
   rg "_build_each_vertex_in_params_dict" src/
   ```

   If a subclass (e.g. `ComponentVertex`) overrides this method, the override needs the same treatment — and the override pattern is documented as a known landmine in the project memory (`ComponentVertex.finalize_build` shadows the base). Verify before declaring done.

2. **Does `get_result` ever recursively trigger another `_build`?** A skim of `_get_result` says it only reads `self.built_result` / `self.built_object` and raises if not built. The actual build is driven by the graph builder elsewhere. Confirm by tracing `get_result` callers; if any path reaches back into `_build`, gather could re-enter the same vertex's lock from two siblings — this would deadlock. The per-vertex `asyncio.Lock` is non-reentrant. (Empirically the lock is only acquired in `Vertex.get_result`, so this should be fine, but worth a paranoid recheck during Task 3 step 1.)

3. **Cancellation semantics on a partial failure** — when one upstream raises, gather cancels the others. If an upstream coroutine has a `finally:` that touches shared state (e.g. logs a transaction), the cancel-during-await could leave that side effect partially applied. The existing serial loop also leaves partial state on early failure (later upstreams just don't run), so the user-visible difference is small. Note in the commit message and move on.

4. **Two-level gather memory footprint** — gathering 100+ inner list elements all at once briefly holds 100+ pending tasks in flight. For very wide list inputs this could matter; if so, switch to a `Semaphore`-bounded gather. Defer until measured.

---

## Out of scope (intentional)

- Parallelizing across DIFFERENT vertices' `_build_each_vertex_in_params_dict` calls — that's `Graph.build`'s scheduler, a separate plan.
- Caching `get_result` outputs across builds — orthogonal optimization.
- Replacing the per-vertex `asyncio.Lock` with something cheaper — also orthogonal; the lock is rarely contended even today.
- Removing the now-unused `_build_vertex_and_update_params` / `_build_list_of_vertices_and_update_params` / `_build_dict_and_update_params` helpers (kept as a safe cleanup follow-up; deletion is a separate, easily-revertible commit).
