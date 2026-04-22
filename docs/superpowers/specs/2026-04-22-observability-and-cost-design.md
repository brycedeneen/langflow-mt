# Observability & Cost — Design

**Roadmap items covered:**
- P0-5 — Run history dashboard per org
- P0-7 — Per-flow cost visibility (LLM tokens + compute)
- P0-8 — Pre-run cost estimator for AI/agent flows

**Roadmap source:** `2026-04-22-integration-platform-roadmap.md`
**Scope:** Bundled because they share data plumbing (run outcomes + token usage + model identity all flow from the same completion hook) and the same UI surfaces.

## Background — key findings

- **`TraceTable` has no link to `FlowRun` today** — it carries `flow_id + session_id`, neither of which uniquely identifies a run. We must add `flow_run_id` to `TraceTable` (populated forward; no backfill) to attribute tokens and cost to specific runs.
- **Pricing:** `litellm.get_model_cost_map()` is available and covers major providers — use it as the source, with a local override table for unlisted/custom models, refreshed daily.
- **Component detection** via `trace_type` on base classes (`LCModelComponent.trace_type == "llm"`, `LCEmbeddingsModel.trace_type == "embedding"`, agent subclasses of `ToolCallingAgentComponent`). Walking `flow.data["nodes"]` is the idiomatic inspection path.
- **No charting library** in `package.json` — adding **recharts** (see Section 4).
- **Service container + run-completion hook** already built out in Design 3. This design piggybacks on the same service (`record_run_completion_and_eval`).

## Goals

1. Per-org run history dashboard with success rate, duration p50/p95, error trends, and per-flow breakdown.
2. Per-flow cost visibility (LLM tokens + compute) on the flow detail page.
3. Pre-run cost estimator that surfaces an approximate per-run cost for flows with AI/agent/embedding components.

## Non-goals (v1)

- Bytes-transferred metric (captured as P1 follow-up on Design 3).
- Per-user (not per-org) cost breakdown.
- Historical cost backfill — runs pre-feature show "—".
- P95 duration alert rule — Design 3 ships per-run SLA rule; P95 deferred.
- Billing / chargeback integration.
- Model-level forecasts beyond the simple estimator heuristics.

## Dependencies on Design 3

- Reuses `OrgUsageDaily` (extending with a `cost_cents` column).
- Reuses `record_run_completion_and_eval` as the single hook point for usage writes.
- Reuses `UsageAlertDispatcher` for any threshold-style alerting on cost (not needed in v1 but the plumbing's there).

## Audience matrix

| Surface | Who sees it |
|---|---|
| Per-org dashboard | Any org member (viewer → owner) |
| Per-flow cost summary | Anyone with access to that flow |
| Pre-run cost estimator | Anyone in the flow builder |
| Cross-org super view | Super admins (via existing `X-Acting-Org-Id` org switcher) |

Rationale: usage/cost is operational, not sensitive. Viewers seeing "our flows cost $43 this week" is fine. Audit-log rows with actor emails stay super-admin-only (Design 2).

## Data model

### Extend `OrgUsageDaily` (Design 3)
- Add `cost_cents` BIGINT (default 0). Rolled up at run completion.

### New table `FlowUsageDaily`
Per-flow-per-day grain — same pattern as `OrgUsageDaily`, different key.

| Column | Type | Notes |
|---|---|---|
| `flow_id` | UUID FK | PK part 1 |
| `date` | DATE | PK part 2 |
| `org_id` | UUID FK | denormalized for fast org-scoped queries |
| `runs` | BIGINT | |
| `run_seconds` | BIGINT | |
| `tokens` | BIGINT | sum across models |
| `cost_cents` | BIGINT | |
| `updated_at` | TIMESTAMPTZ | |

Index: `(org_id, date DESC)` covers the per-org dashboard's per-flow breakdown.

### Extend `FlowRun`
- `cost_cents` INT nullable — computed at completion, null for pre-feature runs.
- `model_usage` JSONB nullable — per-model breakdown:
  ```json
  {"anthropic/claude-opus-4-7": {"input_tokens": 1200, "output_tokens": 800, "cost_cents": 15}, ...}
  ```

### Extend `TraceTable`
- `flow_run_id` UUID FK nullable — enables reliable run→trace linkage. Populated by the tracer on new runs.

Migration: one alembic migration for all four changes. Coordinates with Design 3's migration (decide during plan whether to combine or sequence them).

## Cost computation pipeline

Piggybacks on Design 3's `record_run_completion_and_eval` (same hook, same service, same transaction window). After the existing threshold + rule evaluation:

1. Load spans for this run via `flow_run_id`.
2. For each LLM/Embedding span, extract `model` + `prompt_tokens` + `completion_tokens` from `span.attributes`.
3. Call `PricingService.compute_cost_cents(model, input_tokens, output_tokens)`.
4. Aggregate: total `cost_cents` + per-model `model_usage`.
5. Update `FlowRun.cost_cents` and `model_usage`.
6. Upsert `FlowUsageDaily`; extend the `OrgUsageDaily` upsert with `cost_cents += …`.

### Pricing service

```python
class PricingService:
    def __init__(self, overrides: dict[str, ModelPrice], refresh_interval_h: int = 24): ...
    async def start(self) -> None: ...  # loads litellm cost map + schedules refresh
    def compute_cost_cents(self, model: str, input_tokens: int, output_tokens: int) -> int:
        # resolves price (override > litellm > 0 + warning), returns integer cents
```

- One instance, registered in the service container.
- Refreshes litellm map daily via an arq scheduled task.
- Override table is an env-configurable JSON blob for custom / unlisted models.
- Unknown model → returns `0` and logs a warning once per (model, hour).

### Latency

Added to Design 3's existing hook: ~5–10 ms (one span query + arithmetic). Total hook stays within the ~20–40 ms p95 sized in Design 3.

## API surface

All org-scoped endpoints respect org membership; unauthorized returns 404 (not 403) to avoid leaking existence.

- `GET /api/v1/orgs/:id/usage?window=7d` — KPI cards. Any org member.
- `GET /api/v1/orgs/:id/usage/charts?metric=runs&window=30d` — time-series for charts (metric: runs | success_rate | p50_duration | p95_duration | cost).
- `GET /api/v1/orgs/:id/usage/flows?window=30d&sort=cost_desc&page=1` — per-flow breakdown.
- `GET /api/v1/flows/:id/cost-summary` — flow-detail card data (current-month cost, 30d sparkline points, last-run cost).
- `POST /api/v1/flows/:id/estimate-cost` — pre-run estimator (see Section on estimator). Cached per flow-JSON hash with short TTL.

## Pre-run cost estimator

### Algorithm

1. Walk `flow.data["nodes"]`.
2. Classify each node via the registry:
   - `LCModelComponent` with `trace_type == "llm"` → **LLM**.
   - `LCEmbeddingsModel` descendants (`trace_type == "embedding"`) → **Embedding**.
   - Class name matches `*Agent*` or inherits `ToolCallingAgentComponent` → **Agent**.
3. Extract the configured model name from the node's template fields (typically `model_name` or `model`).
4. Apply heuristic tokens-per-call:

| Kind | Input tokens/call | Output tokens/call | Calls/run |
|---|---|---|---|
| LLM | 800 | 400 | 1 |
| Embedding | 512 | 0 | 1 |
| Agent | 800 | 400 | × `agent_multiplier` (default 4) |

5. Look up pricing via `PricingService`. If unknown → flag `unknown: true` for that component.
6. Return:

```json
{
  "estimate": {
    "expected_cost_cents": 12,
    "low_cost_cents": 5,
    "high_cost_cents": 25,
    "confidence": "rough" | "low" | "none"
  },
  "per_component": [
    {
      "node_id": "…",
      "kind": "llm",
      "model": "claude-opus-4-7",
      "estimated_input_tokens": 800,
      "estimated_output_tokens": 400,
      "cost_cents": 12,
      "unknown": false
    }
  ]
}
```

### Confidence semantics

- `rough` — all components have known models; defaults applied. Most flows land here.
- `low` — user explicitly configured `max_tokens` on any component (tighter input budget, but agent loop counts are still unknown).
- `none` — at least one component has an unknown model. UI shows `?` instead of a price.

### Config knobs (env vars)

- `COST_ESTIMATE_LLM_INPUT_TOKENS` (default `800`)
- `COST_ESTIMATE_LLM_OUTPUT_TOKENS` (default `400`)
- `COST_ESTIMATE_EMBED_INPUT_TOKENS` (default `512`)
- `COST_ESTIMATE_AGENT_MULTIPLIER` (default `4`)

Tunable from ops if defaults turn out wrong across the board.

## Front-end

### Charting library — **recharts**

Chosen because:
- React-idiomatic — fits Radix + Tailwind stack.
- Composable primitives (`<LineChart>`, `<XAxis>`, `<Tooltip>`).
- D3 internally — we can drop down if we ever need custom visuals.
- Team-friendly; most React devs have used it.

Alternatives evaluated and not chosen:
- **Visx** — more flexible, more code per chart. Overkill for our needs.
- **D3.js direct** — imperative, doesn't reconcile with React; only justified for bespoke visuals.
- **Nivo** — heavier, more opinionated.
- **Tremor** — dashboard kit that wraps recharts; we'd pick up another layer of abstraction for not much benefit.
- **uPlot / Chart.js** — canvas-based; weaker accessibility and React integration.

### Page 1 — Org Usage Dashboard (`/orgs/:id/usage`)

Top-to-bottom:

1. **KPI cards:** Runs, Run-minutes, Tokens, Cost for the selected window (Today / 7d / 30d toggle; default 7d).
2. **Primary chart:** metric switcher (runs | success rate | p50 | p95 | cost) over the same window.
3. **Per-flow breakdown table:** flow name, runs, success rate, avg duration, total cost, sparkline. Sortable, paginated. Click → flow detail page.
4. **Thresholds / Alert Rules tabs** (Design 3). Rendered as disabled tabs for non-super-admins so they know the feature exists.

### Page 2 — Flow detail "Cost & Usage" section

- Current-month cost, 30-day sparkline, last-run cost.
- Model breakdown (expandable): `claude-opus-4-7 · 12.4k tokens · $0.42`.
- Recent runs mini-table with per-run cost.

### Flow builder — pre-run cost badge

- Position: small pill next to the Playground button in `flowToolbarComponent`.
- Content: `~$0.02/run` plus confidence icon.
- Click → popover with per-component breakdown + confidence note.
- Visual states:
  - `rough` → normal pill style.
  - `low` → dashed border (the user configured specific caps but agent loops are unknown).
  - `none` → question-mark icon, `?` instead of a price (unknown model).

Copy on the popover: `Estimate — actual cost varies based on inputs and agent loops.` (Avoids anyone treating the estimate as precise.)

## Settings / rollout

- `COST_TRACKING_ENABLED` — bool, default `true`. Kill switch for the cost computation path.
- `COST_ESTIMATE_*` — the four estimator knobs above.
- `PRICING_OVERRIDES_JSON` — optional JSON blob merged on top of litellm's map.
- One alembic migration adds `flow_run_id` on `TraceTable`, `cost_cents` + `model_usage` on `FlowRun`, creates `FlowUsageDaily`, adds `cost_cents` to `OrgUsageDaily` (if Design 3's migration hasn't merged yet, combine them).
- **No backfill** — historical runs stay null for cost. Dashboard renders `—` for pre-feature rows.

## Testing

- **Unit:**
  - `PricingService` — override > litellm > 0 fallback, refresh cycle, unknown-model warning.
  - Cost computation per run — mock spans, assert `FlowRun.cost_cents` + `model_usage`.
  - Estimator against fixture flows: LLM-only / agent-with-tools / embedding-only / mixed / unknown-model. Assert confidence + per-component payload shape.
- **DB integration:**
  - `flow_run_id` populated on new traces.
  - Daily rollups increment correctly after multiple runs in the same day.
  - Org isolation — users in org A can't read org B's endpoints.
- **FE:**
  - Chart rendering with mock data; KPI card + chart + table compose without fetching duplicates.
  - Estimator badge — all three confidence states render correctly.
  - Flow detail cost card — handles pre-feature runs (`—`) gracefully.

## Risks

- **Pricing drift** — litellm map is updated out-of-band; our daily cache may lag 24h behind. Acceptable v1; if it bites, reduce refresh interval.
- **Estimator accuracy** — heuristics can be off 10× for agent-heavy flows. Mitigated by copy that makes clear it's rough, `none` state for unknown models, and per-component breakdown for forensics. **Do not let anyone sell this as precise.**
- **Trace-linkage** — relies on the tracer receiving `flow_run_id` at trace creation. Exact plumbing is a plan-time detail; listed in open questions.
- **Recharts bundle** — ~100 KB gzipped, acceptable for an admin-adjacent page.
- **Daily-rollup contention** — concurrent runs for the same flow racing on `FlowUsageDaily` upsert. Postgres `INSERT … ON CONFLICT DO UPDATE` handles atomically — no extra locking.

## Open questions (resolve during plan)

- Exact callsite/helper to pass `flow_run_id` into tracer creation — requires reading the tracer lifecycle code during plan.
- Flow-members vs org-members for per-flow cost visibility — leaning "anyone in the org can read any flow's cost within that org." Confirm if we ever add flow-level ACLs.
- Override-pricing JSON schema — decide whether to ship a schema validator in v1 or accept loose JSON.
