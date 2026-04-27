# Zod 3 → 4 frontend migration — design

**Date:** 2026-04-25
**Branch:** off `platform-multi-tenant`, in a worktree
**Status:** Spec, awaiting plan

## Goal

Bump `zod ^3.25.76` → latest stable `^4.x` across `src/frontend`. Single bundled
migration. Pre-production, so no API or error-message preservation required —
tests just need to pass against zod 4's new shapes.

## Why now

Stay current and avoid further drift before the production cut. No specific
feature blocked on zod 4 today, but the longer this is deferred, the more code
gets written against v3 idioms that will need rewriting.

## Scope

**In scope:** Everything under `src/frontend` that imports `zod`.

**Out of scope:**
- `zod/mini` adoption (bundle-size optimization) — separate initiative
- Tightening `permissive` flags in `src/schemas/api/generated.meta.ts` — separate
  initiative
- Changing the generator-vs-handwritten boundary established by the in-flight
  DTO boundary-types plan
  (`docs/superpowers/specs/2026-04-24-frontend-dto-boundary-types-design.md`)

`zod` is only declared in `src/frontend/package.json`. No other JS package in
the repo (including `src/lfx`) uses it, and the backend is Python.

## Surface area

`grep` snapshot at spec time:

| Bucket | Files | Breaking-change-prone occurrences |
| --- | --- | --- |
| Generated (`src/schemas/api/_generated.ts`) | 1 | ~460 |
| Handwritten schemas (`src/schemas/app/{internal,stream}/*`) | 14 | ~50 |
| Validated-runtime + consumers (queries, lib, stores, components, tests) | 76 | ~0 (mostly imports + error formatting) |
| **Total** | **91** | **~510** |

## Phases

### Phase 0 — Generator probe (≤ 1 hour, throwaway)

Spike on a worktree off `platform-multi-tenant`:

1. Update `openapi-zod-client` to its latest release (currently pinned at 1.18.3).
2. Run `make gen_frontend_schemas` against the current `openapi.json`.
3. Inspect the diff. Specifically check whether the generator now emits:
   - `z.record(K, V)` two-arg form (vs `z.record(V)`)
   - `z.looseObject({...})` (vs `z.object({...}).passthrough()`)
   - `z.strictObject({...})` (vs `z.object({...}).strict()`)
   - `error:` parameter (vs `errorMap:` / `message:` / `invalid_type_error:`)
   - `z.enum(EnumObj)` (vs `z.nativeEnum(EnumObj)`)

**Decision gate:**
- Output already zod-4-clean → skip Phase 1A's post-processor, just adopt the
  newer generator version
- Output emits v3 idioms but only the predictable ones above → Phase 1A
- Output uses APIs zod 4 dropped entirely or in a way regex can't reach → drop
  to Phase 1B (orval swap)

Discard the spike branch; record the decision in this spec or the plan before
doing real work.

### Phase 1A — Post-process generator output (default path)

Extend `src/frontend/scripts/gen-schemas.mjs` step `[3/5]` (the dedup loop)
with a syntactic transform that runs before the file is written. Targeted
rewrites only — covers the patterns the generator actually emits:

- `.passthrough()` → `z.looseObject(...)` (rewrite at the call site, not just
  trailing-method removal — the receiver becomes the argument)
- `.strict()` → `z.strictObject(...)` (same shape transform)
- `z.record(V)` (single argument) → `z.record(z.string(), V)`
- `z.nativeEnum(X)` → `z.enum(X)` (only if Phase 0 confirms generator still
  emits it)

Regex rewrites are sufficient given the generator's predictable output shape;
no AST step needed. Pin `openapi-zod-client` to whatever version Phase 0
settled on; document in the file header alongside the existing
flatten-openapi-defs.py note.

Estimated +50–80 LOC in `gen-schemas.mjs`.

### Phase 1B — Orval swap (fallback only)

If Phase 0 finds the generator emits something Phase 1A can't reach, replace
`openapi-zod-client` with `orval@8.x` in zod-output mode:

- Rewrite `gen-schemas.mjs` to drive orval
- Drop `src/frontend/scripts/flatten-openapi-defs.py` (orval handles
  Pydantic v2 `$defs` natively per the prior tooling-block research)
- Output goes to the same `_generated.ts` path so consumers don't change
- Update `Makefile` target if invocation differs

Estimate per the prior research:
`docs/superpowers/research/2026-04-24-phase-1-tooling-block.md` Option B —
4–6 hours of rework.

### Phase 2 — Bump dependency

- `src/frontend/package.json`: `"zod": "^4.x"` (latest stable at execution time)
- `npm install` (lockfile is `package-lock.json` — repo uses npm, not bun/pnpm)
- No code changes yet; expect `tsc` to fail loudly until later phases

### Phase 3 — Codemod handwritten schemas

Run `nicoespeon/zod-v3-to-v4` (community codemod) over:
- `src/schemas/app/**`
- `src/schemas/index.ts`
- Anything under `src/lib/validated-*.ts` and `src/lib/schema-errors.ts` that
  declares its own schemas (rare but check)

Hand-review the diff. The codemod handles the safe mechanical bits:
`.passthrough()`, single-arg `z.record`, deprecated chained string formats,
`.merge()`. Spot-check `.optional().nullable()` chains (they stay valid but
worth eyeballing).

Do **not** run the codemod against `src/schemas/api/_generated.ts` — that file
is owned by the generator pipeline and Phase 1 already handled it.

### Phase 4 — Manual sweep for nuanced patterns

The codemod can't infer intent for these, so each is a hand-graded find/fix.

| Pattern | Grep | Action |
| --- | --- | --- |
| `.default()` after `.transform()` (silent semantic flip — default applies to *output* in v4) | `\.transform\([^)]*\)\.default\(` | Each hit: keep new behavior or convert to `.prefault()` |
| `.refine((val): val is X => ...)` (type predicates no longer narrow) | `refine.*: \w+ =>` | Replace with `.pipe(z.custom<X>(...))` if narrowing was load-bearing |
| `errorMap` callsites | `errorMap` | → `error:` |
| `error.format()` / `error.flatten()` | `\.format\(\)\|\.flatten\(\)` (within zod-error context) | → `z.treeifyError(error)`; rewrite `src/lib/schema-errors.ts` formatter for the new tree shape |
| `_def` access | `\._def\b` | → `._zod.def` |
| `ZodTypeAny` imports/refs | `ZodTypeAny` | → `ZodType` |
| `z.coerce.X` callers passing typed input | `z\.coerce\.` | Inputs are now `unknown`; type-check will surface call sites |
| `z.nativeEnum` (handwritten only) | `z\.nativeEnum` | → `z.enum` |

### Phase 5 — Build / type-check / test gauntlet

- `npm run type-check` — fix what surfaces. Most likely fallout: `_def` access,
  `ZodTypeAny`, and `z.unknown() / z.any()` properties losing their implicit
  optionality in object shapes.
- `npm run lint` (biome).
- `npm test` (Jest). Update any test that snapshots zod error message strings
  to the new shape. Pre-prod — no obligation to preserve old wording.
- `npm start` — manual smoke covering each runtime that consumes a schema:
  - Build a flow (exercises `validated-named-event-stream`, `buildEvents`)
  - Upload a file (exercises file-management hooks + `validated-fetch`)
  - Open voice assistant (exercises `voice` and `voiceAssistant` schemas)
  - Trigger a validation error (verify `ValidationErrorOverlay` renders)

### Phase 6 — Cleanup

- If Phase 1B was taken, delete `src/frontend/scripts/flatten-openapi-defs.py`
- Re-run `make gen_frontend_schemas` from clean to confirm the pipeline is
  reproducible
- Single bundled commit set on the worktree branch
- Per project memory: do **not** push or PR upstream to `langflow-ai/langflow`

## Risk callouts

- **`.default()` semantic flip is the only landmine that doesn't surface as a
  type or test error.** It's a runtime behavior change. The Phase 4 grep is
  non-negotiable.
- **`z.unknown()` / `z.any()` properties are no longer optional in object
  shapes.** May produce type errors at consumers that expected the `?:` form.
- **`z.uuid()` is now RFC 9562/4122 strict.** If any backend-emitted ID is a
  UUID-like string that isn't formally valid (custom prefixes, etc.), use
  `z.guid()` for permissive. Grep `\.uuid\(\)` in handwritten schemas and
  spot-check a sample payload.
- **Generator output is a moving target.** Phase 0 may surface patterns not in
  the table above. The plan should budget +2 hours for unexpected post-processor
  work.

## Effort estimate

| Phase | Hours |
| --- | --- |
| 0 — Generator probe | 1 |
| 1A — Post-process generator output | 2–3 |
| 1B — Orval swap (fallback) | 4–6 |
| 2 — Bump dependency | <0.1 |
| 3 — Codemod handwritten schemas | 1 |
| 4 — Manual sweep | 3–4 |
| 5 — Build / type-check / test gauntlet | 2–4 |
| 6 — Cleanup | 0.5 |
| **Total (A path)** | **~10–14** |
| **Total (B path)** | **~13–18** |

## Acceptance criteria

- `src/frontend/package.json` declares `zod: ^4.x`
- `make gen_frontend_schemas` runs end-to-end and produces a zod-4-clean
  `_generated.ts`
- `npm run type-check` passes
- `npm run lint` passes
- `npm test` passes
- Manual smoke covering the four flows in Phase 5 shows no schema-validation
  regressions
- No imports of `zod/v3` remain (we are not using a compat-import strangler;
  this is a clean cut)
