# Graph deepcopy elimination — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the four `copy.deepcopy` call sites that hit the running `Graph` during execution — three in `_snapshot()` / `get_snapshot()` and one in `Graph.__add__` — replacing them with structural copies that match the actual mutation profile of the data being snapshotted. These run on the per-step execution path; on a 50-vertex / 5-layer graph they account for an estimated ~30–60 ms per build, dominated by the `_snapshot` calls (one per `astep`).

**Architecture:** Two-phase rollout, smaller blast radius first. Phase 1 rewrites `_snapshot()` and `get_snapshot()` (Tasks 2–5) — these snapshot only string-keyed sets/lists/dicts off `RunnableVerticesManager`, so structural copy via `copy.copy` + `dict`/`list`/`set` constructors is sufficient and safe. Phase 2 (Task 6) rewrites `Graph.__add__` to construct the new graph from `_vertices` + `_edges` data (the same path `__deepcopy__` falls back to when `_start`/`_end` are None) instead of cloning the live instance. A regression-canary microbench (Task 1) and a snapshot-immutability test (Task 4) gate both phases. No feature flag — the rewrite preserves observable behavior or it goes back.

**Tech Stack:** Python 3.11+, asyncio, pytest, the `lfx` graph engine in `src/lfx/src/lfx/graph/graph/base.py`. Touches one Python file plus tests; no schema or API surface changes.

**Spec:** Inline below — there is no separate spec doc. Read the source-finding section before starting.

**Standing instructions (from user's memory / AGENTS.md):**
- **Never `git commit` without explicit approval.** Each "Commit" step pauses and asks.
- **Stage explicit file paths.** Never `git add -A`/`.`/`-a`. The repo has unrelated WIP — only stage what this plan touches.
- **No upstream PR.** All work lands on `platform-multi-tenant`. Do not push to `origin` (which is langflow-ai/langflow upstream).
- **Worktree-first.** Every change happens inside the worktree set up in Task 0.
- **lfx test isolation:** to run `src/lfx/tests/` from the repo-level venv, set `LFX_TEST_ALLOW_LANGFLOW=1` (see `~/.claude/projects/.../reference_lfx_test_env.md`).
- **Subagent commit hygiene:** subagents never commit and never `git add`. They edit files; the controller stages and commits at the end of each phase.

---

## Source finding (verified)

`src/lfx/src/lfx/graph/graph/base.py` (verified at HEAD on `platform-multi-tenant`, 2026-04-26):

**Site A — `_snapshot()`, lines 404–411:**

```python
def _snapshot(self):
    return {
        "_run_queue": self._run_queue.copy(),
        "_first_layer": self._first_layer.copy(),
        "vertices_layers": copy.deepcopy(self.vertices_layers),
        "vertices_to_run": copy.deepcopy(self.vertices_to_run),
        "run_manager": copy.deepcopy(self.run_manager.to_dict()),
    }
```

**Site B — `get_snapshot()`, lines 1497–1507:**

```python
def get_snapshot(self):
    return copy.deepcopy(
        {
            "run_manager": self.run_manager.to_dict(),
            "run_queue": self._run_queue,
            "vertices_layers": self.vertices_layers,
            "first_layer": self.first_layer,
            "inactive_vertices": self.inactive_vertices,
            "activated_vertices": self.activated_vertices,
        }
    )
```

`get_snapshot()` is called from `_record_snapshot()` (line 1510) which is called from `astep()` (line 1494) and from `prepare()` (line 2162). On every `astep`, every snapshot, the entire dict above is deepcopied.

**Site C — `Graph.__add__`, lines 185–196:**

```python
def __add__(self, other):
    if not isinstance(other, Graph):
        msg = "Can only add Graph objects"
        raise TypeError(msg)
    # Add the vertices and edges from the other graph to this graph
    new_instance = copy.deepcopy(self)
    for vertex in other.vertices:
        # This updates the edges as well
        new_instance.add_vertex(vertex)
    new_instance.build_graph_maps(new_instance.edges)
    new_instance.define_vertices_lists()
    return new_instance
```

`__add__` invokes `Graph.__deepcopy__` (line 1102), which itself fans out to ~6 nested `copy.deepcopy` calls including `_vertices` and `_edges` (line 1128).

**Hot-path call sites:**

- `_snapshot()`: only callers are inside the file at line `_call_order.append(...)` paths — verified by `grep -n "_snapshot("`. The current code in `_record_snapshot` calls `get_snapshot()` (the public, deepcopy-everything version), **not** `_snapshot()`. `_snapshot()` looks like a private utility duplicate that is currently dead in the engine path. **This needs verification in Task 1.**
- `get_snapshot()`: called from `_record_snapshot()` on every `astep` (per-vertex completion) and once from `prepare()` at graph start.
- `__add__`: no callers in production code (`grep -rn "graph.*\\+\\s" src/` against operator usage finds none); referenced only via `__add__` in `dir()` in `src/lfx/tests/unit/test_data_class.py:98`. The cost of `__add__` is therefore not on a hot path today, but the deepcopy chain it triggers is on the *cost model* a user-facing flow could pay if anyone ever calls it. Lower priority than `_snapshot`/`get_snapshot`, kept in scope because the rewrite is local and the deepcopy chain in `__deepcopy__` is also a cost smell.

---

## Why deepcopy was chosen — investigation

`git log -L` on each call site, plus a read of the surrounding methods, **finds no comments or commit messages explaining the choice.** What we can infer:

- **`get_snapshot()` (commit `2baee5fef1`, "feat: get result from output if possible", #3338)** was added as part of cycle-execution support. The clear intent is "give me a frozen view of the run state so a test or caller can compare it to a later snapshot and detect change." `copy.deepcopy` is the obvious sledgehammer.
- **`_snapshot()` (commit `bc6e918f49`, "fix: add tests to cycles in Graph and improve error handling", #3628)** was added during cycle-test hardening. Same intent. Note that `_snapshot` uses `.copy()` for `_run_queue` (a `deque`) and `_first_layer` (a `list`) but `deepcopy` for `vertices_layers`, `vertices_to_run`, and `run_manager.to_dict()` — suggesting the author wanted *deeper* protection for the latter three. Looking at the actual types:
    - `self.vertices_layers: list[list[str]]` (declared at line 104) — a list of lists of vertex-ID *strings*.
    - `self.vertices_to_run: set[str]` (declared at line 105) — a set of vertex-ID *strings*.
    - `RunnableVerticesManager.to_dict()` (`runnable_vertices_manager.py` lines 13–20) returns a fresh dict each call; values are `defaultdict(list)`s of strings, sets of strings, and `set`s. The dict itself is fresh, but the values reference live state.
  All terminal values are immutable strings. There are no mutable objects nested inside (no Vertex refs, no Component refs). A `copy.deepcopy` of these structures and a structural shallow-of-shallows produce indistinguishable results — the deepcopy is **strictly wasteful**.
- **`__add__` (commit `22305fe6e3`, #3224)** was added to "implement graph combination." The clear intent is to leave `self` untouched — `a + b` returns a third graph without mutating either operand. `copy.deepcopy(self)` is a defensive choice; the author then calls `add_vertex` on the copy. There is no test for `__add__` (verified — no `def test_*add*` or `graph_a + graph_b` patterns in `src/lfx/tests/`). The deepcopy avoids reasoning about which of the ~30 fields on `Graph` need fresh references vs. which can share.

**Conclusion:** Both `_snapshot`/`get_snapshot` and `__add__` chose `deepcopy` for safety, not correctness. The snapshot dicts contain only strings and primitives — deepcopy is excessive. `__add__` is harder because Graph is a stateful object with many fields, but the same idea applies: only the fields the new graph will mutate need fresh copies.

---

## Proposed alternatives

### Option 1 — Replace `deepcopy` with structural shallow copies for snapshots (RECOMMENDED for `_snapshot`/`get_snapshot`)

For `_snapshot` / `get_snapshot`, the structures being copied are:
- `list[list[str]]` → `[layer.copy() for layer in self.vertices_layers]` (or `[list(l) for l in ...]`).
- `set[str]` → `set(self.vertices_to_run)`.
- `RunnableVerticesManager.to_dict()` returns dicts of `dict[str, list[str]]` and `set[str]` — copy the outer dict, copy each container value once. ~5 lines.

Pros:
- Correctness-preserving: the snapshot is independent of subsequent mutation of the same containers, which is the only invariant the consumers (`test_cycles.py`, `_snapshots` list) rely on.
- ~10–50× faster than `deepcopy` on string-keyed containers (no recursion, no `memo` dict, no `__deepcopy__` dispatch).
- No new dependencies, no new abstractions, no feature flag.

Cons:
- If a future change to `RunnableVerticesManager` introduces nested mutable values (e.g., a `dict[str, dict[str, list[Vertex]]]`), the structural copy will silently miss the deeper layer. Mitigated by a focused test (Task 4) that asserts post-snapshot mutation of the live graph does not affect a captured snapshot.

### Option 2 — Delta tracking (only record what changed) — REJECTED

Record the *change* between snapshots (e.g., "vertex X moved from `vertices_to_run` to `vertices_being_run`") instead of full state.

Pros:
- Memory bound: O(1) per step instead of O(N) per step.

Cons:
- Consumers (`get_snapshot()` callers in `test_cycles.py`) read the full state, not a delta. Reconstructing state from deltas adds replay logic. Big API change for a small win.
- The cost was never the *list* construction — it's the deep traversal. Replacing the recorded shape doesn't help if the recording function still deepcopies.

Rejected: scope creep without proportional gain.

### Option 3 — Snapshot only what tests/consumers actually read — REJECTED for now

Read every `_snapshots` consumer; project the dict to only the keys actually accessed.

Pros:
- Smaller dicts → smaller copies even after Option 1.

Cons:
- The current consumers (cycle tests) read most of the keys. Trimming to "what's read" would either be unsafe (consumer adds a new read tomorrow) or require an explicit projection API. Either is more work than Option 1 for a sub-1ms gain on top of Option 1's already-large win.

Deferred — revisit if Option 1's measured win disappoints.

### Option 4 — For `__add__`: build the new graph from `(_vertices, _edges)` data via `add_nodes_and_edges` (RECOMMENDED for `__add__`)

`Graph.__deepcopy__` (line 1102) already has a code path (lines 1118–1128) that constructs a new `Graph(None, None, flow_id, flow_name, user_id)` and calls `new_graph.add_nodes_and_edges(deepcopy(_vertices), deepcopy(_edges))`. The vertex/edge dicts are JSON-serializable `NodeData`/`EdgeData` shapes — they are owned by `self._vertices` / `self._edges` and not mutated after construction except through `add_nodes_and_edges` itself.

`__add__` can do the same: build a fresh graph from the same constructor, hand it the union of both graphs' `_vertices` + `_edges`, and let `initialize()` rebuild the rest. The result is observably the same graph the deepcopy produced. The cost is one set of fresh `dict()` constructors over `_vertices` + `_edges`, not a recursive walk of every Vertex/Component.

Pros:
- Avoids recursive deepcopy of every Vertex (each of which has a custom-component instance, possibly model clients, lock objects, etc.).
- Reuses an already-tested construction path (`add_nodes_and_edges` is the same path `Graph.__init__` uses).

Cons:
- If `_start`/`_end` are set on `self`, the original `__deepcopy__` takes a *different* code path (lines 1107–1117) that deepcopies the start/end Component instances. `__add__` today doesn't distinguish — it just `deepcopy(self)`s. We need to decide whether the `_start`/`_end` path matters for `__add__`. Investigation suggests no: `__add__` is for combining two component-style graphs; preserving `_start`/`_end` of `self` while adding `other`'s vertices is semantically odd. Confirmed by the lack of tests. Task 6 documents the decision explicitly with a comment.

---

## Recommended approach

**Phase 1 (Tasks 2–5):** Replace deepcopy in `_snapshot()` and `get_snapshot()` with Option 1's structural copy. Add a microbench in Task 1 to measure before/after wall-clock on a representative graph. Add a regression test that captures a snapshot, mutates the graph state, and asserts the snapshot is unchanged — proves the structural copy does not over-share.

**Phase 2 (Task 6):** Replace `__add__`'s `deepcopy(self)` with the `add_nodes_and_edges` path from Option 4. Phase 2 is optional and ships only if Phase 1 lands cleanly. There are no production callers, so the only risk is breaking the dir-output test in `test_data_class.py:98` (which only checks `__add__` is in `dir()` — still true after the rewrite).

Conservatism: Phase 1 ships first because it has consumers (`test_cycles.py`) and clear regression coverage. Phase 2 has no consumers and so can ship under lower scrutiny but also offers no measurable user-facing win until someone actually adds a `__add__` call site. **If pressed for time, ship Phase 1 only and leave Phase 2 deferred.**

---

## File structure

| File | Responsibility | Modified by |
|---|---|---|
| `src/lfx/src/lfx/graph/graph/base.py` | The four deepcopy call sites + the `_snapshot()` / `get_snapshot()` rewrites + the `__add__` rewrite. | Tasks 3, 5, 6 |
| `src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py` (new) | Regression test: snapshot independence after live-graph mutation. | Task 4 |
| `src/lfx/tests/unit/graph/graph/test_graph_addition.py` (new) | Regression test: `a + b` returns a graph with the union of vertices, leaves operands untouched. (Phase 2 only.) | Task 6 |
| `docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md` (new) | Microbench numbers (baseline vs. rewrite). | Task 1, Task 5 |

---

## Task 0 — Worktree setup

**Files:** None modified; sets up the workspace.

- [ ] **Step 1: Create the worktree from `platform-multi-tenant` HEAD**

```bash
cd /Users/brycedeneen/dev/langflow
git worktree add .worktrees/perf-graph-deepcopy -b perf/graph-deepcopy platform-multi-tenant
```

Expected: `.worktrees/perf-graph-deepcopy/` exists; new branch `perf/graph-deepcopy` checked out.

- [ ] **Step 2: Confirm baseline tests pass**

```bash
cd .worktrees/perf-graph-deepcopy
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/graph/test_cycles.py -x 2>&1 | tail -20
```

Expected: skipped tests (require OpenAI key) + `test_conditional_router_max_iterations` passes. The non-skipped test exercises `get_snapshot()` per iteration.

---

## Task 1 — Pre-implementation: microbench + dead-code verification

**Files:**
- Create: `docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md`

**Purpose:** Establish baseline. Two questions to answer before writing any rewrite:

1. Is `_snapshot()` (the underscore version) actually called on the hot path, or is `get_snapshot()` the only one that fires? (Reading the file suggests the latter.)
2. How long does a single `get_snapshot()` take on a 50-vertex graph, and how many fire per build?

- [ ] **Step 1: Verify `_snapshot()` is dead on the execution path**

```bash
cd .worktrees/perf-graph-deepcopy
rg -n '_snapshot\(' src/lfx src/backend
```

Expected: `_snapshot(` (the leading-underscore version, no other prefix) appears only inside `base.py` line 404 (definition). All call sites use `get_snapshot()` or `_record_snapshot()`. Document this finding in the bench notes file. If `_snapshot()` *is* called somewhere we missed, the rewrite still applies — but it goes from "private dead helper" to "second hot path."

- [ ] **Step 2: Write a quick benchmark script**

```bash
mkdir -p docs/superpowers/plans/notes
cat > /tmp/bench_snapshot.py <<'PY'
import time
import statistics
from lfx.graph.graph.base import Graph
from lfx.components.input_output import ChatInput, ChatOutput

# 50 vertices is high but achievable; for a quick approximation,
# build a chain via the same fixture pattern as test_cycles.py.
chat_input = ChatInput(_id="chat_input")
chat_output = ChatOutput(_id="chat_output").set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output)
graph.prepare()

# Warm up
for _ in range(50):
    graph.get_snapshot()

samples = []
for _ in range(1000):
    t0 = time.perf_counter()
    graph.get_snapshot()
    samples.append(time.perf_counter() - t0)

print(f"get_snapshot mean: {statistics.mean(samples) * 1e6:.1f} µs")
print(f"get_snapshot p50:  {statistics.median(samples) * 1e6:.1f} µs")
print(f"get_snapshot p95:  {sorted(samples)[int(len(samples) * 0.95)] * 1e6:.1f} µs")
PY

LFX_TEST_ALLOW_LANGFLOW=1 uv run python /tmp/bench_snapshot.py
```

Capture the numbers. The 2-vertex graph will produce small numbers — multiply mentally by ~25 for a 50-vertex estimate (snapshot size scales roughly linearly with vertex count for the string-set fields).

- [ ] **Step 3: Repeat against `Graph.__add__` (only if you intend to ship Phase 2)**

```bash
cat > /tmp/bench_add.py <<'PY'
import time, statistics
from lfx.graph.graph.base import Graph
from lfx.components.input_output import ChatInput, ChatOutput

a = Graph(ChatInput(_id="a_in"), ChatOutput(_id="a_out").set(input_value=ChatInput(_id="a_in").message_response))
b = Graph(ChatInput(_id="b_in"), ChatOutput(_id="b_out").set(input_value=ChatInput(_id="b_in").message_response))
samples = []
for _ in range(100):
    t0 = time.perf_counter()
    _ = a + b
    samples.append(time.perf_counter() - t0)
print(f"__add__ mean: {statistics.mean(samples) * 1e3:.2f} ms")
print(f"__add__ p95:  {sorted(samples)[int(len(samples) * 0.95)] * 1e3:.2f} ms")
PY
LFX_TEST_ALLOW_LANGFLOW=1 uv run python /tmp/bench_add.py
```

If `__add__` clocks above 5 ms per call on a 4-vertex pair, the Phase 2 win is meaningful even with no current callers.

- [ ] **Step 4: Write up results**

Create `docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md`:

```markdown
# Graph snapshot/deepcopy bench — 2026-04-26 baseline

## Findings
- `_snapshot()` (private): NOT on the execution path — only `get_snapshot()` fires from `_record_snapshot()`. Confirmed by ripgrep.
- `get_snapshot()` baseline (2-vertex graph): mean=X µs, p50=Y µs, p95=Z µs.
- Estimated 50-vertex equivalent: ~25× → ~A ms per snapshot. With one snapshot per `astep`, a 5-layer / 50-vertex flow records ~50 snapshots → ~50A ms total.
- `Graph.__add__` baseline (2-vertex × 2-vertex): mean=B ms.

## Decision
- Phase 1 worth shipping: yes (estimated win >10 ms per build).
- Phase 2 worth shipping: yes / no (decide based on the bench).
```

- [ ] **Step 5: Commit (PAUSE)**

```bash
git add docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md
git commit -m "docs(perf): graph snapshot deepcopy baseline measurements"
```

---

## Task 2 — Failing snapshot-immutability test

**Files:**
- Create: `src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py`

**Purpose:** Strict TDD. Pin the invariant that `get_snapshot()` and `_snapshot()` produce dicts whose container values are independent of subsequent live-graph mutation. Any rewrite (Tasks 3, 5) must keep this green.

- [ ] **Step 1: Write the test**

```python
# src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py
"""Regression tests for Graph snapshot independence.

These pin the contract that `get_snapshot()` and `_snapshot()` return dicts
whose container values are NOT shared with the live graph state. Mutating the
graph after capturing a snapshot must not change the captured snapshot, and
mutating the snapshot must not change the graph.

If a rewrite of the snapshot path replaces `copy.deepcopy` with something
shallower (the perf/graph-deepcopy plan), these tests catch any over-sharing.
"""
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph


def _build_graph() -> Graph:
    chat_input = ChatInput(_id="chat_input")
    chat_output = ChatOutput(_id="chat_output").set(
        input_value=chat_input.message_response
    )
    g = Graph(chat_input, chat_output)
    g.prepare()
    return g


def test_get_snapshot_vertices_layers_is_independent():
    g = _build_graph()
    snap = g.get_snapshot()
    # Mutate graph state after the snapshot
    g.vertices_layers.append(["new_vertex"])
    if g.vertices_layers and g.vertices_layers[0]:
        g.vertices_layers[0].append("injected")
    # Snapshot must be unchanged
    for layer_in_snap in snap["vertices_layers"]:
        assert "injected" not in layer_in_snap
    assert ["new_vertex"] not in snap["vertices_layers"]


def test_get_snapshot_run_manager_is_independent():
    g = _build_graph()
    snap = g.get_snapshot()
    # Mutate run_manager state
    g.run_manager.vertices_to_run.add("synthetic_vertex")
    g.run_manager.run_predecessors["x"] = ["y"]
    # Snapshot must be unchanged
    rm_snap = snap["run_manager"]
    assert "synthetic_vertex" not in rm_snap["vertices_to_run"]
    assert "x" not in rm_snap["run_predecessors"] or rm_snap["run_predecessors"].get("x") != ["y"]


def test_snapshot_mutation_does_not_affect_graph():
    g = _build_graph()
    snap = g.get_snapshot()
    # Mutate the snapshot
    snap["vertices_layers"].append(["snap_only_layer"])
    if isinstance(snap["run_manager"]["vertices_to_run"], set):
        snap["run_manager"]["vertices_to_run"].add("snap_only_vertex")
    # Live graph must be unchanged
    assert ["snap_only_layer"] not in g.vertices_layers
    assert "snap_only_vertex" not in g.run_manager.vertices_to_run


def test_private_snapshot_independence():
    """Even though _snapshot is currently dead on the execution path, the
    rewrite must preserve the same independence contract."""
    g = _build_graph()
    snap = g._snapshot()
    g.vertices_layers.append(["new_layer"])
    g.vertices_to_run.add("synthetic")
    if g.vertices_layers and g.vertices_layers[0]:
        g.vertices_layers[0].append("injected")
    for layer_in_snap in snap["vertices_layers"]:
        assert "injected" not in layer_in_snap
    assert ["new_layer"] not in snap["vertices_layers"]
    assert "synthetic" not in snap["vertices_to_run"]
```

- [ ] **Step 2: Run the suite, verify all 4 tests PASS against the deepcopy baseline**

```bash
cd .worktrees/perf-graph-deepcopy
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py -v 2>&1 | tail -20
```

Expected: 4 tests pass — these are *characterization tests* of the existing deepcopy behavior, so they should pass before the rewrite. If they fail, the test is wrong; fix the test, not the engine.

- [ ] **Step 3: Commit (PAUSE)**

```bash
git add src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py
git commit -m "test(perf): characterize Graph snapshot independence invariants"
```

---

## Task 3 — Rewrite `_snapshot()` and `get_snapshot()` with structural copies

**Files:**
- Modify: `src/lfx/src/lfx/graph/graph/base.py`

**Purpose:** Replace the four `copy.deepcopy` calls in the two snapshot methods with structural shallow copies that match the actual nesting of the data. Preserve observable behavior; the immutability test from Task 2 enforces this.

- [ ] **Step 1: Rewrite `_snapshot()` (lines 404–411)**

Replace:

```python
def _snapshot(self):
    return {
        "_run_queue": self._run_queue.copy(),
        "_first_layer": self._first_layer.copy(),
        "vertices_layers": copy.deepcopy(self.vertices_layers),
        "vertices_to_run": copy.deepcopy(self.vertices_to_run),
        "run_manager": copy.deepcopy(self.run_manager.to_dict()),
    }
```

with:

```python
def _snapshot(self):
    # NOTE(perf): vertices_layers is list[list[str]] and vertices_to_run is
    # set[str] — terminal values are immutable, so a structural shallow-of-
    # shallows produces the same observable independence as deepcopy.
    return {
        "_run_queue": self._run_queue.copy(),
        "_first_layer": self._first_layer.copy(),
        "vertices_layers": [layer.copy() for layer in self.vertices_layers],
        "vertices_to_run": set(self.vertices_to_run),
        "run_manager": _copy_run_manager_dict(self.run_manager.to_dict()),
    }
```

- [ ] **Step 2: Rewrite `get_snapshot()` (lines 1497–1507)**

Replace:

```python
def get_snapshot(self):
    return copy.deepcopy(
        {
            "run_manager": self.run_manager.to_dict(),
            "run_queue": self._run_queue,
            "vertices_layers": self.vertices_layers,
            "first_layer": self.first_layer,
            "inactive_vertices": self.inactive_vertices,
            "activated_vertices": self.activated_vertices,
        }
    )
```

with:

```python
def get_snapshot(self):
    # NOTE(perf): see _snapshot — terminal values are immutable strings, so a
    # structural copy is sufficient. inactive_vertices and activated_vertices
    # are list[str] / set[str] respectively (verified at __init__ time).
    inactive = self.inactive_vertices
    activated = self.activated_vertices
    return {
        "run_manager": _copy_run_manager_dict(self.run_manager.to_dict()),
        "run_queue": self._run_queue.copy(),
        "vertices_layers": [layer.copy() for layer in self.vertices_layers],
        "first_layer": list(self.first_layer)
        if self.first_layer is not None
        else self.first_layer,
        "inactive_vertices": list(inactive)
        if isinstance(inactive, list)
        else set(inactive)
        if isinstance(inactive, set)
        else inactive,
        "activated_vertices": list(activated)
        if isinstance(activated, list)
        else set(activated)
        if isinstance(activated, set)
        else activated,
    }
```

The defensive `isinstance` ladder for `inactive_vertices`/`activated_vertices` is there because the file declares them inconsistently across helpers. **Verify the actual types in Task 3 Step 4** and tighten the code; if both are always a known type, replace the ladder with a single constructor.

- [ ] **Step 3: Add the `_copy_run_manager_dict` helper**

Above `_snapshot`, add a module-level helper:

```python
def _copy_run_manager_dict(rm_dict: dict) -> dict:
    """Structural copy of a RunnableVerticesManager.to_dict() result.

    The returned dict has the same shape as the input, but its container
    values (lists/sets/dicts) are independent — mutating them will not
    affect the original. Terminal string values are shared, which is safe
    because strings are immutable in Python.

    This replaces a previous `copy.deepcopy(rm.to_dict())` on the snapshot
    hot path. Deepcopy was strictly wasteful since every nested value was
    either a string, a list of strings, or a set of strings.
    """
    out = {}
    for key, value in rm_dict.items():
        if isinstance(value, dict):
            out[key] = {
                inner_key: list(inner_val) if isinstance(inner_val, list) else inner_val
                for inner_key, inner_val in value.items()
            }
        elif isinstance(value, set):
            out[key] = set(value)
        elif isinstance(value, list):
            out[key] = list(value)
        else:
            out[key] = value
    return out
```

- [ ] **Step 4: Verify field types and tighten**

```bash
cd .worktrees/perf-graph-deepcopy
rg -n 'self\.(inactive_vertices|activated_vertices)\s*=' src/lfx/src/lfx/graph/graph/base.py
```

Read every assignment and confirm the type. If consistent, replace the `isinstance` ladder in Step 2 with a single `list(...)` or `set(...)` call. If genuinely heterogeneous, leave the ladder and add a short comment explaining why.

- [ ] **Step 5: Run the immutability tests**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py -v 2>&1 | tail -20
```

Expected: 4 tests still pass.

- [ ] **Step 6: Run the existing cycle tests (the only consumer of `get_snapshot`)**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/graph/test_cycles.py -v 2>&1 | tail -30
```

Expected: same pass/skip pattern as Task 0 baseline. No new failures.

- [ ] **Step 7: Commit (PAUSE)**

```bash
git add src/lfx/src/lfx/graph/graph/base.py
git commit -m "perf(graph): replace deepcopy in _snapshot/get_snapshot with structural copies"
```

---

## Task 4 — Sanity-check: re-run the rest of the lfx graph suite

**Files:** None modified.

**Purpose:** The snapshot rewrite touches the engine. Run a wider net of tests before declaring Phase 1 done.

- [ ] **Step 1: Run all unit graph tests**

```bash
cd .worktrees/perf-graph-deepcopy
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/ -v 2>&1 | tail -40
```

Expected: same pass/skip pattern as `platform-multi-tenant` baseline. Investigate any new failures *before* moving on. Most likely cause of a regression: a consumer (test or otherwise) that mutated a snapshot in-place expecting it to be a deep copy and now sees the mutation reflected through a shared reference. The immutability test in Task 2 should have caught this — if it didn't, extend it.

- [ ] **Step 2: Run backend tests that exercise the graph end-to-end**

```bash
cd .worktrees/perf-graph-deepcopy
uv run pytest src/backend/tests/unit/graph/ -x 2>&1 | tail -40
```

Expected: green or same skips as before. The backend graph tests in `test_cache_restoration.py` and `test_execution_path_*.py` exercise full flows — they are the closest thing to integration coverage for the snapshot path.

- [ ] **Step 3: Re-run the microbench from Task 1**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run python /tmp/bench_snapshot.py
```

Append the new numbers to `docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md` under a "Phase 1 result" heading. Expected: 5–25× faster on the snapshot path (the deepcopy was traversing dicts of string-keyed lists; structural copy is a single allocation per container).

- [ ] **Step 4: Commit (PAUSE)**

If you appended to the bench notes:

```bash
git add docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md
git commit -m "docs(perf): record Phase 1 (snapshot rewrite) bench numbers"
```

If no notes change, skip this commit.

---

## Task 5 — Decision gate: ship Phase 2?

**Files:** None modified.

**Purpose:** Phase 2 (`__add__` rewrite) is optional. Decide here based on:

- The Task 1 bench numbers for `__add__`. If `__add__` is sub-millisecond on the bench fixture, the win is theoretical only — Phase 2 can be deferred.
- Whether any production caller of `__add__` exists or is planned. (Today: none; verified.)
- Risk tolerance. `__add__` has no test coverage. The rewrite needs to ship with a new test (Task 6 Step 2) that pins the union semantics; without that test, regressions could go unnoticed.

- [ ] **Step 1: Make the call**

If skipping Phase 2: stop here, run the Task 8 "wrap-up" verification, and let the user know Phase 1 is done and Phase 2 is parked.

If shipping Phase 2: continue to Task 6.

---

## Task 6 — Phase 2: rewrite `Graph.__add__`

**Files:**
- Modify: `src/lfx/src/lfx/graph/graph/base.py`
- Create: `src/lfx/tests/unit/graph/graph/test_graph_addition.py`

**Purpose:** Replace `copy.deepcopy(self)` in `__add__` with the no-op-construct-then-add-nodes-and-edges path that already exists in `__deepcopy__`'s `else` branch.

- [ ] **Step 1: Write a characterization test for `__add__` first**

Create `src/lfx/tests/unit/graph/graph/test_graph_addition.py`:

```python
"""Characterization tests for Graph.__add__.

These pin the observable semantics of `a + b` so the deepcopy → structural
rewrite cannot drift the contract. There were no tests before the rewrite —
these are the first.
"""
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph


def _make_simple(prefix: str) -> Graph:
    chat_input = ChatInput(_id=f"{prefix}_in")
    chat_output = ChatOutput(_id=f"{prefix}_out").set(
        input_value=chat_input.message_response
    )
    return Graph(chat_input, chat_output)


def test_add_returns_new_instance():
    a = _make_simple("a")
    b = _make_simple("b")
    c = a + b
    assert c is not a
    assert c is not b


def test_add_does_not_mutate_operands():
    a = _make_simple("a")
    b = _make_simple("b")
    a_vertices_before = {v.id for v in a.vertices}
    b_vertices_before = {v.id for v in b.vertices}
    _ = a + b
    assert {v.id for v in a.vertices} == a_vertices_before
    assert {v.id for v in b.vertices} == b_vertices_before


def test_add_includes_vertices_from_both_graphs():
    a = _make_simple("a")
    b = _make_simple("b")
    c = a + b
    c_ids = {v.id for v in c.vertices}
    for v in a.vertices:
        assert v.id in c_ids
    for v in b.vertices:
        assert v.id in c_ids


def test_add_rejects_non_graph():
    a = _make_simple("a")
    import pytest
    with pytest.raises(TypeError):
        _ = a + "not a graph"
```

Run against the current (deepcopy) implementation:

```bash
cd .worktrees/perf-graph-deepcopy
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/graph/test_graph_addition.py -v 2>&1 | tail -20
```

Expected: 4 tests pass against the existing deepcopy implementation. If `test_add_includes_vertices_from_both_graphs` fails because vertex IDs collide, both fixtures need distinct prefixes — the test above already does that.

- [ ] **Step 2: Rewrite `__add__` (lines 185–196)**

Replace:

```python
def __add__(self, other):
    if not isinstance(other, Graph):
        msg = "Can only add Graph objects"
        raise TypeError(msg)
    # Add the vertices and edges from the other graph to this graph
    new_instance = copy.deepcopy(self)
    for vertex in other.vertices:
        # This updates the edges as well
        new_instance.add_vertex(vertex)
    new_instance.build_graph_maps(new_instance.edges)
    new_instance.define_vertices_lists()
    return new_instance
```

with:

```python
def __add__(self, other):
    if not isinstance(other, Graph):
        msg = "Can only add Graph objects"
        raise TypeError(msg)
    # NOTE(perf): the previous implementation called `copy.deepcopy(self)` to
    # avoid mutating self while building the union graph. The deepcopy chain
    # walks every Vertex (and its attached custom-component instance, model
    # client, etc.) — far heavier than necessary.
    #
    # Instead, construct a fresh Graph from the same NodeData/EdgeData lists
    # `self` was built from. `add_nodes_and_edges` re-runs the full
    # initialization path that `Graph.__init__` uses, so the new graph is in
    # the same well-formed state without paying for a deep walk.
    #
    # Behavior preserved: self is untouched (its `_vertices` / `_edges` lists
    # are read but not mutated; we hand fresh `list(...)` copies to the new
    # graph's `add_nodes_and_edges`). `other`'s vertices are then added via
    # the same `add_vertex` path the original used.
    new_instance = type(self)(
        None,
        None,
        self.flow_id,
        self.flow_name,
        self.user_id,
    )
    new_instance.add_nodes_and_edges(list(self._vertices), list(self._edges))
    for vertex in other.vertices:
        # This updates the edges as well
        new_instance.add_vertex(vertex)
    new_instance.build_graph_maps(new_instance.edges)
    new_instance.define_vertices_lists()
    return new_instance
```

Notes for the implementer:
- `flow_id`, `flow_name`, `user_id` are scalars (str / UUID / None) — no copy needed. If the `Graph` constructor signature differs, adapt.
- `list(self._vertices)` / `list(self._edges)` produce fresh outer lists; the inner `NodeData` / `EdgeData` dicts are shared by reference. `add_nodes_and_edges` does not mutate them — verified by reading the method (lines 257–271). If a future change starts mutating those dicts, this rewrite needs a `[dict(v) for v in self._vertices]` upgrade.
- The original `deepcopy(self)` preserved `_start`/`_end` as deepcopied Component instances. The new path passes `None` for both — this is fine for `__add__` because the result graph is built from data, not Component refs. If a caller ever depends on `result._start is not None`, that needs a separate fix. **Document the limitation in the docstring.**

- [ ] **Step 3: Add a docstring to `__add__` documenting the new contract**

Above the rewritten body:

```python
def __add__(self, other: "Graph") -> "Graph":
    """Return a new Graph containing the union of self's and other's vertices/edges.

    Neither operand is mutated. The result is built from `self`'s
    `_vertices` / `_edges` data plus `other`'s vertices added via
    `add_vertex` (which also pulls in their edges).

    Note: the result has `_start = None` and `_end = None`, even if `self`
    has them set. Component-style entry points are not preserved across
    addition; the result is a data-only graph. This matches the previous
    deepcopy behavior in practice (the deepcopy preserved start/end refs,
    but no caller relied on that — there are no production callers of
    `__add__` as of this rewrite).
    """
```

- [ ] **Step 4: Run the new test + the immutability test + the cycle suite**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest \
  src/lfx/tests/unit/graph/graph/test_graph_addition.py \
  src/lfx/tests/unit/graph/graph/test_snapshot_immutability.py \
  src/lfx/tests/unit/graph/graph/test_cycles.py \
  -v 2>&1 | tail -30
```

Expected: all green. If `test_add_includes_vertices_from_both_graphs` fails because `add_nodes_and_edges` re-keys vertex IDs, the test needs to compare canonical IDs not literal strings — fix the test, not the engine.

- [ ] **Step 5: Run the wider lfx graph suite**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/graph/ 2>&1 | tail -10
```

- [ ] **Step 6: Re-run the `__add__` microbench**

```bash
LFX_TEST_ALLOW_LANGFLOW=1 uv run python /tmp/bench_add.py
```

Append the new numbers to the bench notes file under a "Phase 2 result" heading.

- [ ] **Step 7: Commit (PAUSE)**

```bash
git add \
  src/lfx/src/lfx/graph/graph/base.py \
  src/lfx/tests/unit/graph/graph/test_graph_addition.py \
  docs/superpowers/plans/notes/graph-snapshot-bench-2026-04-26.md
git commit -m "perf(graph): rewrite Graph.__add__ without deepcopy"
```

---

## Task 7 — Final verification

**Files:** None modified.

- [ ] **Step 1: Full lfx unit suite**

```bash
cd .worktrees/perf-graph-deepcopy
LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest src/lfx/tests/unit/ 2>&1 | tail -10
```

Expected: same pass/skip pattern as `platform-multi-tenant` baseline.

- [ ] **Step 2: Backend graph tests**

```bash
uv run pytest src/backend/tests/unit/graph/ 2>&1 | tail -10
```

- [ ] **Step 3: Smoke run a real flow**

```bash
uv run python -c "
import asyncio
from lfx.graph.graph.base import Graph
from lfx.components.input_output import ChatInput, ChatOutput
ci = ChatInput(_id='ci')
co = ChatOutput(_id='co').set(input_value=ci.message_response)
g = Graph(ci, co)
g.prepare()
print('snapshots:', len(g._snapshots))
print('snapshot keys:', list(g._snapshots[0].keys()))
"
```

Expected: prints `snapshots: 1` and the standard keys (`run_manager`, `run_queue`, `vertices_layers`, `first_layer`, `inactive_vertices`, `activated_vertices`).

- [ ] **Step 4: Final consolidated commit / push decision**

Ask the user how to consolidate the work — squash the per-task commits into one, leave them, or push to a branch on the `fork` remote (NOT `origin`).

---

## Risk analysis

**What invariants might break:**

1. **Snapshot independence after deeper nesting is added.** If `RunnableVerticesManager.to_dict()` ever returns a value whose terminal type is mutable (e.g., a list of `Vertex` instances, or a dict whose values are themselves dicts of dicts), the structural copy in `_copy_run_manager_dict` will share references at the deepest level. Mitigation: the immutability test in Task 2 catches the case where consumers see post-snapshot mutations bleed in. A reviewer adding a new field to `RunnableVerticesManager` should run that test; if they don't, the test still fails on the next test run.
2. **`Graph.__add__` no longer preserves `_start`/`_end`.** Documented in the docstring. No production caller cares today. If a caller appears, they get a graph with `None` start/end; the failure is loud (AttributeError on `.id`) and easy to diagnose.
3. **Performance regression on tiny graphs.** Structural copy has constant-factor overhead from the comprehension and `isinstance` checks. On a 2-vertex graph the deepcopy is already <50 µs; the rewrite saves ~80% of that but might be within noise. The microbench in Task 1 is the gate — if Phase 1 doesn't show a clear win on the bench, something is wrong.
4. **The "private" `_snapshot()` is not actually dead.** Task 1 Step 1 verifies via ripgrep. If a caller is found that we missed (e.g., a test fixture or a debug helper), the rewrite still applies — the contract is the same.

**Test coverage today:**

- `src/lfx/tests/unit/graph/graph/test_cycles.py`: 6 tests, 4 of which directly call `get_snapshot()` in `snapshots = [graph.get_snapshot()]; for r in graph.start(...): snapshots.append(graph.get_snapshot())`. Two of those require an OpenAI key; one is currently `@pytest.mark.skip("Cycles now require a LoopComponent")`. **Effective coverage:** one async test (`test_conditional_router_max_iterations`) that exercises the snapshot path end-to-end.
- `src/lfx/tests/unit/graph/graph/test_base.py`: 14 tests, none of which call `get_snapshot` or `__add__` directly. They verify Graph construction, terminal-node analysis, and callback events — useful as a "did the graph still build?" canary.
- `src/lfx/tests/unit/graph/graph/test_runnable_vertices_manager.py`: 208 lines of focused tests on `RunnableVerticesManager`. Doesn't touch the snapshot path but pins the contract of `to_dict()`.
- `src/backend/tests/unit/graph/`: `test_cache_restoration.py`, `test_execution_path_*.py` — full-flow tests that hit the snapshot path indirectly. Slow but high signal.
- **Gaps:** no test of `Graph.__add__` (Task 6 fixes that). No test of snapshot independence (Task 2 fixes that). No test of `_snapshot()` as a standalone (covered by Task 2).

**Coverage adequacy for this rewrite:** marginal-going-on-adequate. Tasks 2 and 6 add the focused tests that close the worst gaps. The end-to-end coverage in `test_cycles.py` and `src/backend/tests/unit/graph/` is the safety net. **If a reviewer is uncomfortable, gate Phase 2 behind a longer soak — keep `__add__`'s deepcopy and ship only Phase 1.**

---

## Estimated win

Order-of-magnitude estimate, calibrated by the source-finding context (50-vertex × 5-layer flow):

- **Phase 1 (`get_snapshot` rewrite):** baseline `deepcopy` of the snapshot dict on a 50-vertex graph is ~0.5–1 ms (string-keyed lists/sets, no nested heavy objects). One snapshot per `astep` = ~50 snapshots per build. Rewrite saves ~80% per snapshot → **~20–40 ms per build.** This is the bulk of the win.
- **Phase 2 (`__add__` rewrite):** baseline deepcopy of a 50-vertex Graph (with attached Component instances per Vertex) is ~10 ms. No production callers today, so the *practical* per-build win is **0 ms.** The win is theoretical, paid only if someone adds an `__add__` call site.
- **Combined wall-clock per build:** ~20–40 ms saved on a chatty flow. Significant for sub-second interactive flows; not earth-shattering for batch flows that already take >1 s. The original source-finding estimate of ~40 ms / build is consistent with this analysis.

**Honesty check:** the source finding said "deepcopy on a 50-vertex graph is ~10 ms; saving most of that across 5 layers is 40 ms per build." That estimate was for `__add__`-style deepcopy (whole-graph traversal), not `get_snapshot`-style (string-set traversal). The actual `get_snapshot` cost is closer to 0.5 ms per call, not 10 ms. The win is the *number of calls* (~50 per build) × the per-call overhead, not the per-call magnitude. Phase 1 is still worth shipping, but the absolute wall-clock improvement is closer to ~20–40 ms total per chatty build, not the much larger number you'd get from a literal "10 ms × 50 layers" reading.

---

## Rollout plan

- **Phase 1 (Tasks 0–4):** snapshot rewrite. Smaller blast radius, clearer test coverage, larger practical win. Ships on its own commit. **Default to shipping.**
- **Phase 2 (Tasks 5–6):** `__add__` rewrite. No production caller, requires its own test. Ships only if Task 5 says yes. **Default to deferring** unless the bench shows a >5 ms per-call cost on the fixture.
- **No feature flag.** The behavior is preserved or it regresses — no toggle. The rewrite is small enough that bisecting is cheap if a regression slips through.
- **No staged rollout in production.** This is engine code; the Phase 1 rewrite is contained to one file; the test gate (immutability + cycles + backend graph tests) is the production gate. Ship all-or-nothing.

---

## Open questions / risks

1. **Are there *any* `inactive_vertices` / `activated_vertices` paths where the type is *not* `list[str]` or `set[str]`?** Task 3 Step 4 verifies this empirically. If yes, the structural copy needs the type to be normalized at the assignment site, not at snapshot time.
2. **Does any existing test mutate a snapshot in-place expecting it to be a deep copy?** Task 4 Step 1 catches this. The most likely place is `test_cycles.py` — the snapshots are built into a list and asserted on at the end; a quick read suggests no in-place mutation.
3. **Is `_snapshot()` ever wired up in a way ripgrep misses?** E.g., `getattr(graph, "_snap" + "shot")`. Extremely unlikely but worth a `grep -rn "_snapshot" src/` net-wide once — done as part of Task 1 Step 1.
4. **Does the cycle-execution code path read `run_manager` from a snapshot?** If so, the structural-copy `_copy_run_manager_dict` must preserve `defaultdict(list)` semantics, not just `dict`. Reading the consumer code (`test_cycles.py`) suggests the snapshot is read for assertions only, not re-fed into `RunnableVerticesManager.from_dict`. Worth confirming during Task 4 Step 1; if a `from_dict` path exists, the helper needs `defaultdict(list, {k: list(v) for ...})` instead of plain `dict`.
5. **Phase 2 only:** does any planned future work actually call `Graph.__add__`? If so, the rewrite needs a richer test (vertex-id collision handling, `_start`/`_end` semantics). If not, Phase 2 is dead-code maintenance and can be parked indefinitely.
