# Admin Hardening & UI Cleanup — Design

**Roadmap items covered:** P0-1 (restrict Code button to super admins), P0-2 (remove Share → Embed link)
**Roadmap source:** `2026-04-22-integration-platform-roadmap.md`
**Scope:** Bundled because both are small, unrelated-but-tenant-safety-adjacent UI changes that ship together cleanly.

## Background

### P0-1 — Code button

In the multi-tenant model, `isAdmin` is "org admin" (per-org scope) and `is_superuser` is "platform super admin" (fork-wide). We want custom-component Python authoring restricted to platform super admins only. Today the Code button on the node toolbar is shown to both, and the backend update endpoint is open to any authenticated user.

Relevant code:
- `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx:115-127` — reads `isAdmin` and `userData.is_superuser`; gates the Code button with `hasCode && (isAdmin || !!userData?.is_superuser)`.
- `src/frontend/src/pages/FlowPage/components/nodeToolbarComponent/index.tsx:523-533` — render site.
- `src/backend/base/langflow/api/v1/endpoints.py:1156-1220` — `POST /custom_component/update`, auth via `CurrentActiveUser`. No superuser gate.

### P0-2 — Embed link

The Share dropdown offers an "Embed into site" option that opens a modal rendering an iframe snippet for the chat widget. The roadmap decision is to remove the UI affordance entirely (not hide behind a flag); the broader embed story is deferred to its own future project.

Relevant code:
- `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx:161-169` — Embed menu item, gated on `ENABLE_WIDGET`.
- `src/frontend/src/customization/feature-flags.ts:13` — `ENABLE_WIDGET = true`.
- `src/frontend/src/modals/EmbedModal/embed-modal.tsx` — modal with iframe snippet.
- `src/frontend/src/modals/apiModal/utils/get-widget-code.tsx` — HTML/JS snippet generator.

## Goals

- Only platform super admins can open the Python code editor on a component, both in the UI and via the API.
- The Share menu no longer surfaces an iframe/embed affordance to anyone.
- No dead code left behind by the embed removal.

## Non-goals

- Builder embed with scoped tokens (deferred).
- Removing any backend embed endpoints — leave those intact in case a future embed project reuses them.
- Rearchitecting the broader custom-component auth story.

## Design

### P0-1 — Code button restriction

**Frontend**
- In `nodeToolbarComponent/index.tsx`:
  - Change `canViewCode = hasCode && (isAdmin || !!userData?.is_superuser)` → `canViewCode = hasCode && !!userData?.is_superuser`.
  - Drop the now-unused `isAdmin` from the `useAuthStore` selector to keep the surface clean.
- Any other render site that displays the Code affordance (component header, context menus) gets the same treatment. Audit during implementation — node toolbar is the one we've found; confirm there aren't others via a targeted grep for `"Code"` / `hasCode`.

**Backend**
- `POST /custom_component/update` in `src/backend/base/langflow/api/v1/endpoints.py`: replace the `CurrentActiveUser` dependency with the existing superuser dependency (e.g., `get_current_active_superuser` — confirm exact name during implementation). Non-superusers get 403.
- **Research task during implementation:** grep the API layer for any other endpoint that accepts raw Python component code (by payload field name, e.g., `code`, or by the `UpdateCustomComponentRequest` schema). If such endpoints exist and are reachable from the authoring UI or flow save paths, guard them identically. Document what was found in the plan, not the design.
- **Safety check before merging:** confirm `/custom_component/update` is not called during flow load or component render — only during edit. If it's called during load, we must scope the guard to the "update" path only.

**Approach considered and rejected**
- A feature flag (e.g., `ENABLE_CUSTOM_COMPONENTS_FOR_ADMINS`) — rejected: this is a product-policy decision, not an operational toggle.

### P0-2 — Embed removal

**Deletion list**
- In `deploy-dropdown.tsx`: remove the Embed menu item block (lines 161-169), any `ENABLE_WIDGET` import, and any `setOpenEmbedModal` state + the `EmbedModal` render (the modal component opened from this dropdown).
- Delete `src/frontend/src/modals/EmbedModal/` (component + tests + index).
- Delete `src/frontend/src/modals/apiModal/utils/get-widget-code.tsx` + its tests if the utility is only used by `EmbedModal`.
- Remove `ENABLE_WIDGET` from `customization/feature-flags.ts` if it is used *only* by the deleted code. Grep first — if anything else gates on it, leave it or tighten scope.

**Do not touch**
- Any backend routes or services that serve the chat widget — they stay.

**Approaches considered and rejected**
- Flip `ENABLE_WIDGET = false` — rejected: leaves dead code, contradicts "won't be doable or allowed."
- Delete UI entry but leave modal in place — rejected: creates orphans.

## Testing

**Frontend**
- Unit test for `nodeToolbarComponent`: Code button renders for super admin; does NOT render for org admin; does NOT render for regular member.
- Snapshot/assertion test for `deploy-dropdown`: menu no longer lists "Embed into site" for any role.
- Remove any existing tests that assert the embed menu item exists.

**Backend**
- Unit test for `POST /custom_component/update`: 403 for org admin and regular user, 200 for super admin.
- Integration test: posting valid `UpdateCustomComponentRequest` as non-superuser is rejected even if authenticated.

**Manual verification**
- Log in as each of: super admin, org admin, regular member — confirm Code button visibility and Share menu contents match expectations.

## Migration / rollout

- No DB migrations.
- No feature flag — ships direct. Any org admin currently using custom code loses access immediately; that's the intended behavior.

## Risks

- Existing org admins who relied on Code access lose it silently. Acceptable; if anyone files a ticket, the answer is "intended — use a super admin."
- If `/custom_component/update` is somehow in the flow-load hot path, a 403 there would break flow loading for non-superusers. We verify this is edit-only before merging (see safety check above).
- `ENABLE_WIDGET` flag might gate something we haven't found. Grep-first rule in the implementation plan catches this.

## Open questions / follow-ups

- Are there additional endpoints that accept raw component Python code beyond `/custom_component/update`? Research during implementation.
- Is the Code button surfaced anywhere besides the node toolbar (context menus, a "library" editor, etc.)? Audit during implementation.
