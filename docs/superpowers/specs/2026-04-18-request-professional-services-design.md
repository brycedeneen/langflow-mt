# Request Professional Services

**Date:** 2026-04-18
**Status:** Draft

## Overview

Lets a client, mid-conversation with ADP Assist, request a Professional Services engagement with an auto-generated proposal of effort and cost. Two entry points: a "Request PS" button in the fullscreen header (always available to the flow owner and org admins) and an assistant-suggested card that surfaces when the conversation signals the client is stuck or explicitly needs human help. A preview modal shows the AI estimate (hours + dollars, derived from per-component metadata and a rate band), plus an editable narrative and conversation summary. On submit, Langflow posts an HMAC-signed JSON payload to a configurable webhook URL — no vendor-specific ticketing integration is built; the webhook receiver is whatever the deployment points it at (Zapier, Lambda, internal intake endpoint, email forwarder, etc.). Prevents duplicate submissions via a `ps_request_active` flag on the flow.

## Key Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Ticket integration target | **Generic webhook only.** Langflow POSTs a signed JSON payload to `professional_services_settings.webhook_url`. Deployment configures the receiver (no native Zendesk/Salesforce/email adapters). | Collapses the "longest pole" blocker: every client has a different ticketing system; a webhook serves all of them. Reuses the existing `worker_app/webhook.py` HMAC+retry pattern. |
| Trigger surface | **Both: persistent header button + assistant-suggested card.** Header button always available to flow owner/org admin; card surfaced by a new `suggest_professional_services` assistant tool when the conversation warrants. | Passive availability + proactive detection. Most flexible. |
| Proposal payload | **Structured metadata + LLM-generated narrative + LLM-generated conversation summary.** No full flow snapshot; PS can follow a link back to Langflow if they need to inspect the flow itself. | Keeps payload small while giving PS enough context. Full snapshots exceed most webhook receivers' payload limits. |
| Preview UX | **Preview modal, editable narrative/summary, read-only structured data.** User reviews before submitting. AI-estimate disclaimer displayed non-editably. | Enterprise expectation: clients see what they're committing to. Editing the narrative lets them add context the LLM didn't know. |
| Submitter permission | **Flow owner + org admin.** Viewers can't fire off PS requests. | Matches who's close to the friction and who has business authority. |
| Rate source | **DB-stored global default (`professional_services_settings.default_hourly_rate_low/high`) + per-org overrides (`org.billable_rate_low/high`).** Superuser edits via a new Settings tab. Resolution: `org_rate ?? global_rate`. | Different clients with negotiated rates need per-org flexibility. Storing in DB (not env) lets superuser reconfigure without redeploys. |
| Dollar display | **Shown when either org or global rate is set; hidden when both are NULL.** | Graceful degradation — fresh installs can show hours alone until rates are configured. |
| Duplicate prevention | **`flow.ps_request_active: bool`** flag. Set true at submit; cleared manually by superuser or by the external ticket system via an admin endpoint. | This is an integration tool, not a ticket system — no need for a full submissions history UI. Flag prevents the "submit and submit and submit" scenario. |
| Proposal history UI | **None in Phase 1.** `ProposalRecord` rows exist for debugging and future audit features. | Client doesn't need to see their own history in v1. If they want status, they contact PS directly. |
| LLM privacy guard | **System-prompt instruction for narrative/summary generation: never include credentials, API keys, tokens, URLs with tokens, or values that look like secrets.** | The webhook receiver may persist the payload in less-trusted places (Zapier DB, third-party ticketing). Belt-and-suspenders against credential leakage. |

## Architecture

```
┌────────── Client: Request Professional Services ────────────────────┐
│                                                                      │
│  Option 1 — user clicks header button                                │
│  Option 2 — assistant surfaces PS suggestion card → user clicks it   │
│                      │                                                │
│                      ▼                                                │
│  POST /api/v1/flows/{flow_id}/professional-services/proposal/preview │
│    ├─ Reads flow.data.nodes                                          │
│    ├─ Joins with component_metadata.integration_hours_low/high       │
│    ├─ Resolves rate band: org.billable_rate_* ?? global.default_*    │
│    ├─ LLM call: generate narrative + conversation_summary            │
│    │   (prompt explicitly forbids secret values in output)           │
│    └─ Returns preview payload                                        │
│                      │                                                │
│                      ▼                                                │
│  Preview modal (user reviews, optionally edits narrative/summary)    │
│                      │                                                │
│                      ▼                                                │
│  POST /api/v1/flows/{flow_id}/professional-services/proposal/submit  │
│    ├─ Validate flow.ps_request_active = false (409 otherwise)        │
│    ├─ Write proposal_record                                          │
│    ├─ Fire HMAC-signed webhook (reuses worker_app/webhook.py pattern)│
│    ├─ Set flow.ps_request_active = true                              │
│    └─ Return { proposal_id, delivery_status }                        │
│                      │                                                │
│                      ▼                                                │
│  (external) Webhook receiver — e.g., Zapier → Salesforce             │
└──────────────────────────────────────────────────────────────────────┘

┌────────── PS team: clear the flag when engagement completes ────────┐
│                                                                      │
│  Superuser via UI OR external ticket system via API:               │
│    POST /api/v1/admin/flows/{flow_id}/professional-services/clear    │
│    → flow.ps_request_active = false                                  │
│    Client can now submit again for future engagements                │
└──────────────────────────────────────────────────────────────────────┘
```

## Section 1: Data Model

### New columns on existing tables

| Table | Column | Type | Notes |
|---|---|---|---|
| `component_metadata` | `integration_hours_low` | INT, nullable | |
| `component_metadata` | `integration_hours_high` | INT, nullable | |
| `flow` | `ps_request_active` | BOOLEAN NOT NULL DEFAULT FALSE | |
| `org` | `billable_rate_low` | INT, nullable | Overrides global default |
| `org` | `billable_rate_high` | INT, nullable | |

### New table `professional_services_settings` (singleton)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Singleton row; application code always SELECTs a single row |
| `default_hourly_rate_low` | INT, nullable | |
| `default_hourly_rate_high` | INT, nullable | |
| `webhook_url` | str, nullable | Fallback to `LANGFLOW_PS_WEBHOOK_URL` env if null (optional secondary source) |
| `webhook_secret` | str, nullable | HMAC signing key; stored encrypted via existing secret-store pattern |
| `updated_by` | UUID, FK → user.id | |
| `updated_at` | datetime | |

### New table `proposal_record`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `flow_id` | UUID, FK → flow.id | Indexed |
| `submitted_at` | datetime | Server default now |
| `submitted_by` | UUID, FK → user.id | |
| `org_id` | UUID, FK → org.id | |
| `payload` | JSON | Full submitted proposal (narrative + conversation_summary + components + totals + disclaimer copy) |
| `webhook_delivery_status` | Enum (`pending`, `sent`, `failed`, `disabled`) | `disabled` = webhook URL was not configured at submit time |
| `webhook_delivery_attempts` | INT, default 0 | |
| `webhook_delivery_last_error` | str, nullable | |
| `external_ticket_id` | str, nullable | If the webhook receiver returns a ticket ID in its 200 body, store it |

**Dependency note:** the `org` table exists on a WIP branch (per session memory: `Organization/Membership/org_helpers.py` untracked on `feat/adp-connector`). Plan 8 assumes the multi-tenant foundation is landed before implementation. If the branch hasn't merged, implementation defers the `org.billable_rate_*` columns to a sub-plan and runs Phase 1 without per-org rate overrides.

## Section 2: API Endpoints + Assistant Tool

### Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/flows/{flow_id}/professional-services/proposal/preview` | flow owner or org admin | Generates the preview payload. Reads flow nodes, joins component_metadata, resolves rates, and calls the LLM to generate `narrative` + `conversation_summary`. Does NOT fire the webhook or store a `ProposalRecord`. |
| `POST` | `/api/v1/flows/{flow_id}/professional-services/proposal/submit` | flow owner or org admin | Accepts the user's (possibly-edited) narrative/summary. Validates `flow.ps_request_active = false` (409 otherwise). Writes `ProposalRecord`. Fires HMAC-signed webhook via the existing delivery pattern (`worker_app/webhook.py`). Sets `flow.ps_request_active = true`. |
| `GET` | `/api/v1/admin/professional-services/settings` | superuser | Returns the singleton settings row. |
| `PUT` | `/api/v1/admin/professional-services/settings` | superuser | Updates global rates / webhook URL / webhook secret. |
| `POST` | `/api/v1/admin/professional-services/settings/test-webhook` | superuser | Fires a dummy signed POST at the configured URL and returns the receiver's response. |
| `POST` | `/api/v1/admin/flows/{flow_id}/professional-services/clear` | superuser, OR authenticated via the webhook secret (for external ticket systems) | Clears `flow.ps_request_active = false`. |

### Preview payload shape

```jsonc
{
  "proposal_id": null,  // null until submitted
  "flow": { "id": "uuid", "name": "...", "url": "https://app/flows/uuid" },
  "components": [
    { "component_name": "Agent", "count": 1, "hours_low": 4, "hours_high": 8 },
    { "component_name": "Webhook", "count": 1, "hours_low": 2, "hours_high": 6 },
    { "component_name": "ChatInput", "count": 1, "hours_low": null, "hours_high": null }
  ],
  "totals": { "hours_low": 6, "hours_high": 14, "cost_low": 1500, "cost_high": 4200 },
  "rate_band": { "low": 250, "high": 300, "source": "org" | "global" | null },
  "narrative": "…LLM generated…",
  "conversation_summary": "…LLM generated…",
  "disclaimer": "This is an AI estimate only. …"
}
```

`totals.cost_low` / `cost_high` are null when both org and global rates are unset.

### Submit payload shape

Same as preview, with user-edited `narrative` and `conversation_summary`. Server recomputes `components`, `totals`, `rate_band` from DB (ignores anything the client sent in those fields — prevents tampering).

### Webhook delivery payload (what the receiver gets)

```jsonc
{
  "proposal_id": "uuid",
  "submitted_at": "2026-04-18T14:32:00Z",
  "submitter": {
    "user_id": "uuid",
    "email": "client@example.com",
    "org_id": "uuid",
    "org_name": "Customer Org"
  },
  "flow": { "id": "uuid", "name": "Workday → Payroll Sync", "url": "..." },
  "components": [...],
  "totals": { "hours_low": 6, "hours_high": 14, "cost_low": 1500, "cost_high": 4200 },
  "narrative": "...",
  "conversation_summary": "..."
}
```

Plus an HMAC header (`X-Langflow-Signature: sha256=...`) computed from the JSON body + `webhook_secret`. Reuses the `sign_payload` / verification helpers from `src/backend/base/langflow/worker_app/webhook.py`. Retries on 429/5xx with backoff (max 6 attempts), same as the existing flow-run webhook.

### New assistant tool

Added to `src/backend/base/langflow/services/assistant/tools/registry.py`:

```python
{
  "name": "suggest_professional_services",
  "description": "Surface a clickable 'Request Professional Services' card in the chat when the user's needs exceed what you can build, or when they've been stuck on a problem for multiple attempts. Only call this when it's genuinely warranted.",
  "parameters": {
    "type": "object",
    "properties": {
      "reason": {
        "type": "string",
        "description": "Brief reason for suggesting PS (1 sentence). Shown in the card."
      }
    },
    "required": ["reason"]
  }
}
```

Handler: emits SSE event `ps_suggestion_card` with `{reason}`. Returns `{"result": "Card surfaced."}` — or `{"result": "PS request already in progress; card not shown."}` if the flag is active.

### New system-prompt guideline

Appended to `## Guidelines` in `SYSTEM_PROMPT_TEMPLATE`:

> - When the user is stuck after ~3+ back-and-forths on the same issue, OR explicitly says they need human help, OR describes needs that require custom work outside your component catalog (e.g., integration with a legacy mainframe, compliance-reviewed cryptography, bespoke enterprise workflow), call `suggest_professional_services` with a one-sentence reason. Do NOT call it for minor issues that can be resolved conversationally. The card the tool surfaces gives the user a clear path to request human assistance without derailing the conversation.

Pin the key substrings via `test_ps_guideline_in_prompt.py` (same pattern as Plan 4's greet / Plan 5's test-failure guidelines).

### Narrative + conversation summary generation

Done inside the `/preview` endpoint via a single LLM call:

> You are preparing a Professional Services proposal summary. Given the following flow structure and conversation history, write:
>
> 1. **Narrative** (2–3 sentences): what this flow does, what components it uses, what's the primary source of complexity or uncertainty.
> 2. **Conversation summary** (2–4 sentences): what the user asked for, what's been built, what's blocked, what they've explicitly requested help with.
>
> **Do NOT include** credentials, API keys, URLs with tokens, customer-specific identifiers, or any value that looks like a secret. The output will be sent to an external webhook.

Returns both fields; endpoint merges into the preview payload.

## Section 3: UX Flow

### 3a. Header button (fullscreen mode)

Added next to existing Test / View Canvas / Close buttons in `fullscreen-shell.tsx`:

```
[ADP Assist — Test]  [Back to chat]  [View Canvas]  [Request PS]  [X]
```

- Visible to: flow owner + org admin.
- Disabled + tooltipped when `flow.ps_request_active = true`: *"A PS request is already in progress for this flow. Contact support for status."*
- Disabled (hidden) when global webhook URL is not configured (the button cannot deliver value).
- Click → opens preview modal.

### 3b. Assistant-suggested card

Triggered by `suggest_professional_services(reason)`. Rendered in the message list with a visually distinct treatment (icon, subtle border):

```
┌───────────────────────────────────────────────────────────┐
│  💼 Professional Services available                       │
│                                                            │
│  {reason from the tool call}                              │
│                                                            │
│  [ Request Professional Services ]   [ Not now ]          │
└───────────────────────────────────────────────────────────┘
```

- "Request Professional Services" → opens same preview modal as the header button.
- "Not now" dismisses the card (frontend state only; LLM may surface it again later).
- Suppressed when `flow.ps_request_active = true`.

### 3c. Preview modal

Three sections:

**① Proposal summary (read-only)**

```
Flow: Workday → Payroll Sync
Components involved:
  • Agent                             4 – 8 hours
  • Webhook                           2 – 6 hours
  • ChatInput                         — not estimated

Estimated effort: 6 – 14 hours
Estimated cost: $1,500 – $4,200     (based on your rate band)
```

- Components without metadata hours are listed with "— not estimated".
- Cost row hidden when rate band is fully null.

**② Summary (editable)**

Two text areas, pre-filled by `/preview`:

- `Narrative` — what the flow does + uncertainty.
- `Conversation summary` — what's been tried + blocked.

Each has a small "Regenerate" button that re-runs the LLM call for that field.

**③ AI-estimate disclaimer (non-editable)**

> **This is an AI estimate only.** The estimated effort and cost are based on per-component metadata and are not a commitment. After you submit this request, a Professional Services team member will review and provide an official quote tailored to your specific needs.

**Actions:** `Cancel` | `Submit Request`

Submit → POST `/submit`. On success: modal closes, toast *"Request sent — we'll be in touch shortly."* Flag flips, header button disables. On webhook delivery failure: submission still succeeds (ProposalRecord written with `delivery_status=failed`), toast reads *"Request logged. Delivery to our ticket system will retry automatically."*

### 3d. Superuser Professional Services settings tab

New tab in `SettingsPage/pages/`:

- **Global rate settings:** `default_hourly_rate_low` + `default_hourly_rate_high` number inputs.
- **Webhook delivery:** `webhook_url` text input, `webhook_secret` password input (stored encrypted). `Test webhook` button → fires signed POST, shows response + status.
- **Per-org overrides:** (optional for Phase 1) table of orgs with editable `billable_rate_low/high` cells. If the project has an existing org-management page, add the columns there instead. If neither exists and multi-tenant is still WIP, defer this UI to a sub-plan and document the CLI path.
- **Failed deliveries log:** recent `ProposalRecord` rows with `delivery_status = failed`. Retry button per row.

### 3e. Flag clearing

Superuser UI: a "Clear PS request flag" action on a flow admin page (same surface as other flow-admin actions). Confirmation modal → POST `/clear`.

Alternative: the external ticket system can hit the same endpoint programmatically, authenticated by the webhook secret (header `X-Langflow-Webhook-Secret`).

## Section 4: Migration

Single alembic revision. No data backfill beyond a singleton seed.

1. Create `proposal_record` table.
2. Create `professional_services_settings` table. Insert one row with all NULL / default values.
3. Add `integration_hours_low INT NULL` and `integration_hours_high INT NULL` to `component_metadata`.
4. Add `ps_request_active BOOLEAN NOT NULL DEFAULT FALSE` to `flow`.
5. Add `billable_rate_low INT NULL` and `billable_rate_high INT NULL` to `org`.

**Organization model dependency:** step 5 requires the `org` table to exist. If the multi-tenant foundation (`Organization/Membership/org_helpers.py`) hasn't landed from the WIP branch by implementation time, the plan will either land a minimal Organization stub as part of Plan 8 OR defer step 5 to a sub-plan and skip per-org rate overrides in Phase 1.

**Code touch points:**

- **Backend:** new router `src/backend/base/langflow/api/v1/professional_services.py`, new admin router `src/backend/base/langflow/api/v1/admin/professional_services.py`, extensions to `src/backend/base/langflow/services/assistant/service.py` (new tool handler + system-prompt bullet), new settings model file `src/backend/base/langflow/services/database/models/professional_services_settings/model.py`, new `proposal_record/model.py`.
- **Frontend:** `PreviewProposalModal.tsx`, `PSRequestButton.tsx`, `PSSuggestionCard.tsx`, new `ProfessionalServicesSettingsTab.tsx`, new SSE event handler for `ps_suggestion_card`, changes to `fullscreen-shell.tsx` to add the header button.

**Rollback:** alembic downgrade drops the new tables/columns. `proposal_record` data is lost. Acceptable — no downstream dependencies.

## Section 5: Testing Strategy

### Backend tests

- `tests/unit/api/v1/test_professional_services_endpoints.py`:
  - `/preview` as flow owner succeeds; as viewer → 403.
  - `/preview` blocked when `flow.ps_request_active=true`.
  - `/submit` fires webhook (mocked), writes `ProposalRecord`, flips `ps_request_active`.
  - `/submit` succeeds when webhook delivery fails; `delivery_status=failed`.
  - `/submit` second call while flag is active → 409.
- `tests/unit/api/v1/admin/test_professional_services_admin.py`:
  - `/settings` GET/PUT superuser-only.
  - `/clear` superuser succeeds; webhook-secret-authenticated succeeds; regular user → 403.
  - `/settings/test-webhook` fires real signed POST (mocked receiver).
- `tests/unit/services/assistant/test_suggest_ps_tool.py`:
  - Tool is registered.
  - Handler emits SSE event + returns success.
  - Tool is a no-op when `ps_request_active=true`.
- `tests/unit/services/assistant/test_ps_guideline_in_prompt.py`:
  - Bullet's key substrings are present in `SYSTEM_PROMPT_TEMPLATE` (matches Plan 4/5 pinning pattern).
- `tests/unit/services/database/test_proposal_record_model.py`:
  - Column constraints; JSON payload round-trips; enum values.
- `tests/integration/test_ps_webhook_delivery.py`:
  - HMAC signature matches for a known payload + secret.
  - Retry backoff on 5xx matches the existing flow-run delivery behavior.
  - `external_ticket_id` captured from receiver's 200 response when present.

### Frontend tests (Jest)

- `PreviewProposalModal.test.tsx`:
  - Renders summary + hours/dollars ranges (dollars hidden when rate band is null).
  - Editable fields update state; Submit sends the correct payload.
  - "Regenerate" fetches on demand.
  - Disclaimer is non-editable.
- `PSRequestButton.test.tsx`:
  - Visible to owner/admin; hidden for viewers.
  - Disabled + tooltip when `ps_request_active=true`.
  - Disabled when webhook URL is not configured.
- `PSSuggestionCard.test.tsx`:
  - Renders reason; click opens modal; "Not now" dismisses.
- `ProfessionalServicesSettingsTab.test.tsx`:
  - Superuser can edit global rates + webhook URL.
  - "Test webhook" shows receiver response.

### Manual verification checklist

1. Boot → Settings → "Professional Services" tab exists for superuser, hidden for others.
2. Superuser configures webhook URL + rates. "Test webhook" shows success.
3. Flow owner opens fullscreen → header shows "Request PS" button.
4. Click → preview modal loads. Hours computed from metadata-seeded components; dollars computed from rate band.
5. Edit narrative → Submit → toast "Request sent." Button disables. DB confirms `ps_request_active=true`.
6. Webhook receiver (e.g., requestbin.com) shows HMAC-signed payload with all expected fields.
7. Click button again → disabled tooltip fires.
8. Superuser clears flag → button re-enables. Submit again → works.
9. Drive the assistant into a stuck scenario → suggestion card appears → click → same modal.
10. Viewer role opens the flow → no button visible.
11. Break webhook URL (point at 404) → submit succeeds, admin log shows `delivery_status=failed`.
12. Component with NULL hours: renders "— not estimated" in the preview; does not contribute to totals.

## Section 6: Out of Scope

- **Native Zendesk / Salesforce / Jira adapters** — generic webhook only in Phase 1.
- **In-UI proposal history for clients** — no "My Requests" view in Phase 1.
- **Full flow snapshot in webhook payload** — out of scope; receiver follows `flow.url` back to Langflow if they need to inspect.
- **Automatic status updates from ticket system back into chat** — one-way outbound today; inbound status updates may be a later phase.
- **Multi-step approval workflow** (e.g., client admin → account manager → PS) — single submit in Phase 1.
- **Discount / pricing tier logic beyond hours × rate** — keep math simple.
- **LLM-generated component hour estimates** when metadata is missing — skip; `— not estimated` is the truth.
- **Editing component hours via the preview modal** — hours come from metadata only.
- **Per-user (rather than per-org) rate overrides.**
- **Recurring engagements, retainer billing, or project-tracking features.**
- **Attachments (file uploads) in the proposal payload.**

## Relationship to Other Specs

- **Depends on** Plan 2 (Metadata Infrastructure) — `ComponentMetadata` table; Phase 8 adds two columns.
- **Depends on** Plan 4 (Full-Screen Experience) — `fullscreen-shell.tsx`, system-prompt template, assistant tool registry pattern.
- **Depends on** the Organization / multi-tenant model (currently WIP on `feat/adp-connector` branch) for per-org rate overrides. Plan will verify status at implementation time.
- **Reuses** `src/backend/base/langflow/worker_app/webhook.py` for HMAC-signed delivery with retries.
- **Reuses** existing `SecretStrInput` / secret-store pattern for the encrypted `webhook_secret` field.
- **Extends** `SettingsPage` with a new "Professional Services" tab.

## Open Items Flagged During Implementation

- **Organization model availability.** Decide at plan-write time whether to proceed with per-org rates (if the WIP branch has merged), land a minimal Organization stub as part of Plan 8, or defer per-org overrides to a sub-plan.
- **Per-org rate editing UI location.** If there's an existing org-management page in Settings, add the `billable_rate_*` columns there. If not, add a minimal table on the Professional Services settings tab. Confirm at plan-write time.
- **Failed-delivery retry UX.** Phase 1 stores failed records in the admin log with a retry button. Consider whether to wire it up in Phase 1 or defer to a follow-up polish task.
- **Singleton enforcement for `professional_services_settings`.** Easiest via app-code convention (always SELECT the first row; UPSERT only). If you prefer a CHECK constraint or a dedicated single-row view, decide at plan-write time.
- **Card dismissal state persistence.** The suggestion card's "Not now" dismissal is frontend-only in Phase 1. If users want the LLM to back off after a dismissal, we'd need to store dismissal state server-side. Flag for feedback after rollout.
