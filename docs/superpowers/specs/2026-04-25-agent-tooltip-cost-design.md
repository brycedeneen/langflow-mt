# Per-Vertex Estimated Cost in Node-Status Tooltip

**Status:** Design complete, awaiting implementation plan
**Date:** 2026-04-25
**Branch:** `platform-multi-tenant`

## Goal

Display the estimated USD cost for each vertex run in the existing per-node status tooltip on the canvas, computed from the *actual* model used and the recorded token counts. Accuracy comes from the existing backend `PricingService` (LiteLLM cost map + `PRICING_OVERRIDES_JSON` env overrides) — not a frontend approximation.

## Scope

- **Applies to:** every vertex that emits `token_usage` (Agent, plain Language Model, anything calling an LLM through the existing usage-recording path). One code path, no per-component branching.
- **UI surface:** the existing per-node status tooltip. The tooltip *container* lives in `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/index.tsx` (the `<ShadTooltip>` at ~line 399), but the tooltip *content* is rendered by `BuildStatusDisplay` in `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx`, where `TokenUsageDisplay` already encapsulates the Input/Output token rows. The new "Estimated cost" row goes inside `TokenUsageDisplay` directly beneath "Output tokens".
- **Pill is unchanged.** It stays `tokens | duration`. Cost is a hover-revealed secondary detail.
- **Hide-on-missing.** When cost cannot be computed (unknown model, cost-tracking disabled, no model recorded), the row is omitted entirely.

## Architecture

### 1. Backend: new precision-preserving pricing method

The existing `PricingService.compute_cost_cents` returns `int` (rounded whole cents) and returns `0` for both unknown models and genuinely-zero cost — those two cases are indistinguishable, which collides with the UI rule "render `<$0.01` for sub-cent positives, `$0.00` only for genuine zero".

Add a sibling method on `src/backend/base/langflow/services/pricing/service.py`:

```python
def compute_cost_micros(
    self, model: str, *, input_tokens: int, output_tokens: int
) -> int | None:
    """Return cost in micro-USD (millionths of a dollar), or None when the model is unknown."""
    price = self.get_price(model)
    if price is None:
        return None
    cents = (
        (input_tokens / 1000.0) * price.input_cents_per_1k
        + (output_tokens / 1000.0) * price.output_cents_per_1k
    )
    return int(round(cents * 10_000))  # 1 cent = 10,000 micros
```

Encoding semantics:

| Returned `cost_micros` | Meaning                            | Tooltip render |
|------------------------|------------------------------------|----------------|
| `None`                 | Unknown model, no pricing data     | row hidden     |
| `0`                    | Genuine zero (no tokens / 0 rate)  | `$0.00`        |
| `1` … `9_999`          | Sub-cent positive                  | `<$0.01`       |
| `≥ 10_000`             | Cost in micros, render as dollars  | `$X.XX`        |

`compute_cost_cents` is **not** modified — the metering service (`src/backend/base/langflow/services/metering/service.py:193-197`) keeps its existing contract.

### 2. Backend: extend the `Usage` schema (LFx)

Edit `src/lfx/src/lfx/schema/properties.py`:

```python
class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    model_name: str | None = None     # NEW — model that produced these tokens
    cost_micros: int | None = None    # NEW — micro-USD; None = unknown / not computed
```

LFx remains pricing-agnostic: these are passthrough fields. The values are stamped by Langflow during `finalize_build`.

### 3. Backend: stash `_model_name` on token-emitting components

Mirror the existing `self._token_usage` convention in `src/lfx/src/lfx/custom/custom_component/component.py`:

```python
self._token_usage: Usage | None = None
self._model_name: str | None = None   # NEW
```

Token-emitting components set this when they resolve their model:

- `src/lfx/src/lfx/components/models_and_agents/agent.py` — `_get_llm()` sets `self._model_name = self.model` after resolving.
- The shared `LanguageModelComponent` and any other component that resolves an LLM does the same. (Concrete file list lives in the implementation plan.)

### 4. Backend: single hook in `Vertex.finalize_build()`

Edit `src/lfx/src/lfx/graph/vertex/base.py:525-543`. After token usage is extracted:

1. Copy `self.custom_component._model_name` onto `usage.model_name`.
2. If `settings.cost_tracking_enabled` is `True` **and** `usage.model_name` is set, call `pricing_service.compute_cost_micros(...)` (passing `input_tokens` and `output_tokens`, defaulting `None` to `0`) and stamp the result on `usage.cost_micros`. Zero-token runs flow through and produce `0`, which is intentional — see the edge-cases table.
3. Otherwise leave `cost_micros = None`.

The PricingService is resolved via the existing DI graph (`get_pricing_service()` in `src/backend/base/langflow/services/deps.py`). It's always registered — no feature flag.

### 5. Backend: gating

Reuse the existing `settings.cost_tracking_enabled` flag — same flag the metering service uses for run-level cost. If a deployment turns off cost tracking for billing/privacy reasons, tooltips also hide cost. No new config knob.

### 6. Frontend: extend `UsageType`

Edit `src/frontend/src/types/chat/index.ts:37-41`:

```ts
export type UsageType = {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  model_name?: string | null;     // NEW
  cost_micros?: number | null;    // NEW
};
```

`VertexDataTypeAPI.token_usage` already references `UsageType` — no separate type needed.

### 7. Frontend: new currency formatter

Add `src/frontend/src/utils/format-currency.ts`:

```ts
export function formatUsdFromMicros(
  micros: number | null | undefined,
): string | null {
  if (micros == null) return null;
  if (micros < 0) return null;            // defensive — negatives shouldn't occur
  if (micros === 0) return "$0.00";
  if (micros < 10_000) return "<$0.01";   // sub-cent positive
  // Round in integer-cent space to avoid IEEE-754 surprises with toFixed(2).
  // (e.g., 0.015.toFixed(2) === "0.01" because 0.015 is stored as 0.01499...)
  const cents = Math.round(micros / 10_000);
  return `$${(cents / 100).toFixed(2)}`;
}
```

Returns `null` to mean "nothing to display"; the caller hides the row.

### 8. Frontend: tooltip row

In `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx`, extend the existing `TokenUsageDisplay` component. After the "Output tokens" row, conditionally render:

```tsx
{formatUsdFromMicros(tokenUsage.cost_micros) != null && (
  <div className="flex items-center">
    <div className="text-xxs">Estimated cost:</div>
    <div className="ml-auto font-mono text-xs">
      {formatUsdFromMicros(tokenUsage.cost_micros)}
    </div>
  </div>
)}
```

Layout/typography matches the surrounding "Input tokens" / "Output tokens" rows — same `text-xxs` label, same `ml-auto font-mono text-xs` value. (No coin icon — the coin is a token-count signifier, not a money signifier; including it for cost would be confusing.)

No pill change. No new components. No new files in the frontend (besides the helper from §7).

## Data flow (end-to-end)

```
Agent component runs LLM
  └─ self._token_usage  ← aggregated Usage from lfx.base.agents.agent
  └─ self._model_name   ← stashed in _get_llm()

Vertex.finalize_build()
  ├─ extract token_usage
  ├─ stamp usage.model_name = component._model_name
  └─ if cost_tracking_enabled and model_name:
        usage.cost_micros = PricingService.compute_cost_micros(model_name, ...)

ResultData(token_usage=usage)
  └─ ResultDataResponse  →  VertexBuildTypeAPI.token_usage  →  UsageType (frontend)

NodeStatus tooltip
  └─ formatUsdFromMicros(token_usage?.cost_micros)
        → render "Estimated cost: $X.XX" / "<$0.01" / "$0.00"
        → or hide row when null
```

## Edge cases

| Case                                                   | Behavior                                           |
|--------------------------------------------------------|----------------------------------------------------|
| Model not in LiteLLM cost map and no override          | `cost_micros = None` → row hidden                  |
| `cost_tracking_enabled = False`                        | Backend skips stamping → row hidden                |
| Component never resolved a model                       | `model_name = None` → no pricing call → row hidden |
| Zero-token run (component ran, no LLM call)            | `cost_micros = 0` → render `$0.00`                 |
| Sub-cent positive (e.g. tiny prompt on a cheap model)  | `cost_micros ∈ [1, 9_999]` → render `<$0.01`       |
| Old run / cached `flowPool` from before this ships     | `cost_micros` absent → row hidden, no migration    |
| Multiple LLM calls within a single agent run           | `Usage` already aggregated upstream → one row      |

## Known limitations (acceptable)

- **Multi-model within one agent.** If an agent uses Claude for planning and a different model for one tool's reasoning, we record only the agent's primary `self.model`. Cost reflects the primary model's rate applied to total tokens — approximate. Real fix is per-call usage attribution; deferred.
- **LiteLLM cost-map staleness.** Provider rate changes can lag LiteLLM. `PRICING_OVERRIDES_JSON` already exists as the escape hatch; we inherit it.

## Out of scope

- Flow-level cost rollup (already exists for billing via the metering service — different surface, not this design).
- Currency switching (USD only — matches the existing pricing service).
- Per-call breakdown in the tooltip (just the aggregate).
- Showing the model name as a separate row in the tooltip (could be added trivially later; not requested).

## Tests

**Backend (pytest):**

1. `compute_cost_micros` unit tests: known model returns `int > 0`; unknown model returns `None`; zero tokens returns `0`; small input that rounds to sub-cent returns `1..9_999`; large input returns expected micros.
2. `Vertex.finalize_build` test: with `cost_tracking_enabled=True` + a known `_model_name` + non-zero tokens, `usage.cost_micros` is populated. With `cost_tracking_enabled=False`, `cost_micros is None`. With unknown model, `cost_micros is None`.

**Frontend (Jest):**

1. `formatUsdFromMicros` unit tests: `null` / `undefined` → `null`; `0` → `"$0.00"`; `1`, `9_999` → `"<$0.01"`; `10_000` → `"$0.01"`; `1_234_567` → `"$1.23"`; negative → `null`.
2. `NodeStatus` tooltip test: row absent when `cost_micros` is null/undefined; row visible with the formatted string when present.

## Files touched (summary)

**Backend (LFx):**
- `src/lfx/src/lfx/schema/properties.py` — extend `Usage`.
- `src/lfx/src/lfx/custom/custom_component/component.py` — add `_model_name` slot.
- `src/lfx/src/lfx/graph/vertex/base.py` — stamp model + cost in `finalize_build`.
- `src/lfx/src/lfx/components/models_and_agents/agent.py` — set `_model_name` in `_get_llm()`.
- Other LLM-resolving components (concrete list determined during plan).

**Backend (Langflow):**
- `src/backend/base/langflow/services/pricing/service.py` — add `compute_cost_micros`.

**Frontend:**
- `src/frontend/src/types/chat/index.ts` — extend `UsageType`.
- `src/frontend/src/utils/format-currency.ts` — new helper.
- `src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/components/build-status-display.tsx` — extend `TokenUsageDisplay` with the cost row.

**Tests:**
- Backend pytest cases under `src/backend/tests/.../pricing/` and `src/lfx/tests/.../graph/vertex/`.
- Frontend Jest cases co-located in `__tests__/` directories next to the touched source files (matches the existing project pattern, e.g. `src/frontend/src/utils/__tests__/format-currency.test.ts`).

## Open follow-ups (not blocking this change)

- Per-call usage attribution for multi-model agents.
- Optional "Model: gpt-4o" row in the tooltip — easy add when desired.
- Flow-canvas total cost overlay (pulls from same data; separate UI surface).
