# ADP Assist Flow Builder

**Date:** 2026-04-18
**Status:** Draft

## Overview

A conversational AI flow builder ("ADP Assist") that enables non-technical users to build integrations through natural language chat, without needing to understand the flow builder canvas. Built by extending the existing assistant panel with new layout modes, a simplified test view, enhanced template metadata, and an ADP-specific trigger component.

All users enter through the same flow builder page. Non-technical users stay in the full-screen assistant; technical users use the canvas with the assistant as a side panel. The assistant is opinionated — it makes decisions and confirms them rather than asking the user to configure things.

## Section 1: Assistant Layout Modes

The existing `AssistantPanel` gains two new layout states managed in `assistantStore`.

### Three modes

- **Panel** (existing) — 400px right sidebar on the flow canvas. Toggle button in toolbar. Unchanged.
- **Fullscreen** — assistant overlay covers the entire viewport. The canvas is hidden behind it. Header bar has: ADP Assist branding, "Test" button, "View Canvas" toggle, close/minimize button. "View Canvas" swaps to the canvas with the assistant minimized back to panel mode.
- **Test** — split view within fullscreen. Pipeline view on left, chat on right. Activated by clicking "Test" from fullscreen mode. Pipeline component reads the flow's nodes/edges from `flowStore` and renders a simplified DAG with nested tool grouping.

### State additions to `assistantStore`

- `layoutMode: 'panel' | 'fullscreen' | 'test'`
- `selectedTestComponent: string | null` — node ID the user clicked to test

### Entry points

- "Build with ADP Assist" button in template modal → creates flow, navigates to flow page, sets `layoutMode: 'fullscreen'`
- "Start Building" button → creates flow, navigates to flow page, assistant stays closed (existing behavior)
- Existing toolbar toggle → cycles between panel open/closed (existing behavior)
- Full-screen toggle button added to panel header → switches to `fullscreen` mode

## Section 2: Template Modal Redesign

Changes to the existing `templatesModal/index.tsx`.

### Selection behavior

- Clicking a template card **selects** it (highlighted border, radio dot) instead of immediately creating the flow
- Only one template can be selected at a time
- "Blank Flow" becomes a regular template card in the grid (first card, always visible) instead of a separate button at the bottom

### New state

- `selectedTemplate: FlowType | 'blank' | null` — tracks which template is selected

### Action bar

Bottom of the modal gets three buttons:

- **Cancel** — closes modal
- **Start Building** — creates the flow from selected template (or blank), navigates to canvas. Disabled until a template is selected.
- **Build with ADP Assist** — creates the flow from selected template (or blank), navigates to canvas, opens assistant in fullscreen mode with template context loaded. Disabled until a template is selected.

### Template context loading

- When "Build with ADP Assist" is clicked, the assistant's first message is seeded with context from the template's `agent_instructions` and `agent_summary` fields (from `TemplateMetadata` table)
- If "Blank Flow" is selected, the assistant opens with a generic welcome: "What kind of integration would you like to build?" and uses available template summaries to match the user's request to a template if one fits

## Section 3: Template Metadata Extensions

### TemplateMetadata table

A new database table to store agent-facing metadata for templates, editable at runtime by super admins without a deployment.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `flow_id` | UUID | FK to the starter project/template flow |
| `agent_instructions` | text, nullable | Structured guidance for the assistant: what questions to ask, what fields need customization, common configurations, pre-grouped event defaults |
| `agent_summary` | text, nullable | Rich AI-oriented description for template matching: what the template does, use cases it covers, components it contains |
| `updated_by` | UUID | FK to user who last edited |
| `updated_at` | datetime | Last update timestamp |

### Why a separate table

- Templates are a subset of flows — most flows are user-created and don't need these fields
- Super admin edits to metadata shouldn't mutate the flow record itself (avoids version/audit confusion)
- Clean separation: the flow is the "what", the metadata is the "how the assistant should handle it"

### Super admin UI

- New page under admin settings: "Template Management"
- Lists all templates (starter projects) with their name, description, and current `agent_instructions` / `agent_summary`
- Click a template to edit its metadata in a form with two text areas
- Changes take effect immediately — the assistant reads from this table at conversation start

### API endpoints

- `GET /api/v1/admin/template-metadata` — list all template metadata (requires super admin role)
- `PUT /api/v1/admin/template-metadata/{flow_id}` — update instructions/summary for a template (requires super admin role)

## Section 4: Full-Screen Assistant Experience

### Initial greeting (template selected)

- Assistant receives the template's `agent_instructions` as system context
- Opens with something like: "I've set up a [Template Name] flow for you. Let me ask a few questions to customize it for your needs."
- Follows the instruction-driven question flow (e.g., "Which Slack channel should notifications go to?")

### Initial greeting (blank flow)

- Assistant opens with: "What kind of integration would you like to build?"
- User describes their need in plain language
- Assistant queries `TemplateMetadata.agent_summary` across all templates to find the best match
- If match found: "I found a template for that — [Template Name]. Let me set it up and ask you a few questions." Then loads the template into the flow via flow patches and switches to the template-guided question flow.
- If no match: "I'll build this from scratch. Let me ask a few questions..." and proceeds to add components one by one

### Flow building

- The assistant uses the existing flow-patch SSE mechanism to add nodes and edges
- It makes opinionated choices (picks components, wires them, sets defaults) and confirms with the user rather than asking the user to choose
- Questions are non-technical: "Which Slack channel?", "What info should the message include?", not "Configure the webhook endpoint URL"

### Transition to testing

- Once the flow is assembled, the assistant suggests testing: "Your flow is ready. Want to test the components to make sure everything's connected?"
- If the user agrees, it triggers the switch to test mode (`layoutMode: 'test'`)

### Error handling / credentials

- When a test fails due to missing credentials, the assistant walks the user through it conversationally: "The Slack connection needs an API token. Here's how to get one..." rather than showing a raw config form

## Section 5: Test Mode Pipeline View

A new React component (`FlowPipelineView`) that renders a simplified DAG of the flow.

### Data source

- Reads `nodes` and `edges` from `flowStore`
- Builds a simplified topology: identifies root nodes (no incoming edges), follows edges to build execution order
- Groups tool/input nodes that feed into the same parent (e.g., 3 tools feeding into an agent are nested inside the agent card)

### Rendering rules

- Each node rendered as a card: icon + friendly display name + short description + test status
- Cards connected by simple arrows (`↓`) showing flow direction
- Multi-input nodes (agents with tools, components with multiple inputs) show their inputs as nested sub-items within the parent card, with a "Tools" or "Inputs" label
- Parallel branches (if any) shown side-by-side with a horizontal layout at that level

### Test states per component

| State | Visual | Action button |
|-------|--------|---------------|
| `not_tested` | Gray badge | "▶ Test" |
| `testing` | Spinner animation | — |
| `passed` | Green border + badge | "Re-test" |
| `failed` | Red border + badge with error summary | "Re-test" |

### Interactions

- Click a component card → sets `selectedTestComponent` in store, assistant acknowledges ("Testing [component name]...") and triggers a build of that single node
- "▶ Test All" button → runs the full flow build and updates all statuses
- Test results stream back via the existing SSE connection, assistant narrates the results conversationally
- "View full test output →" link in the chat expands raw output inline

### State additions to `flowStore`

- `componentTestStatus: Record<string, 'not_tested' | 'testing' | 'passed' | 'failed'>`
- `componentTestResults: Record<string, { output: any, error: string | null }>`

## Section 6: ADP Triggers Component

A new Python component extending the webhook pattern.

### Component definition

- Class: `ADPTriggerComponent`
- Display name: "ADP Trigger"
- Category: Same category as existing webhook component

### Inputs

`event_types` — multi-select dropdown with friendly names mapped to ADP event identifiers:

| Friendly name | ADP event identifier(s) |
|---------------|------------------------|
| New Hire | `worker.hire.eventNotify` |
| Rehire | `worker.rehire.eventNotify`, `worker.rehire.eventNotify.subscribe` |
| Retirement | `worker.workAssignment.retire.eventNotify.subscribe` |
| Leave | `worker.onLeave.eventNotify.subscribe` |
| Hire Date Change | `worker.workerOriginalHireDate.change.eventNotify.subscribe` |
| Deceased | `worker.deceased.eventNotify.subscribe` |

Inherits the webhook's `data` input for receiving the raw payload.

### Pre-grouped defaults

Used by the assistant, stored in `TemplateMetadata.agent_instructions` (not hardcoded in the component):

- "Termination" group → selects Retirement + Deceased, assistant confirms: "We've included retirement and deceased events — let me know if we should exclude any."
- "Onboarding" group → selects New Hire, assistant may suggest adding Rehire

### Behavior

- Accepts inbound webhooks like the existing webhook component
- Filters incoming payloads: checks the event type field in the ADP webhook payload against the selected `event_types` — only passes through matching events
- Outputs a structured `Data` object with the ADP event payload parsed into a clean schema

### Output schema

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | string | Friendly name ("New Hire", "Retirement", etc.) |
| `event_id` | string | ADP's event identifier |
| `worker` | dict | Normalized worker data (name, employee ID, department, etc.) |
| `effective_date` | string | When the event takes effect |
| `raw_payload` | dict | Full original ADP payload for advanced users |

## Section 7: Assistant Backend Enhancements

### Template matching

- The assistant's system prompt includes available template summaries from `TemplateMetadata`
- The LLM itself decides which template fits the user's request — no separate embedding/search system
- If a match is found, the assistant loads the template into the flow via the existing flow-patch mechanism

### System prompt extensions

When a flow is created from a template:
- Template's `agent_instructions` from `TemplateMetadata`
- The flow's current node/edge structure
- Available ADP event types and their pre-grouped defaults

When a flow is blank:
- All available template summaries (for matching)
- The full component catalog (for building from scratch)

### Test execution

- New SSE message type: `component_test` — streams test results for individual components
- The assistant can trigger a single-node build (existing build infrastructure supports building individual vertices)
- Test results include: status (pass/fail), output data summary, error message if failed
- The assistant narrates results conversationally based on the raw output

### Conversation context

- The assistant maintains awareness of the flow state throughout the conversation
- When it adds components via patches, those are reflected in subsequent turns
- Template context persists for the full conversation, not just the first message

## Section 8: Flow List Integration

### Flow card changes

- Each flow card gets a small "ADP Assist" icon/button alongside existing edit/delete actions
- Clicking it opens the flow page with `layoutMode: 'fullscreen'` — the assistant loads the existing conversation for that flow
- Clicking the flow name/card itself opens the canvas as normal (existing behavior)

### Flow metadata

- New field on Flow model: `built_with_assist: boolean` — set to `true` when created via "Build with ADP Assist"
- Flows built with assist show the ADP Assist icon more prominently on their card
- All flows show the icon regardless — technical users can also jump into the assistant

## Key Files to Modify

### Frontend
- `src/frontend/src/stores/assistantStore.ts` — new layout mode state
- `src/frontend/src/stores/flowStore.ts` — component test status/results
- `src/frontend/src/modals/AssistantPanel/index.tsx` — fullscreen and test layout modes
- `src/frontend/src/modals/templatesModal/index.tsx` — radio selection, action bar
- New: `src/frontend/src/components/core/flowPipelineView/` — pipeline DAG component
- `src/frontend/src/pages/FlowPage/index.tsx` — assistant layout mode rendering
- `src/frontend/src/types/flow/index.ts` — `built_with_assist` field

### Backend
- `src/backend/base/langflow/services/database/models/flow/model.py` — `built_with_assist` field
- New: `src/backend/base/langflow/services/database/models/template_metadata/model.py` — TemplateMetadata table
- New: `src/backend/base/langflow/api/v1/admin/template_metadata.py` — admin API endpoints
- New: `src/lfx/src/lfx/components/adp/adp_trigger.py` — ADP Trigger component
- Assistant API — system prompt extensions, component_test SSE message type
