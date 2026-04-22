# Phase 3 — LC 1.x tooling (composio + openinference)

**Date:** 2026-04-22
**Status:** Plan — awaiting Phase 1/2 stabilization
**Goal:** Verify the two pieces of tooling around the langchain stack still behave correctly against LC-1.x runnables: Composio's langchain adapter and the OpenInference langchain instrumentor. Both currently import clean but weren't exercised live during Phase 1.

## Context

- Phase 1 (commit `46953dc30b`) lifted langchain core + integration caps to 1.x.
- `composio-langchain` and `openinference-instrumentation-langchain` are the two "adapter" packages that sit between langchain runnables and external systems (tool catalog, tracing). Both are currently at their latest releases (`composio-langchain==0.11.5`, `openinference-instrumentation-langchain==0.1.62`; PyPI latest `0.11.5` / `0.1.63`).
- Neither has been live-smoked against LC-1.x runnables yet.

## Item 1 — `composio-langchain`

**Current state**
- Pin: `composio-langchain>=0.11.0,<1.0.0` (backend/base pyproject `composio` extra).
- Installed: `0.11.5` — already latest in the 0.x line.
- Usage in repo: `src/lfx/src/lfx/components/composio/composio_api.py`, `src/lfx/src/lfx/base/composio/composio_base.py`.
- Composio also shipped a `1.x` of their own base SDK (`composio==1.x`), but `composio-langchain` stays on 0.11.x. The integration contract is: composio-langchain wraps composio actions as langchain `BaseTool` subclasses.

**Risks under LC 1.x**
- `BaseTool` contract tightened in LC 1.x (args schema, callback signatures). If composio-langchain 0.11.x builds tools using the 0.3-era BaseTool surface, the resulting tools may fail when added to a LangGraph `create_agent(tools=[...])` (LC 1.x) invocation.
- Tool `.run()` / `.invoke()` dispatch also changed in LC 1.x — async-by-default; composio-langchain's sync-shape adapters may need wrapping.

**Verification steps**
1. Import smoke: `uv run python -c "from composio_langchain import ComposioToolSet; ts = ComposioToolSet(); print(ts)"` — confirm class still loads without deprecation errors against LC-1.x.
2. Tool construction: build a tool via composio-langchain (no network — use one of the offline actions) and inspect `.args_schema`, `.func`, `.coroutine` shapes. Confirm `isinstance(tool, langchain_core.tools.BaseTool)` holds under LC 1.x.
3. End-to-end via LangGraph: wire the tool into `langchain.agents.create_agent(model=..., tools=[composio_tool])` using a fake model, run `astream_events` v2, verify no `TypeError`/attribute errors and the tool appears in the graph spec.

**Decision points**
- If steps 1–2 pass but step 3 fails, the fix is composio-side; pin `composio-langchain` to whatever 0.11.x release has their LC-1.x fixes, or wrap their tools in a thin adapter in `src/lfx/src/lfx/base/composio/`.
- If composio never ships LC-1.x support and Langflow's Composio component becomes unreliable, consider swapping to the base `composio` SDK (1.x) and doing the langchain `BaseTool` wrapping in-house. That's a bigger refactor — separate ticket.

**Estimated effort:** 1–2 hrs for the verification, + whatever adapter work the results trigger.

## Item 2 — `openinference-instrumentation-langchain`

**Current state**
- Pin: `openinference-instrumentation-langchain>=0.1.29` (backend/base pyproject `openinference` extra, no upper bound).
- Installed: `0.1.62`. PyPI latest: `0.1.63`.
- Usage in repo: `src/backend/base/langflow/services/tracing/arize_phoenix.py` — the Arize Phoenix tracer integration uses this instrumentor to emit OpenTelemetry spans for langchain runnable execution.

**Risks under LC 1.x**
- The instrumentor patches `langchain_core.callbacks.BaseCallbackHandler` / `Runnable.invoke` / `astream_events` at known entry points. LC 1.x renamed some internal callback hooks and shifted `Runnable` execution into LangGraph for the agent path.
- `LangGraph create_agent()` runs in a compiled graph; langchain-style callbacks still fire but span correlation may drop at graph-node boundaries.
- Tracing adapters in `src/backend/base/langflow/services/tracing/` (opik.py, openlayer.py, arize_phoenix.py, langfuse_tracer.py) all import clean after Phase 1 but none have been live-exercised.

**Verification steps**
1. Install Arize Phoenix locally: `uv pip install arize-phoenix` (or use their in-process collector). Launch Phoenix: `python -m phoenix.server`.
2. Start Langflow with `LANGFLOW_TRACER_ARIZE_PHOENIX_ENABLED=true` (verify the actual env-var name — likely defined in `langflow/services/tracing/arize_phoenix.py`).
3. Run the LangGraph Agent golden path (the one used for Phase 1 item 3 smoke): Agent flow with one tool, non-trivial prompt, OPENAI_API_KEY set.
4. In Phoenix UI, look for:
   - Parent span for the graph invocation
   - Child spans for each LLM call
   - Tool-execution spans with input/output
5. Confirm span attributes are populated: model name, prompt tokens, completion tokens, tool name, tool input.

**Decision points**
- **All spans present, attrs populated:** pass. Bump pin upper bound to `<0.2.0` for explicit safety; keep shipping.
- **Spans present but missing LangGraph-node granularity:** expected; LangGraph's internal graph execution isn't wrapped by the langchain instrumentor. Acceptable — file an issue upstream but don't block release.
- **Spans missing entirely / attribute errors in logs:** instrumentor is broken on LC 1.x. Fallback: either downgrade to an instrumentor version matching the LC 0.3 line (regress the tracing extra), or swap to a LangGraph-native instrumentor if OpenInference has published one. Check `openinference-instrumentation-langgraph` on PyPI.

**Estimated effort:** 2–3 hrs (Phoenix setup + span audit).

## Supporting work

- **Opik + Openlayer adapters**: `src/backend/base/langflow/services/tracing/opik.py` and `openlayer.py` use the same LC callback surface. Run the same smoke against these if the deploy uses them. Langfuse migration already landed (commit `1f244e18f6`) and is presumed working.
- **ALTK tracing**: if ALTK's own span-emitter interacts with LC callbacks, the `altk_base_agent.py` path may need a separate smoke.

## Sequencing

1. Do Item 1 first — cheaper, no infrastructure needed. If composio is broken on LC 1.x, that's a blocker for any deploy relying on Composio components and escalates priority.
2. Item 2 only if the deploy's tracing backend is Phoenix/Arize. Otherwise run the analogous smoke against whichever tracer the deploy actually uses.

## Exit criteria

- `uv run pytest src/backend/tests/unit/components/bundles/composio/` + component-level tests for the two tracing files pass (check if these test files exist — if not, create a minimal smoke test).
- Manual Agent-with-tool run (LangGraph runtime) produces the expected traces in the deploy's tracing backend.
- No new deprecation noise introduced (compare against the current filter-warnings list in `src/backend/base/langflow/__init__.py`).

## Out of scope

- Migrating Composio off `composio-langchain` (tracked as a separate ticket if Item 1 fails hard).
- Bumping the `openinference` extra to strict upper bound (tracked after Item 2 verification).
