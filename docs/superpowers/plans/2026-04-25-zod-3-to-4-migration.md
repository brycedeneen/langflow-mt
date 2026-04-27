# Zod 3 → 4 Frontend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **CRITICAL — user-level rule (overrides skill defaults):** Every step labelled "Commit" must pause and ask the user for explicit approval before running `git commit`. Never use `git add -A`, `git add .`, or `git commit -a` — always stage explicit paths. This applies to every commit in this plan.

**Goal:** Bump `zod ^3.25.76` → latest stable `^4.x` across `src/frontend`. One bundled migration on a worktree off `platform-multi-tenant`.

**Architecture:** Three buckets — (1) the auto-generated `src/schemas/api/_generated.ts` is fixed by adding a post-processor to the existing `gen-schemas.mjs` pipeline; (2) handwritten schemas in `src/schemas/app/**` get a community codemod followed by review; (3) the validated-runtime libs need only a small `ZodTypeAny` → `ZodType` rename. Pre-production — no error-message preservation.

**Tech Stack:** zod 4, `openapi-zod-client@1.18.x` (pinned via Phase 0 probe), Node `node:test`, npm, Vite, Jest (frontend test runner), biome (lint).

**Spec:** `docs/superpowers/specs/2026-04-25-zod-3-to-4-migration-design.md`

**Related in-flight:** `docs/superpowers/specs/2026-04-24-frontend-dto-boundary-types-design.md` — also touches `_generated.ts` and `gen-schemas.mjs`. If that work lands first, rebase before starting Phase 1A. If this plan lands first, the DTO plan inherits the post-processor.

---

## File map

| Path | Role |
| --- | --- |
| `src/frontend/scripts/zod4-postprocessor.mjs` | NEW — pure transform `(source: string) => string` rewriting v3 generator output to v4 syntax |
| `src/frontend/scripts/__tests__/zod4-postprocessor.test.mjs` | NEW — `node:test` cases against fixture snippets |
| `src/frontend/scripts/gen-schemas.mjs` | MODIFY — wire the post-processor into step `[3/5]` |
| `src/frontend/package.json` | MODIFY — bump `zod` |
| `src/frontend/package-lock.json` | MODIFY — `npm install` regenerates |
| `src/frontend/src/schemas/api/_generated.ts` | REGENERATED — `make gen_frontend_schemas` |
| `src/frontend/src/schemas/app/**/*.ts` | MODIFY — codemod + manual review |
| `src/frontend/src/lib/validated-fetch.ts` | MODIFY — `ZodTypeAny` → `ZodType` |

---

## Task 0: Create worktree

**Files:**
- Create: `~/dev/langflow-worktrees/zod4-migration/` (worktree)

- [ ] **Step 1: Create worktree off `platform-multi-tenant`**

```bash
cd /Users/brycedeneen/dev/langflow
git worktree add -b zod4-migration ../langflow-worktrees/zod4-migration platform-multi-tenant
```

Expected: new directory created with the branch checked out.

- [ ] **Step 2: Verify clean state**

```bash
cd ../langflow-worktrees/zod4-migration
git status
```

Expected: "On branch zod4-migration" and "nothing to commit, working tree clean".

- [ ] **Step 3: Note the worktree path**

All subsequent commands run from this worktree. Replace `<WT>` in this plan with `/Users/brycedeneen/dev/langflow-worktrees/zod4-migration` (or wherever Step 1 created it).

---

## Task 1: Phase 0 — Generator probe

**Files:** No file changes; this task only produces information that gates Task 2 vs Task 2-alt.

- [ ] **Step 1: Capture current generator output as baseline**

```bash
cd <WT>/src/frontend
make -C ../.. openapi_json
make -C ../.. gen_frontend_schemas
cp src/schemas/api/_generated.ts /tmp/_generated.before.ts
```

Expected: `_generated.ts` regenerates without error, copy saved.

- [ ] **Step 2: Check for newer `openapi-zod-client` releases**

```bash
npm view openapi-zod-client versions --json | tail -20
```

Note any version newer than what's currently installed (`npm ls openapi-zod-client` shows installed version).

- [ ] **Step 3: If a newer release exists, try it**

```bash
# Substitute <VERSION> for the latest from Step 2
npx openapi-zod-client@<VERSION> /tmp/openapi-flat.json --output /tmp/probe-client.ts --export-schemas --group-strategy none
```

If the command fails on the same `MissingPointerError` chain documented in `docs/superpowers/research/2026-04-24-phase-1-tooling-block.md`, run `make gen_frontend_schemas` instead (which goes through the Python flattener) after temporarily editing `gen-schemas.mjs` to invoke the new version.

- [ ] **Step 4: Diff for v4 syntax markers**

```bash
grep -E 'looseObject|strictObject|z\.record\([^,]+,' /tmp/probe-client.ts | head
grep -E '\.passthrough\(\)|\.strict\(\)|nativeEnum' /tmp/probe-client.ts | head
```

Decision matrix:

| Probe result | Path |
| --- | --- |
| Output uses `z.looseObject` and two-arg `z.record` | Skip the post-processor; just bump generator version. Update `package.json` and `gen-schemas.mjs` and proceed straight to Task 3. |
| Output still uses `.passthrough()`, single-arg `z.record`, etc. | Continue with Task 2 (post-processor). |
| Output uses removed-in-v4 APIs in ways regex can't reach (e.g. `z.literal(Symbol(...))`, `z.function().args(...).returns(...)` style schemas) | Drop to Task 2-alt (orval swap). |

- [ ] **Step 5: Record the verdict**

Append a "Probe outcome" section to this plan file with a one-paragraph note: which generator version, what syntax it emits, which path you're taking. Do **not** commit yet — the spec and plan get one combined commit at the end of the migration.

---

## Task 2: Phase 1A — Post-processor module (test-first)

Skip this task entirely if Task 1 Step 4 said "Skip the post-processor". Skip and go to Task 2-alt if Task 1 Step 4 said "Drop to orval swap".

**Files:**
- Create: `<WT>/src/frontend/scripts/zod4-postprocessor.mjs`
- Create: `<WT>/src/frontend/scripts/__tests__/zod4-postprocessor.test.mjs`

- [ ] **Step 1: Write the failing test file**

Create `<WT>/src/frontend/scripts/__tests__/zod4-postprocessor.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { rewriteV3ToV4 } from "../zod4-postprocessor.mjs";

test("rewrites trailing .passthrough() into z.looseObject wrap (single-line)", () => {
  const input = `export const SendMessageRequest = z.object({ content: z.string() }).passthrough();`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `export const SendMessageRequest = z.looseObject({ content: z.string() });`);
});

test("rewrites trailing .passthrough() into z.looseObject wrap (multi-line block)", () => {
  const input = [
    `export const Foo = z`,
    `  .object({`,
    `    a: z.string(),`,
    `    b: z.number(),`,
    `  })`,
    `  .passthrough();`,
  ].join("\n");
  const output = rewriteV3ToV4(input);
  assert.equal(
    output,
    [
      `export const Foo = z.looseObject({`,
      `    a: z.string(),`,
      `    b: z.number(),`,
      `  });`,
    ].join("\n"),
  );
});

test("rewrites inline .object({}).partial().passthrough() into z.looseObject({}).partial()", () => {
  const input = `template: z.object({}).partial().passthrough().optional(),`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `template: z.looseObject({}).partial().optional(),`);
});

test("rewrites trailing .strict() into z.strictObject wrap", () => {
  const input = `export const Foo = z.object({ a: z.string() }).strict();`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `export const Foo = z.strictObject({ a: z.string() });`);
});

test("rewrites single-arg z.record(V) to z.record(z.string(), V)", () => {
  const input = `vertex_builds: z.record(z.array(VertexBuildTable))`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `vertex_builds: z.record(z.string(), z.array(VertexBuildTable))`);
});

test("leaves two-arg z.record(K, V) untouched", () => {
  const input = `env: z.record(z.string(), z.string())`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, input);
});

test("rewrites z.nativeEnum(X) to z.enum(X)", () => {
  const input = `kind: z.nativeEnum(NodeKind)`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, `kind: z.enum(NodeKind)`);
});

test("does not touch passthrough mentions inside string literals", () => {
  const input = `description: z.literal("must use .passthrough()")`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, input);
});

test("is idempotent on already-v4 source", () => {
  const input = `export const Foo = z.looseObject({ a: z.string() });`;
  const output = rewriteV3ToV4(input);
  assert.equal(output, input);
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd <WT>/src/frontend
node --test scripts/__tests__/zod4-postprocessor.test.mjs
```

Expected: All tests fail with "Cannot find module '../zod4-postprocessor.mjs'" (the module doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `<WT>/src/frontend/scripts/zod4-postprocessor.mjs`:

```javascript
/**
 * zod4-postprocessor.mjs — rewrite zod-v3 idioms emitted by openapi-zod-client
 * into zod-v4 syntax.
 *
 * Pure synchronous transform. Idempotent on already-v4 input.
 *
 * Patterns covered:
 *   - `<expr>.passthrough()`        → wrap `<expr>` arg in `z.looseObject(...)`
 *   - `<expr>.strict()`             → wrap `<expr>` arg in `z.strictObject(...)`
 *   - `z.record(V)` (single arg)    → `z.record(z.string(), V)`
 *   - `z.nativeEnum(X)`             → `z.enum(X)`
 *
 * Patterns intentionally NOT touched (still functional in v4, just deprecated):
 *   - chained `.email()`, `.url()`, `.uuid()`
 */

const PASSTHROUGH = "passthrough";
const STRICT = "strict";

export function rewriteV3ToV4(source) {
  let out = source;
  out = rewriteObjectMethodToWrapper(out, PASSTHROUGH, "z.looseObject");
  out = rewriteObjectMethodToWrapper(out, STRICT, "z.strictObject");
  out = rewriteSingleArgRecord(out);
  out = rewriteNativeEnum(out);
  return out;
}

/**
 * Find every `<expr>.METHOD()` where `<expr>` is a `z.object(<args>)` (possibly
 * with intermediate `.partial()`, etc.) and rewrite it to `wrapper(<args>)`
 * preserving any chained methods that came BEFORE METHOD (`.partial()`).
 *
 * Approach: scan for `.METHOD()` occurrences, walk left across balanced parens
 * to find the matching `z.object(`, replace.
 */
function rewriteObjectMethodToWrapper(src, method, wrapper) {
  const needle = `.${method}()`;
  let out = "";
  let i = 0;
  while (i < src.length) {
    const next = src.indexOf(needle, i);
    if (next < 0) {
      out += src.slice(i);
      break;
    }
    // Confirm we're not inside a string literal (cheap check: count unescaped
    // backticks / quotes since last newline).
    if (insideStringLiteral(src, next)) {
      out += src.slice(i, next + needle.length);
      i = next + needle.length;
      continue;
    }

    const replaced = tryRewriteAt(src, next, method, wrapper);
    if (replaced === null) {
      out += src.slice(i, next + needle.length);
      i = next + needle.length;
    } else {
      out += src.slice(i, replaced.start) + replaced.text;
      i = replaced.end;
    }
  }
  return out;
}

function tryRewriteAt(src, methodIdx, method, wrapper) {
  // methodIdx points at the `.` of `.METHOD()`. Walk left across optional
  // chained calls (`.partial()`, `.optional()` patterns BEFORE METHOD are not
  // expected here — only AFTER METHOD — so stop at the first non-call segment).
  let cursor = methodIdx;
  // Collect chained methods that were applied to the object BEFORE .METHOD().
  // Example: z.object({}).partial().passthrough()
  //          we want to walk back past `.partial()` to find z.object({}).
  const preChains = [];
  while (true) {
    if (cursor === 0) return null;
    if (src[cursor - 1] !== ")") {
      // Could be after `.partial` without parens? Generator never emits that.
      return null;
    }
    // Walk back over balanced parens.
    const argEnd = cursor - 1;
    const argStart = matchOpenParen(src, argEnd);
    if (argStart < 0) return null;
    // Identifier before the open paren.
    const idEnd = argStart;
    const idStart = readIdentLeft(src, idEnd);
    if (idStart < 0) return null;
    const ident = src.slice(idStart, idEnd);
    if (ident === "z.object") {
      // Found the base. Build replacement.
      const objArgs = src.slice(argStart + 1, argEnd);
      const tail = preChains.length ? "." + preChains.reverse().join(".") : "";
      return {
        start: idStart,
        end: methodIdx + `.${method}()`.length,
        text: `${wrapper}(${objArgs})${tail}`,
      };
    }
    // Otherwise, this is a chained call between z.object and .METHOD. Capture
    // it and keep walking.
    preChains.push(`${ident}(${src.slice(argStart + 1, argEnd)})`);
    // The dot before this identifier:
    if (idStart === 0 || src[idStart - 1] !== ".") return null;
    cursor = idStart - 1;
  }
}

function matchOpenParen(src, closeIdx) {
  let depth = 1;
  for (let i = closeIdx - 1; i >= 0; i--) {
    const c = src[i];
    if (c === ")") depth++;
    else if (c === "(") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function readIdentLeft(src, end) {
  let i = end;
  while (i > 0 && /[A-Za-z0-9_.]/.test(src[i - 1])) i--;
  return i < end ? i : -1;
}

function insideStringLiteral(src, idx) {
  // Cheap heuristic: walk back to start of line and count unescaped quote
  // characters. Generator output puts strings on single lines, so this is safe.
  let lineStart = src.lastIndexOf("\n", idx - 1) + 1;
  let single = 0, double = 0, back = 0;
  for (let i = lineStart; i < idx; i++) {
    const c = src[i];
    if (c === "\\") { i++; continue; }
    if (c === "'") single++;
    else if (c === '"') double++;
    else if (c === "`") back++;
  }
  return (single % 2 === 1) || (double % 2 === 1) || (back % 2 === 1);
}

function rewriteSingleArgRecord(src) {
  // Rewrite z.record(<one arg>) → z.record(z.string(), <one arg>).
  // Skip if a comma at the top level of the argument list already exists.
  let out = "";
  let i = 0;
  while (i < src.length) {
    const next = src.indexOf("z.record(", i);
    if (next < 0) {
      out += src.slice(i);
      break;
    }
    if (insideStringLiteral(src, next)) {
      out += src.slice(i, next + "z.record(".length);
      i = next + "z.record(".length;
      continue;
    }
    const argStart = next + "z.record(".length;
    const argEnd = matchCloseParen(src, argStart - 1);
    if (argEnd < 0) {
      out += src.slice(i, argStart);
      i = argStart;
      continue;
    }
    const args = src.slice(argStart, argEnd);
    if (hasTopLevelComma(args)) {
      out += src.slice(i, argEnd + 1);
      i = argEnd + 1;
      continue;
    }
    out += src.slice(i, argStart) + "z.string(), " + args + ")";
    i = argEnd + 1;
  }
  return out;
}

function matchCloseParen(src, openIdx) {
  let depth = 1;
  for (let i = openIdx + 1; i < src.length; i++) {
    const c = src[i];
    if (c === "(") depth++;
    else if (c === ")") {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function hasTopLevelComma(args) {
  let depth = 0;
  for (let i = 0; i < args.length; i++) {
    const c = args[i];
    if (c === "(" || c === "[" || c === "{") depth++;
    else if (c === ")" || c === "]" || c === "}") depth--;
    else if (c === "," && depth === 0) return true;
  }
  return false;
}

function rewriteNativeEnum(src) {
  return src.replace(/\bz\.nativeEnum\(/g, "z.enum(");
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd <WT>/src/frontend
node --test scripts/__tests__/zod4-postprocessor.test.mjs
```

Expected: All 9 tests pass.

If any fail, fix the implementation. Do not loosen the test — the test cases describe required behavior. The trickiest is the multi-line `.passthrough()` case which exercises the balanced-paren walker.

- [ ] **Step 5: Commit (ASK USER FIRST per memory rule)**

Pause and ask the user: "Ready to commit the post-processor module + tests?" Wait for explicit yes.

```bash
cd <WT>
git add src/frontend/scripts/zod4-postprocessor.mjs src/frontend/scripts/__tests__/zod4-postprocessor.test.mjs
git commit -m "build(frontend): add zod4-postprocessor for openapi-zod-client output"
```

---

## Task 2-alt: Phase 1B — Orval generator swap (fallback)

Only follow if Task 1 Step 4 said "Drop to orval swap". Otherwise skip.

**Files:**
- Modify: `<WT>/src/frontend/scripts/gen-schemas.mjs`
- Delete: `<WT>/src/frontend/scripts/flatten-openapi-defs.py`
- Modify: `<WT>/Makefile` (the `gen_frontend_schemas` target)
- Modify: `<WT>/src/frontend/package.json` (add `orval` devDependency)

This is a substantial sub-project. Scope per the prior research doc (`docs/superpowers/research/2026-04-24-phase-1-tooling-block.md` Option B) is 4–6 hours; it deserves its own dedicated plan. **If you reach this branch, stop and write a separate orval-swap plan rather than expanding this one.**

---

## Task 3: Wire post-processor into `gen-schemas.mjs`

Skip if Task 1 said "Skip the post-processor".

**Files:**
- Modify: `<WT>/src/frontend/scripts/gen-schemas.mjs:55-75` (the dedup loop area in step `[3/5]`)

- [ ] **Step 1: Add the import**

In `<WT>/src/frontend/scripts/gen-schemas.mjs`, add at the top (after the existing imports around line 20):

```javascript
import { rewriteV3ToV4 } from "./zod4-postprocessor.mjs";
```

- [ ] **Step 2: Apply the transform after dedup, before write**

Locate where `promoted.join("")` produces the final declarations block (around line 105 in the current file — it's the value passed into the `generated` array). Replace:

```javascript
const generated = [
  // ... header lines ...
  promoted.join(""),
].join("\n");
```

with:

```javascript
const generated = [
  // ... header lines ...
  rewriteV3ToV4(promoted.join("")),
].join("\n");
```

Also update the header comment in the generated file (the lines that say "Pre-process: scripts/flatten-openapi-defs.py …") to add a sentence:

```
// Post-process: scripts/zod4-postprocessor.mjs rewrites v3 idioms
// (.passthrough(), single-arg z.record, z.nativeEnum) emitted by
// openapi-zod-client into v4 syntax (z.looseObject, two-arg z.record, z.enum).
```

- [ ] **Step 3: Regenerate to confirm clean output**

```bash
cd <WT>
make openapi_json
make gen_frontend_schemas
```

Expected: completes without error.

- [ ] **Step 4: Verify no v3 idioms remain in `_generated.ts`**

```bash
cd <WT>/src/frontend
grep -nE '\.passthrough\(\)|\.strict\(\)|nativeEnum' src/schemas/api/_generated.ts || echo "OK — no v3 idioms"
grep -nE 'z\.record\([^,)]+\)' src/schemas/api/_generated.ts || echo "OK — no single-arg record"
```

Expected: both echo "OK …". If either prints matches, the post-processor missed a pattern — go back to Task 2 and add a failing test for the missed shape, then re-implement.

- [ ] **Step 5: Commit (ASK USER FIRST)**

Ask user: "Ready to commit the gen-schemas wiring + regenerated `_generated.ts`?"

```bash
cd <WT>
git add src/frontend/scripts/gen-schemas.mjs src/frontend/src/schemas/api/_generated.ts
git commit -m "build(frontend): post-process generator output into zod 4 syntax"
```

---

## Task 4: Bump zod dependency

**Files:**
- Modify: `<WT>/src/frontend/package.json` (the `"zod"` line)
- Modify: `<WT>/src/frontend/package-lock.json` (regenerated)

- [ ] **Step 1: Look up the latest stable zod 4 version**

```bash
npm view zod version
```

Note the version. Should be `4.x.y`.

- [ ] **Step 2: Bump in `package.json`**

In `<WT>/src/frontend/package.json`, change:

```json
"zod": "^3.25.76",
```

to:

```json
"zod": "^4.x.y",
```

(substituting the version from Step 1).

- [ ] **Step 3: Install**

```bash
cd <WT>/src/frontend
npm install
```

Expected: lockfile updates; no install errors. `npm ls zod` shows the new version.

- [ ] **Step 4: Confirm type-check now fails (proof the bump took effect)**

```bash
npm run type-check
```

Expected: many errors. They will be cleaned up in the next tasks. **Do not commit yet** — bundling the bump with the codemod fix-up keeps the repo bisectable.

---

## Task 5: Run codemod against handwritten schemas

**Files:**
- Modify: every file under `<WT>/src/frontend/src/schemas/app/**/*.ts`
- Modify: `<WT>/src/frontend/src/schemas/index.ts` (if any zod usage there)

- [ ] **Step 1: Verify the codemod is available**

```bash
npx --yes zod-v3-to-v4 --help
```

Expected: usage banner. If the package can't be resolved, fall back to the alternative invocation `npx --package=@nicoespeon/zod-v3-to-v4 zod-v3-to-v4 --help`. If neither works, skip Task 5 and do the rewrites by hand in Task 6 — the surface is small enough.

- [ ] **Step 2: Run the codemod**

```bash
cd <WT>/src/frontend
npx --yes zod-v3-to-v4 src/schemas/app
```

Expected: codemod prints a per-file summary of rewrites.

- [ ] **Step 3: Inspect the diff**

```bash
git diff src/frontend/src/schemas/app
```

Verify: `.passthrough()` removed, `z.record(V)` became `z.record(z.string(), V)`, no semantic surprises. Anything that looks wrong, revert the file and rewrite by hand in Task 6.

- [ ] **Step 4: Run type-check on just these files (optional sanity)**

```bash
cd <WT>/src/frontend
npx tsc --noEmit --pretty src/schemas/app/internal/store.ts
```

Not a hard gate — the full type-check happens in Task 7.

- [ ] **Step 5: Stage but do not commit yet**

The codemod output bundles with manual fixes from Task 6 in a single commit.

---

## Task 6: Manual sweep

The spec listed eight grep patterns. At plan time, seven of them have zero hits in handwritten code; only one needs action. The task lists all eight defensively — re-run the grep before each step in case the codebase moved.

**Files:**
- Modify: `<WT>/src/frontend/src/lib/validated-fetch.ts:5,21` (`ZodTypeAny` → `ZodType`)
- Inspect (likely no-op): everywhere else

- [ ] **Step 1: `ZodTypeAny` → `ZodType`**

```bash
cd <WT>/src/frontend
grep -rn 'ZodTypeAny' src/
```

For each hit, replace `z.ZodTypeAny` with `z.ZodType`. At plan time this is two callsites in `src/lib/validated-fetch.ts`:

```typescript
// Before
export function validatedQueryFn<TSchema extends z.ZodTypeAny>(
// After
export function validatedQueryFn<TSchema extends z.ZodType>(

// Before
export function validatedMutationFn<TReqSchema extends z.ZodTypeAny, TResSchema extends z.ZodTypeAny>(
// After
export function validatedMutationFn<TReqSchema extends z.ZodType, TResSchema extends z.ZodType>(
```

- [ ] **Step 2: `_def` access audit**

```bash
grep -rn '\._def\b' src/ | grep -v node_modules
```

Expected at plan time: zero hits. If any appear, replace `._def` with `._zod.def`.

- [ ] **Step 3: `errorMap` audit**

```bash
grep -rn 'errorMap' src/ | grep -v node_modules
```

Expected: zero hits. If any appear, replace the option key `errorMap:` with `error:` and adjust the callback to return a string (not `{message: string}`).

- [ ] **Step 4: `nativeEnum` audit (handwritten only)**

```bash
grep -rn 'nativeEnum' src/ | grep -v node_modules | grep -v _generated.ts
```

Expected: zero hits. `_generated.ts` is owned by the post-processor.

- [ ] **Step 5: `.format()` / `.flatten()` on ZodError audit**

```bash
grep -rnE 'ZodError.*\.(format|flatten)\(\)|zodError\.(format|flatten)\(\)' src/
```

Expected: zero hits. If any appear, replace with `z.treeifyError(error)`. Note that `schema-errors.ts` already iterates `.issues` directly — no rewrite needed there.

- [ ] **Step 6: `.transform().default()` semantic-flip audit**

```bash
grep -rnE '\.transform\([^)]*\)[^)]*\.default\(' src/
```

Expected: zero hits. If any appear, the v4 default applies to the *output* of the transform — for each hit, decide whether the new behavior is correct or whether `.prefault()` is needed to preserve v3 semantics. Rule of thumb: `.prefault()` if the default needs to be parsed *through* the transform.

- [ ] **Step 7: `.refine` type-predicate audit**

```bash
grep -rnE '\.refine\([^)]*\): \w+ =>' src/
```

Expected: zero hits. If any appear, type-predicate refines no longer narrow the inferred type in v4. Replace with `.pipe(z.custom<X>(...))` if the narrow was load-bearing.

- [ ] **Step 8: `z.coerce` audit**

```bash
grep -rn 'z\.coerce\.' src/
```

Expected: zero hits. If any appear, the input type is now `unknown` rather than the source type — type-check will surface affected callers.

- [ ] **Step 9: Stage everything and confirm diff is reviewable**

```bash
cd <WT>
git status
git diff --stat src/frontend
```

Expected: changes concentrated in `src/frontend/src/schemas/app/`, `src/frontend/src/lib/validated-fetch.ts`, plus `package.json` and `package-lock.json`.

- [ ] **Step 10: Commit (ASK USER FIRST)**

Ask user: "Ready to commit the zod 4 bump + codemod + manual sweep as one commit?"

```bash
cd <WT>
git add src/frontend/package.json src/frontend/package-lock.json \
        src/frontend/src/schemas/app src/frontend/src/lib/validated-fetch.ts
# Add any other files surfaced by Steps 2-8
git commit -m "feat(frontend): bump zod 3 → 4 across handwritten schemas and runtime"
```

---

## Task 7: Build & type-check gauntlet

**Files:** Whatever the type-checker surfaces.

- [ ] **Step 1: Run type-check**

```bash
cd <WT>/src/frontend
npm run type-check 2>&1 | tee /tmp/zod4-typecheck.log
```

Expected outcome categories (in approximate likelihood order):

| Error pattern | Cause | Fix |
| --- | --- | --- |
| `Property 'a' is required …` on object types where the property was `z.unknown()` or `z.any()` | v4 makes these properties non-optional in object shapes | Add `.optional()` if the property genuinely is, otherwise update the consumer to pass it |
| `Type 'string' is not assignable to '<X>'` from `.coerce.X(...)` callers | v4 coerce input is `unknown` | Cast the call site or wrap the input |
| `.format` / `.flatten` does not exist on type 'ZodError' | Missed in Task 6 Step 5 | Replace with `z.treeifyError(error)` |
| Generic constraint errors mentioning `ZodTypeAny` | Missed in Task 6 Step 1 | Replace with `ZodType` |
| `Cannot find module 'zod/v3'` | Stray legacy import | Remove it — this migration is a clean cut |

- [ ] **Step 2: Fix errors in batches**

Group errors by file and fix one file at a time. After each file, re-run `npm run type-check` to shrink the error list.

- [ ] **Step 3: Run lint**

```bash
cd <WT>/src/frontend
npm run lint 2>&1 | tee /tmp/zod4-lint.log
```

Fix any new biome diagnostics. Expected: minimal — biome doesn't know about zod APIs.

- [ ] **Step 4: Commit fixes (ASK USER FIRST)**

If Step 2 or 3 produced changes:

Ask user: "Ready to commit type-check / lint fixes?"

```bash
cd <WT>
git add <files-touched>   # explicit paths only
git commit -m "fix(frontend): resolve zod 4 type-check fallout"
```

---

## Task 8: Test gauntlet

**Files:** Test files only — only update tests, do not change production code unless the test surfaces a real bug.

- [ ] **Step 1: Run Jest**

```bash
cd <WT>/src/frontend
npm test 2>&1 | tee /tmp/zod4-jest.log
```

- [ ] **Step 2: Triage failures**

| Failure pattern | Cause | Fix |
| --- | --- | --- |
| Snapshot diff on zod error message text | v4 emits different message wording | Update the snapshot — pre-prod, no preservation needed |
| `error.format(...)` undefined in test setup | Tests that asserted on the old `.format()` shape | Replace with `z.treeifyError(error)` and update the assertion shape |
| Type-import errors mentioning `ZodIssue` / `ZodTypeAny` | v4 renamed internal types | Use the v4 name (`z.ZodIssue` may still exist as alias; if not, use `z.core.$ZodIssue`) |
| Real assertion failures (not snapshot, not error-shape) | Possible silent semantic change — likely `.default()` flip | Investigate the schema; consult Task 6 Step 6 |

- [ ] **Step 3: Update snapshots**

After verifying each snapshot diff is the expected zod 4 wording change (and not a regression):

```bash
cd <WT>/src/frontend
npm test -- -u
```

- [ ] **Step 4: Commit (ASK USER FIRST)**

Ask user: "Ready to commit test updates?"

```bash
cd <WT>
git add <test-files>     # explicit paths only
git commit -m "test(frontend): update fixtures for zod 4 error shapes"
```

---

## Task 9: Manual smoke

**Files:** None — interactive verification.

- [ ] **Step 1: Start dev server**

```bash
cd <WT>/src/frontend
npm start
```

Expected: Vite serves on the usual port without runtime warnings about zod.

- [ ] **Step 2: Exercise the four runtime schema consumers**

| Flow | Schema exercised | What to check |
| --- | --- | --- |
| Build a flow → run it | `validated-named-event-stream`, `buildEvents` | Build events stream successfully; ValidationErrorOverlay does **not** appear |
| Upload a file in file management | `file-management` query schemas, `validated-fetch` | Upload completes; file appears in the list |
| Open Voice Assistant | `voice`, `voiceAssistant` schemas | Modal opens and connects (or fails for non-zod reasons) |
| Trigger a deliberate validation error | Anything — easiest is mocking a malformed response in the network tab via dev-tools | `ValidationErrorOverlay` renders; the error text is present and readable |

- [ ] **Step 3: Note any regressions**

Anything that worked on `platform-multi-tenant` baseline but breaks here is a zod 4 problem. Stop and investigate. Document the reproduction in a commit-message-ready note.

- [ ] **Step 4: Stop the dev server**

`Ctrl+C` in the terminal running `npm start`.

---

## Task 10: Cleanup & final verification

- [ ] **Step 1: Re-run the full pipeline from clean**

```bash
cd <WT>
make openapi_json
make gen_frontend_schemas
cd src/frontend
npm run type-check
npm run lint
npm test
```

Expected: all green.

- [ ] **Step 2: Confirm no `zod/v3` imports remain**

```bash
cd <WT>/src/frontend
grep -rn "from ['\"]zod/v3['\"]" src/
```

Expected: zero hits. This migration is a clean cut.

- [ ] **Step 3: Diff summary against baseline**

```bash
cd <WT>
git log --oneline platform-multi-tenant..HEAD
git diff --stat platform-multi-tenant..HEAD
```

Sanity-check: commit list is the migration story, no stray unrelated changes.

- [ ] **Step 4: Update the spec with probe outcome**

If Task 1 Step 5 was deferred (you didn't write the verdict back to the spec / plan), do it now — append a "Probe outcome" section to either `docs/superpowers/specs/2026-04-25-zod-3-to-4-migration-design.md` or this plan describing which generator path was taken and any patterns added to the post-processor mid-flight.

- [ ] **Step 5: Commit spec/plan updates if needed (ASK USER FIRST)**

If Step 4 produced changes:

Ask user: "Ready to commit the spec/plan updates documenting the probe outcome?"

```bash
cd <WT>
git add docs/superpowers/specs/2026-04-25-zod-3-to-4-migration-design.md \
        docs/superpowers/plans/2026-04-25-zod-3-to-4-migration.md
git commit -m "docs(superpowers): record zod 4 migration probe outcome"
```

- [ ] **Step 6: Stop**

Per project memory, **do not push or PR upstream to `langflow-ai/langflow`**. The branch lives locally on the worktree until the user chooses what to do with it.

Hand back to the user: "Migration complete on branch `zod4-migration` in worktree `<WT>`. <N> commits. All gates green. Ready for review or merge into `platform-multi-tenant`."
