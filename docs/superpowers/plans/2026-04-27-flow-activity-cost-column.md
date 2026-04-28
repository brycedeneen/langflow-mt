# Flow Activity — Cost column & detail tile — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commit gate:** Per `feedback_no_git_commits.md`, pause and ask the user before running `git commit` at each commit step — do NOT auto-commit even when the plan says "commit".

**Goal:** Surface per-trace USD cost on the Flow Activity list and Trace Details panel, computed on read from existing LLM/embedding spans via `PricingService`.

**Architecture:** Pure helper in `services/tracing/formatting.py` turns a list of `(span_type, attributes)` rows into `total_cost_micros: int | None`. The repository invokes it inside the existing span-iteration loop in `fetch_trace_summary_data`. The new value rides through `TraceSummaryData` → `TraceSummaryRead` / `TraceRead` → API → frontend types → column + MetricCard. No DB schema change.

**Tech Stack:** Python (FastAPI, SQLModel, Pydantic), pytest. TypeScript (React, ag-grid-community), Jest. Existing `formatUsdFromMicros` util at `src/frontend/src/utils/format-currency.ts` is reused as the formatter — do **not** create a new one.

**Spec:** `docs/superpowers/specs/2026-04-27-flow-activity-cost-column-design.md`

---

## File touch map

**Backend create:**
- `src/backend/tests/unit/services/tracing/test_compute_trace_cost.py`

**Backend modify:**
- `src/backend/base/langflow/services/tracing/formatting.py` — add `compute_trace_cost_micros` helper; add `total_cost_micros` field to `TraceSummaryData`.
- `src/backend/base/langflow/services/database/models/traces/model.py` — add `total_cost_micros: int | None` to `TraceSummaryRead` and `TraceRead`.
- `src/backend/base/langflow/services/tracing/repository.py` — include `span_type` in span query; invoke the cost helper per trace; pass through `_trace_to_base_fields`.
- `src/backend/tests/unit/services/tracing/test_repository.py` — extend `TraceSummaryData` defaults test for the new field.
- `src/backend/tests/unit/api/v1/test_traces_api.py` — extend `_make_trace_summary` / `_make_trace_read` factories with the new field.

**Frontend modify:**
- `src/frontend/src/controllers/API/queries/traces/types.ts` — replace `totalCost: number` with `totalCostMicros: number | null` on `TraceListItem` and `TraceApiResponse`.
- `src/frontend/src/pages/FlowPage/components/TraceComponent/types.ts` — extend `Span.tokenUsage` with `costMicros?: number | null`.
- `src/frontend/src/pages/FlowPage/components/TraceComponent/config/flowTraceColumns.tsx` — insert Cost column between Token and Latency.
- `src/frontend/src/pages/FlowPage/components/TraceComponent/TraceDetailView.tsx` — populate `costMicros` on the synthetic summary span.
- `src/frontend/src/pages/FlowPage/components/TraceComponent/SpanDetail.tsx` — add Cost MetricCard; widen grid when 5 cards.

**Frontend create:**
- `src/frontend/src/pages/FlowPage/components/TraceComponent/config/__tests__/flowTraceColumns.test.tsx` (only if no existing test file in that folder; otherwise extend).

---

## Task 1: Backend — `compute_trace_cost_micros` pure helper (TDD)

A pure function that takes per-span `(span_type, attributes)` plus a `PricingService` and returns `total_cost_micros: int | None`. Pure-function design lets us test it without a DB.

**Files:**
- Create: `src/backend/tests/unit/services/tracing/test_compute_trace_cost.py`
- Modify: `src/backend/base/langflow/services/tracing/formatting.py`

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/services/tracing/test_compute_trace_cost.py`:

```python
"""Unit tests for compute_trace_cost_micros — the pure cost-aggregation helper
used by the trace repository to populate Flow Activity rows.

Inputs are (span_type_str, attributes_dict) tuples plus a fake PricingService;
no DB or async needed.
"""

from __future__ import annotations

from langflow.services.database.models.traces.model import SpanType
from langflow.services.tracing.formatting import compute_trace_cost_micros


class FakePricing:
    """Stand-in for PricingService.compute_cost_micros.

    Returns None for unknown models, otherwise (input + 2*output) * 100 micros.
    """

    def compute_cost_micros(self, model: str, *, input_tokens: int, output_tokens: int):
        if model == "unknown":
            return None
        return (input_tokens + 2 * output_tokens) * 100


def _row(span_type: str, **attrs):
    return (span_type, attrs)


def test_returns_none_when_no_spans():
    assert compute_trace_cost_micros([], FakePricing()) is None


def test_returns_none_when_no_llm_or_embedding_spans():
    rows = [_row(SpanType.TOOL.value, model_name="gpt-4", prompt_tokens=10)]
    assert compute_trace_cost_micros(rows, FakePricing()) is None


def test_returns_none_when_only_unknown_models():
    rows = [
        _row(SpanType.LLM.value, model_name="unknown", prompt_tokens=10, completion_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) is None


def test_sums_single_llm_span():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
    ]
    # FakePricing: (10 + 2*5) * 100 = 2000
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_sums_multiple_llm_spans_same_model():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=20, completion_tokens=10),
    ]
    # Bucketing per model: (30 + 2*15) * 100 = 6000
    assert compute_trace_cost_micros(rows, FakePricing()) == 6000


def test_sums_across_multiple_models():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
        _row(SpanType.LLM.value, model="claude-3", prompt_tokens=4, completion_tokens=2),
    ]
    # 2000 + (4 + 2*2)*100 = 2000 + 800 = 2800
    assert compute_trace_cost_micros(rows, FakePricing()) == 2800


def test_partial_pricing_returns_priced_only():
    rows = [
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
        _row(SpanType.LLM.value, model_name="unknown", prompt_tokens=999, completion_tokens=999),
    ]
    # Unknown contributes nothing; known returns 2000.
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_includes_embedding_spans():
    rows = [
        _row(SpanType.EMBEDDING.value, model_name="ada-002", input_tokens=100),
    ]
    # (100 + 0) * 100 = 10000
    assert compute_trace_cost_micros(rows, FakePricing()) == 10000


def test_skips_non_llm_non_embedding():
    rows = [
        _row(SpanType.TOOL.value, model_name="gpt-4", prompt_tokens=999),
        _row(SpanType.LLM.value, model_name="gpt-4", prompt_tokens=10, completion_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000


def test_skips_spans_with_no_model_attribute():
    rows = [
        _row(SpanType.LLM.value, prompt_tokens=10, completion_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) is None


def test_accepts_alternate_attribute_keys():
    """LiteLLM/legacy emitters use input_tokens/output_tokens instead of
    prompt_tokens/completion_tokens. Both must work — same fallback behavior
    as compute_cost_for_run."""
    rows = [
        _row(SpanType.LLM.value, model="gpt-4", input_tokens=10, output_tokens=5),
    ]
    assert compute_trace_cost_micros(rows, FakePricing()) == 2000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/backend && uv run pytest tests/unit/services/tracing/test_compute_trace_cost.py -v`
Expected: ImportError — `compute_trace_cost_micros` not yet defined.

- [ ] **Step 3: Implement the helper**

Append to `src/backend/base/langflow/services/tracing/formatting.py` (place after `compute_leaf_token_total`):

```python
def compute_trace_cost_micros(
    rows: list[tuple[str, dict[str, Any]]],
    pricing: Any,
) -> int | None:
    """Sum cost in micro-USD across LLM/embedding spans for a single trace.

    Mirrors the bucketing in `services/cost/compute.py::compute_cost_for_run`
    but returns micros instead of cents so the UI can render sub-cent values.

    Args:
        rows: Iterable of ``(span_type, attributes)`` tuples for the spans
            in one trace. ``span_type`` is the string value (e.g. ``"llm"``).
        pricing: Object with ``compute_cost_micros(model, *, input_tokens,
            output_tokens) -> int | None`` — typically ``PricingService``.

    Returns:
        Total cost in micro-USD, or ``None`` when no priced LLM/embedding
        span produced a number (zero spans, all unknown models, or no model
        attribute present).
    """
    cost_span_types = {SpanType.LLM.value, SpanType.EMBEDDING.value}

    per_model: dict[str, dict[str, int]] = {}
    for span_type, attrs in rows:
        if span_type not in cost_span_types:
            continue
        if not attrs:
            continue
        model = str(attrs.get("model_name") or attrs.get("model") or "").strip()
        if not model:
            continue
        prompt = int(attrs.get("prompt_tokens") or attrs.get("input_tokens") or 0)
        completion = int(attrs.get("completion_tokens") or attrs.get("output_tokens") or 0)
        bucket = per_model.setdefault(model, {"input_tokens": 0, "output_tokens": 0})
        bucket["input_tokens"] += prompt
        bucket["output_tokens"] += completion

    if not per_model:
        return None

    total: int | None = None
    for model, bucket in per_model.items():
        priced = pricing.compute_cost_micros(
            model, input_tokens=bucket["input_tokens"], output_tokens=bucket["output_tokens"]
        )
        if priced is None:
            continue
        total = (total or 0) + priced
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/backend && uv run pytest tests/unit/services/tracing/test_compute_trace_cost.py -v`
Expected: 10 PASSED.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/services/tracing/formatting.py src/backend/tests/unit/services/tracing/test_compute_trace_cost.py
git commit -m "feat(tracing): add compute_trace_cost_micros helper"
```

---

## Task 2: Backend — Add `total_cost_micros` to `TraceSummaryData` and Pydantic models

**Files:**
- Modify: `src/backend/base/langflow/services/tracing/formatting.py`
- Modify: `src/backend/base/langflow/services/database/models/traces/model.py`
- Modify: `src/backend/tests/unit/services/tracing/test_repository.py`

- [ ] **Step 1: Extend `TraceSummaryData`**

In `src/backend/base/langflow/services/tracing/formatting.py`, edit the dataclass:

```python
@dataclass
class TraceSummaryData:
    """Aggregated per-trace data fetched in a single span query.
    ... (existing docstring) ...
    Attributes:
        total_tokens: Sum of tokens from leaf spans only (avoids double-counting).
        input: Simplified input payload derived from the "Chat Input" span.
        output: Simplified output payload derived from the last root span.
        total_cost_micros: Total cost in micro-USD across LLM/embedding spans,
            or None when no priced span produced a number.
    """

    total_tokens: int = 0
    input: dict[str, Any] | None = field(default=None)
    output: dict[str, Any] | None = field(default=None)
    total_cost_micros: int | None = None
```

- [ ] **Step 2: Extend `TraceSummaryRead` and `TraceRead`**

In `src/backend/base/langflow/services/database/models/traces/model.py`:

For `TraceRead` (after `total_tokens: int`):

```python
    total_cost_micros: int | None = None
```

For `TraceSummaryRead` (after `total_tokens: int`):

```python
    total_cost_micros: int | None = None
```

- [ ] **Step 3: Add a defaults test for the new field**

In `src/backend/tests/unit/services/tracing/test_repository.py`, inside `class TestTraceSummaryData`, add:

```python
    def test_should_have_none_total_cost_micros_by_default(self):
        data = TraceSummaryData()
        assert data.total_cost_micros is None

    def test_should_accept_explicit_total_cost_micros(self):
        data = TraceSummaryData(total_cost_micros=2500)
        assert data.total_cost_micros == 2500
```

- [ ] **Step 4: Run tests**

Run: `cd src/backend && uv run pytest tests/unit/services/tracing/test_repository.py -v`
Expected: all existing tests still PASS plus the 2 new ones PASS.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/services/tracing/formatting.py src/backend/base/langflow/services/database/models/traces/model.py src/backend/tests/unit/services/tracing/test_repository.py
git commit -m "feat(tracing): add total_cost_micros field to trace summary/read models"
```

---

## Task 3: Backend — Wire cost into `fetch_trace_summary_data` and `fetch_single_trace`

**Files:**
- Modify: `src/backend/base/langflow/services/tracing/repository.py`

The existing span query already loads `attributes`. We add `span_type` to the select, then call `compute_trace_cost_micros` per trace. Pricing is fetched via `get_pricing_service()` once per call.

- [ ] **Step 1: Update `_trace_to_base_fields` to pass through cost**

In `src/backend/base/langflow/services/tracing/repository.py`, edit the function (currently at lines 43-76):

```python
def _trace_to_base_fields(
    trace: TraceTable,
    total_tokens: int,
    summary: TraceSummaryData | None,
) -> dict:
    """Build the shared field mapping common to both TraceSummaryRead and TraceRead.
    ... (keep existing docstring) ...
    """
    return {
        "id": trace.id,
        "name": trace.name,
        "status": trace.status or SpanStatus.UNSET,
        "start_time": trace.start_time,
        "total_latency_ms": trace.total_latency_ms,
        "total_tokens": total_tokens,
        "total_cost_micros": summary.total_cost_micros if summary else None,
        "flow_id": trace.flow_id,
        "session_id": trace.session_id or str(trace.id),
        "input": summary.input if summary else None,
        "output": summary.output if summary else None,
    }
```

- [ ] **Step 2: Add `span_type` to the span select and wire helper into `fetch_trace_summary_data`**

In the same file, edit `fetch_trace_summary_data` (currently lines 79-131):

```python
async def fetch_trace_summary_data(session: AsyncSession, trace_ids: list[UUID]) -> dict[str, TraceSummaryData]:
    """Fetch aggregated token totals, cost, and I/O summaries for a batch of traces.
    ... (existing docstring; add a sentence noting cost is computed via compute_trace_cost_micros) ...
    """
    summary_map: dict[str, TraceSummaryData] = {}
    if not trace_ids:
        return summary_map

    all_spans_stmt = select(
        col(SpanTable.trace_id),
        col(SpanTable.id),
        col(SpanTable.name),
        col(SpanTable.parent_span_id),
        col(SpanTable.end_time),
        col(SpanTable.inputs),
        col(SpanTable.outputs),
        col(SpanTable.attributes),
        col(SpanTable.span_type),
    ).where(col(SpanTable.trace_id).in_(trace_ids))
    rows = (await session.exec(all_spans_stmt)).all()

    parent_ids = {row[3] for row in rows if row[3] is not None}

    rows_by_trace: dict[str, list[Any]] = {}
    for row in rows:
        rows_by_trace.setdefault(str(row[0]), []).append(row)

    pricing = get_pricing_service()

    for trace_id_str, trace_rows in rows_by_trace.items():
        span_ids = [row[1] for row in trace_rows]
        attributes_by_id = {row[1]: (row[7] or {}) for row in trace_rows}
        total_tokens = compute_leaf_token_total(span_ids, parent_ids, attributes_by_id)

        io_rows = [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in trace_rows]
        io_data = extract_trace_io_from_rows(io_rows)

        cost_rows = [(_span_type_value(r[8]), r[7] or {}) for r in trace_rows]
        total_cost_micros = compute_trace_cost_micros(cost_rows, pricing)

        summary_map[trace_id_str] = TraceSummaryData(
            total_tokens=total_tokens,
            input=io_data.get("input"),
            output=io_data.get("output"),
            total_cost_micros=total_cost_micros,
        )

    return summary_map
```

Add the small helper near the top of the file (just below `_trace_to_base_fields`):

```python
def _span_type_value(span_type: Any) -> str:
    """SQLAlchemy may return either an Enum instance or a raw string for span_type."""
    return span_type.value if hasattr(span_type, "value") else str(span_type or "")
```

Update imports at the top of the file:

```python
from langflow.services.deps import get_pricing_service, session_scope
from langflow.services.tracing.formatting import (
    TraceSummaryData,
    build_span_tree,
    compute_leaf_token_total,
    compute_trace_cost_micros,
    extract_trace_io_from_rows,
    extract_trace_io_from_spans,
)
```

- [ ] **Step 3: Wire cost into `fetch_single_trace`**

In the same file, edit `fetch_single_trace` (currently around lines 218-257). After the existing `compute_leaf_token_total` call:

```python
        parent_ids = {s.parent_span_id for s in spans if s.parent_span_id}
        span_ids = [s.id for s in spans]
        attributes_by_id = {s.id: (s.attributes or {}) for s in spans}
        computed_tokens = compute_leaf_token_total(span_ids, parent_ids, attributes_by_id)

        effective_tokens = computed_tokens or trace.total_tokens

        pricing = get_pricing_service()
        cost_rows = [(_span_type_value(getattr(s, "span_type", None)), s.attributes or {}) for s in spans]
        total_cost_micros = compute_trace_cost_micros(cost_rows, pricing)

        # Build a lightweight summary so _trace_to_base_fields can supply io_data.
        io_summary = TraceSummaryData(
            total_tokens=effective_tokens,
            input=io_data.get("input"),
            output=io_data.get("output"),
            total_cost_micros=total_cost_micros,
        )

        return TraceRead(
            **_trace_to_base_fields(trace, effective_tokens, io_summary),
            end_time=trace.end_time,
            spans=span_tree,
        )
```

- [ ] **Step 4: Run the existing repository test to confirm nothing regressed**

Run: `cd src/backend && uv run pytest tests/unit/services/tracing/test_repository.py -v`
Expected: all tests PASS (we didn't change anything they assert on).

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/services/tracing/repository.py
git commit -m "feat(tracing): compute total_cost_micros for trace list and detail"
```

---

## Task 4: Backend — Update `test_traces_api.py` factory + add an assertion

**Files:**
- Modify: `src/backend/tests/unit/api/v1/test_traces_api.py`

This file uses helper factories `_make_trace_summary` and `_make_trace_read` that build Pydantic instances; the new field is optional with a default of `None`, so existing tests pass without changes. Add one targeted test that asserts the new field is round-tripped through the endpoint.

- [ ] **Step 1: Read the existing factories**

```bash
grep -n "_make_trace_summary\|_make_trace_read" src/backend/tests/unit/api/v1/test_traces_api.py | head -10
```

- [ ] **Step 2: Add a happy-path test that exercises `total_cost_micros`**

Add this test alongside the other `get_traces` tests (search for `def test_get_traces_happy_path` to find the section). New test (drop into the same class/section, exact placement is fine after any existing happy-path test):

```python
def test_get_traces_returns_total_cost_micros(self, client):
    """Cost should be serialized as camelCase ``totalCostMicros`` in the response."""
    summary = _make_trace_summary(total_cost_micros=12345)

    async def _fetch(*_args, **_kwargs):
        return TraceListResponse(traces=[summary], total=1, pages=1)

    with patch("langflow.api.v1.traces.fetch_traces", side_effect=_fetch):
        response = client.get(f"/monitor/traces?flowId={_FAKE_FLOW_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["traces"][0]["totalCostMicros"] == 12345
```

If `_make_trace_summary` doesn't yet accept `total_cost_micros` via `**kwargs` overrides, look at its body — it most likely just merges defaults with `kwargs`. If it filters keys, add `total_cost_micros` to its defaults dict (`"total_cost_micros": None`) so the kwarg passes through.

- [ ] **Step 3: Run the API test**

Run: `cd src/backend && uv run pytest tests/unit/api/v1/test_traces_api.py -v`
Expected: all tests PASS, including the new one.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git add src/backend/tests/unit/api/v1/test_traces_api.py
git commit -m "test(api): assert total_cost_micros surfaces in /monitor/traces response"
```

---

## Task 5: Frontend — Update API types

**Files:**
- Modify: `src/frontend/src/controllers/API/queries/traces/types.ts`
- Modify: `src/frontend/src/pages/FlowPage/components/TraceComponent/types.ts`

Replace the unused `totalCost: number` with `totalCostMicros: number | null` (matches the API).

- [ ] **Step 1: Edit `controllers/API/queries/traces/types.ts`**

```typescript
export interface TraceListItem {
  id: string;
  name: string;
  status: Span["status"];
  startTime: string;
  endTime?: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCostMicros: number | null;
  flowId: string;
  sessionId?: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
}
```

```typescript
export interface TraceApiResponse {
  id: string;
  name: string;
  status: string;
  startTime: string;
  endTime?: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCostMicros: number | null;
  flowId: string;
  sessionId: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  spans: SpanApiResponse[];
}
```

- [ ] **Step 2: Add `costMicros` to `Span.tokenUsage`**

Open `src/frontend/src/pages/FlowPage/components/TraceComponent/types.ts` and find the `Span` interface (or the `tokenUsage` type). Add a `costMicros?: number | null` field on the same shape that already has `cost: number`. Show full file path + line:

```bash
grep -n "tokenUsage\|cost" src/frontend/src/pages/FlowPage/components/TraceComponent/types.ts
```

In the `tokenUsage` shape (whichever interface declares it), insert:

```typescript
  costMicros?: number | null;
```

Leave the existing `cost: number` field alone — out of scope to remove.

- [ ] **Step 3: Run frontend type-check**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: PASS. Other call sites that read `totalCost` will FAIL — this is expected because we're renaming. There should be very few; the only meaningful one is `TraceDetailView.tsx:46` which Task 7 fixes. If there are other consumers, fix them now (they almost certainly are dead reads since the field was never populated).

```bash
grep -rn "totalCost\b" src/frontend/src --include="*.ts" --include="*.tsx"
```

For each match: if it's a read of `trace.totalCost`, either delete the dead read or change it to use `totalCostMicros` (depending on context). Note `TraceDetailView.tsx` will be addressed in Task 7 — leave it for now if it's the only remaining failure.

- [ ] **Step 4: Run TypeScript check again**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | head -40`
Expected: 0 errors, OR only errors localized to `TraceDetailView.tsx` (deferred to Task 7).

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/frontend/src/controllers/API/queries/traces/types.ts src/frontend/src/pages/FlowPage/components/TraceComponent/types.ts
git commit -m "refactor(types): switch trace cost field to totalCostMicros"
```

---

## Task 6: Frontend — Cost column on Flow Activity table

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/TraceComponent/config/flowTraceColumns.tsx`

Reuse the existing `formatUsdFromMicros` from `src/frontend/src/utils/format-currency.ts`. Render `null` (and `undefined`) as an em dash.

- [ ] **Step 1: Add the import**

At the top of `flowTraceColumns.tsx`:

```typescript
import { formatUsdFromMicros } from "@/utils/format-currency";
```

- [ ] **Step 2: Insert the Cost column between Token and Latency**

In the array returned by `createFlowTracesColumns`, between the `Token` column object (currently around lines 69-84) and the `Latency` column object (currently around lines 85-100), insert:

```typescript
    {
      headerName: "Cost",
      field: "totalCostMicros",
      flex: 0.5,
      minWidth: 80,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: (params) => {
        const micros = pickFirstNumber(
          params.data?.totalCostMicros,
          params.data?.total_cost_micros,
        );
        return formatUsdFromMicros(micros) ?? "—";
      },
    },
```

(`pickFirstNumber` is the existing helper used by the Token and Latency columns; it returns the first numeric value or `null`. If both are nullish, `formatUsdFromMicros(null)` returns `null`, and the `?? "—"` falls through to em dash.)

- [ ] **Step 3: Smoke-test in the browser**

Run the dev server (`cd src/frontend && npm run start` if not already running). Open a flow with at least one agent run. Verify the Flow Activity table now shows a **Cost** column between Token and Latency:

- Agent run with priced model → `$X.XX`.
- Run with no LLM/embedding spans (e.g., the `cf4170e0-…` row in the screenshot, output starts `"connection":"ADPConnection"`) → `—`.
- Compute small to verify sub-cent → `<$0.01`.

Report what you see — if any state isn't reachable in dev data, note it; do NOT block on it.

- [ ] **Step 4: Run frontend tests**

Run: `cd src/frontend && npx jest --testPathPattern="flowTraceColumns" 2>&1 | tail -30`

If a test file exists, ensure it still passes. If none exists for `flowTraceColumns`, that's fine — column logic is mostly type-driven and the existing `formatUsdFromMicros` tests cover the formatter. Skip.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/frontend/src/pages/FlowPage/components/TraceComponent/config/flowTraceColumns.tsx
git commit -m "feat(flow-activity): add Cost column"
```

---

## Task 7: Frontend — Cost MetricCard tile in Trace Details

**Files:**
- Modify: `src/frontend/src/pages/FlowPage/components/TraceComponent/TraceDetailView.tsx`
- Modify: `src/frontend/src/pages/FlowPage/components/TraceComponent/SpanDetail.tsx`

Add a 5th MetricCard "Cost" on the summary span. Per-span cost is out of scope.

- [ ] **Step 1: Pass cost through the synthetic summary span**

In `TraceDetailView.tsx`, edit the `summarySpan` builder (currently around lines 30-50). Replace the line `cost: trace.totalCost` with `costMicros: trace.totalCostMicros` (and leave the rest of `tokenUsage` alone). Also drop or repurpose the legacy `cost` field — since we changed its type, just remove it. The block:

```typescript
      tokenUsage:
        trace.totalTokens > 0 || trace.totalCostMicros !== null
          ? {
              promptTokens: 0,
              completionTokens: 0,
              totalTokens: trace.totalTokens,
              cost: 0,
              costMicros: trace.totalCostMicros,
            }
          : undefined,
```

We keep `cost: 0` because the existing `tokenUsage.cost` field is required by other consumers (e.g., the legacy "Estimated Cost" row). Setting it to 0 keeps that branch dormant; the new MetricCard reads from `costMicros`.

The trigger condition widens (`|| trace.totalCostMicros !== null`) so cost-bearing traces with zero `totalTokens` (rare) still surface a tokenUsage object carrying cost.

- [ ] **Step 2: Add Cost MetricCard in `SpanDetail.tsx`**

In `SpanDetail.tsx`, near the top of the function body (around line 37), add:

```typescript
  const hasCost =
    span?.tokenUsage?.costMicros !== undefined &&
    span?.tokenUsage?.costMicros !== null;
```

Then update the metrics-row JSX (lines 89-126). Widen the grid when cost is present:

```jsx
        <div
          className={`mb-4 grid grid-cols-2 gap-4 ${
            hasCost ? "sm:grid-cols-5" : "sm:grid-cols-4"
          }`}
        >
          <MetricCard
            label="Latency"
            value={formatTotalLatency(span.latencyMs)}
            icon="Clock"
          />
          {(hasTokenUsage || isLlmSpan) && (
            <>
              <MetricCard
                label="Tokens"
                value={
                  hasTokenUsage
                    ? span.tokenUsage!.totalTokens.toLocaleString()
                    : "—"
                }
                icon="Coins"
              />
              <MetricCard
                label="Prompt"
                value={
                  hasTokenUsage
                    ? span.tokenUsage!.promptTokens.toLocaleString()
                    : "—"
                }
                icon="ArrowUp"
              />
              <MetricCard
                label="Completion"
                value={
                  hasTokenUsage
                    ? span.tokenUsage!.completionTokens.toLocaleString()
                    : "—"
                }
                icon="ArrowDown"
              />
            </>
          )}
          {hasCost && (
            <MetricCard
              label="Cost"
              value={
                formatUsdFromMicros(span.tokenUsage!.costMicros) ?? "—"
              }
              icon="DollarSign"
            />
          )}
        </div>
```

Add the import at the top of the file:

```typescript
import { formatUsdFromMicros } from "@/utils/format-currency";
```

The legacy "Estimated Cost" row (currently lines 129-136) stays untouched. It's gated on `tokenUsage.cost > 0`, and we set `cost: 0` on the summary span, so it remains dormant. (Out of scope to delete.)

- [ ] **Step 3: TypeScript check**

Run: `cd src/frontend && npx tsc --noEmit 2>&1 | head -40`
Expected: 0 errors.

- [ ] **Step 4: Smoke-test in the browser**

Open a flow with an agent run, click the row to open Trace Details. Verify the **Cost** tile renders alongside Latency / Tokens / Prompt / Completion (5 tiles, sm:grid-cols-5). Pick a non-LLM run → no Cost tile, grid stays at 4 cols. Pick a tool span inside the agent → no Cost tile.

Report what you see — note any rendering glitches.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/frontend/src/pages/FlowPage/components/TraceComponent/TraceDetailView.tsx src/frontend/src/pages/FlowPage/components/TraceComponent/SpanDetail.tsx
git commit -m "feat(flow-activity): show Cost tile on trace details"
```

---

## Verification (after Task 7)

- [ ] **Backend tests:** `cd src/backend && uv run pytest tests/unit/services/tracing tests/unit/api/v1/test_traces_api.py -v`
- [ ] **Frontend type-check:** `cd src/frontend && npx tsc --noEmit`
- [ ] **Manual UI:** Flow Activity row shows Cost column with `$X.XX` / `<$0.01` / `$0.00` / `—` cases reachable. Trace Details panel shows 5 MetricCards on the summary span when cost is present.
- [ ] **No DB schema drift:** `git diff main -- src/backend/base/langflow/alembic` should be empty.

## Self-review notes

- **Spec coverage** — every requirement in the design has a task: pure helper (Task 1), data class field (Task 2), API contract (Tasks 2, 3, 4), frontend types (Task 5), list column (Task 6), detail tile (Task 7).
- **No placeholders** — all code blocks are concrete; no "implement appropriately" steps.
- **Type consistency** — backend uses `total_cost_micros: int | None`; serialized as camelCase `totalCostMicros: number | null`; frontend `Span.tokenUsage.costMicros: number | null` (with `?` because not all spans carry it).
- **Reuse over creation** — `formatUsdFromMicros` already exists with the exact semantics. Do NOT add a new formatter.
