# Integration Platform Roadmap

**Source:** `Integration-Platform-PRD-Validation.docx` (2026-04-22)
**Branch:** `platform-multi-tenant` (effective main)
**Baseline:** 456-commit divergence from `langflow-ai/langflow main`

This is the working roadmap derived from the PRD validation doc. Every item from the PRD
and the "additional requirements" section is captured somewhere below. Priorities reflect
what we've chosen to ship for the current ADP-scoped release, what we're deferring, and
what we've decided not to build at all.

## Legend

| Tag | Meaning |
|-----|---------|
| **P0** | Must ship — actively scheduled |
| **P1** | Important — next after P0 lands |
| **P2** | Future / captured backlog — revisit later |
| **🔁 External** | We won't build it; an external tool / manual project handles it |
| **❌ Won't do** | Explicit "no" — do not reopen without a specific ask |
| **✅ Shipped** | Already in the fork |

---

## 1. P0 — Must ship

Ordered roughly by build dependency and value.

### P0-1. Restrict "Code" button on components to super admins
- **Why:** Prevents tenant users from opening the Python custom-component editor; aligns with the "no custom components allowed" posture.
- **Scope:** Hide/disable the Code toggle in component headers for any user whose role is not super admin. Backend enforcement: reject custom component updates from non-super-admin users even if the UI is bypassed.
- **Touches:** Component header UI, flow editor permission checks, any endpoint that accepts raw component Python code.

### P0-2. Remove Share → Embed link from the UI
- **Why:** Chat-widget embed is not supported in our deployment model and a broader embed story is a separate future project.
- **Scope:** Remove the "Embed" option from the Share menu and any routes/components that render the iframe snippet. Leave backend embed endpoints untouched if they exist upstream — just no UI affordance.

### P0-3. Audit log of user actions
- **Why:** Operational forensics ("who changed this template?"), incident response, customer trust. Independent of SOC 2 / SSO — those stay deferred.
- **Scope:** Append-only audit records for create/update/delete/archive on flows, templates, secrets (variables), organizations, memberships, roles, API keys. Include actor, org, target, action, timestamp, and a diff or before/after hash. Admin UI to browse and filter.
- **Out of scope (explicitly):** OIDC/SAML integration, SOC 2-grade compliance export formats.

### P0-4. Metering & usage accounting (with warning thresholds)
- **Why:** Per-org visibility into runs, minutes, and tokens; foundation for future billing/quotas if we ever want them.
- **Scope:**
  - Usage counters per org: runs executed, run-minutes, LLM tokens, data transferred.
  - Configurable **warning thresholds** per org (soft limits only — **no hard stops**).
  - When a threshold is crossed, trigger an **in-app notification to super admins** (v1).
  - Notification dispatch must be **pluggable**: class/function hook that v1 fulfills with in-app, and future implementations can extend to email, external APIs, Slack, etc.
- **Out of scope:** Hard rate-limiting, tenant tiering, billing integration.

### P0-5. Run history dashboard (per org)
- **Why:** Must-have for clients. Operators and admins need to see what ran and how it performed.
- **Scope:** Per-org view with success rate, duration p50/p95, error trends over time, per-flow breakdown, filter by time window + flow + trigger type.

### P0-6. Alerting on failed runs / SLA breaches
- **Why:** Must-have for clients. Closes the loop on the dashboard.
- **Scope:** Configurable per-flow or per-org alert rules (e.g., "notify on N consecutive failures", "notify when p95 duration exceeds X"). Reuses the pluggable notifier from P0-4.

### P0-7. Per-flow cost visibility
- **Why:** Must-have for clients. Answers "what is this flow costing us?"
- **Scope:** Aggregate LLM token spend + (optional) compute per flow per run, rolled up per flow over selectable windows. Displayed on the flow detail page and on the run history dashboard.

### P0-8. Pre-run cost estimator for AI/agent flows
- **Why:** Clients asked for a "what will one run cost?" number before they execute an AI-heavy flow.
- **Scope:** Detect agent / LLM / embedding components in a flow, estimate per-run cost based on configured models + typical token footprint + known provider pricing. Show on the flow builder before a run and optionally on the templates/browse view.
- **Nuance:** Estimator should degrade gracefully when models are unknown — show a range or an "unable to estimate" state rather than silently hiding cost.

---

## 2. P1 — Important, next after P0

Grouped by theme. These aren't on the current sprint but are the obvious next set.

### Assistant / agentic UX
- **Manage-side conversational monitoring** — "why did yesterday's ADP sync fail?" Extends the assistant over run logs.
- **Change explanations** — when the assistant edits a live flow, surface a short "here's what I changed and why" card before apply.

### Scale & reliability
- **Resource caps per flow run** — memory/CPU ceilings beyond arq wall-time.
- **API-tier autoscaling documentation** — HPA manifest + docs for the FastAPI tier.
- **Worker autoscaling** — KEDA on queue depth.
- **Read replicas / connection pool tuning docs** — operational guide, not new code.
- **Large-payload streaming hardening** — extend the existing payload-offload helper to streaming paths that still load in memory.
- **Structured error taxonomy completion** — transient vs permanent, retryable vs fatal; surfaces in dashboard + alerting.
- **Backup & restore per tenant** — tied to the "backup flows in DB" decision; needs an actual restore path.

### Triggers & integration mechanics
- **Idempotency keys on trigger delivery** — replay safety for webhook + event-bus retries.
- **DLQ replay UI** — `delivery_state` already tracks permanently-failed deliveries; this is just the UI on top.
- **Event-bus triggers** — Kafka / SQS / Pub/Sub / EventBridge consumers (pairs with the connectors below).

### Security
- **PII redaction in logs / traces** — avoids leaking customer data into observability stack.

### Governance / steering
- **Org-level AI policy** — "this org can't use model X", "Anthropic only", etc.
- **Per-flow guardrails** — input validation + output schema enforcement per flow.
- **Prompt injection / redaction policies** — steered by component/flow metadata.
- **Tagging / labeling for flows and templates** — powers search, filter, and cost-center attribution on the dashboard.
- **Metadata taxonomy extension** — add the org-level policy layer on top of the existing component/template metadata.

### Connectors
- **SCIM formatter connector** — outgoing: transform data to SCIM format and POST to an API. Used for user/group provisioning; common customer ask. (The full SCIM-as-provider + SSO story is a separate future manual project.)
- **OAuth 2.0 framework** — shared reusable OAuth2 connector scaffold. Currently only ADP has OAuth.
- **Message queue connectors** — Kafka / SQS / Pub/Sub outbound + inbound, pairs with event-bus triggers above.
- ~~**Validate upstream coverage** — confirm status of Postgres/MySQL/Snowflake/BigQuery, S3/GCS/Azure Blob, Email/SMTP/IMAP, Slack/Teams notifications.~~ ✅ **Done (2026-04-23)** — results reflected in §7 below. Follow-ups surfaced: native SMTP/IMAP, native Slack sender, and MySQL/Snowflake convenience components tagged **P1.5** (ship if a customer asks); GCS/Azure Blob and Teams kept **P2**.

### Developer experience
- **OpenAPI / typed SDKs** — FastAPI generates OpenAPI; no typed client SDK exists. Useful for host-app integration even without the full embed story.

---

## 3. P2 — Future / captured backlog

Everything here is "eventually, maybe." Not scheduled. Listed so nothing from the PRD disappears.

### Deferred because we chose a different approach
- **Flow environment promotion (dev → staging → prod with config overrides).** Not needed for current clients. Revisit when we onboard a regulated customer.
- **Flow-level diff / history / rollback UI.** Pairs with promotion. DB backups cover disaster recovery today.
- **CI hooks (test flow on PR, deploy on merge).**
- **Approval workflows / gates** — non-tech proposes, tech reviews, promotes to prod. Bridges req 2 ↔ req 3.

### Embedding (deprioritized — will be its own project)
- **Builder embed into host UIs (APIC, Partners, etc.)** — marked as priority but deferred because it's a big project with details still being scoped. Includes:
  - Scoped tokens for embedded sessions (user X → org Y, flow Z only)
  - PostMessage API for host ↔ embed events (open flow, save, run-complete)
  - Auth passthrough design (will likely converge with the SSO/OIDC work below)
- **Headless mode / API-only.**

### Security / compliance (deferred, manual when needed)
- **GSO / OIDC / SAML** — future manual project; company-specific details.
- **SCIM-as-provider (Langflow as SCIM target for user provisioning).** Full Microsoft/Entra integration stays with the same project.
- **Microsoft connectors (Graph, Entra, Teams, SharePoint).**
- **Tenant encryption keys (BYOK / CMK).**
- **Session management** — forced logout, concurrent session limits.
- **SOC 2-style audit export formats.** Pulled out of P0-3; build only if a compliance push arrives.

### Metering / billing extensions
- **Billing / chargeback hooks** — integration points for finance systems. Blocked on "do we ever bill?" decision.

### Non-tech assistant polish
- **Natural-language test assertion authoring** — "assert output has ≥1 row."
- **Guided onboarding / first-flow wizard** beyond the templates modal.

### Agent + deterministic polish
- **Hybrid pattern formalization** — agent-calls-DataMapper contract.
- **Mapping test harness** — fixture inputs → expected outputs for regression safety.

### Observability extras
- **Load test harness** — baseline RPS / throughput per deploy.
- **Data lineage** — which flows touched which data per tenant. Traces exist but aren't lineage-shaped.
- **Blue/green or canary deploys for flows.**
- **Feature flags per org.**
- **Connection pooling for reused API credentials.**

### Templates polish
- **Template marketplace / ratings / usage counts.**
- **Template testing requirement** — ship fixture inputs with each template.

### Metadata extras
- **Metadata-driven cost controls** — "flows tagged `expensive` require approval." Blocked on approval workflows.

### Components
- **Component discovery automation** — replace manual `__init__.py` registration.
- **Component testing framework** / harness DSL.
- **Component deprecation pipeline** — warn → migrate → remove.

### Dev / ops
- **Terraform / IaC provider** — manage orgs + flows as code.
- **CLI for flow CRUD** — complete the partial `langflow` CLI.
- **Sandbox / test org isolated from production.**

### Connectors (future)
- **Salesforce / HubSpot / Workday** — common HR / CRM targets.
- **Slack / Teams notifications polish** — upstream partial, harden or replace.

### Low-priority items I'm adding to the list (capture now, address later)
These weren't in the PRD but are adjacent concerns we should track:
- **Global API rate-limit** — basic DDoS protection, distinct from per-org quotas (which we're not doing).
- **Webhook body-hash deduplication** — complements idempotency keys (P1) with a content-hash dedupe window.
- **Notification Center UI** — richer home for the super-admin alerts that P0-4 introduces.
- **Long-running flow cancellation from the UI** — surface cancel for in-flight arq runs.
- **Org-scoped environment variables** — non-secret per-org config values (URLs, feature toggles) beyond the secret store.
- **In-app onboarding checklist / empty-state polish** — improve first-run experience without a full wizard.
- **Graceful degradation when an LLM provider is down** — retry/failover story for assistant + flow LLM calls.
- **Flow execution log retention policy** — configurable cleanup window; GDPR-adjacent.
- **Readiness / liveness endpoints + documented k8s manifests** — production-hardening.

---

## 4. ❌ Won't do

Explicit "no" list. Reopening any of these requires a specific ask, not a drift.

| Item | Reason |
|------|--------|
| Per-org quotas (hard rate limits) | P0-4 does warnings only; no hard stops by design |
| Tenant tiering (free / standard / enterprise plans) | No plan model; we don't price by tier |
| Cold-path hibernation | Not worth the complexity given our scale |
| Git integration for flows | DB backups cover this |
| Local dev SDK for custom components | Tenant users can't author custom components |
| Private component packages | Tenant users can't install org-specific components |
| Cross-org template sharing ("publish to all orgs") | Out of scope |
| Template versioning / history | Out of scope |
| Polling triggers | External scheduler + webhooks covers the use case |
| White-label theming per host app | Out of scope |
| Chat-widget embed (UI affordance) | Removed in P0-2; broader embed is a future project |
| Data residency / region pinning per org | Infra-level concern, not Langflow's problem |
| Secret rotation automation | Manual via Vault when needed |
| API key rotation for webhooks | Manual reset via existing endpoint |

---

## 5. 🔁 External tools

We won't build these in Langflow; they're handled elsewhere.

| Concern | Where it's handled |
|---------|---------------------|
| Scheduling | External scheduler fires our webhook triggers |
| Native cron-to-webhook adapter | Same — external scheduler owns it end-to-end |
| Conversational schedule/trigger management | External scheduler (revisit once that tool's UX is clearer) |
| Flow storage / version control | DB backups instead of git |
| Enterprise SSO / SCIM-as-provider / MSFT Entra | Separate manual project, not part of this roadmap |
| IP allowlist per org for inbound triggers | Gateway / infra layer, not Langflow |

---

## 6. ✅ Already shipped (reference)

Compressed so it doesn't drown the live backlog. Ordered by PRD section.

- **Multi-tenant & scale (req 1, 5):** Shared app tier, `Organization` / `Membership` with cross-org FK guard, shared arq worker pool with per-org Redis-Lua concurrency + priority tier, payload offload, Prometheus metrics, reaper + retention sweep, batched run-log sink.
- **Secrets (req 8):** VaultSecretStore (hvac KV v2), factory + in-memory dev backend, `SecretStrInput.auto_promote`, `TextFileSecretInput` for PEM/SSH, mTLS in API Request + ADP Auth, webhook HMAC + per-flow API keys, bcrypt 5.x (passlib dropped), 5-tier RBAC + last-owner + escalation guards, cross-org FK validator, Fernet (upstream).
- **Assistant (req 2):** Flow Builder Assistant (conversational, Anthropic + OpenAI), Test mode with pipeline view, component-level assistant with guide registry, template context steering, Apply/Dismiss inline diff, `assist_enabled` opt-out contract.
- **Templates (req 9):** `Template` model with archive + org scope + lineage, categories with icon/color CRUD, Save-as-Template modal, Templates browse modal, `user_can_edit_template`, starter flows seeded as Templates.
- **Components (req 11):** Component versioning + changelog end-to-end, Update Components modal, fork-owned bundle (ADP, Data Mapper, SFTP, webhook + API Request enhancements), component authoring skill enforces version-bump ritual.
- **Data Mapper (req 4):** 6 transform types (direct/static/variable/template/expression/array), composite-key left-join, jsonschema validation, auto-map flow.
- **Triggers (req 6):** Webhook triggers with HMAC + delivery retry state machine, webhook reset endpoint + dialog, ADP Trigger native component, chat trigger via Playground (upstream).
- **Metadata (req 10):** Component metadata (ADP Trigger), flow/template metadata models, component guide registry (class-attr + YAML), assistant template context, `assist_enabled` opt-out.

---

## 7. Connector coverage (req 12)

| Connector | Status | Notes |
|-----------|--------|-------|
| SFTP | ✅ | SFTP CSV Upload with host-key fingerprint |
| REST APIs | ✅ | API Request with mTLS + bearer + form-urlencoded + v2 changelog |
| Agents | ✅ 🟦 | Langflow Agent + ADP Worker Tools as StructuredTool wrappers |
| Webhooks | ✅ | Per-flow API keys, HMAC signing, delivery retries |
| ADP | ✅ | Full bundle: Auth, APIRequest, MCP, WorkerTools, Trigger |
| MCP | ✅ 🟦 | Langflow speaks MCP + fork exposes component catalog as MCP server |
| SCIM formatter (outbound) | **P1** | Converts data to SCIM format and POSTs to an API |
| OAuth 2.0 framework | **P1** | Shared reusable scaffold; ADP has its own today |
| Message queues (Kafka / SQS / Pub/Sub) | **P1** | Paired with event-bus triggers |
| PostgreSQL | ✅ | `pgvector` vectorstore + generic `data_source/sql_executor.py` SQLComponent (SQLAlchemy, shared-cache) |
| MySQL | 🟡 | Works through generic SQLComponent when a driver (`pymysql` / `mysqlclient`) is installed; no MySQL-specific component. **P1.5** — ship a thin MySQL convenience component if demand appears |
| Snowflake | 🟡 | Works through generic SQLComponent with `snowflake-sqlalchemy` installed; Composio stub exists but delegates to the Composio framework. **P1.5** — native connector only if a customer asks |
| BigQuery | ✅ | Dedicated `google/google_bq_sql_executor.py` with service-account JSON auth |
| Amazon S3 | ✅ | `amazon/s3_bucket_uploader.py` with upload-by-data and upload-by-path strategies; backend tests cover both paths |
| Google Cloud Storage | ❌ | Not implemented. **P2** — parity with S3 if a GCP customer asks |
| Azure Blob Storage | ❌ | Not implemented. **P2** — parity with S3 if an Azure customer asks |
| Gmail | ✅ | Native `google/gmail.py` (GmailLoaderComponent) with service-account auth; `gmail_composio.py` available as Composio alternative |
| Outlook / Exchange mail | 🟡 | Via Composio only (`outlook_composio.py`); no native component |
| Generic SMTP / IMAP | ❌ | Not implemented. **P1.5** — generic SMTP send + IMAP fetch would unblock any email provider |
| Slack | 🟡 | Via Composio (`slack_composio.py`, `slackbot_composio.py`); no native send-message component. **P1.5** — native incoming-webhook sender is cheap to add |
| Microsoft Teams | ❌ | Not present in native or Composio components. **P2** — paired with the MS suite below |
| Microsoft (Graph / Entra / Teams / SharePoint) | **P2** | Paired with the future SSO/SCIM project |
| Salesforce / HubSpot / Workday | **P2** | Common HR/CRM targets |
| SCIM-as-provider (Langflow as SCIM target) | 🔁 External | Future manual project with SSO |

---

## 8. Open questions / follow-ups

- Who owns picking the external scheduler, and what does the webhook handshake look like from its side? (Affects the "External" row above.)
- Confirm that the DB backup path for flows is actually restore-tested (P1 "Backup & restore per tenant" assumes it is).
- Pricing model for cost estimator (P0-8): do we hard-code provider prices, pull from a config, or read from a vendor API?
