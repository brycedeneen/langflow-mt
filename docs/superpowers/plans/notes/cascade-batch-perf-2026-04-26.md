# Cascade-delete batching — synthetic perf capture (2026-04-26)

## Method

Wall-clock smoke (per the original Task 6 of the cascade-delete batching
plan) was deferred — it required a running server with a populated dev
Postgres which the CLI can't drive directly. Substitute: a parametrized
unit test that uses a recording fake session to count `session.exec`
invocations for both call shapes across `n_flows ∈ {1, 10, 50, 100}`.

The recording fake returns no rows on the trace SELECT, so the
conditional span DELETE inside `_cascade_delete_flow_chunk` is skipped.
That mirrors the typical production case — most flows are never traced —
giving the documented constant of 7 statements per chunk:

1. `DELETE FROM message       WHERE flow_id IN (...)`
2. `DELETE FROM transaction   WHERE flow_id IN (...)`
3. `DELETE FROM vertex_build  WHERE flow_id IN (...)`
4. `DELETE FROM flow_version  WHERE flow_id IN (...)`
5. `SELECT trace.id FROM trace WHERE flow_id IN (...)` (returns empty)
6. `DELETE FROM trace         WHERE flow_id IN (...)`
7. `DELETE FROM flow          WHERE id      IN (...)`

Test:
`src/backend/tests/unit/api/utils/test_cascade_delete_flows_call_count.py`

Run:

```
uv run pytest \
  src/backend/tests/unit/api/utils/test_cascade_delete_flows_call_count.py \
  -v -s --timeout=60
```

## Results

| n_flows | loop calls | batched calls | round-trip speedup |
|---------|------------|---------------|--------------------|
| 1       | 7          | 7             | 1.0×               |
| 10      | 70         | 7             | 10.0×              |
| 50      | 350        | 7             | 50.0×              |
| 100     | 700        | 7             | 100.0×             |

All four parametrized cases passed in 0.31s. Output captured via `-s`:

```
n_flows=1:   loop=7   batched=7  speedup=1.0x
n_flows=10:  loop=70  batched=7  speedup=10.0x
n_flows=50:  loop=350 batched=7  speedup=50.0x
n_flows=100: loop=700 batched=7  speedup=100.0x
```

The batched call count is invariant in N within a single chunk — exactly
what the plan promised. The legacy loop scales linearly at 7×N.

## Caveats

- This is a round-trip *count*, not wall-clock latency. Per-call latency
  (network RTT + server-side processing) will dominate in practice.
  At ~2 ms RTT to Postgres-over-network the 100-flow case drops from
  ~1.4 s of round-trip time to ~14 ms — the win the plan estimated.
- Traceless flows are the majority case in production. A flow that *does*
  have traces produces 8 calls per chunk (additional span DELETE) — still
  constant per chunk, still O(chunks) overall.
- Chunking at 500 ids means a 1000-flow project takes 14 calls; a
  10 000-flow project takes 140 calls — still O(chunks), not O(N).
- The fake session does not exercise the actual database, so this
  benchmark cannot detect issues that surface only under real query
  planning (e.g. the helper degrading to a seq-scan on `flow_id` if the
  appropriate index is missing on Postgres). See "Future work" below.

## Future work

When a perf-oriented project-deletion benchmark exists against a real
database (Postgres-over-network), capture wall-clock numbers and replace
this synthetic note. The plan's open questions include verifying
`flow_id` indexes on the cascade-relevant child tables — large-batch
DELETEs degrade to seq-scans without those indexes, and the round-trip
win measured here can be silently undone at the DB layer.
