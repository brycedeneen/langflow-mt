# Metering, Pluggable Notifier, and Alerting — Design

**Roadmap items covered:** P0-4 (metering + warning thresholds + pluggable notifier), P0-6 (alerting on failed runs / SLA breaches)
**Roadmap source:** `2026-04-22-integration-platform-roadmap.md`
**Scope:** Bundled because alerting reuses the metering notifier and the same run-completion hook.

## Background

The fork already has most of the primitives we need:

- **`FlowRun`** (`services/database/models/flow_run/model.py`) — rows per run with `organization_id`, `status`, `queued_at/started_at/finished_at`, `inputs`, `result`, `error`, triggered-by source.
- **Worker completion hook** (`worker_app/execute.py:~171`) — after the terminal-status commit, all variables we need (`run`, `org_id_captured`, timings, status) are in scope.
- **`TraceTable`/`SpanTable`** (`services/database/models/traces/model.py`) — `total_tokens` per trace. Not linked to org directly; traverse `trace.flow_id → flow.organization_id`.
- **Multi-tenant deps** — `CurrentOrg` (`api/utils/org_helpers.py`) and `PlatformAdmin` (`api/utils/core.py`).

What's missing:
- No in-app notification surface at all.
- No usage counters at the org grain.
- No alert rules.

## Goals

1. **Metering:** per-org counters for runs, run-seconds, and LLM tokens. Daily grain, cheap to read, cheap to write.
2. **Warning thresholds:** soft limits only. Crossing a threshold fires a notification. No hard stops, no rate limiting.
3. **Pluggable notifier:** one dispatch seam; v1 ships in-app notifications for super admins; future implementations (email, webhook, Slack, external API) plug in without changing threshold or alerting code.
4. **Alerting:** run-outcome rules (consecutive failures, error rate, per-run SLA duration) reusing the same notifier.
5. **Surfaced UI:** super-admin bell in the header, notification center page, usage & alert-rules settings per org.

## Non-goals (v1)

- Hard stops / quota enforcement.
- Bytes-transferred metric — no reliable source; captured as a P1 follow-up.
- Per-user metering.
- Billing / invoicing integration.
- Cost rollups (owned by Design 4 — observability & cost).
- Non-super-admin audiences for notifications. (Model supports it; only one audience value is used in v1.)
- P95 / rolling-window alert rules — per-run SLA rule covers the common case; P95 deferred.

## Architecture

```
  ┌───────────────────┐
  │ Worker completes  │  (execute.py ~171, post-commit)
  │ a FlowRun         │
  └─────────┬─────────┘
            │
            ▼
  ┌──────────────────────────────┐
  │ record_run_completion_and_   │  new service function
  │ eval(session, run, ...)      │
  └─────────┬────────────────────┘
            │
   ┌────────┼─────────────────┬──────────────────┐
   ▼        ▼                 ▼                  ▼
Increment  Sum tokens from    Threshold check     Alert-rule eval
OrgUsage   TraceTable via     (OrgUsageThreshold) (AlertRule) — per
Daily      flow_id →          — per crossed       fired rule
(runs,     flow.org_id        threshold
seconds)
            │                 │                  │
            └─────────────────┴──────────┬───────┘
                                         ▼
                              ┌──────────────────────┐
                              │ UsageAlertDispatcher │  pluggable notifier layer
                              │  .dispatch(event)    │
                              └─────────┬────────────┘
                                        │
                     ┌──────────────────┼──────────────────┐
                     ▼                  ▼                  ▼
              InAppNotifier       EmailNotifier      WebhookNotifier
              (v1 — ships)        (future)           (future)
                     │
                     ▼
             AdminNotification table
                     │
                     ▼
             Super-admin bell + notification center (FE)
```

## Data model

Four new tables, one alembic migration.

### `OrgUsageDaily`

Single write-through source of truth for threshold checks and dashboard reads. Daily grain keeps rows small and charts trivial.

| Column | Type | Notes |
|--------|------|-------|
| `org_id` | UUID FK | PK part 1 |
| `date` | DATE | PK part 2, UTC |
| `runs` | BIGINT | count of terminal runs that day |
| `run_seconds` | BIGINT | sum of `finished_at - started_at` for terminal runs |
| `tokens` | BIGINT | sum of `total_tokens` for traces attributed to that day's runs |
| `updated_at` | TIMESTAMPTZ | for cache-busting dashboards |

Index: `(org_id, date DESC)` primary key covers the common read pattern.

### `OrgUsageThreshold`

Per-org soft limits. Multi-rule per org supported. Super-admin managed.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `org_id` | UUID FK |  |
| `metric` | ENUM | `runs` \| `run_seconds` \| `tokens` |
| `period` | ENUM | `daily` \| `monthly` |
| `threshold_value` | BIGINT |  |
| `is_active` | BOOL | default true |
| `last_fired_at` | TIMESTAMPTZ | null when never fired |
| `cooldown_seconds` | INT | default 3600 (1 hr) |
| `created_by_user_id` | UUID FK | super admin who created it |
| `created_at`, `updated_at` | TIMESTAMPTZ |  |

Index: `(org_id, is_active)`.

### `AlertRule`

Run-outcome rules. Separate from thresholds because evaluation logic differs.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `org_id` | UUID FK |  |
| `flow_id` | UUID FK nullable | null = org-wide |
| `rule_type` | ENUM | `consecutive_failures` \| `error_rate` \| `sla_duration` |
| `config` | JSONB | rule-specific (see below) |
| `is_active` | BOOL | default true |
| `last_fired_at` | TIMESTAMPTZ | null when never fired |
| `cooldown_seconds` | INT | default 900 (15 min) |
| `created_by_user_id` | UUID FK |  |
| `created_at`, `updated_at` | TIMESTAMPTZ |  |

Indexes: `(org_id, flow_id, is_active)`, `(org_id, is_active)`.

**Rule `config` shapes:**
- `consecutive_failures`: `{"n": 5}`
- `error_rate`: `{"window_minutes": 60, "min_samples": 10, "rate_pct": 20}`
- `sla_duration`: `{"max_seconds": 120}`

### `AdminNotification`

In-app notification sink.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `org_id` | UUID FK nullable | null = system-wide |
| `category` | ENUM | `usage_threshold` \| `alert_rule` \| `system` |
| `severity` | ENUM | `info` \| `warning` \| `critical` |
| `title` | TEXT |  |
| `body_md` | TEXT | short markdown body |
| `metadata` | JSONB | e.g., `{"threshold_id": "...", "metric": "tokens", "crossed_value": 12345}` |
| `audience` | ENUM | `super_admin` (v1 only value) |
| `created_at` | TIMESTAMPTZ |  |
| `read_at` | TIMESTAMPTZ nullable |  |
| `read_by_user_id` | UUID FK nullable |  |

Indexes: `(audience, read_at, created_at DESC)` for the unread-count / feed query.

## Pluggable notifier

### Protocol

```python
class UsageAlertNotifier(Protocol):
    async def notify(self, event: UsageAlertEvent) -> None: ...
```

### Event shape

```python
@dataclass
class UsageAlertEvent:
    category: Literal["usage_threshold", "alert_rule"]
    severity: Literal["info", "warning", "critical"]
    org_id: UUID
    title: str
    body_md: str
    metadata: dict[str, Any]  # threshold_id / rule_id / metric / crossed_value / etc.
```

### Dispatcher

```python
class UsageAlertDispatcher:
    def __init__(self, notifiers: list[UsageAlertNotifier]): ...
    async def dispatch(self, event: UsageAlertEvent) -> None:
        # fan-out; one notifier raising does NOT cancel the others; errors are logged.
```

### Factory / registration

Same pattern as the existing Vault secret-store factory:

```python
def build_usage_alert_dispatcher(settings) -> UsageAlertDispatcher:
    notifiers: list[UsageAlertNotifier] = [InAppNotifier(...)]
    # Future: if settings.USAGE_ALERT_EMAIL_ENABLED: notifiers.append(EmailNotifier(...))
    return UsageAlertDispatcher(notifiers)
```

Registered once at app startup; injected via service container so tests can swap it out.

### v1 implementation — `InAppNotifier`

Writes a row into `AdminNotification` with `audience = super_admin`. That's it.

## Run-completion hook

### Placement

`worker_app/execute.py` already has a clean post-commit block around line 171 (after terminal status + `finished_at` are committed). We add a single call there:

```python
await record_run_completion_and_eval(session, run, dispatcher)
```

### What the service function does

1. **Increment `OrgUsageDaily`** (upsert) — `runs += 1`, `run_seconds += duration`. Date = UTC date of `finished_at`.
2. **Sum tokens** — `SELECT SUM(total_tokens) FROM traces WHERE flow_id = :flow_id AND run_reference = :run_id` (or whatever links traces to a run; confirm during implementation). If non-zero, add to `OrgUsageDaily.tokens`. Gracefully skip if tracing disabled / no rows.
3. **Evaluate thresholds** — load active `OrgUsageThreshold`s for the org. For each, compute current-period sum (day: just read the row; month: sum over date range). If the **newly committed** sum has crossed the threshold (previous sum < threshold ≤ new sum) AND cooldown has elapsed, stamp `last_fired_at` and emit a `UsageAlertEvent`.
4. **Evaluate alert rules** — load active `AlertRule`s where `flow_id IS NULL OR flow_id = :flow_id`. Per `rule_type`:
   - `consecutive_failures`: query last N runs for that flow; if all failed AND this run failed AND cooldown elapsed → fire.
   - `error_rate`: query last `window_minutes` runs for that flow; if sample size ≥ `min_samples` AND failure rate ≥ `rate_pct` AND cooldown elapsed → fire.
   - `sla_duration`: if this run's duration > `max_seconds` AND cooldown elapsed → fire.
   Stamp `last_fired_at` on firing rules and emit events.
5. **Dispatch** all events via the injected `UsageAlertDispatcher`.

All SQL executed on the existing session; one commit at the end.

### Concurrency / race safety

Two workers finishing runs for the same org at the same instant could both read "not crossed" and then both cross, firing twice. To prevent this:
- Use `SELECT ... FOR UPDATE` on the `OrgUsageThreshold` row during eval. Row-level lock on Postgres; serializes threshold check per threshold.
- Stamp `last_fired_at` inside the locked transaction.

Similarly for `AlertRule.last_fired_at`.

### Expected latency

Synchronous, against local Postgres:

| Step | Cost |
|---|---|
| `OrgUsageDaily` upsert | 2–5 ms |
| Sum tokens from traces (indexed on `flow_id`) | 5–10 ms |
| Threshold load + eval (0–5 rules typical) | 2–5 ms |
| Alert-rule load + eval (0–5 rules typical) | 3–10 ms |
| Notifier dispatch (usually 0 firings) | 0–5 ms |

- **Baseline** (org has no rules configured): ~5–15 ms
- **Typical** (3 thresholds + 3 alert rules, 0–1 firings): **~20–40 ms p95**
- **Worst case** (10 rules, several firings, network DB): ~50–80 ms

This adds to worker throughput cost but not to perceived run duration (run is already committed). At 100 short runs/min/worker, 30ms × 100 = 3s extra serial work/minute — survivable.

**Fallback (not built in v1):** enqueue a separate arq job for metering; worker returns immediately. Switch if profiling shows it matters.

## API surface

All endpoints require `PlatformAdmin` unless otherwise noted.

### Metering + thresholds
- `GET /api/v1/admin/orgs/:org_id/usage` — current-period counters + last-30-days sparkline data.
- `GET /api/v1/admin/orgs/:org_id/usage/thresholds` — list.
- `POST /api/v1/admin/orgs/:org_id/usage/thresholds` — create.
- `PATCH /api/v1/admin/usage/thresholds/:id` — update (toggle active, change value).
- `DELETE /api/v1/admin/usage/thresholds/:id` — delete.

### Alert rules
- `GET /api/v1/admin/orgs/:org_id/alert-rules` — list.
- `POST /api/v1/admin/orgs/:org_id/alert-rules` — create.
- `PATCH /api/v1/admin/alert-rules/:id` — update.
- `DELETE /api/v1/admin/alert-rules/:id` — delete.

### Notifications
- `GET /api/v1/admin/notifications?unread=true&limit=20` — paged feed.
- `GET /api/v1/admin/notifications/unread-count` — for the bell badge.
- `POST /api/v1/admin/notifications/:id/read` — mark read.
- `POST /api/v1/admin/notifications/mark-all-read` — bulk.

## Front-end

- **Super-admin bell** in main header, only rendered when `is_platform_admin`. Badge count polls `unread-count` every 30s (or listens to SSE — stretch). Dropdown shows last 10 with relative timestamps; "View all" links to notification center.
- **Notification center** `/admin/notifications` — filterable table (category, severity, unread).
- **Org usage page** `/admin/orgs/:id/usage` — current-period counters cards, 30-day daily bar chart, thresholds list with create/edit/toggle.
- **Alert rules tab** on the same page — list per rule type with create/edit/toggle.

## Settings / rollout

- `ENABLE_METERING` setting (default true) wraps the run-completion hook. Flip off if a regression leaks into prod.
- One alembic migration creates all four tables.
- Backfill `OrgUsageDaily` from `FlowRun` + traces for the last 90 days as a one-time script, run manually post-deploy. Documented in the plan, not automated.

## Testing

- **Unit:** each service function (`record_run_completion_and_eval`, threshold evaluator, rule evaluator, dispatcher) with fake notifiers. No DB.
- **DB integration:** one test per rule type end-to-end — seed runs, call the hook, assert `OrgUsageDaily` and `AdminNotification` rows.
- **Concurrency:** seed one threshold, fire two concurrent `record_run_completion_and_eval` calls, assert exactly one notification row.
- **Cooldown:** fire once, fire again inside cooldown — assert second doesn't write a notification.
- **FE:** jest unit for bell badge (count from hook), notification center paging, thresholds create/toggle flow.

## Risks

- **Token attribution hole.** If tracing is disabled or incomplete for a run, that run's tokens are 0. Documented; acceptable v1 behavior.
- **Evaluator coupling.** Every run pays eval cost. Budgeted above; profile in plan.
- **Race on threshold-crossing.** Mitigated by row-level lock on `OrgUsageThreshold`.
- **Notification spam.** Mitigated by per-rule cooldown. Default 1hr for thresholds, 15min for alert rules.
- **Dispatcher failure blast.** If one notifier raises, others must still fire. Enforced by dispatcher impl (log + continue).

## Open questions

- Exact column linking a trace to a specific run — confirm during implementation (likely `session_id` on `TraceTable`). If no reliable link exists, token attribution falls back to "sum all traces for the flow on the same day" — less precise but still useful.
- Whether to expose usage visibility to org admins (viewer-only) as a P1 follow-up. Not in v1.
