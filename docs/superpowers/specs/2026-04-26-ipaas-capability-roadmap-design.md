# iPaaS Capability Roadmap (post-scheduler) — Design

**Status:** Roadmap. Each initiative below is a placeholder for its own future spec → plan cycle. This document is a sequencing artifact, not an implementation plan.

**Audience:** Personal use — anchors what to build next and why, in what order.

## Context

Langflow on `platform-multi-tenant` is a strong AI workflow builder with broad connector reach (~150+ via native + Composio), solid transformation/flow-control primitives, and the multi-tenant + secret-store + metering + audit foundations already shipped. The 2026-04-25 gap analysis identified five subsystems that distinguish a serious iPaaS from a flow runner: scheduling, reliability primitives, trigger surface, enterprise connector depth, and bulk/data-movement patterns.

Scheduling is **out of scope** — handled externally. The remaining four are the scope of this roadmap.

## Sequencing summary

| Tier | Initiative | Why this tier |
|------|-----------|---------------|
| 1 | Reliability primitives | Foundational. Every connector and trigger benefits. Other initiatives compose with these. |
| 2 | Trigger surface (non-scheduler) | Webhook signature validation unlocks Stripe/GitHub/Slack patterns used by Tier 3. |
| 3 | Enterprise connector pack | Volume work, parallelizable across connectors once OAuth broker exists. Best with Tier 1 + Tier 2 primitives in place. |
| 4 | Bulk / data-movement patterns | Depends on cursor primitives (T2), idempotency (T1), and connector-specific bulk paths (T3). |

Tiers 2 and 3 can overlap — webhook signature work in T2 is small and independent of polling/file-watch within T2. Tier 4 should not start until T1 is at least at the retry + idempotency stage.

## Initiative 1: Reliability primitives

### Scope
- Native retry-with-backoff component (configurable attempts, base delay, jitter, exponential)
- Try/Catch component pair — wrap any node, route errors to a separate branch
- Fallback router — if A fails, route to B
- Circuit breaker — open after N failures, half-open after cooldown
- Dead-letter sink — failed payloads land in a structured store with replay UI
- Idempotency key helper — generates/checks deterministic keys against a store to suppress duplicate runs
- Rate-limit / token-bucket node — throttles outbound calls per-org or per-API-target

### Key components / surfaces
- `lfx/components/reliability/retry.py` — wraps a downstream tool/component, runs with backoff
- `lfx/components/reliability/try_catch.py` — pair node, exposes `result` and `error` outputs
- `lfx/components/reliability/fallback.py` — A→B routing primitive
- `lfx/components/reliability/circuit_breaker.py` — stateful, needs per-org store
- `lfx/components/reliability/idempotency.py` — needs store backend (Redis via existing arq infra)
- `lfx/components/reliability/rate_limit.py` — token bucket on the same Redis
- `services/dead_letter/` — new service, schema for stored failures, retention policy, replay endpoint
- API: `GET /api/v1/dead-letter`, `POST /api/v1/dead-letter/{id}/replay`
- UI: minimal DLQ list + replay button (defer fancy filtering/search)

### Dependencies
- Already shipped: arq + Redis (idempotency, rate-limit, circuit-breaker state); audit log (replay attribution); metering (rate-limit observability)
- No blocking deps on other initiatives in this roadmap

### Size
**L** — 7 new components + a new service + UI surface. Roughly 4 specs: (1) retry / try-catch / fallback as a batch, (2) circuit-breaker + idempotency + rate-limit on Redis, (3) DLQ service + API, (4) DLQ UI.

### Deferred
- Saga / compensating-transaction orchestration — revisit after retry + idempotency are bedded in
- Per-tenant rate-limit policies via UI — start with config-only, add UI later
- Sophisticated DLQ filtering / search — start with list + replay, iterate

## Initiative 2: Trigger surface (non-scheduler)

### Scope
- Cursor primitive — durable per-flow cursor state for delta polling (paired with the external scheduler tick)
- Email-arrived trigger — IMAP poll variant + Gmail push receiver variant
- File-watch / object-storage triggers — S3 event receiver, GCS event receiver, SFTP poll
- Webhook signature validation — generic HMAC verifier + provider-specific shims (Stripe, GitHub, Slack, GitLab)

Note on scope shape: with scheduling external, "polling trigger" decomposes into a cursor primitive + a source-fetch component fired by the external tick. The roadmap focuses on those primitives, not the scheduler itself.

### Key components / surfaces
- `lfx/components/triggers/cursor.py` — get/set per-flow cursor state
- New table: `flow_cursor (flow_id, org_id, key, value, updated_at)` + alembic migration
- `lfx/components/triggers/webhook_hmac.py` — generic HMAC verifier (header name, algorithm, secret source)
- `lfx/components/triggers/webhook_stripe.py`, `webhook_github.py`, `webhook_slack.py`, `webhook_gitlab.py` — provider shims over the generic verifier
- `lfx/components/triggers/s3_event.py` — receives S3 ObjectCreated webhook payloads
- `lfx/components/triggers/gcs_event.py` — equivalent for GCS Pub/Sub push
- `lfx/components/triggers/sftp_poll.py` — list + cursor-aware fetch
- `lfx/components/triggers/email_imap.py` — IMAP poll fetch
- `lfx/components/triggers/gmail_push.py` — Gmail push notification receiver

### Dependencies
- Already shipped: per-flow webhook API key auth (`secret-store-webhook-auth`), Vault secret store
- Reliability primitives (T1): polling failure handling benefits from retry/DLQ; not blocking
- External scheduler: assumed available, out of scope

### Size
**M** — 11 components + cursor state schema/migration. Roughly 3 specs: (1) generic HMAC verifier + provider shims (Stripe/GitHub/Slack/GitLab), (2) cursor primitive + IMAP poll + SFTP poll, (3) push receivers (S3 / GCS / Gmail).

### Deferred
- Native scheduler component (out of scope per user)
- Webhook delivery replay UI (covered by audit log + DLQ replay from T1)
- Drift / schema-change detection on polled sources — start with cursor-only deltas
- Outlook / Exchange email push (start with Gmail-push + IMAP fallback)

## Initiative 3: Enterprise connector pack

### Scope
- CRM: Salesforce (REST + Bulk), HubSpot
- Comms: Twilio (SMS / voice / WhatsApp), Microsoft Teams
- Ticketing: ServiceNow, Zendesk
- HR (non-ADP): Workday
- Finance / payments: Stripe (full component set, not just webhook receiver)
- Databases: a unified DB pack with MySQL, Oracle, and SQL Server dialects

Each connector pack ships a minimal first cut: auth + the 5–8 most common operations. Bulk variants are tracked under T4.

### Key components / surfaces
- `lfx/components/salesforce/` — auth, soql_query, create, update, delete (Bulk variants → T4)
- `lfx/components/hubspot/` — auth, contacts/companies/deals CRUD, list, search
- `lfx/components/twilio/` — auth, send_sms, send_whatsapp, make_call, tts
- `lfx/components/teams/` — auth (Graph API), send_message, list_channels, post_card
- `lfx/components/servicenow/` — auth, table_query, table_insert, table_update, incident_create
- `lfx/components/zendesk/` — auth, ticket_create, ticket_update, search, comment
- `lfx/components/workday/` — auth, get_worker, list_workers, time_off, hr_event
- `lfx/components/stripe/` — auth, charge_create, customer_create, refund, subscription
- `lfx/components/databases/{mysql,oracle,sqlserver}/` — query, execute, schema_inspect, bulk_insert
- `services/oauth_broker/` — generic OAuth 2.0 broker, provider registrations, callback at `/oauth/{provider}/callback`, token persistence in Vault, refresh logic

The OAuth broker is the most important shared piece. Without it every connector duplicates auth boilerplate. ADP currently has its own bespoke flow; the broker generalizes that pattern.

### Dependencies
- Reliability primitives (T1): every connector composes with retry / circuit-breaker / DLQ
- Webhook signature validation (T2): pairs with Stripe webhook events, GitHub events, etc.
- Already shipped: Vault secret store, multi-tenant scoping, `CrossOrgFKError` validator, audit log

### Size
**XL** — 9 connector packs (8 SaaS + 1 DB pack with 3 dialects) × ~5–8 components + OAuth broker ≈ 50–75 new components. Roughly 10 specs: 1 for the OAuth broker, 8 for individual SaaS connectors, 1 for the DB pack. Highly parallelizable once the broker exists; each SaaS connector is independent.

### Deferred
- Long-tail connectors (Pipedrive, Monday, Asana-native) — keep relying on Composio
- Per-connector advanced features (Salesforce CDC, Workday EIB, Stripe Connect platform accounts) — start with synchronous APIs
- OAuth consent UI polish — start with the functional flow, iterate
- Connector-specific bulk paths (Salesforce Bulk API, etc.) — tracked in T4

## Initiative 4: Bulk / data-movement patterns

### Scope
- CDC primitives — Postgres logical decoding, Debezium consumer pattern for shops already running Kafka
- Batch primitives — generic split/collect over DataFrames, plus connector-specific bulk paths
- Streaming / windowed aggregation — tumbling / sliding / session windows, dedupe-over-window, simple aggregators (sum/count/avg)

### Key components / surfaces
- `lfx/components/cdc/postgres_logical.py` — replication slot consumer, emits changes
- `lfx/components/cdc/debezium_consumer.py` — Kafka consumer for existing Debezium pipelines
- `lfx/components/batch/bulk_split.py` — split DataFrame into N chunks for parallel downstream calls
- `lfx/components/batch/bulk_collect.py` — collect chunked results back into one DataFrame
- `lfx/components/salesforce/bulk_query.py`, `bulk_load.py` — Salesforce Bulk API
- `lfx/components/databases/{mysql,postgres}/copy.py` — COPY-protocol bulk paths
- `lfx/components/storage/s3_multipart.py` — S3 multipart upload primitive
- `lfx/components/streaming/window.py` — windowed aggregation primitive (tumbling/sliding/session)
- `lfx/components/streaming/dedupe.py` — dedupe over a window
- `lfx/components/streaming/aggregator.py` — sum/count/avg over window

### Dependencies
- Reliability primitives (T1): idempotency is essential for CDC; retry for bulk APIs
- Triggers (T2): CDC behaves as a trigger; reuses cursor primitive
- Connector pack (T3): bulk variants pair with each connector's base set

### Size
**L** — 9–11 components depending on CDC source coverage. Roughly 4 specs: (1) batch split/collect primitives, (2) connector-specific bulk paths (paired with their connector specs in T3), (3) Postgres CDC + Debezium consumer, (4) streaming/windowed primitives.

### Deferred
- Full native Kafka connector (use Debezium consumer pattern instead initially)
- Stateful stream processing (delegate to external Flink / Spark)
- Materialized view / continuous query semantics
- MySQL binlog and SQL Server CDC (start with Postgres logical, extend later)

## Cross-cutting concerns

- **OAuth broker** — central to T3, must be designed once and reused. Don't let any T3 connector spec ship its own auth shim.
- **State store layering** — Vault for secrets (already in place), Redis for ephemeral state (rate-limits, circuit-breaker, idempotency keys), new Postgres tables for durable state (cursors, DLQ entries, OAuth tokens). Each new initiative must pick the right layer; don't store secrets in Postgres or durable cursors in Redis.
- **Observability hooks** — every new component plumbs into existing metering counters and audit log. Bake in from the start; retrofitting is painful.
- **Multi-tenant scoping** — every new persisted table needs `org_id`; every cross-org reference uses the existing `CrossOrgFKError` validator pattern (introduced 2026-04-22 user-detail Phase 6). No exceptions.
- **Component versioning** — every new component goes through the version-bump + changelog ritual surfaced by the Update components modal (`langflow-component-authoring` skill enforces this).

## Deferred (out of this roadmap)

- Native scheduling — handled externally per user
- Saga / compensating-transaction orchestration — revisit once retry + idempotency are mature
- Stateful stream processing engines — out of platform scope, delegate to Flink/Spark
- Long-tail connector breadth — keep relying on Composio
- Visual debugger / step-through execution
- iPaaS-style "integration templates gallery" — existing template management already covers this surface
- Watsonx full removal — separate initiative tracked elsewhere

## Sequencing notes (recap)

Build T1 first to a usable subset (retry + try-catch + DLQ at minimum) before starting T3 work, so connectors can compose with reliability primitives from day one rather than being retrofit. Webhook signature validation (the small piece of T2) can run in parallel with early T1 work — it's independent. Polling primitives in T2 can wait until T1's idempotency is shipped, since most polling sources need dedupe. T4 starts last; it's the smallest forcing function and gains the most from T1+T2+T3 already existing.
