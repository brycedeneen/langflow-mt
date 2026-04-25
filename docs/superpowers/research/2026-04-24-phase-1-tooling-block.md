# Phase 1 tooling block — `openapi-zod-client` + Pydantic v2 incompatibility

**Date:** 2026-04-24 (later in same session as `2026-04-24-phase-1-prep.md`)
**Status:** **Phase 1 blocked.** Decision needed before resuming.

---

## TL;DR

`openapi-zod-client@1.18.3` (latest, the library the plan committed to) **cannot generate** from this codebase's OpenAPI spec without significant pre-processing. The root cause is fundamental — Pydantic v2 emits OpenAPI 3.1 with nested `$defs` blocks that the generator's underlying ref-parser doesn't resolve.

I tried two pre-processing approaches before stopping. Both failed differently. The second nearly worked but uncovered an orphan `JobStatus` ref in v2/workflows that suggests broader brittleness.

We need a tooling decision before Phase 1.2 (gen-schemas.mjs) can be written.

---

## What works (already committed, no rollback needed)

- `cd2dd3f98a` — spec + plan
- Phase 0 (10 commits, merged as `ba3a61ce67`) — all wrappers, overlay, walking skeleton, recipe doc
- `cbab605abf` — research doc
- `549e43c56d` — plan housekeeping (Phase 1 budget bump, 14-router list, dedupe pseudocode)
- `855054730b` — `make openapi_json` + `make gen_frontend_schemas` Makefile targets

The first three Phase 0 deliverables (validation wrappers, store/stream shims, overlay) are unaffected by this discovery. They work against any schema, regardless of how schemas are produced.

---

## What I tried

### Attempt 1 — vanilla generator call

```bash
npx openapi-zod-client scripts/openapi.json --output /tmp/client.ts --export-schemas --group-strategy tag-file
```

**Failed:** `MissingPointerError: Token "$defs" does not exist.`

The generator's underlying parser is `@apidevtools/json-schema-ref-parser`, which doesn't understand JSON Schema 2020-12's `$defs` keyword. FastAPI ≥0.99 + Pydantic v2 emits OpenAPI 3.1 with `$defs` everywhere.

### Attempt 2 — rename `$defs` → `definitions`

```python
# Walk the spec, rename "$defs" → "definitions" and "#/$defs/X" → "#/definitions/X"
```

**Failed:** `MissingPointerError: Token "definitions" does not exist.`

The renaming created `definitions` blocks at the same nested location they came from (inside individual schemas under `components.schemas.SomeModel`). The refs are document-root-relative (`#/definitions/X`), but the actual `definitions` lives nested. The parser only resolves refs against the document root.

### Attempt 3 — flatten `$defs` into `components/schemas`

```python
# For each schema in components/schemas with a nested $defs:
#   - Lift each entry out as components/schemas/{parent}__{child}
#   - Rewrite refs accordingly
```

**Partially worked:** flattened 188 schemas, 0 remaining root-level `$defs` refs. But the generator still failed:

```
MissingPointerError: Token "JobStatus" does not exist.
```

Why? Three remaining `$defs` blocks live in **path response inline schemas**, not in `components/schemas`:

```
paths./api/v2/workflows.post.responses.200.content.application/json.schema.oneOf[0].$defs
paths./api/v2/workflows.post.responses.200.content.application/json.schema.oneOf[1].$defs
paths./api/v2/workflows.get.responses.200.content.application/json.schema.$defs
```

`JobStatus` only exists inside one of those nested `$defs` blocks. To resolve it, we'd need to extend the flattener to walk the `paths` tree too, lift inline schemas into `components.schemas`, and rewrite their internal refs.

This is solvable. But the fact that we're already at three layers of pre-processing for one library limitation suggests more edge cases will surface as more endpoints get added. The library is fragile against this codebase's OpenAPI shape.

---

## Three options forward

### Option A — full pre-processor in `gen-schemas.mjs`

Continue the path I'm on: extend the flattener to walk the `paths` tree, lift every inline schema into `components.schemas`, rewrite all refs, then feed the result to `openapi-zod-client`. Estimated +2-3 hours of work for the pre-processor.

**Pros:**
- Keeps the library choice the spec committed to.
- Schemas-only mode + tag-file output.
- Once done, `make gen_frontend_schemas` is a one-shot.

**Cons:**
- Brittle. Every new edge case in FastAPI's OpenAPI emission needs another pre-processor branch.
- The pre-processor becomes another piece of code to maintain.
- We've already spent ~1 hour on this; signal-to-noise is poor.

### Option B — switch to `orval`

`orval@8.8.1` (current) supports OpenAPI 3.1 + Pydantic v2 + zod schemas natively. It's the more modern / actively-maintained generator in this space.

**Pros:**
- Real OpenAPI 3.1 support.
- Active development.
- Well-documented zod integration.

**Cons:**
- More opinionated. Wants to own more of the client layer than `openapi-zod-client`. Q4 of the brainstorming explicitly chose `openapi-zod-client` over orval-style approaches because of this.
- The plan / spec / call-site recipes all assume `openapi-zod-client`. Switching means re-reading orval's output format, re-writing `gen-schemas.mjs`, possibly tweaking the `validatedQueryFn` integration recipe.
- Estimated rework: 4-6 hours.

### Option C — abandon code generation, hand-write everything

Drop the generator entirely. Hand-write zod schemas for the ~150 endpoints, in addition to the ~65 hidden ones already on Phase 1.3's plate.

**Pros:**
- Zero tooling risk. No library to fight.
- Schemas can be more precise than what a generator would emit (use real enums, real refinements, etc.).
- One source of truth: the schemas themselves.

**Cons:**
- ~25-30 hours of focused authoring (vs. the 7-8 hours estimated for hidden-endpoints alone).
- Drift risk between Pydantic and zod is now fully on the developer — no CI gate via `git diff --exit-code` against a generator's output.
- Loses the "OpenAPI is the source of truth" principle that brainstorming Q2 chose.

### Option D — change the backend to emit OpenAPI 3.0

FastAPI's `app.openapi()` emits 3.1 by default in current versions. There may be a way to get 3.0 output, but I haven't verified — and even if it exists, this asks the backend to emit a less-current OpenAPI version to satisfy a generator limitation. Not recommended.

---

## What I'd do if I were the user

**Option A first**, with a hard time-box: spend 1-2 more hours extending the pre-processor. If at the end we still can't get a clean generator pass on the full spec, fall back to **Option B** (orval).

Reasoning: Option A is the cheapest "yes" if it works. We're 70% of the way there. The orval rewrite is real work; only commit to it if Option A definitively can't reach 100%.

**Don't go to Option C** unless both A and B fail. Hand-writing 150 schemas is a major scope expansion that effectively triples Phase 1's budget.

---

## Recommended decision moment

Reply with **"a"**, **"b"**, or **"c"** to pick a direction. I'll resume Phase 1 from where I paused (`855054730b`). All Phase 0 work is safely on `platform-multi-tenant`; nothing pushed.

The branch `dto/boundary-types-2026-04` currently has:
- Plan housekeeping (`549e43c56d`)
- Makefile targets for openapi extraction (`855054730b`)

If we end up switching libraries or abandoning generation, those two commits stay valid (the Makefile target is library-agnostic — it just emits the openapi.json).
