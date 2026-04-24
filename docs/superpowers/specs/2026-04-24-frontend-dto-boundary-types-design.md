# Frontend DTO / Boundary-Types Design

**Date:** 2026-04-24
**Author:** brycedeneen (with Claude)
**Status:** Approved — ready for implementation plan

---

## Goal

Eliminate `: any` in the frontend by making every value that crosses a boundary — HTTP response/request, persisted storage, realtime (SSE/WebSocket) — parse through a zod schema generated from the backend OpenAPI spec, with per-schema parse mode that starts permissive and flips to strict per domain as migration lands.

The project is the foundation that makes a future `noImplicitAny: true` flip non-hacky: downstream types (React props, Zustand stores, react-query return shapes) derive from `z.infer<typeof FooSchema>`, so tightening the compiler flag doesn't cascade into hundreds of `as any` escape hatches.

## Non-goals

- Full OpenAPI → typed client (zodios replacement path).
- Rewriting react-query hooks or axios interceptors.
- Class-based DTOs with methods.
- URL-params validation (`useSearchParams` → schema). Deferred.
- `postMessage` validation. Deferred.
- Property-based tests (fast-check + zod). Follow-up.
- Backend Pydantic refactors. If OpenAPI fidelity is lossy, we override on the frontend or open a narrow backend ticket — not scope here.
- Performance optimization of zod parsing. Revisit only if profiling shows a hot path.
- Cross-project validation library standardization (backend, docs, other frontends). Scoped to `src/frontend/`.

## Standing constraints

- **Worktree.** All work lands in `.worktrees/dto-boundary-YYYY-MM/` on branch `dto/boundary-types-YYYY-MM`, branched from `platform-multi-tenant`. No edits in the main worktree until final merge.
- **No upstream PR.** All work merges back to local `platform-multi-tenant`, never to `langflow-ai/langflow`.
- **No git commits without explicit approval.** Every commit step in the downstream plan must pause and ask.
- **Stage explicit paths.** Never `git add -A` / `git add .` / `git commit -a`; the repo carries unrelated WIP.
- **Jest, not Vitest.** Frontend unit tests run with `npm run test` (jest).

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────┐
│  React components / pages (consume inferred types)      │
├─────────────────────────────────────────────────────────┤
│  React-Query hooks (src/controllers/API/queries/*)      │
│    unchanged public API; internals now call wrapper     │
├─────────────────────────────────────────────────────────┤
│  validatedQueryFn(schema, axios-call)  ◄── NEW          │
│    calls axios → schema.safeParse/parse → typed data    │
├─────────────────────────────────────────────────────────┤
│  axios instance (unchanged)                             │
├─────────────────────────────────────────────────────────┤
│  HTTP                                                   │
└─────────────────────────────────────────────────────────┘

        Parallel boundaries, each with its own wrapper:

  Zustand `persist`  ──►  validatedStorage(schema, storage)
  SSE/EventSource    ──►  validatedEventStream(schema, url)
  WebSocket          ──►  validatedSocket(schema, socket)

                Schema registry (strict flag)
                  ────────────────────────
                  api.flows.getFlow       strict:true
                  api.templates.list      strict:false  (migrating)
                  storage.flowsSlice      strict:false
                  stream.buildEvents      strict:false
```

**Four new building blocks:**

1. `src/schemas/` — zod schemas. Two subfolders:
   - `api/` — generated from OpenAPI, one file per tag, plus `_overrides/`.
   - `app/` — hand-written: persisted slices (`storage/`), stream messages (`stream/`), plus reserved `urlParams/` for a later chunk.
2. `src/lib/validated-fetch.ts` — `validatedQueryFn`, `validatedMutationFn`, `parseResponse`. ~80 lines. Imports zod, reads the strict-flag registry, logs to Sentry on failure.
3. `src/lib/validated-storage.ts` — persist-middleware shim for Zustand; validates on hydrate, discards corrupt state in strict mode, logs.
4. `src/lib/validated-stream.ts` — SSE/WS message validator; attaches to existing `EventSource` / `WebSocket` creation points.

**What does NOT change:**

- axios instance, interceptors, auth headers, retry logic.
- Every existing `useGetX` / `usePostX` hook keeps the same name, same file, same return shape.
- `src/types/*` files stay on disk throughout the migration; they gradually become thin re-exports of `z.infer<typeof FooSchema>` as each domain lands.

**Core invariant:** at any point between Chunk 0 and Chunk 4, the app compiles, tests pass, and production boots. No big-bang checkpoints.

---

## Library + tooling

### Runtime

- **`zod`** (v3.x current stable). ~13KB min+gz. Single dependency.

### Generator

- **`openapi-zod-client`** in **schemas-only mode** (`--output-type schemas`). We want the generated `z.object(...)`s, not its client — the client layer is our own `validatedQueryFn` wrapper over axios.
- *Rejected:* `orval` (too opinionated, wants to own the client), `zodios` (overlaps Q4 choice), hand-writing (drift).

### Generation pipeline

New Makefile target, `make gen-frontend-schemas`:

1. Start backend in a temp venv, pull `/openapi.json` (or reuse an existing `make frontend_openapi`-like target if one exists; confirm in Chunk 0).
2. Run `openapi-zod-client openapi.json --output src/frontend/src/schemas/api/generated.ts --output-type schemas-only`.
3. Post-process script:
   - Split the single generated file into one file per OpenAPI tag (flows, templates, messages, …).
   - Inject the strict-flag registry import at the top of each generated file.
   - Run Biome format.
4. CI: same target runs on every backend schema change; `git diff --exit-code src/frontend/src/schemas/api/` fails the build if checked-in schemas are stale.

**Generated schemas are committed to git.** Not build-time codegen.

**Alternatives considered + rejected:**
- **valibot:** smaller bundle; mature OpenAPI → valibot generator is experimental. Revisit after zod 4 (tree-shakable imports).
- **ArkType:** great inference; ecosystem lags on react-query adapters and OpenAPI generators.
- **io-ts / runtypes / superstruct:** less active, fewer adapters.

**Risk:** the spec contains ~150 endpoints; the splitting post-process keeps any one generated file under ~500 lines.

---

## Directory layout

```
src/frontend/src/
├── schemas/
│   ├── api/
│   │   ├── generated.meta.ts         # strict-flag registry + version stamp
│   │   ├── flows.ts                  # generated, post-split
│   │   ├── templates.ts
│   │   ├── messages.ts
│   │   ├── users.ts
│   │   ├── organizations.ts
│   │   └── ... (~15 files, one per OpenAPI tag)
│   │   └── _overrides/
│   │       └── flows.ts              # hand-curated refinements, imported by flows.ts
│   ├── app/
│   │   ├── storage/
│   │   │   ├── flowsSlice.ts
│   │   │   ├── authSlice.ts
│   │   │   └── darkSlice.ts
│   │   ├── stream/
│   │   │   ├── buildEvents.ts        # SSE message discriminated union
│   │   │   └── chatMessages.ts
│   │   └── urlParams/                # reserved for later chunk
│   └── index.ts                      # barrel; re-exports both trees
└── lib/
    ├── validated-fetch.ts
    ├── validated-storage.ts
    ├── validated-stream.ts
    ├── schema-registry.ts
    └── schema-errors.ts
```

---

## API wrapper design

### Strict-flag registry

Central to the permissive → strict migration. Flipping a domain to strict = editing one file.

```ts
// src/lib/schema-registry.ts
type Mode = "permissive" | "strict";

const registry = new Map<string, Mode>();

export function registerSchema(id: string, mode: Mode) { registry.set(id, mode); }
export function getMode(id: string): Mode { return registry.get(id) ?? "permissive"; }
```

At boot, `src/schemas/api/generated.meta.ts` populates the registry from a single declarative table:

```ts
export const SCHEMA_MODES: Array<[string, "permissive" | "strict"]> = [
  ["api.flows.getFlow",   "strict"],
  ["api.templates.list",  "permissive"],
  ["storage.flowsSlice",  "permissive"],
  ["stream.buildEvents",  "permissive"],
  // ...
];

SCHEMA_MODES.forEach(([id, mode]) => registerSchema(id, mode));
```

Default-default is permissive; any schema added without an entry is safe (non-throwing).

### `validatedQueryFn`

```ts
// src/lib/validated-fetch.ts (sketch)
export function validatedQueryFn<TSchema extends z.ZodTypeAny>(
  id: string,
  schema: TSchema,
  call: () => Promise<unknown>,
): () => Promise<z.infer<TSchema>> {
  return async () => {
    const raw = await call();
    const mode = getMode(id);
    const result = schema.safeParse(raw);
    if (result.success) return result.data;

    reportParseFailure({ id, mode, error: result.error, raw, boundary: "http" });
    if (mode === "strict") throw new ValidationError(id, result.error, "http");
    return raw as z.infer<TSchema>;
  };
}

export function validatedMutationFn<TReq, TRes>(
  id: string,
  reqSchema: z.ZodType<TReq>,
  resSchema: z.ZodType<TRes>,
  call: (body: TReq) => Promise<unknown>,
): (body: TReq) => Promise<TRes> { /* same pattern; validates both req and res */ }
```

### Call-site migration

Two-line diff per hook. Before:

```ts
export const useGetFlow = (id: string) =>
  useQuery({
    queryKey: ["flow", id],
    queryFn: () => api.get(`/api/v1/flows/${id}`).then(r => r.data),
  });
```

After:

```ts
import { FlowSchema } from "@/schemas/api/flows";
import { validatedQueryFn } from "@/lib/validated-fetch";

export const useGetFlow = (id: string) =>
  useQuery({
    queryKey: ["flow", id],
    queryFn: validatedQueryFn(
      "api.flows.getFlow",
      FlowSchema,
      () => api.get(`/api/v1/flows/${id}`).then(r => r.data),
    ),
  });
```

Hook return type is unchanged — `z.infer<typeof FlowSchema>` is identical to the existing `Flow` export once `src/types/flow/index.ts` becomes a re-export.

---

## Storage validation (Zustand persist)

Existing pattern: `persist((set, get) => ({ ... }), { name: "flows-storage", storage: createJSONStorage(...) })`. Stale localStorage survives app upgrades and schemas drift silently.

```ts
// src/lib/validated-storage.ts
export function validatedStorage<T>(id: string, schema: z.ZodType<T>, base = localStorage) {
  return {
    getItem: (key: string) => {
      const raw = base.getItem(key);
      if (raw === null) return null;
      let parsed: unknown;
      try { parsed = JSON.parse(raw); } catch { return null; }
      const result = schema.safeParse(parsed);
      if (result.success) return JSON.stringify(result.data);
      reportParseFailure({ id, mode: getMode(id), error: result.error, raw: parsed, boundary: "storage" });
      if (getMode(id) === "strict") { base.removeItem(key); return null; }
      return raw;
    },
    setItem: base.setItem.bind(base),
    removeItem: base.removeItem.bind(base),
  };
}
```

Call-site migration:

```ts
persist(..., {
  name: "flows-storage",
  storage: createJSONStorage(() => validatedStorage("storage.flowsSlice", FlowsSliceSchema)),
})
```

Corrupt data in strict mode → slice initializes from defaults (safer than booting with garbage). Permissive → pass through + Sentry breadcrumb.

Slice schemas are hand-written in `schemas/app/storage/*`. No OpenAPI source for "what's in a Zustand slice." Co-located under `schemas/app/storage/` (not next to the store file) so there's one place to audit what survives upgrades.

---

## Realtime validation (SSE / WebSocket)

Langflow uses `EventSource` for `/api/v1/build/{flow_id}/stream` and chat message streams. Current code does `JSON.parse(event.data)` with no validation.

```ts
// src/lib/validated-stream.ts
export function validatedEventStream<T>(
  id: string,
  schema: z.ZodType<T>,
  source: EventSource,
  onMessage: (msg: T) => void,
  onInvalid?: (raw: unknown, err: z.ZodError) => void,
) {
  source.onmessage = (event) => {
    let raw: unknown;
    try { raw = JSON.parse(event.data); }
    catch (parseErr) {
      // Malformed JSON can't produce a ZodError; surface a synthetic one so callers
      // have a uniform shape to react to. Parser treats it the same as shape-mismatch.
      const synthetic = new z.ZodError([{
        code: "custom", path: [], message: `Invalid JSON: ${(parseErr as Error).message}`,
      }]);
      return onInvalid?.(event.data, synthetic);
    }
    const result = schema.safeParse(raw);
    if (result.success) return onMessage(result.data);
    reportParseFailure({ id, mode: getMode(id), error: result.error, raw, boundary: "stream" });
    if (getMode(id) === "permissive") onMessage(raw as T);
    else onInvalid?.(raw, result.error);
  };
}
```

Stream message shapes are **discriminated unions** — e.g. `BuildEventSchema = z.discriminatedUnion("type", [VertexStartSchema, VertexEndSchema, ErrorSchema, ...])`. Post-migration, `msg.type === "vertex_build"` narrows `msg.data` without hand-written guards.

Hand-written in `schemas/app/stream/*` (FastAPI's OpenAPI doesn't fully describe SSE event payloads).

**WebSocket** follows the same pattern parameterized over `WebSocket` instead of `EventSource`. Langflow's current WS usage is narrow (chat, polling fallbacks); ~1–2 call sites.

---

## Error handling and observability

### Single `ValidationError` type

```ts
class ValidationError extends Error {
  readonly id: string;                    // "api.flows.getFlow"
  readonly zodError: z.ZodError;
  readonly boundary: "http" | "storage" | "stream";
  // .toString() → "ValidationError [api.flows.getFlow] at data.nodes[2].id: expected string, got undefined"
}
```

No per-boundary subclasses. `boundary` is a field; call sites use `err.boundary === "http"` when they need to branch (currently no consumers do).

### `reportParseFailure`

Single choke-point. Every wrapper calls it. Three destinations:

1. **Console** (dev only): full zod error with path + expected/actual; tagged with schema id for grep-filtering.
2. **Sentry** (prod + preview): `captureMessage`-level event with `fingerprint = [id, top-level-zod-path]` so one schema drift = one Sentry issue. Tags: `boundary`, `mode`, `schema_id`. Raw payload attached as breadcrumb, truncated to 10KB.
3. **React-Query error state** (HTTP only, strict mode only): `ValidationError` throws out of `queryFn` → existing `ErrorList` / `useAlertStore` surfaces it. No new error UI.

**Dedup:** identical `(id, top-level-zod-path)` pairs within a 60-second window are suppressed before hitting Sentry. Client-side, stateless. Prevents one broken polling endpoint from generating one Sentry event per second.

### Admin-only diagnostic overlay

A `<ValidationErrorOverlay />` component mounted once in `App.tsx` at root.

**Visibility rule:**

```
visible ↔ authStore.isAdmin === true OR authStore.isPlatformAdmin === true
```

All `MembershipRole` values (`owner | admin | member | operator | viewer`) get nothing new — the existing toast still surfaces errors so nobody's staring at a broken screen; they just don't get the detailed overlay.

**Features:**
- Full path list (toasts truncate).
- Raw payload side-by-side with the zod error.
- Click-to-copy raw payload.
- "Mute this schema for the session" button (state in `sessionStorage`, not `localStorage` — re-mutes don't carry across sessions, preventing admins from silently skipping fresh regressions).

**Implementation detail:** component early-returns `null` before subscribing to the validation-error store, so organization users pay zero runtime cost.

**Backend dependency — resolved.** `UserRead` (`src/backend/base/langflow/services/database/models/user/model.py:88`) has `is_platform_admin: bool`, and `/api/v1/auth/session` returns `SessionResponse(user=UserRead)` — so the field is already on the wire on every session check. The frontend's current `SessionResponse` type (`src/frontend/src/controllers/API/queries/auth/use-get-auth-session.ts:7-17`) has `[key: string]: any` as an escape hatch that is very likely masking `is_platform_admin` today.

Chunk 0 therefore has a deterministic three-step task (no backend work, no conditional path):
1. Replace `SessionResponse` type with `z.infer<typeof SessionResponseSchema>` (schema hand-written in `schemas/app/auth/session.ts` because `/auth/session` has `include_in_schema=False` — see §OpenAPI-hidden endpoints).
2. Add `isPlatformAdmin: boolean` to `AuthState` in `src/frontend/src/stores/authStore.ts`, mirror the existing `isAdmin` pattern.
3. Set it in the session-response handler from `session.user.is_platform_admin`.

**Production behavior:** overlay ships in prod too (not dev-only), gated on role. Value asymptotes after Chunk 3; reevaluate at Chunk 3 exit whether to keep, hide behind `?debug=1`, or remove.

**Non-goal:** overlay is not a replacement for Sentry. Sentry = cross-session record; overlay = in-the-moment diagnostic.

---

## Migration phases

Each chunk = own plan + own merge train to `platform-multi-tenant`. Chunks 2.a–2.g can reorder based on priorities at start of Chunk 2.

### Chunk 0 — Foundation (walking skeleton, ~1 week)

Prove the pattern end-to-end on one endpoint.

**Deliverables:**
- `zod`, `openapi-zod-client` added to `package.json`.
- `make gen-frontend-schemas` target + post-processing script.
- `src/schemas/api/generated.meta.ts` with empty strict-flag registry.
- `src/lib/validated-fetch.ts` (+ `schema-registry.ts` + `schema-errors.ts`).
- `src/lib/validated-storage.ts` + `validated-stream.ts` — skeletons only, one unit test each.
- `src/components/common/ValidationErrorOverlay/` — mounted at App root, admin-gated.
- `authStore.isPlatformAdmin` + `use-get-auth-session` wiring (or risk-flag if backend doesn't carry it).
- Sentry adapter in `reportParseFailure`.
- **One endpoint migrated end-to-end**: `GET /api/v1/flows/{id}` via `useGetFlow`. Permissive mode, registered in meta.
- Unit tests on wrapper happy/sad paths (strict-throw, permissive-pass-through, dedup window).
- Docs: `docs/frontend/validation-wrapper.md` — the two-line migration recipe downstream chunks copy.

**Gates:** tsc clean; `npm test` green; prod build clean; dev server boots; Sentry receives a synthetic `ValidationError` from a test button; overlay renders for admin user, invisible for a `member`.

**Not in scope:** migrating any other endpoint, touching real storage/streams, flipping any flag to strict.

### Chunk 1 — Generate + hand-write schemas for every endpoint (~1 week)

Run the generator across the full OpenAPI spec; hand-write schemas for the 34 OpenAPI-hidden endpoints; commit the result; no call-site changes.

**Deliverables:**
- `make gen-frontend-schemas` emits one file per OpenAPI tag under `src/schemas/api/*`.
- Hand-written schemas for all 34 `include_in_schema=False` endpoints under `src/schemas/app/internal/` (one file per router tag-equivalent: `auth.ts`, `apiKey.ts`, `variables.ts`, `store.ts`, `voice.ts`, `models.ts`, `modelOptions.ts`, `validate.ts`, `chatInternal.ts`). Sourced by reading each router's Python route definitions + response_model types.
- All schemas (generated + hand-written) registered in `generated.meta.ts` with default **permissive** mode.
- CI job: `make gen-frontend-schemas && git diff --exit-code` fails on stale generated schemas. Hand-written schemas have a smaller CI guard: a Python lint that fails if a router gains a new `include_in_schema=False` route that isn't represented in `src/schemas/app/internal/`.
- `_overrides/` scaffolded with a README; empty unless Chunk 1 discovery finds lossy OpenAPI that needs hand-curation.

**Gates:** tsc clean; `npm test` green; prod build clean; generator idempotent (two runs → no diff).

**Sub-scope expansion:** because the 34 internal endpoints include foundational ones (`/auth/session`, `/auth/login`, `/auth/refresh`, `/api_key/*`, `/variables/*`), they'll be covered by Chunks 2.f (auth/users) and a new **Chunk 2.h — internal (variables, api-keys, store, voice, models)**. Added to the phase table below.

### Chunks 2.a–2.g — Migrate by domain (~1 week each)

Ordered worst-offender-first to retire the most `any`s per chunk. Confirm order from a fresh `any` count at start of Chunk 2.

| Order | Domain | Why here |
|---|---|---|
| 2.a | **flows** (`useGetFlow`, `useGetFlows`, builds, versions) | Touches the most components; biggest `any` reduction; unblocks `flowStore` migration. |
| 2.b | **store-hydration** (Zustand persisted slices) | Natural follow-on; `flowStore` hydrates from persisted state. |
| 2.c | **templates** | Recently shipped; drift risk noted in memory (`project_template_management_state.md` FU-1..FU-6). |
| 2.d | **messages + chat** | Heavy downstream consumers (ChatView, InspectionPanel). |
| 2.e | **streaming / SSE** (`buildEvents`, chat stream) | Pairs naturally with messages. |
| 2.f | **users + organizations + memberships + auth** | Admin surfaces; smaller blast radius. Includes hand-written `/auth/session`, `/auth/login`, `/auth/refresh`, `/auth/logout`. |
| 2.g | **long tail — public** (MCP, files, tweaks, alerts, metadata) | Small public endpoints. |
| 2.h | **long tail — internal** (variables, api-keys, store, voice, models, model_options, validate) | The OpenAPI-hidden endpoints from §Chunk 1. Last because they're all small and isolated. |

**Per-chunk pattern:**

1. List every call site under the domain via grep.
2. Swap `queryFn` / `mutationFn` bodies to use the wrapper (two-line diff each).
3. Replace domain `src/types/<domain>/index.ts` exports with `z.infer<typeof FooSchema>` re-exports.
4. Fix tsc errors cascading from (3) — where hidden `: any` becomes typed and some call sites need narrowing.
5. Watch Sentry for 1 week under real traffic. "Quiet" = zero `ValidationError` events for that domain's schema ids. If any fire, triage the cause (backend drift → backend fix; schema bug → frontend fix) and reset the 1-week clock.
6. Flip the domain's schemas to `strict` in `generated.meta.ts`.
7. Gate, merge.

**Stop-the-line:** if >10 call sites need non-trivial code changes beyond the two-line wrapper swap, stop and reassess — the domain may need its own sub-spec.

### Chunk 3 — Flip `noImplicitAny: true` (~1–2 weeks)

**Prereqs:** Chunks 2.a–2.h all flipped to strict with zero `ValidationError` Sentry events across their schema ids for ≥1 week.

**Deliverables:**
- `tsconfig.json` → `"noImplicitAny": true`.
- Re-snapshot tsc errors. The 616 the prior cleanup spec predicted should be dramatically reduced — most were inferred-any from `any` in API types. Expected after Chunk 2: **~150–250 residual production errors**, almost all in utility functions, event handlers, and third-party adapters.
- Batch-fix residuals, same "one error code per commit" pattern as the prior production cleanup (`2026-04-19-frontend-typescript-cleanup.md`).

### Chunk 4 — Test tsc cleanup (~2–3 days)

**Goal:** close the 235 → 0 test-error loop.

**Prereqs:** Chunk 3 done.

Most test errors are fixture-shape drift. Once domain types derive from schemas, fixtures authored as `FlowSchema.parse({...})` self-update when backend evolves. Doing this last means most errors evaporate before we touch them.

### Totals

- **~8–10 weeks** focused work end-to-end (up from initial 7–9 because Chunk 1 now also produces hand-written schemas for the 34 OpenAPI-hidden endpoints, and a new Chunk 2.h absorbs the internal-endpoint migration).
- **11 merge trains:** Chunk 0, 1, 2.a–h, 3, 4.
- Each chunk independently shippable; can pause between any two without regression.

---

## Testing strategy

### Wrapper unit tests (Chunk 0 deliverables)

- `validatedQueryFn`: happy path; permissive-bad-shape returns raw + calls reporter; strict-bad-shape throws `ValidationError` + calls reporter; dedup window suppresses identical errors within 60s.
- `validatedStorage`: unknown JSON → null; permissive-bad-shape passes through; strict-bad-shape clears key + returns null; malformed JSON → null.
- `validatedEventStream`: same three axes.
- `ValidationErrorOverlay`: renders for `isAdmin` and `isPlatformAdmin`; returns `null` for all `MembershipRole` values; mute persists in `sessionStorage` not `localStorage`.

### Fixture strategy across the migration

- Test fixtures migrate as each domain does. `FlowSchema.parse({ ... })` at the top of a test replaces hand-rolled `as Flow` casts. When schemas evolve, TS flags every drifted fixture.
- `src/test-utils/fixtures.ts`: `makeFixture(schema, overrides)` generates a valid instance (via `zod-mock` or hand-written defaults), then `Object.assign`s overrides. Authored in Chunk 0.

### E2E (Playwright)

Unchanged. Schemas parse real network traffic in e2e runs; backend drift first visible there. No new Playwright scaffolding.

---

## Risks

1. **Backend OpenAPI fidelity.** FastAPI emits great OpenAPI when Pydantic models are used end-to-end. Endpoints returning raw `dict` or `Response(content=json.dumps(...))` lose shape info. Chunk 1 discovery surfaces these; each needs a backend fix or a hand-curated override in `_overrides/`. Estimate: 5–15 endpoints. Logged as Chunk 1 risk, not a blocker.
2. **`noImplicitAny` residual surprise.** ~150–250 residual estimate for Chunk 3 assumes "API-inferred-any is the majority source." Could be higher if deep call-chain any-flow is larger than expected. Chunk 3 spec re-measures baseline before committing to a timeline.
3. **OpenAPI-hidden endpoints drift.** 34 endpoints use `include_in_schema=False`; their schemas are hand-written and could go stale vs. the backend without automated detection. Mitigation: a Python lint in CI that fails if a router adds a new `include_in_schema=False` route lacking a corresponding entry in `src/schemas/app/internal/`. Does not catch response-shape changes on existing endpoints — those still rely on human diligence + `ValidationError` telemetry in permissive mode before strict flip.
4. **Zustand v5 + `validatedStorage` interaction.** V5 snapshot-equality landmines (`project_zustand_v5_migration.md`) are orthogonal to storage adapters, but Chunk 2.b verification step explicitly re-runs store tests looking for render-loop regressions.
5. **Generated-file churn in code review.** One-file-per-tag splitting helps; `git diff` on a regen should still be legible. CI's `git diff --exit-code` gate keeps stale files out.

---

## Open questions for the implementation plan

- Does an existing `make frontend_openapi` or similar target produce `openapi.json`, or does Chunk 0 need to build one?
- Confirm Sentry DSN / config path in frontend — `reportParseFailure` should reuse the existing Sentry client, not initialize a parallel one.
