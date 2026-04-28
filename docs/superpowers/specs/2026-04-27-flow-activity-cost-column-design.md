# Flow Activity — Cost column & detail tile

**Status:** design approved, ready for implementation plan
**Date:** 2026-04-27
**Author:** brainstorming session (`platform-multi-tenant`)

## Goal

Surface per-trace USD cost on the Flow Activity screen (`FlowInsightsContent`)
and on the Trace Details panel. Cost reflects all LLM and embedding spans in
the trace, including those produced inside agent components.

## Why this is mostly wiring

The compute infrastructure already exists:

- `services/pricing/service.py` → `PricingService.compute_cost_cents()` /
  `compute_cost_micros()` driven by LiteLLM pricing + JSON overrides.
- `services/cost/compute.py` → `compute_cost_for_run()` already buckets LLM /
  embedding span attributes by model and produces a total + per-model breakdown.
- `services/metering/service.py` already persists `FlowRun.cost_cents` post-run.
- `controllers/API/queries/traces/types.ts` already declares `totalCost` on
  `TraceListItem` (currently never populated by the backend).

Only the trace read-path needs to expose the value, and the UI needs a column
plus a stat tile.

## Non-goals

- Persisting cost on `TraceTable` (no migration, no schema change).
- Backfilling cost on historical traces (reads recompute on-the-fly).
- A "partial pricing" indicator for traces that mix known and unknown models.
- A per-model breakdown in the detail panel (deferrable follow-up; the data
  is already bucketed per model server-side).
- Fixing the pre-existing `Prompt 0 / Completion 0` inconsistency on the detail
  panel — orthogonal bug.

## Architecture

### Backend — single computation site

Extend `fetch_trace_summary_data()` in
`src/backend/base/langflow/services/tracing/repository.py` (currently around
lines 75–131; the function that already iterates spans for token totals).

Same loop, additional bucketing:

- For each span where `span_type ∈ {LLM, EMBEDDING}` with a non-empty
  `model_name | model` attribute, bucket `(prompt_tokens | input_tokens,
  completion_tokens | output_tokens)` by model. Identical attribute-key
  fallback to `compute_cost_for_run` so behavior matches the metering path.
- After bucketing, call `PricingService.compute_cost_micros(model, ...)` per
  bucket and sum to a per-trace `total_cost_micros: int | None`.
- Pricing service is fetched via `get_pricing_service()` from the service
  registry (same pattern `services/metering/service.py` uses) — keeps
  `fetch_trace_summary_data` stateless.

Returning `micros` (not cents) preserves sub-cent precision so the frontend
can render `<$0.01`. The existing `compute_cost_cents` rounds to integer cents
and would mis-display real 0.4-cent runs as `$0.00`.

### Backend — model + API surface

Add `total_cost_micros: int | None` to:

- `TraceSummaryData` (in-memory aggregate produced by
  `fetch_trace_summary_data`).
- `TraceSummaryRead` and `TraceRead` Pydantic models in
  `services/database/models/traces/model.py`.
- `_trace_to_base_fields(...)` helper passes the value through unchanged.

`GET /api/v1/monitor/traces` and `GET /api/v1/monitor/traces/{id}` then
include `total_cost_micros` automatically via the existing serialization.

No new endpoint, no DB migration, no `TraceTable` schema change.

### Frontend — list column

`src/frontend/src/pages/FlowPage/components/TraceComponent/config/flowTraceColumns.tsx`:

- Insert a new `cost` column between `tokens` and `latency`.
- Cell renderer uses a shared formatter (`formatCostMicros`, see below).
- Header label: `Cost`.

`src/frontend/src/controllers/API/queries/traces/types.ts`:

- Replace the unused `totalCost` field on `TraceListItem` with
  `totalCostMicros: number | null` to match the API contract.
- Update `TraceApiResponse` mapping accordingly.

### Frontend — Trace Details detail panel

The detail panel currently shows four stat tiles: Latency, Tokens, Prompt,
Completion. Add a fifth tile **Cost** mirroring the Tokens tile styling, fed
by the same `total_cost_micros` value.

### Frontend — formatter

Shared util (likely `src/frontend/src/utils/cost.ts` or co-located with the
column definition):

```
formatCostMicros(micros: number | null | undefined): string
  null / undefined → "—"           // no LLM/embedding spans, or all unknown
  0                → "$0.00"        // priced spans ran, math = 0
  1..9999          → "<$0.01"       // sub-cent positive
  ≥10000           → "$X.XX"        // round to cents (Math.round(micros/10000)/100)
```

This matches the project-wide money-format convention.

## Edge cases & semantics

### Null vs zero

| Backend value | Meaning                                                   | Display |
|---------------|-----------------------------------------------------------|---------|
| `null`        | Zero LLM/embedding spans **or** every model is unknown    | `—`     |
| `0`           | Priced spans ran, computed total micros = 0               | `$0.00` |
| `>0`          | Real cost                                                 | `$X.XX` / `<$0.01` |

### Unknown models

If **some** spans match pricing and **some** don't, sum the priced ones and
return that number. Don't fall back to null in mixed cases — that would hide
real cost. A future "partial pricing" UI hint is deferred.

### Span-type filter

LLM and EMBEDDING only — same as `compute_cost_for_run`. Tool / chain /
agent-wrapper spans are skipped because the LLM calls inside an agent emit
their own LLM spans, which is where the tokens and model live.

### Performance

`fetch_trace_summary_data` already loads every span for the visible page. The
new work is O(spans) arithmetic plus one dict lookup per (trace, model).
`PricingService` is fully in-memory after init. No new SQL, no N+1.

### Multi-tenancy

Unchanged. `fetch_traces` already scopes by `flow.organization_id`.

## Testing

### Backend (unit, repository layer)

Synthetic spans → known cost. Cases:

1. Single LLM span, known model → expected micros.
2. Agent trace with two LLM sub-spans on the same model → sum.
3. Mixed models on the same trace → sum across `PricingService` lookups.
4. Unknown model only → `null`.
5. Mixed known + unknown models → partial total (priced ones only), not null.
6. Embedding span only → priced as embedding.
7. Trace with zero LLM/embedding spans → `null`.
8. Sub-cent positive (small token count, expensive model) → small micros > 0.

### Frontend

- Unit test on `formatCostMicros` covering all four display states.
- Snapshot or render test on the cost column rendering all four states.
- Render test on the detail panel showing the new Cost tile alongside Tokens.

## File touch list (preview, finalized in plan)

Backend:
- `src/backend/base/langflow/services/tracing/repository.py` — extend
  `fetch_trace_summary_data` and `fetch_single_trace`'s summary build.
- `src/backend/base/langflow/services/database/models/traces/model.py` —
  add `total_cost_micros` to `TraceSummaryData` / `TraceSummaryRead` /
  `TraceRead`.
- Tests under `src/backend/tests/unit/services/tracing/` (or wherever
  trace-repo tests already live).

Frontend:
- `src/frontend/src/pages/FlowPage/components/TraceComponent/config/flowTraceColumns.tsx`
- `src/frontend/src/pages/FlowPage/components/TraceComponent/FlowInsightsContent.tsx`
  (detail panel tiles).
- `src/frontend/src/controllers/API/queries/traces/types.ts`
- New `src/frontend/src/utils/cost.ts` (or co-located util) +
  matching test file.

## Risks / open questions

- **Pricing service initialization timing.** `get_pricing_service()` must be
  ready when the traces endpoint is hit. Already true in production (it boots
  with the rest of the service registry); flag during plan execution if a
  test setup needs explicit init.
- **Embedding span attribute keys.** `compute_cost_for_run` reads
  `prompt_tokens|input_tokens` for embeddings; double-check our embedding
  span emitters actually set one of those keys, otherwise embedding cost will
  silently be 0. Verify during plan execution; if missing, scope creeps to
  fix the emitter (would be flagged separately).
