# Component Error Output + ErrorHandler — Design

**Status:** Spec. First slice of the parked iPaaS T1 reliability initiative (`docs/superpowers/specs/2026-04-26-ipaas-capability-roadmap-design.md`). Resolves the architectural fork between sub-flow wrappers and runtime extension by committing to runtime extension.

**Audience:** Personal use — feeds into a writing-plans cycle.

## Context

Today, an unhandled exception during component execution kills the entire flow run (`src/lfx/src/lfx/graph/graph/base.py:1848-1856` re-raises in `_execute_tasks`, cancelling all sibling tasks). Recovery is impossible at the graph layer; users must catch errors *inside* component code or accept run-level failure. The previously-parked T1 roadmap proposed three primitives (retry / try-catch / fallback) as separate components built on either sub-flow wrappers or a runtime extension. Recon during this brainstorm confirmed `RunFlow` does not catch sub-flow exceptions either (`src/lfx/src/lfx/base/tools/run_flow.py:501-523` re-raises with a wrapper message), so the sub-flow path would have required the same runtime work as the runtime-extension path. Given that, this spec consolidates the T1-A surface into a single user-facing primitive — a universal error-output port plus one canonical handler component — backed by a small runtime extension.

The bell notification infrastructure (`AdminNotification` model + `UsageAlertNotifier` protocol) is already shipped and reusable. Email infrastructure does not exist anywhere in the codebase and is out of scope for this spec.

## Goals

- Every opt-in component exposes an `error` output port emitting a structured `ErrorPayload`.
- A new `ErrorHandler` component accepts `ErrorPayload` input and configures retry-with-backoff plus alert-mode (bell / ignore / email-stub).
- The runtime catches exceptions from a vertex with a connected error edge, runs the retry loop transparently, and only fires the error edge after retries exhaust.
- Successful retries are invisible at the component layer — the failing vertex's normal output fires as if nothing happened.
- Handled errors yield a new `RunStatus.PARTIAL_SUCCESS` so the runs view distinguishes "ran to completion with handled errors" from clean success and from `FAILED`.
- Bell audience is configurable per `ErrorHandler`, defaulting to the flow's owner.

## Non-goals

- Email service infrastructure (separate follow-up spec; `Email` appears in the alert-mode dropdown labelled `Email (Not Implemented)` and falls through to bell behavior in v1).
- Per-exception-type filters (`retry_on` / `give_up_on` allowlists/denylists).
- Idempotency keys for retried external calls — handled at component level by components that need them.
- Circuit breaker, dead-letter queue service, rate limiter — separate specs in the parked T1 roadmap.
- A "global" handler catching errors from unwired error ports. Unwired = today's behavior (run `FAILED`).
- Stack-trace redaction. V1 stores raw stack traces in `FlowRun.error`; redaction is a follow-up after legal review.

## Architecture

### Component contract

A component opts into the error-output port via a single ClassVar:

```python
class HTTPRequestComponent(Component):
    error_output_enabled: ClassVar[bool] = True
```

Defaults are set on base classes:

- `Component` (root): `error_output_enabled: ClassVar[bool] = False`
- `LCToolComponent`, `LCModelComponent`, `APIComponent`, database/connector bases: `True`
- Trivial bases (`ChatInput`, `Text`, `Prompt`, `TextSplitter`): inherit `False`

When `True`, the component infrastructure injects an extra `Output` named `error` (display name `"Error"`, types `["ErrorPayload"]`) onto the component's `outputs` list at instantiation time. Component authors only flip the ClassVar; they do not declare the output themselves. Subclasses can override to `False` to opt out of an inherited `True`.

### `ErrorPayload` type

A new structured type in `src/lfx/src/lfx/schema/error_payload.py`:

```python
@dataclass
class ErrorPayload:
    error_message: str
    error_type: str           # exception class name
    stack_trace: str          # truncated to ~4KB
    component_id: str         # vertex id of the failing component
    component_display_name: str
    flow_id: UUID
    flow_run_id: UUID
    attempt_number: int       # 1-indexed; final attempt that failed
    occurred_at: datetime
```

Registered in `src/lfx/src/lfx/field_typing/__init__.py` so the existing edge-type validator gates connections to inputs declared with `types=["ErrorPayload"]`.

### `ErrorHandler` component

Lives at `src/lfx/src/lfx/components/reliability/error_handler.py` (new package, first occupant of the parked T1 reliability initiative).

**Inputs (visible by default):**

- `error_input` — typed `["ErrorPayload"]`. The connection point.
- `max_attempts` — `IntInput`, default `3`, range `0..10`. `0` = no retry, fire alert + `gave_up` immediately.
- `alert_mode` — `DropdownInput`. Options: `Bell` (default), `Email (Not Implemented)`, `Ignore`.
- `bell_audience` — `DropdownInput`, shown only when `alert_mode = Bell`. Options: `Flow owner` (default), `Org admins`, `Specific user`. Selecting `Specific user` reveals a user-picker dropdown constrained to the flow's org.
- `alert_title_template` — `StrInput`, default `"Flow '{flow_name}' failed at {component_name}"`. Tokens: `{flow_name}`, `{component_name}`, `{error_type}`, `{error_message}`, `{org_name}`.

**Inputs (advanced panel, collapsed by default):**

- `backoff_strategy` — `DropdownInput`, default `Exponential with jitter`. Options: `None`, `Fixed delay`, `Exponential`, `Exponential with jitter`.
- `base_delay_seconds` — `FloatInput`, default `1.0`.
- `max_delay_seconds` — `FloatInput`, default `60.0`.
- `alert_body_template` — `MultilineInput`, default markdown template containing `error_message`, `stack_trace`, `attempt_number`, link to flow.

**Outputs:**

- `gave_up` — typed `["ErrorPayload"]`. Fires after retries exhaust *and* alert dispatch completes (success or failure).

### Runtime behavior

The change lives in `src/lfx/src/lfx/graph/graph/base.py:1848-1856` (`_execute_tasks`):

1. Exception lands at the existing catch site.
2. If the failing vertex has no `error` port → keep current behavior (cancel siblings, re-raise — flow run goes `FAILED`).
3. If the `error` port exists *and is connected*:
   - Walk the edge to find the connected `ErrorHandler` vertex.
   - Read the handler's static config (`max_attempts`, `backoff_strategy`, `base_delay_seconds`, `max_delay_seconds`, `jitter`) — these are flow-build-time values, not runtime values.
   - Run the retry loop in the runtime, calling the failing vertex's `_build` again with the same input snapshot. Sleep between attempts using the configured backoff.
   - If a retry succeeds → emit `vertex.retry_succeeded` SSE event, fire the vertex's normal output edges, drop the error edge for this run. The failing vertex's component code never observes that retries happened.
   - If retries exhaust → invoke the `ErrorHandler` vertex with an `ErrorPayload`. Suppress the failing vertex's normal-output successors for this run via the existing `graph.exclude_branch_conditionally` mechanism (same primitive `ConditionalRouter` uses).
4. If the `error` port exists but is *not connected* → same as no port (cancel siblings, re-raise).

**Backoff math:** `delay = min(base_delay * 2^(attempt-1), max_delay)`. With `jitter`, multiply by `random.uniform(0.5, 1.5)`. Sleep is `await`-cancellable so user-initiated run cancellation interrupts mid-retry.

**Cycles forbidden:** an exception raised inside `ErrorHandler` itself bypasses the runtime extension and goes through today's path (run `FAILED`). No infinite recovery loops.

**Topology:**

- A component's error port can connect to at most one `ErrorHandler` (single error-edge per source).
- An `ErrorHandler` can receive errors from many components (fan-in is free; each invocation gets its own `ErrorPayload`).
- `gave_up` can fan out to any normal-typed successor for fallback / dead-letter wiring.

**SSE events emitted during retry:**

- `vertex.retrying` with `{vertex_id, attempt, max_attempts, next_delay_ms}` — one per attempt, before the sleep.
- `vertex.retry_succeeded` — when an attempt finally succeeds.
- `vertex.retry_exhausted` — when retries exhaust and the error edge is about to fire.

**Billing/metering:** every retry attempt counts as a component execution for metering. All attempts share one `flow_run_id` and roll up into one run's cost.

### Alert dispatch

When `ErrorHandler` is invoked:

1. Render `alert_title` and `alert_body` from templates using the payload + flow context.
2. Dispatch by `alert_mode`:
   - `Ignore` — no-op.
   - `Bell` — call `UsageAlertNotifier.notify(UsageAlertEvent(...))`:
     - `category = "flow_error"` (new constant)
     - `severity = "error"`
     - `org_id` from flow context
     - audience resolved from `bell_audience`:
       - `Flow owner` → `audience_user_id = flow.owner_id`
       - `Org admins` → audience type `PLATFORM_ADMIN`
       - `Specific user` → `audience_user_id = picked_user_id`
     - `title` and `body_md` from rendered templates
     - `metadata = {vertex_id, attempt_number, error_type}`
   - `Email (Not Implemented)` — log warning; fall through to `Bell` so the user is still notified in v1.
3. Persist to `FlowRun.error` JSON: `{component_id, component_display_name, error_type, error_message, stack_trace, attempts, alerted}`. If `FlowRun.error` already exists (multi-error run), append to a `handled_errors[]` list rather than overwriting.
4. Set `run.had_handled_errors = True` on the run context (consumed by `worker_app/execute.py:173`).
5. Fire `gave_up` carrying the original `ErrorPayload`.

Alert dispatch failures (e.g., DB error writing the `AdminNotification`) log but do not re-fail the flow.

### Multi-tenant scoping

Every `AdminNotification` row carries `org_id`. The `Specific user` user-picker is constrained to the flow's org — no cross-org targeting. Pattern matches the existing `CrossOrgFKError` validator surface.

### `RunStatus.PARTIAL_SUCCESS`

A new enum value added to `RunStatus`:

- Stored value: `"partial_success"` (15 chars — fits the existing `String(length=16)` column with no width change).
- Display value: `"Completed with errors"`.
- Set when the run completed normally (no uncaught exception) *and* `FlowRun.error` is non-empty (i.e., at least one error was handled).
- Computed in `worker_app/execute.py:173` (the existing terminal-status decision point) by reading the `had_handled_errors` flag.
- Excluded from `_FAILURE_STATES` in `services/metering/rules.py:11` — handled errors are not reliability failures.
- Mapped to webhook event `"run.partial_success"` in `worker_app/execute.py:262-265`.
- Frontend runs view renders an amber "Completed with errors" badge when status is `PARTIAL_SUCCESS`.

`FAILED` is still reserved for "exception escaped the runtime extension" (today's meaning) — when no error port is wired or `ErrorHandler` itself raised.

### Frontend treatment

- The error port renders on the right side of a node, below normal outputs, with a small triangle-alert icon and a thin `--destructive`-token border (not the ADP brand red `#ED1C2E`).
- Hover tooltip: `"Error output — connects to an Error Handler or Agent."`
- The `ErrorPayload` typed-edge validator is enforced by the existing edge-type validator; no special UI logic.
- During retries, the failing node renders an amber pulsing border with overlay `"Retry 2/3 in 4s…"` driven by the `vertex.retrying` SSE event.
- On retry success, the node flashes green briefly.
- On exhaustion, the node turns red and the error edge animates.
- Runs view: status column renders the `PARTIAL_SUCCESS` badge; a tooltip on hover shows the count of handled errors from `FlowRun.error.handled_errors[]`.

## Schema and migrations

One alembic migration:

- `ALTER TYPE runstatus ADD VALUE 'partial_success'` (Postgres enum extension; idempotent via `IF NOT EXISTS`).
- No column changes.
- No new tables — `AdminNotification` and `FlowRun` are reused.

To verify before drafting:

- Whether `AdminNotification.category` is enum-constrained or free-form. If enum-constrained, a second migration adds `"flow_error"`. If free-form, no migration needed.

Frontend: re-run OpenAPI codegen after the enum change; commit the regenerated `_generated.ts`.

## Testing

**Unit (`src/backend/tests/unit/services/reliability/`):**

- `test_retry_executor.py` — backoff math, cancellable sleep, `max_attempts` boundaries (0, 1, 10).
- `test_error_payload.py` — payload construction from various exception types, stack trace truncation.
- `test_error_handler_component.py` — alert dispatch routing, template rendering, audience resolution.

**Integration (`src/backend/tests/integration/services/`):**

- `test_runtime_error_routing.py` — full flow: component raises, error edge fires, `gave_up` runs, `FlowRun.status == PARTIAL_SUCCESS`, `FlowRun.error` populated.
- `test_runtime_retry_recovery.py` — flaky component (raises N-1 times, succeeds on N) yields no error-edge fire, normal output runs, `FlowRun.status == SUCCEEDED`.
- `test_runtime_retry_exhaustion.py` — flaky component raising N+1 times → error edge fires, `gave_up` runs, run ends `PARTIAL_SUCCESS`.
- `test_runtime_unconnected_error_port.py` — error port present but unwired → flow goes `FAILED` (regression guard for today's behavior).
- `test_runtime_error_handler_in_handler.py` — exception inside `ErrorHandler` → flow goes `FAILED` (no infinite recovery).
- `test_runtime_fan_in.py` — two source components both wired to one shared `ErrorHandler`, both fail in parallel, both alerts fire, both `gave_up` edges run.
- `test_bell_dispatch.py` — `AdminNotification` rows written with correct `org_id`, audience, category, body for each `bell_audience` option.

**Frontend (Jest, per `project_frontend_test_stack` memory):**

- Edge-validator unit test: `ErrorPayload`-typed output cannot connect to non-`ErrorPayload` input.
- Component-rendering test: error port renders below normal outputs with destructive-token border.
- Runs view test: `PARTIAL_SUCCESS` status renders the "Completed with errors" badge.
- SSE handling: `vertex.retrying` event updates canvas node visual state.

**lfx (`src/lfx/tests/unit/components/reliability/test_error_handler.py`):**

The component class itself, in isolation. Set `LFX_TEST_ALLOW_LANGFLOW=1` per the lfx test isolation memory if any cross-package import is needed.

**Cross-cutting verifications:**

- Audit log: the existing audit listener auto-captures the `FlowRun` UPDATE that sets `status = PARTIAL_SUCCESS`. No explicit audit calls needed; integration test confirms.
- Metering: assert `is_failure(RunStatus.PARTIAL_SUCCESS) == False`.
- Webhook delivery: round-trip the new `"run.partial_success"` event through the delivery path.

## Risks and open questions

- **Conditional-exclusion reuse:** suppressing the failing vertex's normal-output successors uses `graph.exclude_branch_conditionally`, the same primitive `ConditionalRouter` depends on. If that mechanism is refactored, this feature breaks silently. Mitigation: integration tests assert the suppression behavior end-to-end so a refactor that breaks it gets caught in CI.
- **`AdminNotification.category` constraint:** must verify whether the field is enum-constrained or free-form before drafting the migration. Listed as a verification step in the schema section.
- **Stack-trace privacy:** stack traces may include sensitive data (variable names, paths). V1 stores them raw in `FlowRun.error` JSON, org-scoped per multi-tenant rules. Redaction is a follow-up after legal review and is called out in non-goals.
- **`ComponentVertex.finalize_build` override:** per the `project_component_vertex_finalize_build_override` memory, every modern component runs through `ComponentVertex.finalize_build`, not the base `Vertex.finalize_build`. The exception-catch logic in `_execute_tasks` is upstream of `finalize_build` so this should not affect us, but the implementation must verify the exception still surfaces at line 1848 regardless of which `finalize_build` ran.

## Sequencing into the parked roadmap

This spec delivers what the parked iPaaS T1-A slice (retry / try-catch / fallback as a batch) was meant to cover, consolidated into one primitive instead of three. After implementation:

- Retry → covered (handler's `max_attempts` + backoff).
- Try/catch → covered (the error-edge wiring is the try/catch boundary).
- Fallback → covered (`gave_up` is the fallback edge).

The remaining T1 slices (circuit breaker, dead-letter service, idempotency helper, rate limiter) become independent specs that compose with this one.

## Final implementation (as shipped)

A handful of decisions diverged from the original design as the implementation hit reality. Recording them here so the spec matches what runs.

### Catch site moved upstream of `_execute_tasks`

The spec called out `_execute_tasks` (`src/lfx/src/lfx/graph/graph/base.py:1848-1856`) as the exception-catch site. That catch only fires for the `Graph.process()` / `astep` path. The streaming `/build/{flow_id}/flow` endpoint (`src/backend/base/langflow/api/build.py`) calls `graph.build_vertex` directly and never reaches `_execute_tasks`, so error edges defined on a vertex would have been silently bypassed in production.

Resolution: `_try_handle_via_error_edge` is now invoked inside `Graph.build_vertex`'s own `except Exception` block. All three execution paths — `astep`, `_execute_tasks`, and the streaming API endpoint — go through `Graph.build_vertex`, so a single catch site handles them all. The pre-existing catches in `_execute_tasks` and `astep` remain in place but are effectively no-ops for the handled-error case (the inner catch returns a synth VBR before they see the exception).

### `gave_up` emits `Message`, not `ErrorPayload`

The spec typed `gave_up` as `["ErrorPayload"]`. Two practical problems:

1. `ErrorPayload` is a structured Python dataclass; downstream UI components (Chat Output, Text Output, Agent input) all consume `Message`. Typing `gave_up` as `ErrorPayload` would have required either lossy adapters at every fan-out target or rejection at the edge-type validator.
2. The user-facing rendering of an error is text — markdown body with the error type, message, attempt count, and a truncated stack trace.

Resolution: `gave_up` is typed `["Message"]`. The runtime renders the `ErrorPayload` into a markdown `Message` and writes it to the failing vertex's `error` output (see next item). `ErrorHandler.on_error_exhausted` forwards `self.error_input` as the `gave_up` value. Chat Output, Text Output, and Agent all receive a `Message` they already know how to render or consume.

### Synthesize-failing-vertex state instead of invoking the handler manually

The spec implied `_try_handle_via_error_edge` would invoke the `ErrorHandler` vertex itself (computing inputs, calling `vertex.build()`, returning a VBR for the handler) on retry exhaustion. That fought the build pipeline's edge resolver — `error_input` is wired to the failing vertex's `error` output, so the handler's normal `_build_each_vertex_in_params_dict` path tried to resolve it from the (failed) failing vertex and we ended up patching `raw_params`/`build_params` and monkey-patching `on_error_exhausted` to fight back.

Resolution: rather than invoke the handler manually, the runtime extension synthesizes a "successful" state on the **failing vertex**:

- Sets `failing_vertex.built = True`.
- Sets `failing_vertex.results["error"] = <Message rendered from the ErrorPayload>`.
- Calls `failing_vertex.set_result(ResultData(results={"error": message}, ...))`.
- Suppresses the failing vertex's non-error successors via `graph.exclude_branch_conditionally`.
- Dispatches the alert and records the handled error.
- Returns a VBR for the **failing vertex** (with `valid=True`).

The standard build pipeline then takes the synth VBR, computes next-runnable from the failing vertex's successors (which is the `ErrorHandler` vertex), builds it via the normal pipeline, resolves `error_input` from the failing vertex's `results["error"]`, and `on_error_exhausted` returns that `Message` as `gave_up`. From the build pipeline's perspective, nothing extraordinary happened — the failing vertex just produced an `error` output.

### Fix: drop the inner `get_next_runnable_vertices` call

The original error-handling block in `Graph.build_vertex` computed `get_next_runnable_vertices` for each handled VBR and stuffed the result into `_run_queue`. Two problems:

1. `_run_queue` is consumed only by `astep`; the streaming API path uses `vertex_build_response.next_vertices_ids` (computed by the outer caller) for recursion, so the queue extension was dead code in production.
2. The inner `get_next_runnable_vertices` call adds the next runnable vertex (e.g. `ErrorHandler`) to `vertices_being_run`. Then the outer caller (`api._build_vertex` line 380, `_execute_tasks` line 1964, `astep` line 1520) calls `get_next_runnable_vertices` *again* on the same failing vertex — but `is_vertex_runnable(ErrorHandler)` now returns `False` because it's in `vertices_being_run`, the recursive predecessor walk finds nothing else, and the outer call returns `[]`. The recursion stalls at the failing vertex and `ErrorHandler` (and anything past it) never queues.

Resolution: the error-handling block in `Graph.build_vertex` no longer computes next-runnable. It just returns the synth VBR and lets each outer caller compute next-runnable from `synth_vbr.vertex` itself, which then traverses the full `failing_vertex → ErrorHandler → … → terminal` chain through normal build-pipeline recursion.

### Auto-injected error output must set `tool_mode=False`

`Output.tool_mode` defaults to `True`. The auto-injection in `Component._maybe_inject_error_output` originally constructed the error `Output` without specifying `tool_mode`, so it inherited the default. That collided with the agent-as-tool path:

`LCAgentComponent` has `error_output_enabled=True` (so it has the auto-injected error output) **and** its `input_value` input has `tool_mode=True`. When an Agent is a *terminal* vertex (no outgoing edges), `_should_process_output` returns True for *every* output in `_outputs_map`. `_handle_tool_mode` adds the `component_as_tool` output (method=`to_toolkit`), which gets processed and calls `Agent._get_tools(tool_name="Call_Agent", ...)`. `ComponentToolkit.get_tools` then iterates `self.outputs`, finds 2 non-skipped outputs (the component's normal output + the `error` output), and raises *"When passing a tool name or description, there must be only one tool, but 2 tools were found."*

This was latent until the multi-hop traversal fix landed — beforehand, the error chain stopped at `ErrorHandler` and the terminal Agent never built. After the fix, the Agent built and the bug surfaced.

Resolution: set `tool_mode=False` on the auto-injected error `Output`. `ComponentToolkit._should_skip_output` excludes it from tool conversion via the `not output.tool_mode` branch. Inline comment at the injection site documents the rationale so a future cleanup pass doesn't strip the flag.

### Component-loader two-load-path gotcha (`isinstance` failure)

`isinstance(component, ErrorHandler)` returned `False` for components instantiated by Langflow's component loader, even when the component class was named `ErrorHandler`. Per the `langflow-component-loader` skill, the loader can instantiate components under a *different* class object than `from lfx.components.reliability.error_handler import ErrorHandler` resolves to in the runtime extension's import.

Resolution: `_try_handle_via_error_edge` matches by class `__name__` plus a duck-type check (`hasattr(component, "dispatch_alert")`) instead of `isinstance`. Both the cycle guard and the handler-target check use the same helper.

### What ships

- `Component.error_output_enabled: ClassVar[bool]` opt-in (default `False` on root, `True` on a curated set of bases per the spec).
- `ErrorPayload` schema in `src/lfx/src/lfx/schema/error_payload.py` and registered in `lfx.field_typing`.
- `ErrorHandler` component at `src/lfx/src/lfx/components/reliability/error_handler.py` with retry config, alert dispatch, `gave_up: Message` output.
- Runtime extension in `Graph.build_vertex` + `_try_handle_via_error_edge` + `_suppress_normal_successors` + `_dispatch_handler_alert` + `_record_handled_error`.
- `RunStatus.PARTIAL_SUCCESS` enum value, `_FAILURE_STATES` exclusion, webhook mapping.
- Frontend cleanEdges regression fix preserving `ErrorPayload`-typed edges (commit `154c025a5a`).
- API Request, ADP API Request, ADP Tools `raise_on_status` toggle (commit `7e607f9dbd`) so 4xx/5xx HTTP responses raise instead of silently returning, which is what makes the error edge fire.
- Skill update at `.claude/skills/langflow-component-error-port/SKILL.md` covering the per-component opt-in mechanics.

### Manually verified end-to-end

Flow: `API Request.error → ErrorHandler.error_input → TextOutput`. With `Raise on HTTP error (4xx/5xx)` enabled and a 4xx-returning URL, the build pipeline now traverses:

```
APIRequest-...   (fails → synth state)  → recurse → [ErrorHandler-...]
ErrorHandler-... (built, gave_up=Message) → recurse → [TextOutput-...]
TextOutput-...   (built)                  → terminal
```

The bell fires once, the magnifier on `gave_up` shows the rendered error markdown, and downstream components (Chat Output / Text Output / Agent input) receive the `Message` through the normal build pipeline.
