# Worker Performance & Effectiveness Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-impact gaps in the Taskiq-backed Langflow worker — multi-process task discovery, configuration knobs, phase-level observability, queue-depth telemetry, retry hardening (jitter + DLQ), tenant timeout safety, and graceful shutdown drain — without restructuring the executor.

**Architecture:** Worker is a Taskiq/Redis ListQueueBroker async executor; one queue per process; jobs flow `execute_run → simple_run_flow`; concurrency is gated per-org via Redis Lua. We add: settings-driven tunables (replacing `HEARTBEAT_INTERVAL`/`CANCEL_POLL_INTERVAL`/`REQUEUE_DELAY` constants and webhook backoff), a `PHASE_DURATION` Prometheus histogram and counters for retry-exhaustion / metering failure, a periodic queue-depth poller that fills the existing `QUEUE_DEPTH` gauge via `LLEN`, jitter on retry backoff, a global `worker_max_run_timeout_seconds` clamp, and a `worker_app.shutdown` registry that drains in-flight `execute_run` tasks on `WORKER_SHUTDOWN`. Each task is independently testable.

**Tech Stack:** Python 3.11+, asyncio, Taskiq 0.12.x, taskiq-redis (ListQueueBroker), Redis (asyncio), prometheus-client, SQLModel/SQLAlchemy async, pytest + pytest-asyncio.

**Operational notes:**
- All work happens on branch `worker-perf-hardening` in `.worktrees/worker-hardening`.
- The user pauses for every commit — when a step says **Commit**, stop and ask before running `git commit`.
- Subagents must stage explicit paths (no `git add -A` / `.`).

---

## File Structure

**Create:**
- `src/backend/base/langflow/worker_app/queue_depth.py` — periodic LLEN poller task that updates `QUEUE_DEPTH`.
- `src/backend/base/langflow/worker_app/shutdown.py` — in-flight `execute_run` registry + drain helper.
- `src/backend/tests/unit/worker_app/test_queue_depth.py` — unit tests for the poller.
- `src/backend/tests/unit/worker_app/test_shutdown.py` — unit tests for the drain registry.
- `src/backend/tests/integration/worker/test_global_timeout_clamp.py` — clamp behavior end-to-end.
- `src/backend/tests/integration/worker/test_dlq_metric.py` — DLQ counter on retry exhaustion.

**Modify:**
- `src/backend/base/langflow/cli/worker_cmd.py` — already-staged task-module fix (Task 1).
- `src/lfx/src/lfx/services/settings/base.py` — add 7 worker tunables (Task 2).
- `src/backend/base/langflow/worker_app/execute.py` — read tunables; phase timing; jitter; clamp; DLQ counter; metering counter; register/unregister with shutdown registry.
- `src/backend/base/langflow/worker_app/log_sink.py` — accept tunable buffer/flush.
- `src/backend/base/langflow/worker_app/webhook.py` — read backoff schedule from settings.
- `src/backend/base/langflow/worker_app/lifecycle.py` — wire shutdown drain into the existing `_on_shutdown` handler.
- `src/backend/base/langflow/services/runs/metrics.py` — add `PHASE_DURATION`, `RUN_RETRY_EXHAUSTED_TOTAL`, `WORKER_METERING_FAILURES_TOTAL`, `WORKER_GRACEFUL_SHUTDOWN_DURATION`.
- `src/backend/base/langflow/worker_app/brokers.py` — register `update_queue_depth` task on `broker_default`.

---

## Task 1 — Commit the multi-worker task-discovery fix

The working tree already contains the fix in `cli/worker_cmd.py` (passes `task_modules` as positional args to `taskiq worker` so `--workers N` child processes register decorated tasks). Ship it on its own commit before anything else — it's load-bearing for any deployment that runs `--concurrency > 1`.

**Files:**
- Modified (already in working tree): `src/backend/base/langflow/cli/worker_cmd.py`
- Test exists: `src/backend/tests/unit/cli/test_worker_cmd.py`

- [ ] **Step 1: Re-read the change**

```bash
git -C .worktrees/worker-hardening diff -- src/backend/base/langflow/cli/worker_cmd.py
```
Expected: the diff adds the `task_modules` list and includes them in `cli_args` before `--workers`.

- [ ] **Step 2: Add a unit test pinning the new behavior**

Add to `src/backend/tests/unit/cli/test_worker_cmd.py`:

```python
def test_worker_passes_task_modules_to_taskiq(monkeypatch):
    """Each child process must re-import task modules so @broker.task decorators fire."""
    captured: dict[str, list[str]] = {}

    class FakeWorkerCMD:
        def exec(self, args):
            captured["args"] = args
            return 0

    import taskiq.cli.worker.cmd as cmd_mod
    monkeypatch.setattr(cmd_mod, "WorkerCMD", FakeWorkerCMD)

    result = CliRunner().invoke(app, ["worker", "-q", "runs:default", "--concurrency", "4"])
    assert result.exit_code == 0, result.output

    args = captured["args"]
    # Broker spec is positional[0]; task modules MUST follow before any flag.
    assert args[0] == "langflow.worker_app.brokers:broker_default"
    expected_modules = {
        "langflow.worker_app.settings",
        "langflow.worker_app.execute",
        "langflow.worker_app.webhook",
        "langflow.worker_app.reaper",
        "langflow.worker_app.retention",
        "langflow.worker_app.audit_cleanup",
        "langflow.worker_app.pricing_refresh",
    }
    # Strip flags to find the positional module list
    positionals = []
    i = 1
    while i < len(args) and not args[i].startswith("--"):
        positionals.append(args[i])
        i += 1
    assert set(positionals) == expected_modules, positionals
    # --workers comes from --concurrency
    assert "--workers" in args and "4" in args
```

- [ ] **Step 3: Run the test**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/cli/test_worker_cmd.py -v
```
Expected: both tests PASS.

- [ ] **Step 4: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/cli/worker_cmd.py src/backend/tests/unit/cli/test_worker_cmd.py
git commit -m "fix(worker): pass task modules to taskiq child workers

Taskiq spawns child processes that re-import only the broker spec, so
@broker.task decorators in execute/webhook/reaper/etc never fire and
the receiver logs 'task ... is not found' for every job. Pass every
task module as a positional CLI arg so each child re-imports them at
startup. Required for --concurrency > 1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — Settings-driven worker tunables

Replace hardcoded constants with settings. Each new setting reads from env via the existing pydantic-settings machinery.

**Files:**
- Modify: `src/lfx/src/lfx/services/settings/base.py` (~line 423, after `cost_tracking_enabled`)
- Modify: `src/backend/base/langflow/worker_app/execute.py` (constants + usages)
- Modify: `src/backend/base/langflow/worker_app/log_sink.py` (default args)
- Modify: `src/backend/base/langflow/worker_app/webhook.py` (`_BACKOFF_SCHEDULE_SEC`)
- Test: `src/backend/tests/unit/worker_app/test_settings_tunables.py` (new)

- [ ] **Step 1: Write a settings test for the new fields**

Create `src/backend/tests/unit/worker_app/test_settings_tunables.py`:

```python
from __future__ import annotations
import importlib
import pytest


def test_worker_tunables_have_defaults():
    from lfx.services.settings.base import Settings
    s = Settings(_env_file=None)
    assert s.worker_heartbeat_interval_s == 15.0
    assert s.worker_cancel_poll_interval_s == 2.0
    assert s.worker_requeue_delay_s == 5.0
    assert s.worker_log_flush_interval_s == 0.5
    assert s.worker_log_max_buffer == 100
    assert s.worker_max_run_timeout_seconds == 3600
    assert s.worker_retry_jitter_ratio == 0.1
    assert s.worker_webhook_backoff_schedule_s == [10, 30, 120, 600, 1800, 3600]
    assert s.worker_shutdown_drain_timeout_s == 30.0


def test_worker_tunables_read_env(monkeypatch):
    monkeypatch.setenv("LANGFLOW_WORKER_HEARTBEAT_INTERVAL_S", "7.5")
    monkeypatch.setenv("LANGFLOW_WORKER_REQUEUE_DELAY_S", "2")
    monkeypatch.setenv("LANGFLOW_WORKER_MAX_RUN_TIMEOUT_SECONDS", "1800")
    from lfx.services.settings import base as base_mod
    importlib.reload(base_mod)
    s = base_mod.Settings(_env_file=None)
    assert s.worker_heartbeat_interval_s == 7.5
    assert s.worker_requeue_delay_s == 2.0
    assert s.worker_max_run_timeout_seconds == 1800
```

- [ ] **Step 2: Run the test — verify it fails**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_settings_tunables.py -v
```
Expected: FAIL with `AttributeError: ... has no attribute 'worker_heartbeat_interval_s'`.

- [ ] **Step 3: Add the settings**

Append to `src/lfx/src/lfx/services/settings/base.py` immediately after the `cost_tracking_enabled` field (~line 423):

```python
    worker_heartbeat_interval_s: float = 15.0
    """How often the worker stamps `flow_run.heartbeat_at`. Reaper marks runs
    FAILED after `STALE_AFTER_SECONDS` (60s) without a heartbeat — keep this
    well under that floor."""

    worker_cancel_poll_interval_s: float = 2.0
    """How often the worker polls Redis for a cancel signal during execution."""

    worker_requeue_delay_s: float = 5.0
    """Delay before requeueing a job that hit the org concurrency cap."""

    worker_log_flush_interval_s: float = 0.5
    """Background flush cadence for `RunLogSink`."""

    worker_log_max_buffer: int = 100
    """Max in-memory FlowRunLog rows before a forced flush in `RunLogSink`."""

    worker_max_run_timeout_seconds: int = 3600
    """Hard ceiling on per-run `timeout_seconds`. A run's requested timeout is
    clamped to this value at execution time so a single tenant can't pin a
    worker for arbitrary durations."""

    worker_retry_jitter_ratio: float = 0.1
    """Multiplicative jitter applied to auto-retry backoff. 0.1 means the
    actual delay is uniform in `[backoff, backoff * 1.1]`. Set to 0 to disable."""

    worker_webhook_backoff_schedule_s: list[int] = [10, 30, 120, 600, 1800, 3600]
    """Webhook delivery retry schedule (seconds). Length determines max attempts."""

    worker_shutdown_drain_timeout_s: float = 30.0
    """How long the worker awaits in-flight `execute_run` tasks during graceful
    shutdown before giving up. Match this to the orchestrator's
    `terminationGracePeriodSeconds`."""
```

- [ ] **Step 4: Run the test — expect PASS**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_settings_tunables.py -v
```
Expected: 2 PASS.

- [ ] **Step 5: Wire the tunables into `execute.py`**

In `src/backend/base/langflow/worker_app/execute.py`:

Replace lines 35-37:

```python
HEARTBEAT_INTERVAL = 15.0
CANCEL_POLL_INTERVAL = 2.0
REQUEUE_DELAY = 5.0
```

with deferred reads from the active settings (resolved per call so tests can monkeypatch):

```python
def _tunables(settings):
    return (
        float(settings.worker_heartbeat_interval_s),
        float(settings.worker_cancel_poll_interval_s),
        float(settings.worker_requeue_delay_s),
    )
```

Update the body of `execute_run` to compute `heartbeat_interval, cancel_poll_interval, requeue_delay = _tunables(settings)` immediately after entering the function, then use those locals in:
- the `REQUEUE_DELAY` log message (line 109) and `delay_s=` argument (line 116)
- the `_heartbeat` call (pass interval as a parameter, default the existing constant)
- the `_cancel_watcher` call (pass interval as a parameter)

Update the helpers' signatures:

```python
async def _heartbeat(session_factory, run_id: UUID, stop: asyncio.Event, interval: float = 15.0) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        ...

async def _cancel_watcher(redis, run_id: UUID, cancel_event: asyncio.Event, stop: asyncio.Event, interval: float = 2.0) -> None:
    while not stop.is_set():
        if await is_cancel_requested(redis, run_id):
            cancel_event.set()
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
```

Drop the module-level `HEARTBEAT_INTERVAL` / `CANCEL_POLL_INTERVAL` / `REQUEUE_DELAY` constants.

- [ ] **Step 6: Wire the tunables into `log_sink.py`**

In `src/backend/base/langflow/worker_app/log_sink.py`, the `RunLogSink.__init__` already accepts `flush_interval` and `max_buffer` keyword args — no signature change. At call site `execute.py:142`, change:

```python
sink = RunLogSink(session_factory=session_factory, run_id=run_uuid)
```

to:

```python
sink = RunLogSink(
    session_factory=session_factory,
    run_id=run_uuid,
    flush_interval=settings.worker_log_flush_interval_s,
    max_buffer=settings.worker_log_max_buffer,
    max_total_bytes=settings.run_logs_max_bytes,
)
```

(`run_logs_max_bytes` already exists in `Settings`.)

- [ ] **Step 7: Wire the tunables into `webhook.py`**

In `src/backend/base/langflow/worker_app/webhook.py`, replace the module-level `_BACKOFF_SCHEDULE_SEC = [10, 30, 120, 600, 1800, 3600]` with a per-call read. Inside `deliver_webhook`, near the top:

```python
backoff_schedule = list(settings.worker_webhook_backoff_schedule_s)
```

Replace `_BACKOFF_SCHEDULE_SEC` references at lines 185 and 207 with `backoff_schedule`.

- [ ] **Step 8: Run the existing worker integration suite**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/ -x -v
```
Expected: existing tests still pass (the seeded conftest does not set the new fields explicitly, and pydantic defaults supply them — but the test settings `Mock` does NOT have these attributes. **Verify** the integration test mocks don't access the new attributes; they don't, since execute_run reads them directly from `settings`).

If the Mock-based tests fail with `AttributeError`, update `conftest.py` (`worker_ctx`):

```python
settings.worker_heartbeat_interval_s = 0.05
settings.worker_cancel_poll_interval_s = 0.05
settings.worker_requeue_delay_s = 0.1
settings.worker_log_flush_interval_s = 0.05
settings.worker_log_max_buffer = 100
settings.worker_max_run_timeout_seconds = 3600
settings.worker_retry_jitter_ratio = 0.0  # deterministic in tests
settings.worker_webhook_backoff_schedule_s = [1, 2, 4]
settings.worker_shutdown_drain_timeout_s = 5.0
settings.run_logs_max_bytes = 10 * 1024 * 1024
```

(Faster heartbeat / cancel / requeue intervals are *required* in tests; the previous constants were 15s / 2s / 5s, which would have made cancel and requeue tests slow. Verify the existing tests that exercise cancel and requeue still pass with these test-fixture overrides.)

- [ ] **Step 9: Commit (ASK USER FIRST)**

Stage explicit paths:

```bash
git add src/lfx/src/lfx/services/settings/base.py \
        src/backend/base/langflow/worker_app/execute.py \
        src/backend/base/langflow/worker_app/log_sink.py \
        src/backend/base/langflow/worker_app/webhook.py \
        src/backend/tests/unit/worker_app/test_settings_tunables.py \
        src/backend/tests/integration/worker/conftest.py
git commit -m "feat(worker): expose tunables as settings (heartbeat, cancel, requeue, logs, webhook backoff)

Replaces hardcoded constants in execute.py, log_sink.py, and webhook.py
with Settings fields read at job start. Adds:
  worker_heartbeat_interval_s        (was HEARTBEAT_INTERVAL=15s)
  worker_cancel_poll_interval_s      (was CANCEL_POLL_INTERVAL=2s)
  worker_requeue_delay_s             (was REQUEUE_DELAY=5s)
  worker_log_flush_interval_s        (was sink default 0.5s)
  worker_log_max_buffer              (was sink default 100)
  worker_webhook_backoff_schedule_s  (was _BACKOFF_SCHEDULE_SEC)
  worker_max_run_timeout_seconds     (new ceiling, applied in Task 5)
  worker_retry_jitter_ratio          (new, applied in Task 4)
  worker_shutdown_drain_timeout_s    (new, applied in Task 7)

Defaults preserve current behavior. Integration test fixture sets
fast intervals so cancel/requeue suites stay quick.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Phase-timing histogram & failure counters

`RUN_DURATION` only measures whole-run latency. Add per-phase visibility plus counters for currently-silent failure modes.

**Files:**
- Modify: `src/backend/base/langflow/services/runs/metrics.py`
- Modify: `src/backend/base/langflow/worker_app/execute.py`
- Test: `src/backend/tests/integration/worker/test_phase_metrics.py` (new)

- [ ] **Step 1: Write the failing metrics test**

Create `src/backend/tests/integration/worker/test_phase_metrics.py`:

```python
from __future__ import annotations
import pytest

pytestmark = pytest.mark.asyncio


async def test_execute_run_records_phase_metrics(worker_ctx, seeded):
    from langflow.worker_app.execute import execute_run
    from langflow.services.runs.metrics import PHASE_DURATION, WORKER_METERING_FAILURES_TOTAL

    run = seeded["run"]

    # Snapshot starting samples for the phases we care about.
    def sample(phase: str) -> int:
        m = PHASE_DURATION.labels(phase=phase)
        # _sum samples increase monotonically; we just want to see it move.
        return int(m._sum.get())  # internal but stable for prometheus_client

    before = {p: sample(p) for p in ("execute_flow", "terminal_writeback")}
    await execute_run(str(run.id))
    after = {p: sample(p) for p in ("execute_flow", "terminal_writeback")}

    assert after["execute_flow"] >= before["execute_flow"]
    assert after["terminal_writeback"] >= before["terminal_writeback"]

    # Metering failures stay at 0 in the happy path.
    val = WORKER_METERING_FAILURES_TOTAL._value.get()
    assert val == 0 or isinstance(val, float)
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/test_phase_metrics.py -v
```
Expected: FAIL with `ImportError: cannot import name 'PHASE_DURATION'`.

- [ ] **Step 3: Add the metrics**

Append to `src/backend/base/langflow/services/runs/metrics.py`:

```python
PHASE_DURATION = Histogram(
    "langflow_worker_phase_duration_seconds",
    "Per-phase latency inside execute_run",
    ["phase"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300),
)
RUN_RETRY_EXHAUSTED_TOTAL = Counter(
    "langflow_worker_retry_exhausted_total",
    "Runs that ran out of auto-retry attempts and finalized in a failed state",
    ["status"],
)
WORKER_METERING_FAILURES_TOTAL = Counter(
    "langflow_worker_metering_failures_total",
    "Exceptions swallowed by the metering post-commit hook",
)
WORKER_GRACEFUL_SHUTDOWN_DURATION = Histogram(
    "langflow_worker_graceful_shutdown_seconds",
    "Time spent draining in-flight execute_run tasks during shutdown",
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120, 300),
)
```

- [ ] **Step 4: Wrap phases in `execute.py` with timing**

Add a small helper at the top of `execute.py` (after imports):

```python
import time as _time
import contextlib as _contextlib

@_contextlib.contextmanager
def _phase(name: str):
    from langflow.services.runs.metrics import PHASE_DURATION
    start = _time.monotonic()
    try:
        yield
    finally:
        PHASE_DURATION.labels(phase=name).observe(_time.monotonic() - start)
```

Wrap these regions:
- `acquire_slot`: around the `concurrency.try_acquire(...)` call (line 104).
- `payload_offload_load`: around `inputs = await offloader.load(inputs_ref)` (line 97).
- `execute_flow`: around the `asyncio.wait({execution, cancel_waiter}, ...)` block (lines 159-161).
- `terminal_writeback`: around the `async with session_factory() as session:` block at line 204 that commits the terminal status.
- `payload_offload_store`: around the `offloader.store(...)` call inside that block (line 217).

- [ ] **Step 5: Replace the silent metering swallow with a counted exception**

In `execute.py`, change lines 248-250 from:

```python
            except Exception:  # noqa: BLE001
                logger.exception(f"[run={run_uuid}] metering post-commit failed")
```

to:

```python
            except Exception:  # noqa: BLE001
                from langflow.services.runs.metrics import WORKER_METERING_FAILURES_TOTAL
                WORKER_METERING_FAILURES_TOTAL.inc()
                logger.exception(f"[run={run_uuid}] metering post-commit failed")
```

- [ ] **Step 6: Run the new test — expect PASS**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/test_phase_metrics.py -v
```
Expected: 1 PASS.

- [ ] **Step 7: Run the full worker integration suite**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/ -x -v
```
Expected: every previous test still passes.

- [ ] **Step 8: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/services/runs/metrics.py \
        src/backend/base/langflow/worker_app/execute.py \
        src/backend/tests/integration/worker/test_phase_metrics.py
git commit -m "feat(worker): per-phase timing + retry/metering failure counters

Adds Prometheus histograms for acquire_slot, payload_offload_load,
execute_flow, terminal_writeback, payload_offload_store; counters for
retry-exhausted runs and metering post-commit failures (previously
silently logged); a histogram for graceful-shutdown drain time
(consumed in a follow-up commit).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Retry jitter + DLQ counter

Add jitter to the auto-retry exponential backoff (no thundering herd on synchronized failure) and increment `RUN_RETRY_EXHAUSTED_TOTAL` when a run finalizes after using its last attempt.

**Files:**
- Modify: `src/backend/base/langflow/worker_app/execute.py`
- Test: `src/backend/tests/integration/worker/test_dlq_metric.py` (new)
- Test: `src/backend/tests/integration/worker/test_execute_run_retry.py` (extend)

- [ ] **Step 1: Write a unit test for jitter math**

Create `src/backend/tests/unit/worker_app/test_retry_jitter.py`:

```python
from __future__ import annotations
import random
from langflow.worker_app.execute import _jittered_backoff


def test_jittered_backoff_zero_ratio_is_deterministic():
    assert _jittered_backoff(60.0, 0.0) == 60.0


def test_jittered_backoff_within_band():
    rng = random.Random(0)
    for _ in range(100):
        v = _jittered_backoff(60.0, 0.1, rng=rng)
        assert 60.0 <= v <= 66.0


def test_jittered_backoff_caps_at_30min():
    # base*2^n grows fast; verify the helper does NOT cap (the caller does).
    v = _jittered_backoff(10_000.0, 0.1, rng=random.Random(0))
    assert v >= 10_000.0
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_retry_jitter.py -v
```
Expected: FAIL with `ImportError: cannot import name '_jittered_backoff'`.

- [ ] **Step 3: Implement `_jittered_backoff` in `execute.py`**

Add near the bottom of the helper section:

```python
def _jittered_backoff(base_seconds: float, ratio: float, *, rng: random.Random | None = None) -> float:
    """Apply multiplicative jitter to a backoff. ratio=0.1 -> [base, base*1.1]."""
    if ratio <= 0:
        return base_seconds
    r = rng if rng is not None else random
    return base_seconds * (1.0 + r.uniform(0.0, ratio))
```

Add `import random` at the top of the file.

- [ ] **Step 4: Replace the auto-retry backoff calc**

In `execute.py`, change line 284 from:

```python
backoff = min(30 * (2 ** (run.attempt - 1)), 1800)
```

to:

```python
base = min(30 * (2 ** (run.attempt - 1)), 1800)
backoff = _jittered_backoff(base, settings.worker_retry_jitter_ratio)
```

(`settings` is already in scope as the function's `TaskiqDepends` param.)

- [ ] **Step 5: Increment retry-exhausted counter when retries run out**

Currently the `if run.auto_retry and run.attempt < run.max_retries:` block only handles the *retry* path. Add the *exhausted* path right before the final `if terminal in {RunStatus.FAILED, RunStatus.TIMED_OUT}:` close:

```python
    if terminal in {RunStatus.FAILED, RunStatus.TIMED_OUT}:
        async with session_factory() as session:
            run = await session.get(FlowRun, run_uuid)
            if run is None:
                return
            if run.auto_retry and run.attempt < run.max_retries:
                # ... existing retry path ...
            else:
                from langflow.services.runs.metrics import RUN_RETRY_EXHAUSTED_TOTAL
                terminal_label = terminal.value if hasattr(terminal, "value") else str(terminal)
                RUN_RETRY_EXHAUSTED_TOTAL.labels(status=terminal_label).inc()
                logger.info(
                    f"[run={run_id}] no retry remaining (auto_retry={run.auto_retry} "
                    f"attempt={run.attempt}/{run.max_retries}); finalising as {terminal_label}"
                )
```

- [ ] **Step 6: Write the integration test**

Create `src/backend/tests/integration/worker/test_dlq_metric.py`:

```python
from __future__ import annotations
import pytest
from uuid import uuid4
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
from langflow.services.database.models.organization.model import Organization

pytestmark = pytest.mark.asyncio


async def test_dlq_counter_fires_when_retries_exhausted(worker_ctx, engine_and_factory):
    from langflow.worker_app import execute as exec_mod
    from langflow.services.runs.metrics import RUN_RETRY_EXHAUSTED_TOTAL

    _, factory = engine_and_factory

    # Failing runner so the run finalises FAILED.
    async def failing_runner(*args, **kwargs):
        raise RuntimeError("boom")

    from langflow.worker_app import deps as worker_deps
    worker_deps._set("graph_runner", failing_runner)

    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org)
        await s.commit()
        flow = Flow(id=uuid4(), name="f", data={"nodes": [], "edges": []}, organization_id=org.id, auto_retry=True, max_retries=1, timeout_seconds=600)
        s.add(flow)
        await s.commit()
        # attempt=1 == max_retries — i.e. this IS the last attempt.
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id, triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED, timeout_seconds=30, auto_retry=True, max_retries=1, attempt=1,
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

    counter_label = RUN_RETRY_EXHAUSTED_TOTAL.labels(status="failed")
    before = counter_label._value.get()
    await exec_mod.execute_run(str(run.id))
    after = counter_label._value.get()
    assert after == before + 1
```

- [ ] **Step 7: Run — expect PASS**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/test_dlq_metric.py src/backend/tests/unit/worker_app/test_retry_jitter.py -v
```
Expected: 4 PASS (3 jitter + 1 dlq).

- [ ] **Step 8: Run the existing retry suite to confirm no regression**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/test_execute_run_retry.py -v
```
Expected: PASS. The jitter ratio is set to `0.0` in the test fixture, so the existing assertions on requeue delay (which check exact delay) are unaffected.

- [ ] **Step 9: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/worker_app/execute.py \
        src/backend/tests/unit/worker_app/test_retry_jitter.py \
        src/backend/tests/integration/worker/test_dlq_metric.py
git commit -m "feat(worker): jittered retry backoff + retry-exhausted counter

Multiplicative jitter (controlled by worker_retry_jitter_ratio, default
0.1) prevents synchronized retry storms across runs failing on the same
upstream blip. RUN_RETRY_EXHAUSTED_TOTAL increments when a FAILED or
TIMED_OUT run has no attempts left, giving operators a real signal to
alert on (no DLQ queue is introduced — the run row is the source of
truth, the metric is the alarm).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Global per-run timeout clamp

Tenants can request `timeout_seconds=86400` and pin a worker for a day. Clamp at job start.

**Files:**
- Modify: `src/backend/base/langflow/worker_app/execute.py`
- Test: `src/backend/tests/integration/worker/test_global_timeout_clamp.py` (new)

- [ ] **Step 1: Write the test**

Create `src/backend/tests/integration/worker/test_global_timeout_clamp.py`:

```python
from __future__ import annotations
import asyncio
import pytest
from uuid import uuid4

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
from langflow.services.database.models.organization.model import Organization

pytestmark = pytest.mark.asyncio


async def test_run_timeout_clamped_to_global_ceiling(worker_ctx, engine_and_factory):
    """A run that requests timeout > worker_max_run_timeout_seconds is clamped."""
    from langflow.worker_app import execute as exec_mod
    from langflow.worker_app import deps as worker_deps

    settings = worker_deps._get("settings")
    settings.worker_max_run_timeout_seconds = 1  # very tight ceiling for the test

    # Slow runner that would only succeed if its actual timeout window were >1s.
    async def slow_runner(flow, triggered_by, inputs, actor_id):
        await asyncio.sleep(5.0)
        return {"ok": True}

    worker_deps._set("graph_runner", slow_runner)

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org)
        flow = Flow(id=uuid4(), name="f", data={"nodes": [], "edges": []}, organization_id=org.id, timeout_seconds=600)
        s.add(flow)
        await s.commit()
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id, triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED,
            timeout_seconds=300,  # tenant request — must be clamped to 1s
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

    await exec_mod.execute_run(str(run.id))

    async with factory() as s:
        finalized = await s.get(FlowRun, run.id)
    assert finalized.status == RunStatus.TIMED_OUT, finalized.error
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/test_global_timeout_clamp.py -v
```
Expected: FAIL — without the clamp, the runner completes in 5s within the 300s window, so the run status is `SUCCEEDED` (or `RUNNING` if it timed out at the test level).

- [ ] **Step 3: Implement the clamp**

In `execute.py`, immediately after the loaded-row block (after line 92, where `timeout_s = run.timeout_seconds` is captured), clamp it:

```python
        timeout_s = run.timeout_seconds
        max_timeout = int(settings.worker_max_run_timeout_seconds)
        if timeout_s and timeout_s > max_timeout:
            logger.info(
                f"[run={run_id}] timeout_seconds={timeout_s} clamped to global ceiling {max_timeout}s"
            )
            timeout_s = max_timeout
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/test_global_timeout_clamp.py -v
```
Expected: PASS.

- [ ] **Step 5: Run the whole worker suite to confirm no regression**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/ -x -v
```
Expected: all PASS. Default ceiling is 3600s, well above test fixtures' 30s timeouts.

- [ ] **Step 6: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/worker_app/execute.py \
        src/backend/tests/integration/worker/test_global_timeout_clamp.py
git commit -m "feat(worker): clamp per-run timeout to worker_max_run_timeout_seconds

A tenant-supplied timeout_seconds is now clamped to a global ceiling
(default 3600s) at job start, so a single misconfigured flow can't pin
a worker process for arbitrary durations.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Queue-depth poller

`QUEUE_DEPTH` gauge already exists (services/runs/metrics.py:15) but nothing populates it. Add a periodic Taskiq scheduled task that LLENs each runs queue + the webhook queue and updates the gauge.

**Files:**
- Create: `src/backend/base/langflow/worker_app/queue_depth.py`
- Create: `src/backend/tests/unit/worker_app/test_queue_depth.py`
- Modify: `src/backend/base/langflow/cli/worker_cmd.py` (add new module to `task_modules`)

- [ ] **Step 1: Write the unit test**

Create `src/backend/tests/unit/worker_app/test_queue_depth.py`:

```python
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio


async def test_queue_depth_polls_each_queue_and_updates_gauge(monkeypatch):
    from langflow.worker_app import queue_depth as qd
    from langflow.services.runs.metrics import QUEUE_DEPTH

    fake_redis = AsyncMock()
    fake_redis.llen = AsyncMock(side_effect=lambda name: {
        "runs:high": 3,
        "runs:default": 7,
        "runs:low": 0,
        "webhooks": 11,
    }[name])

    await qd._poll_once(fake_redis)

    assert fake_redis.llen.call_count == 4
    assert QUEUE_DEPTH.labels(queue="runs:high")._value.get() == 3
    assert QUEUE_DEPTH.labels(queue="runs:default")._value.get() == 7
    assert QUEUE_DEPTH.labels(queue="runs:low")._value.get() == 0
    assert QUEUE_DEPTH.labels(queue="webhooks")._value.get() == 11


async def test_queue_depth_swallows_redis_error(monkeypatch):
    from langflow.worker_app import queue_depth as qd

    fake_redis = AsyncMock()
    fake_redis.llen = AsyncMock(side_effect=ConnectionError("redis down"))
    # Should not raise; polling failures are recoverable.
    await qd._poll_once(fake_redis)
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_queue_depth.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the poller**

Create `src/backend/base/langflow/worker_app/queue_depth.py`:

```python
"""Periodic queue-depth poller.

Updates the QUEUE_DEPTH Prometheus gauge from Redis LLEN every minute.
Runs on broker_default only — running it on every broker would multiply
LLEN traffic without adding value.
"""
from __future__ import annotations

from redis.asyncio import Redis
from taskiq import TaskiqDepends

from lfx.log.logger import logger

from langflow.services.runs.metrics import QUEUE_DEPTH
from langflow.worker_app.brokers import broker_default
from langflow.worker_app.deps import get_redis


_QUEUES = ("runs:high", "runs:default", "runs:low", "webhooks")


async def _poll_once(redis: Redis) -> None:
    for q in _QUEUES:
        try:
            depth = await redis.llen(q)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"queue_depth: failed to LLEN {q}: {exc}")
            continue
        QUEUE_DEPTH.labels(queue=q).set(depth)


@broker_default.task(
    task_name="update_queue_depth",
    schedule=[{"cron": "* * * * *"}],  # every minute
)
async def update_queue_depth(
    *,
    redis: Redis = TaskiqDepends(get_redis),
) -> None:
    await _poll_once(redis)
```

- [ ] **Step 4: Register the module with `worker_cmd.py`**

In `src/backend/base/langflow/cli/worker_cmd.py`, add `"langflow.worker_app.queue_depth"` to the `task_modules` list (after `"langflow.worker_app.pricing_refresh"`) and the eager-import block at lines 41-47:

```python
    from langflow.worker_app import queue_depth as _qd  # noqa: F401
```

Update the corresponding test in `test_worker_cmd.py` to include the new module in `expected_modules`.

- [ ] **Step 5: Run — expect PASS**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_queue_depth.py src/backend/tests/unit/cli/test_worker_cmd.py -v
```
Expected: 3 PASS.

- [ ] **Step 6: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/worker_app/queue_depth.py \
        src/backend/base/langflow/cli/worker_cmd.py \
        src/backend/tests/unit/worker_app/test_queue_depth.py \
        src/backend/tests/unit/cli/test_worker_cmd.py
git commit -m "feat(worker): queue-depth poller populating QUEUE_DEPTH gauge

Adds a 1-minute scheduled task on broker_default that LLENs each known
queue and updates the existing QUEUE_DEPTH Prometheus gauge. The gauge
was previously declared but never populated. Connection failures are
logged and swallowed so the schedule keeps running.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Graceful shutdown drain

Track in-flight `execute_run` invocations in a process-local registry; on `WORKER_SHUTDOWN`, await them with a timeout and record the drain duration. This lets a SIGTERM'd worker finish its in-flight runs (releasing concurrency slots and writing terminal state) instead of leaving zombie RUNNING rows.

**Files:**
- Create: `src/backend/base/langflow/worker_app/shutdown.py`
- Modify: `src/backend/base/langflow/worker_app/execute.py`
- Modify: `src/backend/base/langflow/worker_app/lifecycle.py`
- Test: `src/backend/tests/unit/worker_app/test_shutdown.py` (new)

- [ ] **Step 1: Write the unit test**

Create `src/backend/tests/unit/worker_app/test_shutdown.py`:

```python
from __future__ import annotations
import asyncio
import pytest

pytestmark = pytest.mark.asyncio


async def test_register_unregister_tracks_tasks():
    from langflow.worker_app.shutdown import _registry, register, unregister

    _registry.clear()

    async def work():
        await asyncio.sleep(0.01)

    t = asyncio.create_task(work())
    register(t)
    assert t in _registry
    await t
    unregister(t)
    assert t not in _registry


async def test_drain_waits_for_inflight_then_returns_drain_seconds():
    from langflow.worker_app.shutdown import _registry, drain, register

    _registry.clear()

    async def slow():
        await asyncio.sleep(0.1)

    t = asyncio.create_task(slow())
    register(t)
    duration = await drain(timeout=5.0)
    assert duration >= 0.1
    assert t.done()


async def test_drain_times_out_and_returns_drain_seconds():
    from langflow.worker_app.shutdown import _registry, drain, register

    _registry.clear()

    async def forever():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    t = asyncio.create_task(forever())
    register(t)
    duration = await drain(timeout=0.1)
    # Expectation: drain returns after ~timeout, leaves the task pending,
    # and Drain emits a warning. We don't cancel here — the worker exits anyway.
    assert duration >= 0.1
    t.cancel()
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_shutdown.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the registry**

Create `src/backend/base/langflow/worker_app/shutdown.py`:

```python
"""In-flight execute_run tracking + graceful drain helper.

`register(task)` and `unregister(task)` are called by execute_run wrappers.
`drain(timeout)` is invoked from the WORKER_SHUTDOWN lifecycle hook to
wait for in-flight tasks to terminate naturally (so they release their
org-concurrency slots and write terminal state to FlowRun).
"""
from __future__ import annotations

import asyncio
import time
from typing import Set

from lfx.log.logger import logger

_registry: Set[asyncio.Task] = set()


def register(task: asyncio.Task) -> None:
    _registry.add(task)


def unregister(task: asyncio.Task) -> None:
    _registry.discard(task)


async def drain(timeout: float) -> float:
    """Wait up to `timeout` seconds for tracked tasks to complete.

    Returns the elapsed wall time (seconds). Tasks still running after the
    timeout are left untouched — Taskiq is about to terminate the process.
    """
    if not _registry:
        return 0.0
    start = time.monotonic()
    pending = list(_registry)
    logger.info(f"[shutdown] draining {len(pending)} in-flight execute_run task(s) (timeout={timeout}s)")
    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    elapsed = time.monotonic() - start
    if still_pending:
        logger.warning(
            f"[shutdown] drain timed out after {elapsed:.2f}s with "
            f"{len(still_pending)} task(s) still running"
        )
    else:
        logger.info(f"[shutdown] drain complete in {elapsed:.2f}s ({len(done)} task(s))")
    return elapsed
```

- [ ] **Step 4: Run unit tests — expect PASS**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/test_shutdown.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Wrap `execute_run` with register/unregister**

In `execute.py`, the `@broker_default.task` decorator wraps the body. We can't easily get the task `asyncio.current_task()` from outside, but inside the function `asyncio.current_task()` is reliable. Add at the top of `execute_run`:

```python
async def execute_run(
    run_id: str,
    *,
    sessionmaker = TaskiqDepends(get_db_sessionmaker),
    ...
) -> None:
    from langflow.worker_app.shutdown import register, unregister
    self_task = asyncio.current_task()
    if self_task is not None:
        register(self_task)
    try:
        # ... existing body unchanged ...
    finally:
        if self_task is not None:
            unregister(self_task)
```

(Wrap the entire existing function body in the new try/finally.)

- [ ] **Step 6: Wire drain into the shutdown hook**

In `lifecycle.py`, change `_on_shutdown`:

```python
async def _on_shutdown(_state: TaskiqState) -> None:
    from langflow.services.runs.metrics import WORKER_GRACEFUL_SHUTDOWN_DURATION
    from langflow.worker_app.shutdown import drain

    settings = worker_deps._get("settings")
    drain_timeout = float(getattr(settings, "worker_shutdown_drain_timeout_s", 30.0)) if settings else 30.0
    elapsed = await drain(timeout=drain_timeout)
    WORKER_GRACEFUL_SHUTDOWN_DURATION.observe(elapsed)

    redis = worker_deps._get("redis")
    if redis is not None:
        await redis.aclose()
    worker_deps._clear()
    logger.info(f"Langflow worker shutting down: worker_id={WORKER_ID} drain_seconds={elapsed:.2f}")
```

- [ ] **Step 7: Run the integration suite — expect no regression**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/integration/worker/ -x -v
```
Expected: PASS. The drain registry is empty in tests that call `execute_run` directly without a real Taskiq receiver, but `register`/`unregister` are no-ops in that case (the call is wrapped in try/finally and `current_task()` returns the test task, which is fine — the registry is process-local and cleared between tests).

- [ ] **Step 8: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/worker_app/shutdown.py \
        src/backend/base/langflow/worker_app/execute.py \
        src/backend/base/langflow/worker_app/lifecycle.py \
        src/backend/tests/unit/worker_app/test_shutdown.py
git commit -m "feat(worker): graceful shutdown drain for in-flight execute_run

On WORKER_SHUTDOWN we wait up to worker_shutdown_drain_timeout_s
(default 30s) for in-flight execute_run tasks to finish naturally.
Each task self-registers with a process-local registry on entry and
unregisters on exit. Drain duration is recorded in the new
WORKER_GRACEFUL_SHUTDOWN_DURATION histogram, and a runaway task that
exceeds the timeout logs a warning before the process exits — the
worker's own try/finally would have run terminal writeback + slot
release for any task that finished before the deadline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — README / docs note

A short note in the worker README pointing at the new tunables, queue-depth metric, and drain semantics. Many of these live or die on operator awareness.

**Files:**
- Modify (or create if absent): `src/backend/base/langflow/worker_app/README.md`

- [ ] **Step 1: Check whether the README exists**

```bash
ls /Users/brycedeneen/dev/langflow/.worktrees/worker-hardening/src/backend/base/langflow/worker_app/README.md 2>/dev/null && echo EXISTS || echo MISSING
```

- [ ] **Step 2: If MISSING, create with the content below; if EXISTS, append a "Tunables & Observability" section.**

```markdown
## Tunables (Settings → env)

All knobs read from `lfx.services.settings.base.Settings`. Set via `LANGFLOW_<UPPER>` env.

| Setting                              | Env                                          | Default                       | Notes |
|--------------------------------------|----------------------------------------------|-------------------------------|-------|
| `worker_heartbeat_interval_s`        | `LANGFLOW_WORKER_HEARTBEAT_INTERVAL_S`       | 15.0                          | Reaper threshold is 60s; keep <30s. |
| `worker_cancel_poll_interval_s`      | `LANGFLOW_WORKER_CANCEL_POLL_INTERVAL_S`     | 2.0                           | Lower = faster cancel, more Redis traffic. |
| `worker_requeue_delay_s`             | `LANGFLOW_WORKER_REQUEUE_DELAY_S`            | 5.0                           | Backoff when org concurrency cap hits. |
| `worker_log_flush_interval_s`        | `LANGFLOW_WORKER_LOG_FLUSH_INTERVAL_S`       | 0.5                           | RunLogSink flush cadence. |
| `worker_log_max_buffer`              | `LANGFLOW_WORKER_LOG_MAX_BUFFER`             | 100                           | RunLogSink in-memory rows. |
| `worker_max_run_timeout_seconds`     | `LANGFLOW_WORKER_MAX_RUN_TIMEOUT_SECONDS`    | 3600                          | Hard ceiling on per-run timeout. |
| `worker_retry_jitter_ratio`          | `LANGFLOW_WORKER_RETRY_JITTER_RATIO`         | 0.1                           | 0 disables jitter on retry backoff. |
| `worker_webhook_backoff_schedule_s`  | `LANGFLOW_WORKER_WEBHOOK_BACKOFF_SCHEDULE_S` | `[10,30,120,600,1800,3600]`   | Length = max delivery attempts. |
| `worker_shutdown_drain_timeout_s`    | `LANGFLOW_WORKER_SHUTDOWN_DRAIN_TIMEOUT_S`   | 30.0                          | Match k8s `terminationGracePeriodSeconds`. |

## Observability

- `langflow_worker_phase_duration_seconds{phase}` — per-phase latency inside `execute_run` (`acquire_slot`, `payload_offload_load`, `execute_flow`, `terminal_writeback`, `payload_offload_store`).
- `langflow_worker_retry_exhausted_total{status}` — runs that finalized after using their last retry attempt. Alert on this.
- `langflow_worker_metering_failures_total` — exceptions in the post-commit metering hook (previously logged-and-swallowed).
- `langflow_worker_graceful_shutdown_seconds` — drain duration on `WORKER_SHUTDOWN`.
- `langflow_queue_depth{queue}` — populated every minute by `update_queue_depth` task on `broker_default`.

## Multi-process workers

`langflow worker --concurrency N` spawns N child processes. Each child re-imports task modules (`execute`, `webhook`, `reaper`, `retention`, `audit_cleanup`, `pricing_refresh`, `queue_depth`) so `@broker.task` decorators register. Without this, child processes log `task ... is not found` for every job.

## Graceful shutdown

On `SIGTERM`, the worker waits `worker_shutdown_drain_timeout_s` for in-flight `execute_run` tasks. Tasks that complete in time write terminal state and release their org-concurrency slot. Tasks still running after the deadline are abandoned in place — the reaper picks them up within `STALE_AFTER_SECONDS` (60s, hardcoded).
```

- [ ] **Step 3: Commit (ASK USER FIRST)**

```bash
git add src/backend/base/langflow/worker_app/README.md
git commit -m "docs(worker): tunables, observability, multi-process, shutdown semantics

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final Verification

- [ ] **Step 1: Run the entire backend test suite**

```bash
cd .worktrees/worker-hardening && uv run pytest src/backend/tests/unit/worker_app/ src/backend/tests/unit/worker/ src/backend/tests/unit/cli/ src/backend/tests/integration/worker/ -v
```
Expected: All PASS, no skipped/errored tests.

- [ ] **Step 2: Smoke-check that the worker boots**

```bash
cd .worktrees/worker-hardening && uv run langflow worker --help
```
Expected: prints help including `--queue`, `--concurrency`, `--log-level`. Exit 0.

- [ ] **Step 3: Confirm git log**

```bash
cd .worktrees/worker-hardening && git log --oneline platform-multi-tenant..HEAD
```
Expected: 7-8 commits, one per task, none touching unrelated files.
