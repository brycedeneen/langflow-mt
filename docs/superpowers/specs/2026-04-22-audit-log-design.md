# Audit Log — Design

**Roadmap item:** P0-3 (audit log of user actions on flows/templates/secrets/orgs/memberships/roles/API keys)
**Roadmap source:** `2026-04-22-integration-platform-roadmap.md`

## Background

Nothing exists today — no AuditLog / ActivityLog / History / Changelog infrastructure in the fork. Build from scratch.

Relevant existing primitives we'll reuse:

- `PlatformAdmin = Annotated[User, Depends(require_platform_admin)]` in `src/backend/base/langflow/api/utils/core.py`.
- Service container pattern — `VariableServiceFactory` (`src/backend/base/langflow/services/variable/factory.py`) is the cleanest model to copy for `AuditServiceFactory`.
- SQLAlchemy session events on the main app session.
- `FlowVersion` exists but is created on **explicit** versioning only, not every save. That affects the Flow-`data` diff strategy (see below).

## Goals

- Append-only audit record for every user-initiated **create / update / delete / archive** on:
  - `Flow`
  - `Template`
  - `Variable`
  - `Organization`
  - `Membership`
  - `ApiKey`
  - Membership role assignment (own action type)
- Capture: actor (user), org scope, target, action, per-field before/after diff, request metadata.
- Super-admin read API + admin UI with filter/paging.

## Non-goals (v1)

- OIDC/SAML integration.
- SOC 2-grade compliance export formats.
- Reads (GET) of audited entities — not logged.
- System/worker writes (run-completion updates, backfills, migrations) — excluded by design.
- Per-entity "Activity" tab UI — P1.
- Org-admin read access — P1 (super-admin only in v1).
- Tamper-evident signing / hash-chaining of audit rows — acceptable P2 if compliance ever demands.

## Architecture

**Approach A: SQLAlchemy `after_commit` listener + request-context middleware (contextvar).**

```
  ┌──────────────────────┐
  │ HTTP request arrives │
  └─────────┬────────────┘
            │
            ▼
  ┌────────────────────────────────┐
  │ AuditContextMiddleware         │  new middleware
  │  - sets contextvar:            │
  │     user, ip, ua, request_id,  │
  │     path, method, is_super     │
  └─────────┬──────────────────────┘
            │
            ▼
  ┌────────────────────────────────┐
  │ Endpoint handler writes via    │
  │ SQLAlchemy session             │
  └─────────┬──────────────────────┘
            │ session.commit()
            ▼
  ┌────────────────────────────────────┐
  │ SQLAlchemy after_commit listener   │
  │  - walks session.new/dirty/deleted │
  │  - filters to 7 audited mappers    │
  │  - reads contextvar;               │
  │    if None → skip (system write)   │
  │  - assembles diff                  │
  │  - calls AuditService.record()     │
  │    (fresh session; errors logged)  │
  └────────────────────────────────────┘
```

**Why A:**
- Impossible to miss an endpoint. New CRUD routes for audited types log automatically.
- System/worker writes naturally excluded (contextvar is None outside an HTTP request).
- Zero changes to existing endpoint handlers.

**Considered and rejected:**
- **B: Explicit service calls per endpoint** — reliable but miss-prone across 6 modules and any future additions.
- **C: Endpoint decorator** — brittle; handlers return responses in varying shapes, before/after capture is hard.

## Data model

Single `AuditLog` table, append-only.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `occurred_at` | TIMESTAMPTZ | wall clock of commit |
| `actor_user_id` | UUID FK User nullable | null only for system writes (shouldn't occur in v1 since we skip those) |
| `actor_email` | TEXT | denormalized — user may be deleted later |
| `actor_is_super` | BOOL | denormalized |
| `org_id` | UUID FK Organization nullable | null for platform-scope actions |
| `target_type` | ENUM | `flow` \| `template` \| `variable` \| `organization` \| `membership` \| `api_key` \| `role_assignment` |
| `target_id` | UUID | |
| `action` | ENUM | `create` \| `update` \| `delete` \| `archive` \| `unarchive` \| `assign_role` |
| `diff` | JSONB | see below |
| `diff_hash` | TEXT | SHA-256 of canonical-JSON diff |
| `request_metadata` | JSONB | `{ip, user_agent, request_id, path, method}` |
| `created_at` | TIMESTAMPTZ | row insert time |

**Indexes:**
- `(org_id, occurred_at DESC)` — per-org feed (common).
- `(actor_user_id, occurred_at DESC)` — "what did user X do."
- `(target_type, target_id, occurred_at DESC)` — "history of this entity."

### Diff shape

| Action | Diff |
|---|---|
| `create` | `{"after": {...serialized entity, secrets redacted...}}` |
| `update` | `{"changed": {"<field>": {"before": ..., "after": ...}, ...}}` — per-field delta only |
| `delete` | `{"before": {...serialized entity, secrets redacted...}}` |
| `archive`/`unarchive` | `{"archived": true|false}` |
| `assign_role` | `{"role": {"before": "member", "after": "admin"}}` |

### Field-level handling

- **Variable `value`** (Fernet-encrypted secret): always replaced with `"<redacted>"` in both `before` and `after`. Never write ciphertext to audit rows — useless without the key and noisy.
- **Flow `data`** (graph JSON): can be large. Since `FlowVersion` is not auto-created on every save, we can't point to a version. Strategy:
  - In the `update` diff, store `{"data": {"before_hash": "<sha256>", "after_hash": "<sha256>"}}` instead of full before/after.
  - On `create` / `delete`, include the serialized `data` only if the entity's total serialized size stays under the 64KB cap (see below); otherwise emit `{"data_hash": "<sha256>"}`.
- **Template `data`**: same hash-only strategy as Flow for large fields.
- **Template scope changes** (org-scoped → shared, etc.): bundled into the standard `update` action — the changed `scope` field appears in the `changed` block of the diff.

### Size guard

- Cap total `diff` at **64KB** per row. Oversized payloads get truncated to `{"truncated": true, "original_bytes": N, "summary": {...first-N-changed-fields...}}`.

## Request-context middleware

```python
audit_ctx: ContextVar[AuditContext | None] = ContextVar("audit_ctx", default=None)

class AuditContextMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send); return
        token = audit_ctx.set(AuditContext.from_scope(scope))  # user populated after auth runs
        try:
            await self.app(scope, receive, send)
        finally:
            audit_ctx.reset(token)
```

Captured fields:
- `user_id`, `user_email`, `is_platform_admin`
- `org_id` — read from `X-Acting-Org-Id` header (super-admin impersonation) or the user's membership default.
- `request_id` — generated UUID, also emitted as a response header for debug correlation.
- `ip` — from `request.client.host`. Documented: **not proxy-aware in v1** — behind a reverse proxy, the `ip` field will be the proxy's. Trust-proxy-headers is a follow-up config item.
- `user_agent`, `path`, `method`.

## SQLAlchemy listener

Registered on the app's main `Session`. Fires on `after_commit`:

1. If `audit_ctx.get() is None` → return (system write, worker write, migration).
2. Walk `session.new`, `session.dirty`, `session.deleted`.
3. Filter to the 7 audited mapper classes (registry dict: `{FlowModel: "flow", ...}`).
4. For each `dirty` instance, use SQLAlchemy attribute history to compute the changed-field delta. Excluded fields: `updated_at`, `id`, plus per-type redaction rules (Variable `value`, Flow/Template `data` hash-only).
5. Build `AuditLogEntry` objects; call `AuditService.record_batch(...)`.
6. `AuditService.record_batch` opens a **fresh session** (not the request session) and inserts the rows. Errors are logged + a Prometheus counter `audit_write_failures_total` increments; they do **not** roll back the user's action.

### Why a fresh session

If we wrote to the request session we'd have two bad options: (a) tie the audit insert to the user action's commit — any audit-insert failure rolls back the user's save; (b) commit after the user's action — fires another `after_commit`, recursive. Fresh session sidesteps both.

## Archive / unarchive

- `Template.archive` / `unarchive` endpoints emit `archive` / `unarchive` action rows. The listener recognizes these via explicit hint from the service (see next) or via a change in a dedicated `archived_at`/`archived` field.
- Flows don't have archive in v1 — still mapped through `delete` when that happens.

**Hint mechanism:** for actions that aren't obvious from dirty fields alone (archive vs. generic update), the endpoint handler calls a tiny helper: `audit_hint.set_action("archive")` — recorded into a request-scoped dict the listener reads when building the entry. Defaults to inferred action (`create`/`update`/`delete`).

## Service

Register `AuditService` in the service container:

```python
# services/audit/service.py
class AuditService(Service):
    async def record_batch(self, entries: list[AuditLogEntry]) -> None: ...
    async def query(self, filters: AuditLogFilter, *, page, size) -> AuditLogPage: ...

# services/audit/factory.py
class AuditServiceFactory(ServiceFactory):
    def __init__(self): super().__init__(AuditService)
    def create(self, database_service: DatabaseService): return AuditService(database_service)
```

Add `AUDIT_SERVICE = "audit_service"` to `ServiceType`, register in `services/manager.py`, expose via `services/deps.py`.

## API surface

All endpoints require `PlatformAdmin`.

- `GET /api/v1/admin/audit-logs` — paged, filterable by:
  - `org_id`, `actor_user_id`, `target_type`, `target_id`, `action`, `from`, `to`.
- `GET /api/v1/admin/audit-logs/:id` — single entry detail (full diff + metadata).

## Front-end

- `/admin/audit-logs` page:
  - Filter bar: actor autocomplete, target-type select, action select, date range picker, org select.
  - Columns: `time`, `actor (email)`, `org`, `target type + id`, `action`, `summary` ("3 fields changed" / "archived" / "created").
  - Row click → right-side drawer with full diff (pretty-printed JSON tree) + request metadata.
  - Server-side sort `occurred_at DESC`, page size 50.

## Retention

- **Default: 90 days.** Configurable via `AUDIT_LOG_RETENTION_DAYS` env var. Set to `0` or unset-with-null to keep indefinitely.
- Nightly arq scheduled task deletes rows older than the cutoff. Logs how many rows were deleted.
- Document this in the admin help: "Older than 90 days is purged. Configure via env var."

## Settings

- `AUDIT_LOG_RETENTION_DAYS` — int, default `90`.
- `AUDIT_LOG_ENABLED` — bool, default `true`. Kill switch in case a regression makes audit writes noisy or expensive in prod.

## Migration / rollout

- One alembic migration creates `audit_log` table + enums + indexes.
- No backfill — audit starts empty and fills forward from deploy.

## Testing

- **Unit:** diff builder over synthetic before/after dicts (including redaction + hash-only cases); size-cap truncation; `AuditService.record_batch` with fake session.
- **Integration:** for each of the 7 target types, perform create/update/delete/archive via the real HTTP API, assert the audit row has the right actor, target, action, and diff shape. Includes a negative test: a worker-initiated write on a `Flow` produces **no** audit row.
- **Concurrency:** two parallel updates to the same flow produce two audit rows, neither lost.
- **Retention cleanup:** seed rows older than cutoff, run the sweep task, assert the right rows are deleted.
- **FE:** Jest for filter interactions, paging, drawer rendering.

## Risks

- **Listener overhead** — every commit that touches an audited type pays the listener cost. Budget <5ms per commit for the diff pass; benchmark during plan phase. Mitigated by fast mapper-class filter and short-circuit when contextvar is None.
- **Audit-write failure silently masks activity** — if `AuditService.record_batch` fails, user action still succeeds but isn't logged. Prometheus counter + structured log keep this visible. Alerting on it is deferred to Design 3's alert rules (future: `audit_write_failures` system alert).
- **Proxy IP** — `ip` field is not trust-forwarded in v1. Document the caveat; treat `ip` as advisory until we add proxy-header handling.
- **Recursive commit risk** — addressed by writing audit rows on a fresh session.
- **Large-field diff growth** — mitigated by 64KB cap + hash-only strategy for Flow/Template `data`.

## Open questions (resolve during plan)

- Exact enum discrimination for Template archive: does the model carry `archived_at` (timestamped) or a boolean `is_archived`? Determines whether the listener infers `archive` or whether endpoints must pass the explicit hint.
- Which of `Variable`'s fields besides `value` are sensitive? If there's a `secret_ref` pointing at Vault, that's safe to show. Confirm during the plan.
- Role-assignment row emission — does membership-role-change go through a dedicated endpoint, or via a PATCH on membership? Affects whether we infer `assign_role` via `role`-field change or via explicit hint.
