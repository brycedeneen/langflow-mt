# Phase 3 — `noImplicitAny: true` flip — deferred

**Date:** 2026-04-24
**Status:** Phase 3 is a multi-session / multi-week project. Pivoted to Phase 4 (test tsc cleanup) for this session. Phase 3 will resume after Phase 4 lands and after Phase 2.* permissive-bake telemetry accumulates.

---

## Baseline measured (this session)

**Production `any` count** (`grep ': any\b\| any\[\]\|<any>\|as any\b' src --exclude-tests`):
- Pre-DTO project: 378
- Post-Phase-2 (today): **370**

Only 8 `any`s eliminated by Phase 2's boundary-validation work. The remaining 370 are mostly in:
- Event handlers (`(e: any) => …`)
- Utility functions in `src/utils/`
- Third-party adapter shims (xyflow, react-query custom processors, axios interceptors)
- Test mocks bleeding into shared helper code

These `any`s are **not** in the API plumbing the boundary wrappers cover — that's already z.infer-derived. So the Phase 1+2 work didn't move this needle, as predicted in the design doc's risk R2.

**Errors under `noImplicitAny: true`** (temporarily flipped, measured, reverted):
- **613 errors total**, broken down:

| Code | Count | What |
|------:|------:|---|
| TS7006 | 277 | Parameter implicitly any |
| TS7031 | 161 | Destructured binding implicitly any |
| TS7053 | 153 | Element implicitly any (object indexing) |
| TS7008 | 10 | Class member implicitly any |
| TS7051 | 6 | Parameter has name no type |
| TS7016 | 6 | Module declaration missing |

Spec predicted 616. Reality: 613. Phase 1+2 didn't reduce this.

## Why Phase 3 is gated

The plan's stated prereq:

> **Phase 3 prereq:** Chunks 2.a–2.h all flipped to strict with zero ValidationError Sentry events for ≥1 week.

We've shipped Phase 2.* in permissive mode minutes ago. Even if every domain were perfectly typed, the bake-then-strict-flip cycle requires real telemetry over real traffic. We have neither yet.

Beyond that prereq, **613 errors is genuinely a multi-week project**. The plan's "~1–2 weeks" estimate was correct; doing it in one session would be reckless. Each TS7006/TS7031/TS7053 fix requires reading the function context to pick a real type (not just `: any` or `: unknown` to silence the compiler — the whole point of the flip is to *prevent* future `any` leak). 277 + 161 + 153 = 591 of these "judgment-required" fixes.

## Path forward

Phase 3 stays in the queue but does not block other work. Order of next steps in this project:

1. **Phase 4 — Test tsc cleanup (237 → 0).** Smaller (237 errors), tractable in this session. Benefits directly from Phase 1+2 z.infer aliases; many fixture-shape errors should evaporate once test fixtures import generated schemas.

2. **Per-domain strict flips (Phase 2.a–2.h).** Schedule each ≥1 week after their respective merge, gated on telemetry. Sentry/overlay must show zero `ValidationError` events for that domain's schema ids. Each flip is its own `feat(types): flip <domain> schemas to strict mode` commit editing `src/frontend/src/schemas/api/generated.meta.ts` and `src/frontend/src/schemas/app/internal/<file>.ts`.

3. **Phase 3 (when ready).** Schedule as a dedicated multi-session project after step 2 is well underway. Use the existing `docs/superpowers/plans/2026-04-19-frontend-typescript-cleanup.md` as a template — error-code-batched commits with explicit gates per batch.

## What to remember when Phase 3 resumes

- `tsconfig.json` flip (`noImplicitAny: false → true`) is the **last** commit in Phase 3, after the 613 fixes land. Don't flip first.
- Per the plan's stop-the-line: escape-hatch budget is 10 total `// @ts-expect-error` or `as unknown as X` justifications across Phase 3.
- The TS7006 and TS7031 batches will dominate. Group by file (work one file at a time, smallest blast-radius first).
- TS7016 (6 fixes) is the easiest batch — each is a `declare module '...'` shim. Could be done as a warm-up commit even before the main batches, to validate the workflow.

Production tsc currently at 0 errors with `noImplicitAny: false`. Don't regress that during Phase 3 work.
