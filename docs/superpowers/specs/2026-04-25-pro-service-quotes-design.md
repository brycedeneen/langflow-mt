# Pro-Service Quotes

**Date:** 2026-04-25
**Status:** Draft
**Supersedes:** [`2026-04-18-request-professional-services-design.md`](./2026-04-18-request-professional-services-design.md)

## Overview

Lets a user request a Professional Services engagement from inside Langflow. The system computes a ballpark hours range from per-component metadata, multiplies by a configurable hourly rate band to produce a dollar range, and generates a one-sentence headline, narrative, and conversation summary via an LLM. The user reviews and edits in a preview modal, then submits.

Quotes are first-class entities in Langflow. They appear in a new "Pro-Service Quotes" sidebar nav (above "Knowledge") visible to all logged-in users — org members see their own org's quotes, super-admins and platform-admins see every org's quotes (both are cross-tenant roles in this codebase). A small lifecycle (`open` → `in_progress` → `closed`) lets admins triage requests and the requester self-cancel an open one. Two notes fields (`org_notes`, `admin_notes`) allow each side to leave context.

This is **not** a quoting platform — the AI estimate is a non-binding ballpark. PS does not counter-quote inside Langflow; if real scoping is needed, the PS team contacts the requester out-of-band using the contact details and flow link in the bell notification.

An optional outbound HMAC-signed webhook fires on submit, mirroring the quote into whatever external system a deployment uses (Zapier, internal intake URL, CRM). The internal queue is the source of truth — the webhook is a notification mirror, not a handoff.

## Key Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Source of truth | **Internal queue is primary; webhook is an optional mirror.** | Lets PS triage in-app today; keeps the door open to push to external CRM later without re-architecture. |
| Lifecycle | **Three states: `open` → `in_progress` → `closed`.** No `accepted/rejected` — the AI estimate is a ballpark, not a commitment. | Matches the "ballpark, not CRM" framing. Lower UI surface and fewer notification permutations. |
| Cancellation | **Requester can self-transition `open` → `closed`** with a note like "fixed it on my own." Admin can also close from any state. | One enum, no special-cased "cancel" verb; closure reason lives in `org_notes` + a `closed_by_user_id` audit column. |
| Admin scope | **Both super-admin and platform-admin are cross-tenant.** Both see every org's quotes. Org members see all of their own org's quotes (not user-scoped). | Matches the codebase's working definition: super-admin is global, platform-admin is the platform team that triages across orgs. |
| Quote visibility for org users | **All quotes their org submitted, regardless of submitter.** | PS engagements are usually known to the whole org; per-user privacy isn't the right model. |
| Time unit | **Integer minutes.** Default per component: low=15, high=60. | Cleaner than decimals; matches the user's intuition. |
| Rate unit | **DECIMAL dollars-per-hour** stored directly in the DB. Default = $200/hour for both low and high. | Explicit choice over cents/min: configuring "$200" reads more naturally to admins than "333" cents/min. |
| Per-org rate override | **`org.billable_rate_low_per_hour` / `high_per_hour` columns** override the global default. Resolution: `org_rate ?? global_rate`. | Different orgs negotiate different rates. |
| Dollar display | **Shown when either org or global rate is set; hidden when both are NULL.** Sub-cent positives render as `<$0.01`. | Graceful degradation; matches the project's money-format rule. |
| Component metadata seed | **15 / 60 minutes** for every existing component on first migration. | Seeds something useful from day one; PS team tunes per-component over time. |
| Headline summary | **LLM-generated** alongside the narrative + conversation summary in the same preview API call. User can edit before submit. | A first-sentence-of-narrative shortcut underdelivers; one LLM call is cheap. |
| Trigger surfaces | **Header button + assistant-suggested card.** | Passive availability + proactive detection. The card is the headline assistant integration. |
| Templates-popup entry | **Deferred to v2.** No-flow path is real schema/UX work that doubles the estimation surface. | Ship the in-flow path solid first. |
| Assistant guidance | **Ask up to 2 clarifying questions, then suggest** — don't try to solve once human help is on the table. | Goal is quote-out-the-door fast, not deflect-with-AI. |
| Submitter permission | **Flow owner + org admin.** | Matches who's close to the friction and has business authority. |
| Duplicate-submit guard | **`flow.ps_request_active: bool`**. Set true at submit; cleared on any terminal transition (close or cancel). | Prevents the "submit and submit and submit" scenario without needing a full submissions UI. |
| Rate snapshot | **Snapshot rates onto the quote row at submit time.** | If global rate changes later, closed-quote dollar amounts don't drift. |
| Notification routing | **Bell extended:** add `audience_user_id` (nullable FK) for targeted rows; add `PLATFORM_ADMIN` to `NotificationAudience`. | Smallest change that lets one bell endpoint serve admin broadcasts and per-user pings. |
| LLM secret guard | **System prompt forbids credentials, API keys, tokens, secret-shaped values** in narrative/summary outputs. | Webhook receivers may persist payloads in less-trusted places. |

## Architecture

```
┌──── Client: Request Pro-Service ─────────────────────────────────────┐
│                                                                       │
│  Entry 1: header "Request PS" button (flow owner / org admin)         │
│  Entry 2: assistant card → emitted by suggest_professional_services   │
│                                                                       │
│  POST /api/v1/flows/{flow_id}/pro-service-quotes/preview              │
│    ├─ Read flow.data.nodes                                            │
│    ├─ Sum component_metadata.integration_minutes_low/high             │
│    │   (NULL falls back to seeded 15/60)                              │
│    ├─ Resolve rate band: org.billable_rate_* ?? settings.default_*    │
│    ├─ LLM call → headline_summary + narrative + conversation_summary  │
│    │   (system prompt forbids credentials/tokens/secrets)             │
│    └─ Return preview payload (no persistence)                         │
│                          │                                             │
│  Preview modal: user reviews; edits headline/narrative/summary/notes  │
│                          │                                             │
│  POST /api/v1/flows/{flow_id}/pro-service-quotes                      │
│    ├─ 409 if flow.ps_request_active = true                            │
│    ├─ Snapshot rates onto pro_service_quote row                       │
│    ├─ INSERT row (status=open)                                        │
│    ├─ flow.ps_request_active = true                                   │
│    ├─ INSERT bell rows (super-admin + platform-admin audiences)       │
│    └─ ASYNC: enqueue HMAC webhook (if URL configured)                 │
│                          │                                             │
│  Bell ring → admins triage in /pro-service-quotes                     │
└───────────────────────────────────────────────────────────────────────┘

┌──── Triage ─────────────────────────────────────────────────────────┐
│                                                                       │
│  Admin: PATCH .../pro-service-quotes/{id}                             │
│    open → in_progress → closed (with admin_notes)                     │
│    each transition writes targeted bell row to requester              │
│    closing clears flow.ps_request_active                              │
│                                                                       │
│  Requester: PATCH .../pro-service-quotes/{id}                         │
│    open → closed (self-cancel; writes admin bell)                     │
│    can edit org_notes any time                                        │
│                                                                       │
│  Org member: read-only access to their org's quotes; can edit         │
│    org_notes if requester is in the same org                          │
└───────────────────────────────────────────────────────────────────────┘
```

## Section 1: Data Model

### New columns on existing tables

| Table | Column | Type | Notes |
|---|---|---|---|
| `component_metadata` | `integration_minutes_low` | INT NULL | Backfilled to **15** by migration |
| `component_metadata` | `integration_minutes_high` | INT NULL | Backfilled to **60** by migration |
| `flow` | `ps_request_active` | BOOLEAN NOT NULL DEFAULT FALSE | Dedupe guard, cleared on terminal transition |
| `org` | `billable_rate_low_per_hour` | DECIMAL(10,2) NULL | Per-org override |
| `org` | `billable_rate_high_per_hour` | DECIMAL(10,2) NULL | Per-org override |
| `admin_notification` | `audience_user_id` | UUID NULL FK user | Targeted bell row when set |

Extend `NotificationAudience` enum to include `PLATFORM_ADMIN`. Extend `NotificationCategory` enum to include `professional_services_request`.

### New table `pro_service_quote`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | FK org NOT NULL | |
| `flow_id` | FK flow NULL | Nullable for v2 templates path; v1 always non-null |
| `requester_user_id` | FK user NOT NULL | |
| `status` | ENUM('open','in_progress','closed') NOT NULL DEFAULT 'open' | |
| `assigned_admin_user_id` | FK user NULL | Set when admin moves → in_progress |
| `estimated_minutes_low` | INT NOT NULL | |
| `estimated_minutes_high` | INT NOT NULL | |
| `rate_low_per_hour` | DECIMAL(10,2) NULL | Snapshot at submit (resolved org→global) |
| `rate_high_per_hour` | DECIMAL(10,2) NULL | Snapshot at submit |
| `headline_summary` | TEXT NOT NULL | LLM-generated, one sentence, user-editable pre-submit |
| `narrative` | TEXT NOT NULL | LLM-generated, user-editable pre-submit |
| `conversation_summary` | TEXT NULL | LLM-generated; null if no chat context |
| `org_notes` | TEXT NULL | Editable by any org member |
| `admin_notes` | TEXT NULL | Editable by super/platform admin only |
| `created_at` | TIMESTAMP NOT NULL | |
| `updated_at` | TIMESTAMP NOT NULL | |
| `submitted_at` | TIMESTAMP NOT NULL | |
| `in_progress_at` | TIMESTAMP NULL | |
| `closed_at` | TIMESTAMP NULL | |
| `closed_by_user_id` | FK user NULL | |

Indexes: `(org_id, status, created_at DESC)`, `(status, created_at DESC)` for cross-tenant admin queries, `(flow_id)`.

### New table `professional_services_settings` (singleton, id always 1)

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK CHECK (id = 1) | Singleton enforcement |
| `default_hourly_rate_low` | DECIMAL(10,2) NULL | Seeded to 200.00 |
| `default_hourly_rate_high` | DECIMAL(10,2) NULL | Seeded to 200.00 |
| `webhook_url` | TEXT NULL | Optional mirror |
| `webhook_secret_encrypted` | TEXT NULL | Fernet-encrypted HMAC secret |
| `updated_at` | TIMESTAMP NOT NULL | |
| `updated_by_user_id` | FK user NULL | |

### Migration plan

Single alembic revision (rides on `26b3d04efba1`):
1. Add columns to `component_metadata`, `flow`, `org`, `admin_notification`
2. Extend `notificationcategory` and `notificationaudience` enum types
3. Create `pro_service_quote` and `professional_services_settings`
4. Backfill `component_metadata.integration_minutes_low=15, integration_minutes_high=60` for all existing rows
5. INSERT singleton row in `professional_services_settings` with default rates 200.00 / 200.00

## Section 2: API Endpoints

### Quote lifecycle (user-facing)

| Method + Path | Purpose | Permission |
|---|---|---|
| `POST /api/v1/flows/{flow_id}/pro-service-quotes/preview` | Generate AI estimate + LLM narrative/headline/summary. Does **not** persist. 409 if `ps_request_active`. | Flow viewer |
| `POST /api/v1/flows/{flow_id}/pro-service-quotes` | Submit. Body = preview payload + user edits + optional `org_notes`. Writes row, snapshots rates, sets flag, broadcasts bell, enqueues optional webhook. | Flow owner or org admin |
| `GET /api/v1/pro-service-quotes` | List. Query params: `status`, `org_id` (admin-only). Pagination. | Org member sees their org's; super/platform-admin sees cross-tenant |
| `GET /api/v1/pro-service-quotes/{quote_id}` | Detail | Same scope as list |
| `PATCH /api/v1/pro-service-quotes/{quote_id}` | Edit fields. Server enforces per-field perms: `org_notes` for any org member of `org_id`; `admin_notes` + `assigned_admin_user_id` for admins; `status: open→in_progress→closed` admin-only; `status: open→closed` requester self-cancel. | Conditional |

### Admin settings

| Method + Path | Purpose |
|---|---|
| `GET /api/v1/admin/professional-services/settings` | Read singleton |
| `PUT /api/v1/admin/professional-services/settings` | Update default rates, webhook URL, webhook secret (write-only field) |
| `POST /api/v1/admin/professional-services/settings/test-webhook` | Synthetic ping; returns delivery status |

### Assistant tool

`suggest_professional_services(reason: str)` registered in `services/assistant/tools/registry.py`. Calling it during a conversation emits a `ps_suggestion` SSE event with the `reason` field; frontend renders the suggestion card. Tool does **not** create a quote — only surfaces the card.

System-prompt addition for ADP Assist:

> If the user explicitly asks for human help, says they're stuck, or hits the same error twice, call `suggest_professional_services` with a one-sentence reason. Ask at most two clarifying questions before suggesting; do not try to solve the problem yourself once professional help is on the table. The goal is to get a quote out the door, not to keep iterating.

### Error model

- `409 ps_request_active` — flow already has an open quote
- `403` — permission scope mismatch
- `422 missing_rates` — both global *and* org rates are NULL; quote can still submit but UI hides the dollar range
- `502 webhook_test_failed` — for the test-webhook endpoint

## Section 3: Preview Pipeline

```python
# POST /api/v1/flows/{flow_id}/pro-service-quotes/preview
def preview(flow_id):
    flow = load_flow(flow_id)
    if flow.ps_request_active:
        raise HTTPException(409, "ps_request_active")

    # 1. Sum minutes
    component_types = [n["data"]["type"] for n in flow.data["nodes"]]
    metadata_rows = db.fetch_component_metadata(component_types)
    minutes_low = sum(m.integration_minutes_low or 15 for m in metadata_rows)
    minutes_high = sum(m.integration_minutes_high or 60 for m in metadata_rows)

    # 2. Resolve rate band
    org = current_org()
    settings = read_settings_singleton()
    rate_low = org.billable_rate_low_per_hour or settings.default_hourly_rate_low
    rate_high = org.billable_rate_high_per_hour or settings.default_hourly_rate_high

    # 3. Compute cost
    cost_low = (Decimal(minutes_low) * rate_low / 60) if rate_low else None
    cost_high = (Decimal(minutes_high) * rate_high / 60) if rate_high else None

    # 4. LLM call (single call, structured output)
    chat_history = current_assistant_conversation()  # may be None
    llm_response = generate_quote_text(
        flow=flow,
        chat_history=chat_history,
        component_breakdown=metadata_rows,
    )
    # llm_response = {headline_summary, narrative, conversation_summary}

    return PreviewPayload(
        minutes_low=minutes_low, minutes_high=minutes_high,
        rate_low_per_hour=rate_low, rate_high_per_hour=rate_high,
        cost_low=cost_low, cost_high=cost_high,
        headline_summary=llm_response.headline_summary,
        narrative=llm_response.narrative,
        conversation_summary=llm_response.conversation_summary,
        component_breakdown=[
            {"type": m.component_type, "minutes_low": m.integration_minutes_low or 15,
             "minutes_high": m.integration_minutes_high or 60}
            for m in metadata_rows
        ],
    )
```

LLM system prompt (excerpt):

> Generate three fields about a Langflow integration request:
> 1. `headline_summary`: ONE sentence under 120 characters describing what the user is trying to build.
> 2. `narrative`: 2–4 sentences for a Professional Services scoping engineer — what the integration does, the main components involved, any complexity signals from the conversation.
> 3. `conversation_summary`: 2–3 sentences summarizing what the user has tried so far, based on the chat history. Return null if no conversation context is available.
>
> **Critical: never include API keys, tokens, passwords, secret values, or URLs containing tokens. If the conversation references credentials, refer to them generically ("their OAuth token", "the API key").**

## Section 4: Submit + State Transitions

### Submit critical path (synchronous)

```python
def submit_quote(flow_id, payload, user):
    flow = load_flow_for_update(flow_id)
    if flow.ps_request_active:
        raise HTTPException(409, "ps_request_active")
    if not (user.is_owner_of(flow) or user.is_org_admin()):
        raise HTTPException(403)

    org = current_org()
    settings = read_settings_singleton()
    rate_low = org.billable_rate_low_per_hour or settings.default_hourly_rate_low
    rate_high = org.billable_rate_high_per_hour or settings.default_hourly_rate_high

    quote = ProServiceQuote(
        org_id=org.id, flow_id=flow.id, requester_user_id=user.id,
        status="open",
        estimated_minutes_low=payload.minutes_low,
        estimated_minutes_high=payload.minutes_high,
        rate_low_per_hour=rate_low, rate_high_per_hour=rate_high,
        headline_summary=payload.headline_summary,
        narrative=payload.narrative,
        conversation_summary=payload.conversation_summary,
        org_notes=payload.org_notes,
        submitted_at=now(),
    )
    db.session.add(quote)
    flow.ps_request_active = True

    insert_admin_notification(
        category="professional_services_request",
        audience=[SUPER_ADMIN, PLATFORM_ADMIN],
        title=f"New Pro-Service request from {org.name}",
        body_md=quote.headline_summary,
        metadata={"quote_id": str(quote.id)},
    )
    db.session.commit()

    if settings.webhook_url:
        enqueue_webhook_delivery(quote_id=quote.id)

    return quote
```

### State transitions

| Transition | Actor | Side effects |
|---|---|---|
| `open → in_progress` | super/platform admin | Set `in_progress_at`, default `assigned_admin_user_id` to actor; insert targeted bell for `requester_user_id` |
| `in_progress → closed` | super/platform admin | Set `closed_at`, `closed_by_user_id`; clear `flow.ps_request_active=false`; insert targeted bell for requester |
| `open → closed` (self-cancel) | requester | Set `closed_at`, `closed_by_user_id=requester`; clear `flow.ps_request_active=false`; insert broadcast bell for super-admin + platform-admin |

`PATCH` body validates the transition is legal for the actor; illegal transitions return 403.

### Webhook payload

```json
{
  "event": "pro_service_quote.submitted",
  "quote_id": "...",
  "org": { "id": "...", "name": "..." },
  "flow": { "id": "...", "name": "...", "url": "https://langflow.example.com/flow/..." },
  "requester": { "id": "...", "email": "..." },
  "estimate": {
    "minutes_low": 180, "minutes_high": 720,
    "rate_low_per_hour": 200.00, "rate_high_per_hour": 200.00,
    "cost_low": 600.00, "cost_high": 2400.00,
    "currency": "USD"
  },
  "headline_summary": "...",
  "narrative": "...",
  "conversation_summary": "..."
}
```

Headers: `X-Langflow-Signature` (HMAC-SHA256 of body, secret from `webhook_secret_encrypted`), `X-Langflow-Event`, `X-Langflow-Timestamp`, `X-Langflow-Delivery`. Reuses existing `worker_app/webhook.py` retry schedule.

## Section 5: Frontend Surfaces

### In-flow (fullscreen builder)

- **Header `Request PS` button** — flow owner / org admin. Disabled with tooltip when `ps_request_active=true`. Opens preview modal.
- **Assistant suggestion card** — rendered inline in chat when `ps_suggestion` SSE event fires. Shows the reason + "Request Professional Services" CTA + dismiss. Same modal target.
- **`<PreviewProposalModal />`** — single component, two entry points. Sections:
  - AI-estimate disclaimer banner (read-only)
  - Hours range (e.g., `180 – 720 minutes` or `3 – 12 hours` based on size)
  - Dollar range (hidden gracefully if both rates NULL)
  - Component breakdown (collapsible)
  - Editable: `headline_summary` (1-line input), `narrative` (textarea), `conversation_summary` (textarea, hidden if null), `org_notes` (textarea)
  - Submit / Cancel

### Home-screen sidebar nav

In `src/frontend/src/components/core/folderSidebarComponent/components/sideBarFolderButtons/index.tsx`, insert a new `SidebarMenuButton` in the `SidebarFooter` *above* the `ENABLE_KNOWLEDGE_BASES` block:

```tsx
<SidebarMenuButton onClick={handleProServiceQuotesNavigation}>
  <ForwardedIconComponent name="HandCoins" /> Pro-Service Quotes
</SidebarMenuButton>
```

Visible to all roles. Clicks route to `/pro-service-quotes`.

### `/pro-service-quotes` list page

Single React component, role-conditional columns.

**Admin view:** `Org name | Price range | Headline summary | Status | Submitted | Open flow`
**Org-member view:** `Flow | Price range | Headline summary | Status | Submitted | Open flow`

- Default filter: `status=open` with toggle to show all
- Admin view also has org filter dropdown
- "Open flow" column: link to `/flow/{flow_id}` if `flow_id` resolves and is accessible
- Click row → detail page

### `/pro-service-quotes/{id}` detail page

Two-column:

- **Left (read-only):** Hours range, dollar range, headline summary, narrative, conversation summary, component breakdown, "Open flow" deep link, status badge
- **Right (editable):** `org_notes` textarea (any org member), `admin_notes` textarea (admins only), status transition buttons:
  - Admin: `Mark in progress` (if `open`), `Close` (if `in_progress`)
  - Org user with `status=open`: `Cancel my request`
- Footer: created by, submitted at, in-progress at, closed at, closed by

### Super-admin Settings tab "Professional Services"

- Default hourly rate low / high (`$/hour` decimal inputs)
- Webhook URL (optional)
- Webhook secret (write-only, masked display, "Rotate" button generates new secret)
- "Test webhook" button → POST to test endpoint, surfaces delivery status inline

### Bell entry rendering

New category `professional_services_request`:
- **On submit (admin audience):** "New Pro-Service request from {org_name}: {headline_summary}"
- **On state change (requester audience):** "Your Pro-Service request is now {status}"
- **On self-cancel (admin audience):** "{org_name} cancelled their Pro-Service request"
- Click → `/pro-service-quotes/{quote_id}`

## Section 6: Implementation Phasing

| Phase | What | Reviewable artifact |
|---|---|---|
| **1. Schema + migrations** | All columns/tables, 15/60 backfill, $200 settings seed, `NotificationAudience.PLATFORM_ADMIN`, `audience_user_id` on `admin_notification` | One alembic revision; `alembic upgrade head` clean on dev DB |
| **2. Preview pipeline** | `POST .../preview`: nodes → minutes sum → rate resolution → LLM call with secret-redaction prompt | Backend tests with stubbed LLM; integration test for cost math |
| **3. Submit + lifecycle + bell + webhook mirror** | `POST .../pro-service-quotes`, `PATCH` for status/notes/assignment, all 3 transitions wired with their bell rows, optional HMAC webhook reuse | Backend integration tests covering all transitions and the dedup-409 path |
| **4. Admin settings + assistant tool** | Settings GET/PUT, test-webhook endpoint, `suggest_professional_services` tool registered + system-prompt guideline | Tool surfaces in assistant SSE; settings round-trip works |
| **5. Frontend: in-flow surfaces** | `<PreviewProposalModal>`, header button, assistant suggestion card driven by `ps_suggestion` event | Click-through demo: header → modal → submit |
| **6. Frontend: home-screen nav + queue UI** | Sidebar entry, list page (admin + org views), detail page with notes panel + transitions, super-admin Settings tab | Click-through demo end-to-end |
| **7. Bell rendering + targeted notifications** | Bell endpoint extended to read both broadcast + targeted rows; copy templates for new category; deep link to detail page | Bell pings on submit and state changes; clicking opens detail |

## Section 7: Out of Scope (v1)

- **Templates-popup entry tile** — no-flow path deferred to v2; would need nullable `flow_id` already in schema, a free-text intake form, and a different LLM prompt path that estimates from description alone
- **Counter-quote workflow** — AI estimate is final in v1; PS contacts the requester out-of-band if real scoping is needed
- **Comments thread** — single notes field per side is sufficient
- **Email / Slack notifications** — in-app bell only
- **Per-component editing of hours metadata in admin UI** — DB-backed but no UI; superuser edits via DB or future tool
- **Customer-visible quote history filters beyond simple status filter**
- **Quote re-open / revival** — once closed, a new request creates a new row

## Section 8: Risks and Open Items

- **LLM latency in preview** — adds ~3–8s. Modal shows skeleton while loading. If problematic, split: cheap math returns immediately, narrative streams in.
- **Component metadata defaults are dumb** — 15/60 will undershoot `Agent`/`LangChain` and overshoot `TextInput`. Real PS team will tune per-component over time. Not a v1 blocker.
- **Bell audience extension is the most invasive piece** — adding `audience_user_id` and broadening the audience enum touches an existing well-traveled query. Keep that change small and well-tested.
- **Multi-tenant Org table** — confirmed committed on `platform-multi-tenant` via migration `6d926936ec2d`. Adding `billable_rate_*` columns is a normal alembic on top.
- **Sub-cent display** — adhere to the existing money-format rule: `$X.XX`, sub-cent positives shown as `<$0.01`.
