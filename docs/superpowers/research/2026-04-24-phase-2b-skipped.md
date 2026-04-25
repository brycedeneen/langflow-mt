# Phase 2.b — skipped (no Zustand persist usage)

**Date:** 2026-04-24
**Status:** Phase 2.b is **N/A for this codebase**. Storage validation infrastructure ships from Phase 0 and remains available; no current call sites to migrate.

---

## What the plan assumed

Phase 2.b (per `docs/superpowers/plans/2026-04-24-frontend-dto-boundary-types.md`) called for wrapping every Zustand `persist` middleware with `validatedStorage` so localStorage drift across app upgrades surfaces as a `ValidationError` rather than silently rendering corrupted state. The migration pattern was to find each `persist((set, get) => ({...}), { name, storage: createJSONStorage(...) })` block and swap the storage adapter.

## What I found

This codebase has **zero** Zustand `persist` middleware usage:

```bash
grep -rln "from \"zustand/middleware\"" src/frontend/src
# (no results)

grep -rln "persist(" src/frontend/src
# (no results)

grep -rln "createJSONStorage" src/frontend/src
# (no results)
```

What IS in the stores is hand-rolled `localStorage.getItem` / `setItem` calls on primitive values:

- `darkStore.ts` — `localStorage.getItem("isDark")` (boolean as string), `getItem("githubStars")` (number as string), `getItem("githubStarsLastUpdated")` (timestamp).
- `flowStore.ts` — `localStorage.setItem(`dismiss_${flowId}`, JSON.stringify([string, string, ...]))` (per-flow string arrays); `getItem("inspectionPanelVisible")` (boolean as string).
- `authStore.ts` — only `removeItem` for token cookies on logout.
- `validationErrorStore.ts` (added in Phase 0.8) — `sessionStorage.getItem("dto.mutedSchemaIds")` for the muted-schema list, already wrapped in inline try/catch.

None of these are slice-shaped JSON that benefits from schema validation. They're either:

1. **Boolean/number/string values** stringified for storage — schema overhead is silly; a `=== "true"` check is the right tool.
2. **JSON arrays of strings** namespaced per-key (`dismiss_${flowId}`) — too dynamic to register a schema id per key.

## Why this is fine

`validatedStorage` (in `src/frontend/src/lib/validated-storage.ts`, landed in Phase 0.5) is correct code with full unit-test coverage. It ships into the codebase and stays available. The day someone adds a Zustand `persist`-managed slice, the wrapper is ready for them.

But there's nothing to migrate today. Forcing the wrapper onto primitive `localStorage.getItem("isDark")` calls would be ceremony without protection — the existing inline guards (e.g. `localStorage.getItem("isDark") === "true"`) already enforce the only invariant that matters.

## What changes in the plan

`docs/superpowers/plans/2026-04-24-frontend-dto-boundary-types.md` Phase 2.b should be re-marked **N/A** with this note. The merge-train count drops from 11 to 10. The total project budget shrinks correspondingly (~3-5 days less).

If a future Zustand-`persist` slice is ever added — for example, persisting a logged-in user's flow filter preferences — a separate Phase 2.b1 spec can rev the wrapper into use at that point.

## What's next

Phase 2.c — templates. Same migration pattern as Phase 2.a (flows), targeting `src/controllers/API/queries/templates/` and the corresponding generated schemas under `api.templates.*`.
