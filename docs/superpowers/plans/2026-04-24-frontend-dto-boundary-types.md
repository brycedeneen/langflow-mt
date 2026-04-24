# Frontend DTO / Boundary-Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every value that crosses a boundary (HTTP, persisted storage, SSE/WebSocket) parse through a zod schema generated from the backend OpenAPI spec, with per-schema parse mode that starts permissive and flips to strict per domain — the foundation for a future `noImplicitAny: true` flip.

**Architecture:** Zod schemas live in `src/frontend/src/schemas/` (generated `api/` from OpenAPI via `openapi-zod-client`, hand-written `app/` for persisted state, stream messages, and OpenAPI-hidden endpoints). Three thin wrappers (`validated-fetch.ts`, `validated-storage.ts`, `validated-stream.ts`) sit between the existing axios/Zustand/EventSource layers and their call sites. A central strict-flag registry flips validation behavior per-domain without touching call sites. An admin-gated `<ValidationErrorOverlay />` provides in-session diagnostics.

**Tech Stack:** React 19, TypeScript 6.0.3, `zod` v3, `openapi-zod-client` (schemas-only mode), axios, `@tanstack/react-query` v5, Zustand v5 (`persist` middleware), Jest 30, Playwright, FastAPI backend.

**Spec:** `docs/superpowers/specs/2026-04-24-frontend-dto-boundary-types-design.md`

---

## Standing instructions (from user memory / AGENTS.md)

- **No `git commit` without explicit approval.** Every commit step below has a "pause and ask" instruction — honor it literally.
- **Stage explicit file paths.** Never use `git add -A`, `git add .`, or `git commit -a`. The repo carries unrelated WIP.
- **No upstream PRs.** All work lands on local `platform-multi-tenant`. Never push to `langflow-ai/langflow`.
- **Jest, not Vitest.** Frontend unit tests run with `npm run test`.
- **All work happens inside a dedicated worktree** at `.worktrees/dto-boundary-2026-04/`.

---

## Pre-flight — worktree + baselines

Before any phase starts, create the worktree and capture baselines that every phase's gate references.

**Files:** no source changes; worktree creation + baseline log capture.

- [ ] **Step P.1: Verify starting state**

Run from `/Users/brycedeneen/dev/langflow`:

```bash
git status
git rev-parse --abbrev-ref HEAD
```

Expected: on some branch (typically `platform-multi-tenant` or a follow-ups branch off it). Unrelated WIP in working tree is expected — do **not** stash or commit it. The target branch `dto/boundary-types-2026-04` must not exist yet.

- [ ] **Step P.2: Create worktree**

```bash
cd /Users/brycedeneen/dev/langflow
git worktree add .worktrees/dto-boundary-2026-04 -b dto/boundary-types-2026-04 platform-multi-tenant
```

Expected: new worktree checked out at `.worktrees/dto-boundary-2026-04/` on branch `dto/boundary-types-2026-04`, branched from `platform-multi-tenant`.

- [ ] **Step P.3: Install frontend deps in the worktree**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npm install
```

Expected: clean install. Same audit warnings as the main worktree.

- [ ] **Step P.4: Capture tsc baseline**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npx tsc --noEmit 2>&1 | tee /tmp/dto-baseline-tsc.log
grep -E "error TS[0-9]+:" /tmp/dto-baseline-tsc.log | grep -vE "__tests__|\.test\.|\.spec\." | wc -l > /tmp/dto-baseline-prod-count.txt
grep -E "error TS[0-9]+:" /tmp/dto-baseline-tsc.log | grep -E "__tests__|\.test\.|\.spec\." | wc -l > /tmp/dto-baseline-test-count.txt
cat /tmp/dto-baseline-prod-count.txt /tmp/dto-baseline-test-count.txt
```

Expected: production count = `0`, test count ≈ `235`. If production ≠ 0, STOP — a prior project's cleanup has regressed and this plan's gates depend on zero prod errors.

- [ ] **Step P.5: Capture test + build + `any`-count baselines**

```bash
npm test -- --ci 2>&1 | tee /tmp/dto-baseline-tests.log | tail -5
npm run build 2>&1 | tee /tmp/dto-baseline-build.log | tail -5
grep -rn ": any\b\| any\[\]\|<any>\|as any\b" src --include="*.ts" --include="*.tsx" \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l > /tmp/dto-baseline-any-count.txt
cat /tmp/dto-baseline-any-count.txt
```

Expected: tests ~198 suites / 2834 pass, build clean, `any` count ≈ `378`. Log actual values for later phases to reference.

- [ ] **Step P.6: Report baseline to controller**

Present a 5-line summary:
- Worktree at `.worktrees/dto-boundary-2026-04/` on `dto/boundary-types-2026-04`
- Production tsc errors: `<count>`
- Test tsc errors: `<count>`
- Tests: `<suites>/<total>` pass
- Build: clean
- Production `any` surface: `<count>`

Proceed to Phase 0.

---

## Phase 0 — Foundation (walking skeleton)

**Goal:** prove the pattern end-to-end on one endpoint (`GET /api/v1/flows/{id}`).

**Scope:** wrapper code + registry + error type + skeleton overlay + `isPlatformAdmin` wiring + one migrated endpoint. No other endpoints touched, no storage/stream migrated for real, no flags flipped to strict.

**All paths in this phase are relative to the worktree root** `/Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/`.

### Task 0.1 — Install dependencies

**Files:**
- Modify: `src/frontend/package.json`

- [ ] **Step 0.1.1: Install zod (runtime) and openapi-zod-client (dev)**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npm install zod@^3.23
npm install --save-dev openapi-zod-client@^1.18
```

Expected: `package.json` gains `zod` in `dependencies` and `openapi-zod-client` in `devDependencies`. `package-lock.json` updates.

- [ ] **Step 0.1.2: Verify no new tsc errors from the install**

```bash
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
```

Expected: `0` (matches baseline).

- [ ] **Step 0.1.3: Pause and ask**

Ask: "Phase 0 — deps installed (zod + openapi-zod-client). Stage `package.json` + `package-lock.json` and commit?"

- [ ] **Step 0.1.4: Commit (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/package.json src/frontend/package-lock.json
git commit -m "chore(frontend): add zod + openapi-zod-client for boundary validation

zod is the runtime validator; openapi-zod-client generates zod schemas
from the backend OpenAPI spec (schemas-only mode, no client).

Part of the DTO / boundary-types project:
docs/superpowers/specs/2026-04-24-frontend-dto-boundary-types-design.md"
```

### Task 0.2 — Create the schema registry

**Files:**
- Create: `src/frontend/src/lib/schema-registry.ts`
- Create: `src/frontend/src/lib/__tests__/schema-registry.test.ts`

- [ ] **Step 0.2.1: Write the failing test**

Create `src/frontend/src/lib/__tests__/schema-registry.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "@jest/globals";
import { registerSchema, getMode, _resetForTest } from "../schema-registry";

describe("schema-registry", () => {
  beforeEach(() => _resetForTest());

  it("returns 'permissive' for an unregistered schema id", () => {
    expect(getMode("api.unknown.endpoint")).toBe("permissive");
  });

  it("returns the registered mode for a known schema id", () => {
    registerSchema("api.flows.getFlow", "strict");
    expect(getMode("api.flows.getFlow")).toBe("strict");
  });

  it("overwrites when the same id is registered twice", () => {
    registerSchema("api.flows.getFlow", "permissive");
    registerSchema("api.flows.getFlow", "strict");
    expect(getMode("api.flows.getFlow")).toBe("strict");
  });
});
```

- [ ] **Step 0.2.2: Run the test to see it fail**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npm test -- src/lib/__tests__/schema-registry.test.ts
```

Expected: all three tests fail with `Cannot find module '../schema-registry'`.

- [ ] **Step 0.2.3: Create the registry module**

Create `src/frontend/src/lib/schema-registry.ts`:

```ts
export type SchemaMode = "permissive" | "strict";

const registry = new Map<string, SchemaMode>();

export function registerSchema(id: string, mode: SchemaMode): void {
  registry.set(id, mode);
}

export function getMode(id: string): SchemaMode {
  return registry.get(id) ?? "permissive";
}

/** Test-only reset. Do not call from application code. */
export function _resetForTest(): void {
  registry.clear();
}
```

- [ ] **Step 0.2.4: Re-run the test**

```bash
npm test -- src/lib/__tests__/schema-registry.test.ts
```

Expected: all three tests pass.

- [ ] **Step 0.2.5: Pause and ask**

Ask: "Task 0.2 — schema-registry implemented with tests. Stage and commit?"

- [ ] **Step 0.2.6: Commit (only after explicit approval)**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/src/lib/schema-registry.ts src/frontend/src/lib/__tests__/schema-registry.test.ts
git commit -m "feat(frontend): add schema-registry for boundary-validation strict flag"
```

### Task 0.3 — Create the error type and reporter

**Files:**
- Create: `src/frontend/src/lib/schema-errors.ts`
- Create: `src/frontend/src/lib/__tests__/schema-errors.test.ts`

- [ ] **Step 0.3.1: Write the failing test**

Create `src/frontend/src/lib/__tests__/schema-errors.test.ts`:

```ts
import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import {
  ValidationError,
  reportParseFailure,
  configureReporter,
  _resetReporterForTest,
} from "../schema-errors";

describe("ValidationError", () => {
  it("carries id, boundary, and a readable toString()", () => {
    const zErr = new z.ZodError([{
      code: "invalid_type",
      expected: "string",
      received: "undefined",
      path: ["data", "nodes", 2, "id"],
      message: "Required",
    }]);
    const err = new ValidationError("api.flows.getFlow", zErr, "http");
    expect(err.id).toBe("api.flows.getFlow");
    expect(err.boundary).toBe("http");
    expect(err.message).toContain("api.flows.getFlow");
    expect(err.message).toContain("data.nodes[2].id");
  });
});

describe("reportParseFailure", () => {
  beforeEach(() => _resetReporterForTest());

  it("invokes the configured reporter once per call", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const zErr = new z.ZodError([]);
    reportParseFailure({ id: "a.b.c", mode: "permissive", error: zErr, raw: {}, boundary: "http" });
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("dedupes identical (id, top-level-path) pairs within 60s", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const zErr = new z.ZodError([{
      code: "invalid_type", expected: "string", received: "number",
      path: ["data", "x"], message: "bad",
    }]);
    const payload = { id: "a.b.c", mode: "permissive" as const, error: zErr, raw: {}, boundary: "http" as const };
    reportParseFailure(payload);
    reportParseFailure(payload);
    reportParseFailure(payload);
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("does not dedupe different (id, path) pairs", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const zErr1 = new z.ZodError([{ code: "invalid_type", expected: "string", received: "number", path: ["a"], message: "" }]);
    const zErr2 = new z.ZodError([{ code: "invalid_type", expected: "string", received: "number", path: ["b"], message: "" }]);
    reportParseFailure({ id: "x.y.z", mode: "permissive", error: zErr1, raw: {}, boundary: "http" });
    reportParseFailure({ id: "x.y.z", mode: "permissive", error: zErr2, raw: {}, boundary: "http" });
    expect(reporter).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 0.3.2: Run the test to see it fail**

```bash
npm test -- src/lib/__tests__/schema-errors.test.ts
```

Expected: tests fail with `Cannot find module '../schema-errors'`.

- [ ] **Step 0.3.3: Implement `schema-errors.ts`**

Create `src/frontend/src/lib/schema-errors.ts`:

```ts
import type { z } from "zod";
import type { SchemaMode } from "./schema-registry";

export type Boundary = "http" | "storage" | "stream";

export class ValidationError extends Error {
  readonly id: string;
  readonly zodError: z.ZodError;
  readonly boundary: Boundary;

  constructor(id: string, zodError: z.ZodError, boundary: Boundary) {
    const preview = zodError.issues.slice(0, 3).map(formatIssue).join("; ");
    super(`ValidationError [${id}] ${preview}`);
    this.name = "ValidationError";
    this.id = id;
    this.zodError = zodError;
    this.boundary = boundary;
  }
}

function formatIssue(issue: z.ZodIssue): string {
  const path = issue.path.length
    ? issue.path.map((p) => (typeof p === "number" ? `[${p}]` : p)).join(".").replace(/\.\[/g, "[")
    : "<root>";
  return `at ${path}: ${issue.message}`;
}

export interface ParseFailurePayload {
  id: string;
  mode: SchemaMode;
  error: z.ZodError;
  raw: unknown;
  boundary: Boundary;
}

export type Reporter = (payload: ParseFailurePayload) => void;

const DEFAULT_REPORTER: Reporter = (payload) => {
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.warn(`[ValidationError][${payload.boundary}][${payload.mode}] ${payload.id}`, payload.error.issues, { raw: payload.raw });
  }
};

let reporter: Reporter = DEFAULT_REPORTER;
const DEDUP_WINDOW_MS = 60_000;
const recentKeys = new Map<string, number>();

export function configureReporter(next: Reporter): void {
  reporter = next;
}

export function reportParseFailure(payload: ParseFailurePayload): void {
  const topPath = payload.error.issues[0]?.path?.[0] ?? "<root>";
  const key = `${payload.id}::${String(topPath)}`;
  const now = Date.now();
  const last = recentKeys.get(key);
  if (last !== undefined && now - last < DEDUP_WINDOW_MS) return;
  recentKeys.set(key, now);
  try {
    reporter(payload);
  } catch {
    // never let a bad reporter break the app path
  }
}

/** Test-only reset of reporter config + dedup cache. */
export function _resetReporterForTest(): void {
  reporter = DEFAULT_REPORTER;
  recentKeys.clear();
}
```

- [ ] **Step 0.3.4: Re-run the test**

```bash
npm test -- src/lib/__tests__/schema-errors.test.ts
```

Expected: all tests pass.

- [ ] **Step 0.3.5: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/src/lib/schema-errors.ts src/frontend/src/lib/__tests__/schema-errors.test.ts
git commit -m "feat(frontend): add ValidationError + reportParseFailure with 60s dedup

Pluggable reporter. Default reporter is console.warn in non-prod, no-op
in prod. Sentry (or equivalent) adapter configured at app bootstrap
once available."
```

### Task 0.4 — Create `validatedQueryFn` / `validatedMutationFn`

**Files:**
- Create: `src/frontend/src/lib/validated-fetch.ts`
- Create: `src/frontend/src/lib/__tests__/validated-fetch.test.ts`

- [ ] **Step 0.4.1: Write the failing test**

Create `src/frontend/src/lib/__tests__/validated-fetch.test.ts`:

```ts
import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedQueryFn, validatedMutationFn } from "../validated-fetch";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { ValidationError, configureReporter, _resetReporterForTest } from "../schema-errors";

const FlowSchema = z.object({ id: z.string(), name: z.string() });

describe("validatedQueryFn", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("returns parsed data on happy path (permissive)", async () => {
    const fn = validatedQueryFn("api.flows.getFlow", FlowSchema,
      async () => ({ id: "1", name: "x" }));
    const result = await fn();
    expect(result).toEqual({ id: "1", name: "x" });
  });

  it("passes through raw data + reports on permissive bad shape", async () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const bad = { id: 1, name: "x" }; // id should be string
    const fn = validatedQueryFn("api.flows.getFlow", FlowSchema, async () => bad);
    const result = await fn();
    expect(result).toEqual(bad);
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("throws ValidationError on strict bad shape", async () => {
    registerSchema("api.flows.getFlow", "strict");
    const reporter = jest.fn();
    configureReporter(reporter);
    const fn = validatedQueryFn("api.flows.getFlow", FlowSchema,
      async () => ({ id: 1, name: "x" }));
    await expect(fn()).rejects.toBeInstanceOf(ValidationError);
    expect(reporter).toHaveBeenCalledTimes(1);
  });
});

describe("validatedMutationFn", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("validates request body before the call fires", async () => {
    registerSchema("api.flows.updateFlow", "strict");
    const ReqSchema = z.object({ name: z.string() });
    const ResSchema = z.object({ id: z.string() });
    const call = jest.fn<(b: unknown) => Promise<unknown>>(async () => ({ id: "1" }));
    const mut = validatedMutationFn("api.flows.updateFlow", ReqSchema, ResSchema, call);
    // @ts-expect-error intentional wrong type
    await expect(mut({ name: 42 })).rejects.toBeInstanceOf(ValidationError);
    expect(call).not.toHaveBeenCalled();
  });

  it("validates response on return", async () => {
    registerSchema("api.flows.updateFlow", "strict");
    const ReqSchema = z.object({ name: z.string() });
    const ResSchema = z.object({ id: z.string() });
    const mut = validatedMutationFn("api.flows.updateFlow", ReqSchema, ResSchema,
      async () => ({ id: 42 }));
    await expect(mut({ name: "x" })).rejects.toBeInstanceOf(ValidationError);
  });
});
```

- [ ] **Step 0.4.2: Run the test to see it fail**

```bash
npm test -- src/lib/__tests__/validated-fetch.test.ts
```

Expected: tests fail with `Cannot find module '../validated-fetch'`.

- [ ] **Step 0.4.3: Implement `validated-fetch.ts`**

Create `src/frontend/src/lib/validated-fetch.ts`:

```ts
import type { z } from "zod";
import { getMode } from "./schema-registry";
import { ValidationError, reportParseFailure } from "./schema-errors";

export function validatedQueryFn<TSchema extends z.ZodTypeAny>(
  id: string,
  schema: TSchema,
  call: () => Promise<unknown>,
): () => Promise<z.infer<TSchema>> {
  return async () => {
    const raw = await call();
    const result = schema.safeParse(raw);
    if (result.success) return result.data;
    const mode = getMode(id);
    reportParseFailure({ id, mode, error: result.error, raw, boundary: "http" });
    if (mode === "strict") throw new ValidationError(id, result.error, "http");
    return raw as z.infer<TSchema>;
  };
}

export function validatedMutationFn<TReqSchema extends z.ZodTypeAny, TResSchema extends z.ZodTypeAny>(
  id: string,
  reqSchema: TReqSchema,
  resSchema: TResSchema,
  call: (body: z.infer<TReqSchema>) => Promise<unknown>,
): (body: z.infer<TReqSchema>) => Promise<z.infer<TResSchema>> {
  return async (body) => {
    const mode = getMode(id);

    // Validate request body before firing (strict mode throws; permissive warns + proceeds).
    const reqResult = reqSchema.safeParse(body);
    if (!reqResult.success) {
      reportParseFailure({ id: `${id}.request`, mode, error: reqResult.error, raw: body, boundary: "http" });
      if (mode === "strict") throw new ValidationError(`${id}.request`, reqResult.error, "http");
    }

    const raw = await call(body);

    const resResult = resSchema.safeParse(raw);
    if (resResult.success) return resResult.data;
    reportParseFailure({ id: `${id}.response`, mode, error: resResult.error, raw, boundary: "http" });
    if (mode === "strict") throw new ValidationError(`${id}.response`, resResult.error, "http");
    return raw as z.infer<TResSchema>;
  };
}
```

- [ ] **Step 0.4.4: Re-run the test**

```bash
npm test -- src/lib/__tests__/validated-fetch.test.ts
```

Expected: all five tests pass.

- [ ] **Step 0.4.5: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/src/lib/validated-fetch.ts src/frontend/src/lib/__tests__/validated-fetch.test.ts
git commit -m "feat(frontend): add validatedQueryFn + validatedMutationFn wrappers"
```

### Task 0.5 — Create `validatedStorage`

**Files:**
- Create: `src/frontend/src/lib/validated-storage.ts`
- Create: `src/frontend/src/lib/__tests__/validated-storage.test.ts`

- [ ] **Step 0.5.1: Write the failing test**

Create `src/frontend/src/lib/__tests__/validated-storage.test.ts`:

```ts
import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedStorage } from "../validated-storage";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { configureReporter, _resetReporterForTest } from "../schema-errors";

const SliceSchema = z.object({ count: z.number() });

function makeBase() {
  const store = new Map<string, string>();
  return {
    getItem: jest.fn<(k: string) => string | null>((k) => store.get(k) ?? null),
    setItem: jest.fn<(k: string, v: string) => void>((k, v) => { store.set(k, v); }),
    removeItem: jest.fn<(k: string) => void>((k) => { store.delete(k); }),
  };
}

describe("validatedStorage", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("returns null when the key is missing", () => {
    const base = makeBase();
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBeNull();
  });

  it("returns null on malformed JSON", () => {
    const base = makeBase();
    base.setItem("k", "not json");
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBeNull();
  });

  it("passes through bad shape in permissive mode + reports", () => {
    const base = makeBase();
    base.setItem("k", JSON.stringify({ count: "nope" }));
    const reporter = jest.fn();
    configureReporter(reporter);
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBe(JSON.stringify({ count: "nope" }));
    expect(reporter).toHaveBeenCalledTimes(1);
  });

  it("clears the key and returns null on bad shape in strict mode", () => {
    registerSchema("storage.slice", "strict");
    const base = makeBase();
    base.setItem("k", JSON.stringify({ count: "nope" }));
    const reporter = jest.fn();
    configureReporter(reporter);
    const s = validatedStorage("storage.slice", SliceSchema, base as unknown as Storage);
    expect(s.getItem("k")).toBeNull();
    expect(base.removeItem).toHaveBeenCalledWith("k");
    expect(reporter).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 0.5.2: Run the test to see it fail**

```bash
npm test -- src/lib/__tests__/validated-storage.test.ts
```

Expected: tests fail with module-not-found.

- [ ] **Step 0.5.3: Implement `validated-storage.ts`**

Create `src/frontend/src/lib/validated-storage.ts`:

```ts
import type { z } from "zod";
import { getMode } from "./schema-registry";
import { reportParseFailure } from "./schema-errors";

export function validatedStorage<T>(id: string, schema: z.ZodType<T>, base: Storage = localStorage): Storage {
  return {
    get length() { return base.length; },
    key: base.key.bind(base),
    getItem: (key: string) => {
      const raw = base.getItem(key);
      if (raw === null) return null;
      let parsed: unknown;
      try { parsed = JSON.parse(raw); } catch { return null; }
      const result = schema.safeParse(parsed);
      if (result.success) return JSON.stringify(result.data);
      const mode = getMode(id);
      reportParseFailure({ id, mode, error: result.error, raw: parsed, boundary: "storage" });
      if (mode === "strict") { base.removeItem(key); return null; }
      return raw;
    },
    setItem: base.setItem.bind(base),
    removeItem: base.removeItem.bind(base),
    clear: base.clear.bind(base),
  };
}
```

- [ ] **Step 0.5.4: Re-run the test**

```bash
npm test -- src/lib/__tests__/validated-storage.test.ts
```

Expected: all four tests pass.

- [ ] **Step 0.5.5: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/src/lib/validated-storage.ts src/frontend/src/lib/__tests__/validated-storage.test.ts
git commit -m "feat(frontend): add validatedStorage shim for Zustand persist middleware"
```

### Task 0.6 — Create `validatedEventStream`

**Files:**
- Create: `src/frontend/src/lib/validated-stream.ts`
- Create: `src/frontend/src/lib/__tests__/validated-stream.test.ts`

- [ ] **Step 0.6.1: Write the failing test**

Create `src/frontend/src/lib/__tests__/validated-stream.test.ts`:

```ts
import { describe, it, expect, beforeEach, jest } from "@jest/globals";
import { z } from "zod";
import { validatedEventStream } from "../validated-stream";
import { registerSchema, _resetForTest as resetRegistry } from "../schema-registry";
import { configureReporter, _resetReporterForTest } from "../schema-errors";

const EventSchema = z.object({ type: z.literal("ping"), seq: z.number() });

type FakeEventSource = {
  onmessage: ((e: { data: string }) => void) | null;
  dispatch: (data: string) => void;
};

function makeSource(): FakeEventSource {
  return {
    onmessage: null,
    dispatch(data) { this.onmessage?.({ data }); },
  };
}

describe("validatedEventStream", () => {
  beforeEach(() => { resetRegistry(); _resetReporterForTest(); });

  it("invokes onMessage with parsed data on valid event", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage);
    src.dispatch(JSON.stringify({ type: "ping", seq: 1 }));
    expect(onMessage).toHaveBeenCalledWith({ type: "ping", seq: 1 });
  });

  it("invokes onInvalid + reports on malformed JSON", () => {
    const reporter = jest.fn();
    configureReporter(reporter);
    const src = makeSource();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage, onInvalid);
    src.dispatch("not json");
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });

  it("passes raw through onMessage in permissive mode on bad shape", () => {
    const src = makeSource();
    const onMessage = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage);
    src.dispatch(JSON.stringify({ type: "ping", seq: "oops" }));
    expect(onMessage).toHaveBeenCalledWith({ type: "ping", seq: "oops" });
  });

  it("invokes onInvalid in strict mode on bad shape", () => {
    registerSchema("stream.ping", "strict");
    const src = makeSource();
    const onMessage = jest.fn();
    const onInvalid = jest.fn();
    validatedEventStream("stream.ping", EventSchema, src as unknown as EventSource, onMessage, onInvalid);
    src.dispatch(JSON.stringify({ type: "ping", seq: "oops" }));
    expect(onMessage).not.toHaveBeenCalled();
    expect(onInvalid).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 0.6.2: Run the test to see it fail**

```bash
npm test -- src/lib/__tests__/validated-stream.test.ts
```

- [ ] **Step 0.6.3: Implement `validated-stream.ts`**

Create `src/frontend/src/lib/validated-stream.ts`:

```ts
import { z } from "zod";
import { getMode } from "./schema-registry";
import { reportParseFailure } from "./schema-errors";

export function validatedEventStream<T>(
  id: string,
  schema: z.ZodType<T>,
  source: EventSource,
  onMessage: (msg: T) => void,
  onInvalid?: (raw: unknown, err: z.ZodError) => void,
): void {
  source.onmessage = (event) => {
    let raw: unknown;
    try { raw = JSON.parse((event as MessageEvent).data); }
    catch (parseErr) {
      const synthetic = new z.ZodError([{
        code: "custom", path: [],
        message: `Invalid JSON: ${(parseErr as Error).message}`,
      }]);
      reportParseFailure({ id, mode: getMode(id), error: synthetic, raw: (event as MessageEvent).data, boundary: "stream" });
      onInvalid?.((event as MessageEvent).data, synthetic);
      return;
    }
    const result = schema.safeParse(raw);
    if (result.success) { onMessage(result.data); return; }
    const mode = getMode(id);
    reportParseFailure({ id, mode, error: result.error, raw, boundary: "stream" });
    if (mode === "permissive") { onMessage(raw as T); return; }
    onInvalid?.(raw, result.error);
  };
}
```

- [ ] **Step 0.6.4: Re-run the test**

```bash
npm test -- src/lib/__tests__/validated-stream.test.ts
```

Expected: all four tests pass.

- [ ] **Step 0.6.5: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/src/lib/validated-stream.ts src/frontend/src/lib/__tests__/validated-stream.test.ts
git commit -m "feat(frontend): add validatedEventStream for SSE/WebSocket message validation"
```

### Task 0.7 — `isPlatformAdmin` in authStore + typed SessionResponse

**Files:**
- Modify: `src/frontend/src/stores/authStore.ts`
- Modify: `src/frontend/src/controllers/API/queries/auth/use-get-auth-session.ts`
- Modify: `src/frontend/src/contexts/authContext.tsx` (wire the setter call — only if the context currently sets `isAdmin`; leave untouched otherwise)

- [ ] **Step 0.7.1: Read current `authStore.ts`**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
cat src/stores/authStore.ts
```

Confirm the shape: `isAdmin: boolean`, `setIsAdmin`, and the `persist` configuration. `isPlatformAdmin` should mirror `isAdmin` exactly.

- [ ] **Step 0.7.2: Write a failing test against the store**

Create `src/frontend/src/stores/__tests__/authStore-platform-admin.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "@jest/globals";
import useAuthStore from "../authStore";

describe("authStore.isPlatformAdmin", () => {
  beforeEach(() => {
    useAuthStore.setState({ isAdmin: false, isPlatformAdmin: false });
  });

  it("defaults to false", () => {
    expect(useAuthStore.getState().isPlatformAdmin).toBe(false);
  });

  it("setIsPlatformAdmin updates the flag", () => {
    useAuthStore.getState().setIsPlatformAdmin(true);
    expect(useAuthStore.getState().isPlatformAdmin).toBe(true);
  });
});
```

Run and expect fail: `setIsPlatformAdmin` does not exist.

- [ ] **Step 0.7.3: Add the flag + setter to `authStore.ts`**

Edit `src/frontend/src/stores/authStore.ts` to (a) add `isPlatformAdmin: boolean` to `AuthState`, default `false`, (b) add `setIsPlatformAdmin: (v: boolean) => void` and implement it, (c) include `isPlatformAdmin` in the `persist` partialize allow-list if that pattern is present.

- [ ] **Step 0.7.4: Re-run the store test**

```bash
npm test -- src/stores/__tests__/authStore-platform-admin.test.ts
```

Expected: both tests pass.

- [ ] **Step 0.7.5: Type the `SessionResponse` and thread the flag**

Edit `src/frontend/src/controllers/API/queries/auth/use-get-auth-session.ts`:

Replace:

```ts
export interface SessionResponse {
  authenticated: boolean;
  user?: {
    id: string;
    username: string;
    is_active: boolean;
    is_superuser: boolean;
    [key: string]: any;
  };
  store_api_key?: string;
}
```

With (remove the `[key: string]: any` escape hatch, add `is_platform_admin`):

```ts
export interface SessionResponse {
  authenticated: boolean;
  user?: {
    id: string;
    username: string;
    is_active: boolean;
    is_superuser: boolean;
    is_platform_admin: boolean;
  };
  store_api_key?: string;
}
```

- [ ] **Step 0.7.6: Update the session-success callback**

In whichever file currently does `setIsAdmin(session.user.is_superuser)` after a session fetch (check `src/contexts/authContext.tsx`; grep for `setIsAdmin(` if needed), add:

```ts
useAuthStore.getState().setIsPlatformAdmin(Boolean(session.user?.is_platform_admin));
```

as a sibling line.

- [ ] **Step 0.7.7: Run affected tests**

```bash
npm test -- src/stores/__tests__ src/contexts/__tests__
```

Expected: no new failures. Test error count may shift by a small amount — re-record against baseline.

- [ ] **Step 0.7.8: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add \
  src/frontend/src/stores/authStore.ts \
  src/frontend/src/stores/__tests__/authStore-platform-admin.test.ts \
  src/frontend/src/controllers/API/queries/auth/use-get-auth-session.ts \
  src/frontend/src/contexts/authContext.tsx
git commit -m "feat(frontend): thread is_platform_admin from /auth/session into authStore

Removes the \"[key: string]: any\" escape hatch from SessionResponse and
surfaces is_platform_admin (already on UserRead) as a first-class
authStore.isPlatformAdmin flag. Needed for the admin-gated
ValidationErrorOverlay landing later in Phase 0."
```

### Task 0.8 — Validation error slice + `<ValidationErrorOverlay />`

**Files:**
- Create: `src/frontend/src/stores/validationErrorStore.ts`
- Create: `src/frontend/src/stores/__tests__/validationErrorStore.test.ts`
- Create: `src/frontend/src/components/common/ValidationErrorOverlay/index.tsx`
- Create: `src/frontend/src/components/common/ValidationErrorOverlay/__tests__/ValidationErrorOverlay.test.tsx`
- Modify: `src/frontend/src/App.tsx` (mount the overlay at root)
- Modify: `src/frontend/src/lib/schema-errors.ts` (wire the default reporter to push into the store when available)

- [ ] **Step 0.8.1: Write the store test**

Create `src/frontend/src/stores/__tests__/validationErrorStore.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "@jest/globals";
import { z } from "zod";
import useValidationErrorStore from "../validationErrorStore";

describe("validationErrorStore", () => {
  beforeEach(() => {
    useValidationErrorStore.setState({ errors: [], mutedIds: new Set() });
    sessionStorage.clear();
  });

  it("push adds an error to the front", () => {
    const z1 = new z.ZodError([]);
    useValidationErrorStore.getState().push({ id: "a", boundary: "http", mode: "permissive", error: z1, raw: null, at: Date.now() });
    expect(useValidationErrorStore.getState().errors).toHaveLength(1);
  });

  it("mute persists via sessionStorage", () => {
    useValidationErrorStore.getState().mute("a");
    expect(sessionStorage.getItem("dto.mutedSchemaIds")).toContain("a");
  });

  it("filters out muted ids on push", () => {
    useValidationErrorStore.getState().mute("a");
    const z1 = new z.ZodError([]);
    useValidationErrorStore.getState().push({ id: "a", boundary: "http", mode: "permissive", error: z1, raw: null, at: Date.now() });
    expect(useValidationErrorStore.getState().errors).toHaveLength(0);
  });
});
```

- [ ] **Step 0.8.2: Implement the store**

Create `src/frontend/src/stores/validationErrorStore.ts`:

```ts
import { create } from "zustand";
import type { z } from "zod";

export type StoredValidationError = {
  id: string;
  boundary: "http" | "storage" | "stream";
  mode: "permissive" | "strict";
  error: z.ZodError;
  raw: unknown;
  at: number;
};

type Store = {
  errors: StoredValidationError[];
  mutedIds: Set<string>;
  push: (err: StoredValidationError) => void;
  mute: (id: string) => void;
  unmute: (id: string) => void;
  clear: () => void;
};

const MUTE_KEY = "dto.mutedSchemaIds";
const MAX_ERRORS = 100;

function loadMuted(): Set<string> {
  try {
    const raw = sessionStorage.getItem(MUTE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? new Set(arr) : new Set();
  } catch { return new Set(); }
}

function saveMuted(s: Set<string>): void {
  try { sessionStorage.setItem(MUTE_KEY, JSON.stringify([...s])); } catch { /* noop */ }
}

const useValidationErrorStore = create<Store>((set, get) => ({
  errors: [],
  mutedIds: loadMuted(),
  push: (err) => set((s) => {
    if (s.mutedIds.has(err.id)) return s;
    return { errors: [err, ...s.errors].slice(0, MAX_ERRORS) };
  }),
  mute: (id) => set((s) => {
    const next = new Set(s.mutedIds); next.add(id); saveMuted(next); return { mutedIds: next };
  }),
  unmute: (id) => set((s) => {
    const next = new Set(s.mutedIds); next.delete(id); saveMuted(next); return { mutedIds: next };
  }),
  clear: () => set({ errors: [] }),
}));

export default useValidationErrorStore;
```

- [ ] **Step 0.8.3: Wire the default reporter to push into the store**

Edit `src/frontend/src/lib/schema-errors.ts`. Replace the `DEFAULT_REPORTER` definition with one that **dynamically imports** the store to avoid a circular dependency at load time:

```ts
const DEFAULT_REPORTER: Reporter = (payload) => {
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.warn(`[ValidationError][${payload.boundary}][${payload.mode}] ${payload.id}`, payload.error.issues, { raw: payload.raw });
  }
  // Fire-and-forget push to the in-app store; keeps app path untouched if the store isn't present (e.g. unit tests).
  void import("@/stores/validationErrorStore").then(({ default: store }) => {
    store.getState().push({
      id: payload.id, boundary: payload.boundary, mode: payload.mode,
      error: payload.error, raw: payload.raw, at: Date.now(),
    });
  }).catch(() => { /* noop */ });
};
```

- [ ] **Step 0.8.4: Re-run store + errors tests**

```bash
npm test -- src/stores/__tests__/validationErrorStore.test.ts src/lib/__tests__/schema-errors.test.ts
```

Expected: all pass. The schema-errors tests should still pass because `_resetReporterForTest` replaces the default reporter before each test.

- [ ] **Step 0.8.5: Write the overlay component test**

Create `src/frontend/src/components/common/ValidationErrorOverlay/__tests__/ValidationErrorOverlay.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "@jest/globals";
import { render, screen } from "@testing-library/react";
import { z } from "zod";
import ValidationErrorOverlay from "..";
import useAuthStore from "@/stores/authStore";
import useValidationErrorStore from "@/stores/validationErrorStore";

describe("<ValidationErrorOverlay />", () => {
  beforeEach(() => {
    useAuthStore.setState({ isAdmin: false, isPlatformAdmin: false });
    useValidationErrorStore.setState({ errors: [], mutedIds: new Set() });
  });

  it("renders nothing for non-admin users", () => {
    useValidationErrorStore.getState().push({
      id: "x", boundary: "http", mode: "permissive",
      error: new z.ZodError([]), raw: null, at: Date.now(),
    });
    const { container } = render(<ValidationErrorOverlay />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the toggle for super admin", () => {
    useAuthStore.setState({ isAdmin: true });
    render(<ValidationErrorOverlay />);
    expect(screen.getByTestId("validation-error-overlay-toggle")).toBeInTheDocument();
  });

  it("renders the toggle for platform admin", () => {
    useAuthStore.setState({ isPlatformAdmin: true });
    render(<ValidationErrorOverlay />);
    expect(screen.getByTestId("validation-error-overlay-toggle")).toBeInTheDocument();
  });
});
```

- [ ] **Step 0.8.6: Implement the overlay component**

Create `src/frontend/src/components/common/ValidationErrorOverlay/index.tsx`:

```tsx
import { useState } from "react";
import useAuthStore from "@/stores/authStore";
import useValidationErrorStore from "@/stores/validationErrorStore";

export default function ValidationErrorOverlay() {
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const isPlatformAdmin = useAuthStore((s) => s.isPlatformAdmin);
  const visible = isAdmin || isPlatformAdmin;

  // Subscribe AFTER the visibility gate so non-admins pay zero cost.
  if (!visible) return null;
  return <OverlayInner />;
}

function OverlayInner() {
  const errors = useValidationErrorStore((s) => s.errors);
  const mute = useValidationErrorStore((s) => s.mute);
  const clear = useValidationErrorStore((s) => s.clear);
  const [open, setOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const selected = selectedIdx !== null ? errors[selectedIdx] : null;
  return (
    <>
      <button
        data-testid="validation-error-overlay-toggle"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-2 right-2 z-[9999] rounded bg-red-600 px-2 py-1 text-xs text-white shadow"
        aria-label="Validation errors"
      >
        ⚠︎ {errors.length}
      </button>
      {open && (
        <div className="fixed bottom-12 right-2 z-[9999] flex max-h-[70vh] w-[600px] flex-col overflow-hidden rounded border bg-background shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <div className="text-sm font-semibold">Validation errors ({errors.length})</div>
            <div className="flex gap-2 text-xs">
              <button onClick={clear} className="underline">Clear</button>
              <button onClick={() => setOpen(false)} className="underline">Close</button>
            </div>
          </div>
          <div className="flex flex-1 overflow-hidden">
            <ul className="w-1/2 overflow-y-auto border-r text-xs">
              {errors.map((e, i) => (
                <li key={`${e.id}-${e.at}-${i}`} className="cursor-pointer border-b px-2 py-1 hover:bg-muted"
                    onClick={() => setSelectedIdx(i)}>
                  <div className="font-mono">{e.id}</div>
                  <div className="opacity-60">{e.boundary} · {e.mode}</div>
                </li>
              ))}
            </ul>
            <div className="w-1/2 overflow-y-auto p-2 text-xs">
              {selected ? (
                <>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-mono">{selected.id}</span>
                    <div className="flex gap-2">
                      <button onClick={() => navigator.clipboard.writeText(JSON.stringify(selected.raw, null, 2))} className="underline">Copy payload</button>
                      <button onClick={() => mute(selected.id)} className="underline">Mute</button>
                    </div>
                  </div>
                  <pre className="whitespace-pre-wrap break-all rounded bg-muted p-2">
{JSON.stringify(selected.error.issues, null, 2)}
                  </pre>
                  <pre className="mt-2 whitespace-pre-wrap break-all rounded bg-muted p-2">
{JSON.stringify(selected.raw, null, 2)}
                  </pre>
                </>
              ) : (
                <div className="opacity-60">Select an error on the left.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 0.8.7: Run the overlay tests**

```bash
npm test -- src/components/common/ValidationErrorOverlay/__tests__/ValidationErrorOverlay.test.tsx
```

Expected: all three tests pass.

- [ ] **Step 0.8.8: Mount the overlay at App root**

Edit `src/frontend/src/App.tsx`. Import and render `<ValidationErrorOverlay />` at the very top of the returned JSX tree (above whatever the existing root is). Keep its position unconditional — the component self-gates on role.

```tsx
import ValidationErrorOverlay from "@/components/common/ValidationErrorOverlay";
// ...
return (
  <>
    <ValidationErrorOverlay />
    {/* existing root JSX unchanged */}
  </>
);
```

- [ ] **Step 0.8.9: Re-run the full jest suite**

```bash
npm test -- --ci 2>&1 | tail -10
```

Expected: baseline count ± 3 new passing tests (overlay) ± 2 (store) ± 2 (authStore) ± however many the `[key: string]: any` removal surfaces. Record the delta in `/tmp/dto-phase0-tests.txt`.

- [ ] **Step 0.8.10: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add \
  src/frontend/src/stores/validationErrorStore.ts \
  src/frontend/src/stores/__tests__/validationErrorStore.test.ts \
  src/frontend/src/components/common/ValidationErrorOverlay \
  src/frontend/src/App.tsx \
  src/frontend/src/lib/schema-errors.ts
git commit -m "feat(frontend): add admin-gated ValidationErrorOverlay + error slice

Overlay self-gates on authStore.isAdmin || isPlatformAdmin. Non-admins
pay zero cost: the component early-returns before subscribing to the
error store. Mute-per-schema persists in sessionStorage so it doesn't
survive a new session."
```

### Task 0.9 — Migrate `useGetFlow` end-to-end (walking skeleton)

**Files:**
- Create: `src/frontend/src/schemas/api/flows.ts` (hand-written for now; will be regenerated in Phase 1)
- Create: `src/frontend/src/schemas/api/generated.meta.ts`
- Create: `src/frontend/src/schemas/index.ts`
- Modify: `src/frontend/src/controllers/API/queries/flows/use-get-flow.ts` (or equivalent — grep to find the actual path)

- [ ] **Step 0.9.1: Locate the current `useGetFlow` hook**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
grep -rn "useGetFlow\b" src/controllers/API/queries --include="*.ts" | head -5
```

Record the exact file path. If the hook is named differently (e.g. `useGetRefreshFlowsQuery`), pick the simplest single-flow fetch as the walking-skeleton target.

- [ ] **Step 0.9.2: Create the hand-written Flow schema**

Create `src/frontend/src/schemas/api/flows.ts`:

```ts
import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

export const FlowSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  data: z.unknown().nullable().optional(),
  is_component: z.boolean().optional(),
  updated_at: z.string().optional(),
  folder_id: z.string().nullable().optional(),
  user_id: z.string().nullable().optional(),
  icon: z.string().nullable().optional(),
  icon_bg_color: z.string().nullable().optional(),
  gradient: z.string().nullable().optional(),
  tags: z.array(z.string()).nullable().optional(),
  endpoint_name: z.string().nullable().optional(),
  access_type: z.enum(["PRIVATE", "PUBLIC"]).optional(),
}).passthrough(); // permissive during Phase 0; Phase 1 regeneration will produce the authoritative shape.

registerSchema("api.flows.getFlow", "permissive");

export type FlowSchemaType = z.infer<typeof FlowSchema>;
```

> Note: we use `.passthrough()` in Phase 0 only because this schema is a Phase-0 placeholder. Phase 1's `openapi-zod-client`-generated version becomes authoritative and should not use `.passthrough()` globally.

- [ ] **Step 0.9.3: Create the meta/registry barrel file**

Create `src/frontend/src/schemas/api/generated.meta.ts`:

```ts
// Populated by Phase 1 regeneration. Phase 0 leaves it empty and each schema self-registers.
export const SCHEMA_MODES: Array<[string, "permissive" | "strict"]> = [];
```

Create `src/frontend/src/schemas/index.ts`:

```ts
export * as FlowsApi from "./api/flows";
// Phase 1 will extend this barrel with every generated + hand-written schema file.
```

- [ ] **Step 0.9.4: Migrate the hook**

Edit the hook file found in Step 0.9.1. If it looks like:

```ts
export const useGetFlow = (id: string) =>
  useQuery({
    queryKey: ["flow", id],
    queryFn: () => api.get(`/api/v1/flows/${id}`).then(r => r.data),
  });
```

Change to:

```ts
import { FlowSchema } from "@/schemas/api/flows";
import { validatedQueryFn } from "@/lib/validated-fetch";

export const useGetFlow = (id: string) =>
  useQuery({
    queryKey: ["flow", id],
    queryFn: validatedQueryFn(
      "api.flows.getFlow",
      FlowSchema,
      async () => (await api.get(`/api/v1/flows/${id}`)).data,
    ),
  });
```

If the real hook uses a different internal pattern (e.g. `UseRequestProcessor`), adapt the two-line pattern to fit, keeping the public signature identical.

- [ ] **Step 0.9.5: Verify type-check passes**

```bash
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
```

Expected: `0`. If any new production errors appear, fix them (typically a call site narrowing a return field; apply minimal type tightening).

- [ ] **Step 0.9.6: Smoke-test dev server**

```bash
timeout 30 npm start 2>&1 | tee /tmp/dto-phase0-devserver.log || true
grep -E "(ready in|Local:)" /tmp/dto-phase0-devserver.log | head -3
```

Expected: Vite ready line within ~5s. If the server fails to start, investigate — do not proceed until it boots.

- [ ] **Step 0.9.7: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add \
  src/frontend/src/schemas/api/flows.ts \
  src/frontend/src/schemas/api/generated.meta.ts \
  src/frontend/src/schemas/index.ts \
  src/frontend/src/controllers/API/queries/flows/<hook-file>.ts  # use actual path from 0.9.1
git commit -m "feat(frontend): migrate useGetFlow to validatedQueryFn (walking skeleton)

Phase-0 hand-written FlowSchema (permissive mode). Phase 1 regenerates
this file from OpenAPI. No consumer-visible type change — the hook's
return type is z.infer<typeof FlowSchema>, identical to the existing
Flow type."
```

### Task 0.10 — Author the migration-recipe doc

**Files:**
- Create: `docs/frontend/validation-wrapper.md`

- [ ] **Step 0.10.1: Write the doc**

Create `docs/frontend/validation-wrapper.md`:

```markdown
# Validation wrapper — recipe

Every hook in `src/controllers/API/queries/*` migrates via this two-line change.

## HTTP queries (GET)

```ts
import { FlowSchema } from "@/schemas/api/flows";
import { validatedQueryFn } from "@/lib/validated-fetch";

export const useGetFlow = (id: string) =>
  useQuery({
    queryKey: ["flow", id],
    queryFn: validatedQueryFn(
      "api.flows.getFlow",          // id = "api.<tag>.<operation>"
      FlowSchema,
      async () => (await api.get(`/api/v1/flows/${id}`)).data,
    ),
  });
```

## HTTP mutations (POST/PATCH/DELETE)

```ts
import { FlowSchema, UpdateFlowSchema } from "@/schemas/api/flows";
import { validatedMutationFn } from "@/lib/validated-fetch";

export const useUpdateFlow = () =>
  useMutation({
    mutationFn: validatedMutationFn(
      "api.flows.updateFlow",
      UpdateFlowSchema,
      FlowSchema,
      async (body) => (await api.patch(`/api/v1/flows/${body.id}`, body)).data,
    ),
  });
```

## Storage (Zustand persist)

```ts
import { FlowsSliceSchema } from "@/schemas/app/storage/flowsSlice";
import { validatedStorage } from "@/lib/validated-storage";

persist(..., {
  name: "flows-storage",
  storage: createJSONStorage(() => validatedStorage("storage.flowsSlice", FlowsSliceSchema)),
})
```

## SSE / EventSource

```ts
import { BuildEventSchema } from "@/schemas/app/stream/buildEvents";
import { validatedEventStream } from "@/lib/validated-stream";

const es = new EventSource(`/api/v1/build/${flowId}/stream`);
validatedEventStream("stream.buildEvents", BuildEventSchema, es, (event) => {
  // event is narrowed via discriminated union
  if (event.type === "vertex_end") { /* ... */ }
});
```

## Schema id naming

- HTTP: `api.<tag>.<operation>` — e.g. `api.flows.getFlow`, `api.templates.list`.
- Storage: `storage.<slice>` — e.g. `storage.flowsSlice`.
- Stream: `stream.<name>` — e.g. `stream.buildEvents`, `stream.chatMessages`.

The id is the **only** string that appears at the call site; everything else is imported.

## Flipping to strict

When a domain's 1-week permissive bake completes with zero ValidationError Sentry events (or, pre-Sentry, zero overlay entries for that domain's ids on admin-driven smoke traffic), add the schema to `src/schemas/api/generated.meta.ts`:

```ts
export const SCHEMA_MODES: Array<[string, "permissive" | "strict"]> = [
  ["api.flows.getFlow", "strict"],
  // ...
];
```
```

- [ ] **Step 0.10.2: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add docs/frontend/validation-wrapper.md
git commit -m "docs(frontend): validation-wrapper recipe for downstream migrations"
```

### Task 0.11 — Phase 0 gate + merge-back

- [ ] **Step 0.11.1: Run the full gate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend

# Gate 1: production tsc = 0
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l

# Gate 2: test tsc count within baseline + small delta
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -E "__tests__|\.test\.|\.spec\." | wc -l

# Gate 3: jest
npm test -- --ci 2>&1 | tail -5

# Gate 4: build
npm run build 2>&1 | tail -5
```

All four must pass: prod = 0, test count ≤ 240 (baseline 235 + small tolerance for the ~3 new overlay/store tests passing + any cascades from the `[key: string]: any` removal), jest ≥ baseline, build clean.

- [ ] **Step 0.11.2: Report final Phase 0 summary, request merge approval**

Show the user:
- Worktree at `.worktrees/dto-boundary-2026-04/`, 11 commits on `dto/boundary-types-2026-04`.
- Prod tsc: 0
- Test tsc: <current count> (delta from baseline: <diff>)
- Jest: <suites>/<tests>
- Build: clean
- Dev server boots.

Ask: "Phase 0 complete and gates green. Ready to merge `dto/boundary-types-2026-04` into `platform-multi-tenant` as the Phase-0 walking-skeleton, or keep the branch running and land Phase 1 on top first?"

- [ ] **Step 0.11.3: Merge (only after explicit approval) — one of two paths**

**Path A — merge after each phase (conservative):**
```bash
cd /Users/brycedeneen/dev/langflow
git checkout platform-multi-tenant
git merge --no-ff dto/boundary-types-2026-04 -m "merge: DTO boundary-types Phase 0 — foundation

11 commits landing the zod + validation-wrapper scaffold, admin-gated
ValidationErrorOverlay, isPlatformAdmin wiring, and useGetFlow as the
walking-skeleton endpoint."
git worktree remove .worktrees/dto-boundary-2026-04  # re-create for Phase 1 below
```

**Path B — keep the worktree open (faster iteration):** stay on `dto/boundary-types-2026-04` and proceed directly to Phase 1. Merge to `platform-multi-tenant` once Phase 1 also lands.

---

## Phase 1 — Generate + hand-write all schemas

**Goal:** `make gen-frontend-schemas` produces one schema file per OpenAPI tag; hand-written schemas cover the 34 `include_in_schema=False` endpoints; all schemas registered permissive. No call-site changes beyond what Phase 0 already did.

**Scope:** build the generator toolchain, produce schemas, add CI gates. Do NOT migrate any call sites beyond `useGetFlow` from Phase 0.

### Task 1.1 — Add `make openapi-json` target

**Files:**
- Modify: `Makefile` (root)

Langflow has no existing `make openapi` target. Chunk 0 confirmed this; Chunk 1 adds one.

- [ ] **Step 1.1.1: Locate backend entrypoint + openapi function**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
grep -rn "def custom_openapi\|get_openapi\|FastAPI(" src/backend/base/langflow --include="*.py" | head -10
```

Record the path that exposes the FastAPI app object; we'll import and dump its schema from a short Python snippet.

- [ ] **Step 1.1.2: Add the Makefile target**

Edit `Makefile` (root). Add (at the bottom or with other frontend targets):

```makefile
.PHONY: openapi_json
openapi_json: ## Dump the backend OpenAPI schema to scripts/openapi.json
	@mkdir -p scripts
	uv run --no-sync python -c "import json; from langflow.main import create_app; a = create_app(); print(json.dumps(a.openapi(), indent=2))" > scripts/openapi.json
	@echo "Wrote scripts/openapi.json ($$(wc -l < scripts/openapi.json) lines)"

.PHONY: gen_frontend_schemas
gen_frontend_schemas: openapi_json ## Regenerate src/frontend/src/schemas/api/*.ts from OpenAPI
	cd src/frontend && node scripts/gen-schemas.mjs ../../scripts/openapi.json
	cd src/frontend && npx biome format --write src/schemas/api
```

The Python snippet imports `langflow.main.create_app` — confirm this is the correct import path from Step 1.1.1; if not, substitute.

- [ ] **Step 1.1.3: Run the openapi target**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
make openapi_json
```

Expected: `scripts/openapi.json` is written; 1000+ lines. Every endpoint declared in a router with `include_in_schema` defaulting to True (i.e. roughly 120 of the ~150 endpoints) appears.

- [ ] **Step 1.1.4: Pause, ask, commit (Makefile only; openapi.json is gitignored)**

Add `scripts/openapi.json` to `.gitignore` if not already covered. Verify:

```bash
git status scripts/openapi.json
```

Expected: `scripts/openapi.json` should NOT be listed as tracked; if it is, add an entry to `.gitignore` and re-check.

```bash
git add Makefile .gitignore
git commit -m "build: add make openapi_json + gen_frontend_schemas targets

openapi_json dumps the FastAPI schema to scripts/openapi.json (gitignored).
gen_frontend_schemas is the user-facing target that Phase 1's
scripts/gen-schemas.mjs consumes to regenerate src/schemas/api/*.ts."
```

### Task 1.2 — Write the generator + post-process script

**Files:**
- Create: `src/frontend/scripts/gen-schemas.mjs`

- [ ] **Step 1.2.1: Write the script**

Create `src/frontend/scripts/gen-schemas.mjs`:

```js
#!/usr/bin/env node
// Usage: node scripts/gen-schemas.mjs <path-to-openapi.json>
// Invokes openapi-zod-client in schemas-only mode and splits the single
// output file into one file per OpenAPI tag.
//
// Output tree:
//   src/schemas/api/
//     generated.meta.ts   (registry entries, rewritten each run)
//     flows.ts            (one file per tag)
//     templates.ts
//     ...

import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const [, , openapiPath] = process.argv;
if (!openapiPath) { console.error("Usage: gen-schemas.mjs <openapi.json>"); process.exit(2); }

const TMP = path.resolve("scripts", "generated-schemas.ts");
const OUT_DIR = path.resolve("src", "schemas", "api");

fs.mkdirSync(path.dirname(TMP), { recursive: true });

// Run openapi-zod-client in schemas-only mode.
execSync(
  `npx openapi-zod-client "${openapiPath}" --output "${TMP}" --export-schemas --schemas-only`,
  { stdio: "inherit" },
);

const raw = fs.readFileSync(TMP, "utf8");

// Parse: every schema const is `export const <Name>Schema = z...;`.
// Group by operation tag. openapi-zod-client emits a `const endpoints = [...]`
// block; use it to map schema names -> tag.
const endpointMatch = raw.match(/const endpoints\s*=\s*\[([\s\S]*?)\n\];/);
if (!endpointMatch) { console.error("Could not find endpoints block in generated output"); process.exit(3); }

const byTag = new Map(); // tag -> Set<schemaName>
for (const m of endpointMatch[1].matchAll(/alias:\s*"([^"]+)"[\s\S]*?response:\s*([A-Za-z0-9_]+)[\s\S]*?tags?:\s*\[\s*"([^"]+)"/g)) {
  const [, , schemaName, tag] = m;
  if (!byTag.has(tag)) byTag.set(tag, new Set());
  byTag.get(tag).add(schemaName);
}

// Also collect every schema declaration verbatim.
const declarations = new Map(); // name -> declaration text (export const ... = ...;)
for (const m of raw.matchAll(/export const ([A-Za-z0-9_]+)\s*=\s*([\s\S]*?);\n(?=export const|\nconst endpoints|$)/g)) {
  declarations.set(m[1], m[0]);
}

// Kebab->lowercase tag filename.
const toFileName = (tag) => tag.toLowerCase().replace(/[^a-z0-9]+/g, "_") + ".ts";

fs.rmSync(OUT_DIR, { recursive: true, force: true });
fs.mkdirSync(OUT_DIR, { recursive: true });

const registry = []; // [id, "permissive" | "strict"]
const barrelExports = [];

for (const [tag, schemas] of byTag) {
  const fname = toFileName(tag);
  const body = [
    `// AUTO-GENERATED by scripts/gen-schemas.mjs. Do not edit by hand.`,
    `// Run 'make gen_frontend_schemas' to regenerate.`,
    `import { z } from "zod";`,
    `import { registerSchema } from "@/lib/schema-registry";`,
    ``,
    ...[...schemas].map((s) => declarations.get(s) ?? `// MISSING declaration for ${s}`),
    ``,
    ...[...schemas].map((s) => {
      const id = `api.${tag.toLowerCase()}.${s.replace(/Schema$/, "")}`;
      registry.push([id, "permissive"]);
      return `registerSchema(${JSON.stringify(id)}, "permissive");`;
    }),
    ``,
  ].join("\n");
  fs.writeFileSync(path.join(OUT_DIR, fname), body);
  barrelExports.push(`export * as ${tag.replace(/[^A-Za-z0-9]/g, "")} from "./api/${fname.replace(/\.ts$/, "")}";`);
}

// generated.meta.ts — authoritative registry.
const meta = [
  `// AUTO-GENERATED. Edit strict flags per-domain as migrations finish.`,
  `import { registerSchema } from "@/lib/schema-registry";`,
  ``,
  `export const SCHEMA_MODES: Array<[string, "permissive" | "strict"]> = [`,
  ...registry.map(([id, mode]) => `  [${JSON.stringify(id)}, ${JSON.stringify(mode)}],`),
  `];`,
  ``,
  `SCHEMA_MODES.forEach(([id, mode]) => registerSchema(id, mode));`,
  ``,
].join("\n");
fs.writeFileSync(path.join(OUT_DIR, "generated.meta.ts"), meta);

// Warn on any file > 500 lines.
for (const f of fs.readdirSync(OUT_DIR)) {
  const lc = fs.readFileSync(path.join(OUT_DIR, f), "utf8").split("\n").length;
  if (lc > 500) console.warn(`WARN: ${f} is ${lc} lines (>500). Consider further splitting.`);
}

fs.unlinkSync(TMP);
console.log(`Wrote ${byTag.size} tag files to ${OUT_DIR}; ${registry.length} schemas registered.`);
```

- [ ] **Step 1.2.2: Make it executable**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
chmod +x src/frontend/scripts/gen-schemas.mjs
```

- [ ] **Step 1.2.3: Run it**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
make gen_frontend_schemas
```

Expected: `src/frontend/src/schemas/api/` populated with 15–25 `.ts` files plus `generated.meta.ts`. Console reports the tag count. Any file >500 lines produces a `WARN`.

- [ ] **Step 1.2.4: Reconcile with Phase 0's hand-written `flows.ts`**

Phase 0 created a hand-written `src/frontend/src/schemas/api/flows.ts`. The generator rewrote it. The `useGetFlow` hook imports `FlowSchema` from that path. Confirm:

```bash
grep -n "FlowSchema" src/frontend/src/schemas/api/flows.ts | head -5
grep -n "api.flows.getFlow" src/frontend/src/schemas/api/flows.ts src/frontend/src/schemas/api/generated.meta.ts
```

Expected: the generator's `FlowSchema` exists; its registered id is `api.flows.getFlow` or a close variant (confirmed in `generated.meta.ts`). If the id differs, update the `useGetFlow` hook's id string to match, **or** rename in `generated.meta.ts` — whichever is more natural given the actual OpenAPI operation name.

- [ ] **Step 1.2.5: Verify tsc stays clean + jest green**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
npm test -- --ci 2>&1 | tail -5
```

Expected: production errors remain at 0; test suite passes at baseline.

If the generated files produce type errors in the currently-migrated `useGetFlow` (e.g. because `FlowSchema` now has a different shape than the hand-written Phase-0 one), fix the one call site to match.

- [ ] **Step 1.2.6: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/scripts/gen-schemas.mjs src/frontend/src/schemas/api/
# If useGetFlow needed an id/shape tweak:
git add src/frontend/src/controllers/API/queries/flows/<hook-file>.ts
git commit -m "feat(frontend): add schema generator + commit initial generated output

scripts/gen-schemas.mjs splits openapi-zod-client's single-file output
into one file per OpenAPI tag and rewrites generated.meta.ts as the
authoritative strict-flag registry.

Phase 0's hand-written flows.ts is replaced by generated output; the
walking-skeleton useGetFlow continues to work unchanged."
```

### Task 1.3 — Hand-written schemas for OpenAPI-hidden endpoints

**Files:** one file per router group with `include_in_schema=False`:
- Create: `src/frontend/src/schemas/app/internal/auth.ts` — `/auth/session`, `/auth/login`, `/auth/refresh`, `/auth/logout`
- Create: `src/frontend/src/schemas/app/internal/api_key.ts` — all `/api_key/*`
- Create: `src/frontend/src/schemas/app/internal/variables.ts` — all `/variables/*`
- Create: `src/frontend/src/schemas/app/internal/store.ts` — all `/store/*`
- Create: `src/frontend/src/schemas/app/internal/voice.ts` — all `/voice/*`
- Create: `src/frontend/src/schemas/app/internal/models.ts` — all `/models/*`
- Create: `src/frontend/src/schemas/app/internal/model_options.ts` — `/model_options/*`
- Create: `src/frontend/src/schemas/app/internal/validate.ts` — `/validate/code`
- Create: `src/frontend/src/schemas/app/internal/chat_internal.ts` — hidden `/build/*` routes

**Pattern:** each file mirrors a generated file — imports zod + `registerSchema`, exports one or more `Schema` constants, registers each under `api.<router>.<operation>` naming, and re-exports inferred types.

- [ ] **Step 1.3.1: `auth.ts`**

Create `src/frontend/src/schemas/app/internal/auth.ts`:

```ts
import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

export const UserReadSchema = z.object({
  id: z.string().uuid(),
  username: z.string(),
  is_active: z.boolean(),
  is_superuser: z.boolean(),
  is_platform_admin: z.boolean(),
  profile_image: z.string().nullable().optional(),
  store_api_key: z.string().nullable().optional(),
  create_at: z.string().optional(),
  updated_at: z.string().optional(),
  last_login_at: z.string().nullable().optional(),
  optins: z.record(z.unknown()).nullable().optional(),
});

export const SessionResponseSchema = z.object({
  authenticated: z.boolean(),
  user: UserReadSchema.optional(),
  store_api_key: z.string().optional(),
});

export const TokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string().optional(),
  token_type: z.string(),
});

registerSchema("api.auth.getSession", "permissive");
registerSchema("api.auth.login", "permissive");
registerSchema("api.auth.refresh", "permissive");
registerSchema("api.auth.logout", "permissive");

export type SessionResponse = z.infer<typeof SessionResponseSchema>;
export type UserRead = z.infer<typeof UserReadSchema>;
export type TokenResponse = z.infer<typeof TokenResponseSchema>;
```

- [ ] **Step 1.3.2: `api_key.ts`**

Read the backend router to determine response shapes:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
cat src/backend/base/langflow/api/v1/api_key.py
grep -n "class ApiKey\|class APIKey\|class.*Key.*Read\|ApiKeyRead" src/backend/base/langflow/services/database/models/api_key/*.py
```

Create `src/frontend/src/schemas/app/internal/api_key.ts` with schemas for list, create, delete, and store-key responses, following the auth.ts pattern. Register each under `api.api_key.<op>`.

- [ ] **Step 1.3.3: `variables.ts`**

Mirror the pattern using `VariableRead` from `src/backend/base/langflow/services/database/models/variable/`. Register `api.variables.list|create|update|delete`.

- [ ] **Step 1.3.4: `store.ts`, `voice.ts`, `models.ts`, `model_options.ts`, `validate.ts`, `chat_internal.ts`**

Same pattern for each. For each hidden router:
1. Open its Python file under `src/backend/base/langflow/api/`.
2. Note each route's `response_model=` type (or inspect the return value if no explicit model).
3. Author a zod schema that matches.
4. Register each operation under `api.<router>.<op>` with `permissive` mode.

If a route returns a raw `dict` without a response_model, emit a permissive `z.record(z.unknown())` and add a TODO comment: `// TODO: backend returns untyped dict; add z.object(...) once route is tightened (Phase 2.h risk)`.

- [ ] **Step 1.3.5: Extend `schemas/index.ts` barrel**

Edit `src/frontend/src/schemas/index.ts` to also re-export the internal schemas:

```ts
export * as FlowsApi from "./api/flows";
// ... other generated
export * as AuthInternal from "./app/internal/auth";
export * as ApiKeyInternal from "./app/internal/api_key";
export * as VariablesInternal from "./app/internal/variables";
export * as StoreInternal from "./app/internal/store";
export * as VoiceInternal from "./app/internal/voice";
export * as ModelsInternal from "./app/internal/models";
export * as ModelOptionsInternal from "./app/internal/model_options";
export * as ValidateInternal from "./app/internal/validate";
export * as ChatInternal from "./app/internal/chat_internal";
```

- [ ] **Step 1.3.6: Type-check + jest**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
npm test -- --ci 2>&1 | tail -5
```

Expected: 0 production errors, jest green. No call sites yet consume the internal schemas — they're lying in wait for Phase 2.h.

- [ ] **Step 1.3.7: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add src/frontend/src/schemas/app/internal/ src/frontend/src/schemas/index.ts
git commit -m "feat(frontend): hand-written schemas for OpenAPI-hidden endpoints

Covers the 34 include_in_schema=False routes (auth, api_key, variables,
store, voice, models, model_options, validate, internal chat/build).
All registered permissive; call-site migration happens in Phase 2.h
(and 2.f for auth)."
```

### Task 1.4 — CI gates

**Files:**
- Create: `scripts/check_hidden_routes_have_schemas.py`
- Modify: CI workflow (`.github/workflows/*.yml` — find the frontend job)

- [ ] **Step 1.4.1: Write the Python lint**

Create `scripts/check_hidden_routes_have_schemas.py`:

```python
#!/usr/bin/env python3
"""Fail CI if a backend router adds a new include_in_schema=False route
that has no corresponding entry in src/frontend/src/schemas/app/internal/.

This is a coarse check: it greps router files for the marker and
compares against registered schema ids. It does NOT catch response-shape
drift on already-represented routes; that's left to ValidationError
telemetry during the permissive bake.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "src" / "backend" / "base" / "langflow" / "api"
INTERNAL_DIR = REPO / "src" / "frontend" / "src" / "schemas" / "app" / "internal"

ROUTE_RE = re.compile(
    r'@router\.(?P<method>get|post|patch|delete|put)\(\s*"(?P<path>[^"]+)"[^)]*include_in_schema=False',
    re.MULTILINE | re.DOTALL,
)

hidden: list[tuple[Path, str, str]] = []
for py in BACKEND.rglob("*.py"):
    text = py.read_text()
    for m in ROUTE_RE.finditer(text):
        hidden.append((py, m.group("method"), m.group("path")))

if not INTERNAL_DIR.exists():
    print(f"::error::Missing {INTERNAL_DIR}")
    sys.exit(1)

registered = set()
for f in INTERNAL_DIR.glob("*.ts"):
    for m in re.finditer(r'registerSchema\(\s*"([^"]+)"', f.read_text()):
        registered.add(m.group(1))

# Heuristic: every hidden route should map to at least one registered id
# whose tag matches the router filename stem.
missing = []
for py, method, path in hidden:
    router = py.stem  # e.g. "api_key"
    prefix = f"api.{router}."
    if not any(rid.startswith(prefix) for rid in registered):
        missing.append((py.relative_to(REPO), method, path))

if missing:
    print("::error::Hidden routes without matching schemas in schemas/app/internal/:")
    for py, method, path in missing:
        print(f"  {method.upper():6} {path:60}  ({py})")
    sys.exit(1)

print(f"OK: {len(hidden)} hidden routes across {len({p for p,_,_ in hidden})} files all have matching schema-prefixes.")
```

- [ ] **Step 1.4.2: Run it locally**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
python3 scripts/check_hidden_routes_have_schemas.py
```

Expected: `OK: N hidden routes ...`. If it fails, the schemas in Task 1.3 missed a router — add it.

- [ ] **Step 1.4.3: Find the frontend CI workflow**

```bash
ls .github/workflows/
```

Pick the frontend-test workflow (likely `frontend.yml` or `typescript_test.yml`). Add a step:

```yaml
      - name: Check hidden-route schemas
        run: python3 scripts/check_hidden_routes_have_schemas.py

      - name: Check generated schemas are fresh
        run: |
          make gen_frontend_schemas
          git diff --exit-code src/frontend/src/schemas/api/ || { echo "::error::src/frontend/src/schemas/api/ is stale — run 'make gen_frontend_schemas'"; exit 1; }
```

Exact placement: after `npm install` and before `npx tsc` / jest. If the workflow uses a matrix or a separate backend job has Python available, factor accordingly.

- [ ] **Step 1.4.4: Pause, ask, commit**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git add scripts/check_hidden_routes_have_schemas.py .github/workflows/<workflow-file>.yml
git commit -m "ci: enforce schemas for hidden routes + freshness of generated schemas"
```

### Task 1.5 — Phase 1 gate + merge-back

- [ ] **Step 1.5.1: Run the full gate**

Same four gates as Phase 0 (Step 0.11.1). Plus:

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
python3 scripts/check_hidden_routes_have_schemas.py
make gen_frontend_schemas && git diff --exit-code src/frontend/src/schemas/api/
```

Both must pass.

- [ ] **Step 1.5.2: Pause, ask, merge (only after explicit approval)**

Report: "Phase 1 complete: generator + 9 hand-written internal-endpoint schema files + CI gates. Prod tsc: 0. Test tsc: <N>. Jest: <pass>. Build: clean. Ready to merge to `platform-multi-tenant`?"

If user approves Path A (per-phase merge), merge. Otherwise stay on the branch.

---

## §Migration Pattern (reference for Phases 2.a–2.h)

Every domain chunk in Phase 2 follows this pattern. Each task in a chunk is a call-site migration; the concrete files and schema ids differ per domain.

### Standing mini-template for a domain chunk

1. **Inventory call sites.** Grep the domain's hook folder for every `useQuery`/`useMutation` and every `queryFn:` / `mutationFn:` assignment. Produce a checklist. Expected count is logged per chunk below.

2. **Migrate each hook.** For each hook, apply one of:

   **HTTP query pattern:**
   ```ts
   // before
   queryFn: () => api.get(url).then(r => r.data),
   // after
   queryFn: validatedQueryFn("api.<tag>.<op>", XxxSchema, async () => (await api.get(url)).data),
   ```

   **HTTP mutation pattern:**
   ```ts
   // before
   mutationFn: (body) => api.post(url, body).then(r => r.data),
   // after
   mutationFn: validatedMutationFn("api.<tag>.<op>", ReqSchema, ResSchema, async (b) => (await api.post(url, b)).data),
   ```

3. **Re-export types from `src/types/<domain>/index.ts`** as `z.infer` aliases:
   ```ts
   import type { FlowsApi } from "@/schemas";
   export type Flow = FlowsApi.FlowSchemaType;
   ```
   Keep the old exported names to avoid consumer churn.

4. **Fix cascading tsc errors.** Each domain has 0–30 cascaded errors where previously-any values are now typed. Fix minimally — prefer narrowing at the consumer over widening the schema.

5. **Run gates per-chunk:**
   ```bash
   cd src/frontend
   npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l   # expect 0
   npm test -- --ci 2>&1 | tail -5                                                                      # expect ≥ baseline
   npm run build 2>&1 | tail -5                                                                         # expect clean
   ```

6. **Permissive bake.** Merge the chunk to `platform-multi-tenant`. Let it ride in production for ≥1 week. Monitor overlay (admin-driven) + Sentry once wired. Any `ValidationError` events for this domain's ids pause the strict flip; investigate + fix backend drift or schema bug, reset the 1-week clock.

7. **Flip to strict.** Edit `src/frontend/src/schemas/api/generated.meta.ts` (or `schemas/app/internal/*` for hand-written) — change the domain's entries from `"permissive"` to `"strict"`. Commit separately with message like `feat(types): flip <domain> schemas to strict mode`.

8. **Stop-the-line.** If more than **10 call sites** in the chunk need non-trivial code changes beyond the two-line wrapper swap, STOP. Report findings. The domain likely needs its own sub-spec before continuing.

---

## Phase 2.a — flows

**Scope:** every hook under `src/controllers/API/queries/flows/` and downstream type exports in `src/types/flow/`.

**Budget:** ~1 week. Expected call sites: ~15–25 (grep confirms at start).

### Task 2.a.1 — Inventory

- [ ] **Step 2.a.1.1: Enumerate call sites**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
grep -rln "useQuery\|useMutation" src/controllers/API/queries/flows | tee /tmp/flows-hooks.txt
wc -l /tmp/flows-hooks.txt
```

Record the count. Expect 15–25 files.

### Task 2.a.2 — Migrate hooks

- [ ] **Step 2.a.2.1: Migrate each hook from `/tmp/flows-hooks.txt`**

For each file in the list, apply the HTTP query/mutation pattern from §Migration Pattern. Schema ids follow `api.flows.<operation>`. All schemas come from `@/schemas/api/flows` (the Phase-1 generated module).

Example — a real hook edit (`use-get-refresh-flows-query.ts`, if present):

```ts
// before
queryFn: async () => {
  const response = await api.get(`${getURL("FLOWS")}?remove_example_flows=${remove_example_flows}`);
  return response.data;
},

// after
import { validatedQueryFn } from "@/lib/validated-fetch";
import { FlowListSchema } from "@/schemas/api/flows"; // or whatever the generated name is
// ...
queryFn: validatedQueryFn(
  "api.flows.refreshFlows",
  FlowListSchema,
  async () => (await api.get(`${getURL("FLOWS")}?remove_example_flows=${remove_example_flows}`)).data,
),
```

If the generated schema name doesn't match the expected return shape (e.g. the backend returns a paginated wrapper but the generator called it `FlowPage`), import that name instead. Grep `src/frontend/src/schemas/api/flows.ts` for the candidate.

- [ ] **Step 2.a.2.2: Re-export types from `src/types/flow/index.ts`**

Follow §Migration Pattern step 3.

- [ ] **Step 2.a.2.3: Run gates**

```bash
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." | wc -l
npm test -- --ci 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

If >0 prod errors, work through them one by one. If >10 call sites need non-trivial changes, invoke the stop-the-line rule.

- [ ] **Step 2.a.2.4: Pause, ask, commit**

```bash
git add src/frontend/src/controllers/API/queries/flows/ src/frontend/src/types/flow/
git commit -m "feat(types): migrate flows domain to validated boundary (permissive)

<N> hooks migrated. src/types/flow/index.ts now re-exports z.infer aliases.
Schemas registered in permissive mode; strict flip follows a 1-week bake."
```

### Task 2.a.3 — Strict flip (after 1-week bake)

- [ ] **Step 2.a.3.1: Verify quiet bake**

Check Sentry (once wired) or admin overlay: zero `ValidationError` events with ids starting `api.flows.` for ≥7 days. If not quiet, triage and reset.

- [ ] **Step 2.a.3.2: Flip the flag**

Edit `src/frontend/src/schemas/api/generated.meta.ts`: change every row starting `api.flows.` from `"permissive"` to `"strict"`.

- [ ] **Step 2.a.3.3: Gate + pause + commit**

Gates same as 2.a.2.3. Commit message:

```
feat(types): flip flows schemas to strict mode

<N> flows schema ids flipped. 1-week permissive bake showed zero
ValidationError events under real traffic.
```

---

## Phase 2.b — store hydration (Zustand persist)

**Scope:** every Zustand store under `src/stores/` that uses `persist` middleware, wrapping the storage adapter with `validatedStorage`.

**Budget:** ~3–5 days.

### Task 2.b.1 — Inventory + schemas

- [ ] **Step 2.b.1.1: List persisted stores**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
grep -rln "persist(" src/stores | tee /tmp/persist-stores.txt
wc -l /tmp/persist-stores.txt
```

Record the list. Typical: `flowStore`, `authStore`, `darkStore`, `foldersStore`, `messagesStore`, `typesStore`, `tweaksStore`, `utilityStore` (but inspect output).

- [ ] **Step 2.b.1.2: Author slice schemas**

For each persisted store, create `src/frontend/src/schemas/app/storage/<slice>.ts`. Pattern (for `flowsSlice`):

```ts
import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

// The persisted subset (reads from the store's partialize fn, if any).
export const FlowsSliceSchema = z.object({
  // Enumerate exactly the fields the store passes through partialize.
  // Use z.unknown() for genuinely opaque blobs, but name them.
  currentFlowId: z.string().nullable().optional(),
  // ...
});

registerSchema("storage.flowsSlice", "permissive");
export type FlowsSlice = z.infer<typeof FlowsSliceSchema>;
```

To determine the persisted subset, read the store's `persist` call options (`partialize: (s) => ({...})`) and mirror exactly those keys.

- [ ] **Step 2.b.1.3: Migrate each store's `storage` adapter**

For each store, edit the `persist(...)` call:

```ts
// before
persist(..., {
  name: "flows-storage",
  storage: createJSONStorage(() => localStorage),
})

// after
import { validatedStorage } from "@/lib/validated-storage";
import { FlowsSliceSchema } from "@/schemas/app/storage/flowsSlice";
// ...
persist(..., {
  name: "flows-storage",
  storage: createJSONStorage(() => validatedStorage("storage.flowsSlice", FlowsSliceSchema)),
})
```

- [ ] **Step 2.b.1.4: Re-run store tests specifically**

```bash
npm test -- src/stores/__tests__ 2>&1 | tail -10
```

Watch for render-loop regressions noted in memory (`project_zustand_v5_migration.md` and `project_use_get_builds_side_effect.md`). If any store test times out or fails with stack-depth errors, suspect a hydration loop — the schema may be dropping a field the store reads on mount.

- [ ] **Step 2.b.1.5: Gates + pause + commit**

Same gate commands as 2.a.2.3. Commit:

```
feat(types): validate persisted Zustand slices on hydrate (permissive)

<N> stores migrated. Corrupt localStorage is ignored in strict mode
(future flip); permissive mode passes it through + reports.
```

### Task 2.b.2 — Strict flip

- [ ] **Step 2.b.2.1: Bake + flip per §Migration Pattern step 7**

---

## Phase 2.c — templates

**Scope:** hooks under `src/controllers/API/queries/templates/` + `src/types/template/` + `src/types/templates/`. Memory notes 6 follow-ups (FU-1..FU-6) — they surface here because most are shape-drift bugs.

**Budget:** ~1 week.

### Task 2.c.1 — Inventory + migrate

- [ ] **Step 2.c.1.1: Enumerate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
grep -rln "useQuery\|useMutation" src/controllers/API/queries/templates | tee /tmp/templates-hooks.txt
```

- [ ] **Step 2.c.1.2: Migrate per §Migration Pattern**

Schema ids: `api.templates.<op>`. Schemas from `@/schemas/api/templates`.

- [ ] **Step 2.c.1.3: Check for overlap with ShouldBe/category rework**

Memory `project_template_management_state.md` lists FU-1..FU-6. If any FU touches a shape this chunk migrates, coordinate with that work (or open a note that the boundary validation will surface the drift faster).

- [ ] **Step 2.c.1.4: Gate + pause + commit**

### Task 2.c.2 — Strict flip

- [ ] **Step 2.c.2.1: Bake + flip**

---

## Phase 2.d — messages + chat

**Scope:** `src/controllers/API/queries/messages/` + `src/types/messages/` + `src/types/chat/`.

**Budget:** ~1 week.

### Task 2.d.1 — Inventory + migrate

- [ ] **Step 2.d.1.1: Enumerate**

```bash
grep -rln "useQuery\|useMutation" src/controllers/API/queries/messages src/controllers/API/queries/chat 2>/dev/null | tee /tmp/messages-hooks.txt
```

- [ ] **Step 2.d.1.2: Migrate per §Migration Pattern**

Schema ids: `api.messages.<op>`, `api.monitor.<op>` (if chat falls under monitor in OpenAPI — verify), `api.chat.<op>`.

- [ ] **Step 2.d.1.3: Gate + pause + commit**

### Task 2.d.2 — Strict flip

---

## Phase 2.e — streaming (SSE / WebSocket)

**Scope:** every `EventSource` or `WebSocket` construction in `src/`; wrap the message handler with `validatedEventStream` (or the WS counterpart — follow the pattern in `validated-stream.ts` and add a `validatedSocket` helper if >1 usage).

**Budget:** ~3–5 days.

### Task 2.e.1 — Inventory stream usage

- [ ] **Step 2.e.1.1: Enumerate**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
grep -rn "new EventSource\|new WebSocket" src --include="*.ts" --include="*.tsx" | tee /tmp/stream-sites.txt
```

- [ ] **Step 2.e.1.2: Author stream schemas**

Create `src/frontend/src/schemas/app/stream/buildEvents.ts` (discriminated union of vertex-start, vertex-end, error, end-of-stream events — read `src/backend/base/langflow/api/build.py` to identify the event types):

```ts
import { z } from "zod";
import { registerSchema } from "@/lib/schema-registry";

const VertexStartSchema = z.object({ type: z.literal("vertex_build_start"), data: z.record(z.unknown()) });
const VertexEndSchema = z.object({ type: z.literal("vertex_build_end"), data: z.record(z.unknown()) });
const ErrorEventSchema = z.object({ type: z.literal("error"), data: z.object({ message: z.string() }) });
const EndSchema = z.object({ type: z.literal("end"), data: z.record(z.unknown()).optional() });

export const BuildEventSchema = z.discriminatedUnion("type", [
  VertexStartSchema, VertexEndSchema, ErrorEventSchema, EndSchema,
]);

registerSchema("stream.buildEvents", "permissive");
export type BuildEvent = z.infer<typeof BuildEventSchema>;
```

Do the same for `stream/chatMessages.ts`.

- [ ] **Step 2.e.1.3: Migrate call sites**

For each site in `/tmp/stream-sites.txt`, wrap the message handler with `validatedEventStream`. Preserve existing error semantics.

- [ ] **Step 2.e.1.4: Gate + pause + commit**

### Task 2.e.2 — Strict flip

---

## Phase 2.f — users + organizations + memberships + auth

**Scope:** `src/controllers/API/queries/auth/`, `src/controllers/API/queries/organizations/` (or wherever memberships live — grep), `src/controllers/API/queries/users/` (if separate), and the hand-written auth schemas from Phase 1.3.1.

**Budget:** ~1 week.

### Task 2.f.1 — Migrate

- [ ] **Step 2.f.1.1: Enumerate**

```bash
grep -rln "useQuery\|useMutation" src/controllers/API/queries/auth src/controllers/API/queries/users 2>/dev/null
grep -rln "organization\|membership" src/controllers/API/queries 2>/dev/null
```

- [ ] **Step 2.f.1.2: Migrate each hook**

`api.auth.*` schemas come from `@/schemas/app/internal/auth`. `api.users.*` and `api.organizations.*` come from the generated `@/schemas/api/*`.

Note: `use-get-auth-session.ts` was already edited in Phase 0 Task 0.7 to type `SessionResponse`. In this chunk, wrap its `queryFn` with `validatedQueryFn("api.auth.getSession", SessionResponseSchema, ...)`.

- [ ] **Step 2.f.1.3: Gate + pause + commit**

### Task 2.f.2 — Strict flip

---

## Phase 2.g — long tail (public)

**Scope:** MCP, files, tweaks, alerts, metadata — smaller public endpoints. Grep to find each hook folder.

**Budget:** ~1 week.

### Task 2.g.1 — Migrate each sub-domain

- [ ] **Step 2.g.1.1: Enumerate**

```bash
for d in mcp files tweaks alerts metadata; do
  grep -rln "useQuery\|useMutation" src/controllers/API/queries/$d 2>/dev/null | wc -l
done
```

- [ ] **Step 2.g.1.2: Migrate each per §Migration Pattern**

### Task 2.g.2 — Strict flip

---

## Phase 2.h — long tail (internal / OpenAPI-hidden)

**Scope:** call sites for the 34 hidden endpoints. Most hooks are in `src/controllers/API/queries/variables/`, `.../api-key/`, `.../store-components/`, `.../voice/`, `.../models/`; validate-code is often called inline without a hook.

**Budget:** ~1 week.

### Task 2.h.1 — Inventory

- [ ] **Step 2.h.1.1: Find call sites**

```bash
grep -rn "/variables\|/api_key\|/store/\|/voice\|/models/\|/model_options\|/validate/code" src/controllers src/stores 2>/dev/null | tee /tmp/internal-sites.txt
wc -l /tmp/internal-sites.txt
```

- [ ] **Step 2.h.1.2: Migrate per §Migration Pattern**

Schemas from `@/schemas/app/internal/*`.

- [ ] **Step 2.h.1.3: Gate + pause + commit**

### Task 2.h.2 — Strict flip

---

## Phase 3 — Flip `noImplicitAny: true`

**Prereqs:** every domain in Phases 2.a–2.h flipped to strict with ≥1 week of zero `ValidationError` events across their schema ids.

### Task 3.1 — Re-measure baseline

**Files:** none modified; measurement only.

- [ ] **Step 3.1.1: Snapshot `any` count**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
grep -rn ": any\b\| any\[\]\|<any>\|as any\b" src --include="*.ts" --include="*.tsx" \
  | grep -vE "__tests__|\.test\.|\.spec\." | wc -l > /tmp/dto-phase3-any-count.txt
cat /tmp/dto-phase3-any-count.txt
```

Compare to `/tmp/dto-baseline-any-count.txt` from pre-flight. Expected: ≤30–40% of baseline (the API-inferred-any was the majority source).

- [ ] **Step 3.1.2: Snapshot tsc error projection under strict**

```bash
# temporarily flip the flag to see the count
cp src/frontend/tsconfig.json src/frontend/tsconfig.json.bak
sed -i.tmp 's/"noImplicitAny": false/"noImplicitAny": true/' src/frontend/tsconfig.json
rm src/frontend/tsconfig.json.tmp 2>/dev/null || true
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -vE "__tests__|\.test\.|\.spec\." > /tmp/dto-phase3-projection.txt
wc -l /tmp/dto-phase3-projection.txt
cp src/frontend/tsconfig.json.bak src/frontend/tsconfig.json
rm src/frontend/tsconfig.json.bak
```

Expected: 100–300 errors. If >500, the `any` reduction was less than projected; re-audit before committing to a timeline.

- [ ] **Step 3.1.3: Group projected errors by code**

```bash
grep -oE "TS[0-9]+" /tmp/dto-phase3-projection.txt | sort | uniq -c | sort -rn > /tmp/dto-phase3-codes.txt
cat /tmp/dto-phase3-codes.txt
```

TS7006 ("parameter 'x' implicitly has an 'any' type") will dominate.

### Task 3.2 — Batch fixes (same pattern as prior cleanup)

**Files:** various; one commit per error-code batch, modeled on `2026-04-19-frontend-typescript-cleanup.md`.

- [ ] **Step 3.2.1: Flip the flag**

Edit `src/frontend/tsconfig.json` — change `"noImplicitAny": false` to `"noImplicitAny": true`. Don't commit yet; the batches fix the resulting errors.

- [ ] **Step 3.2.2: Batch 1 — TS7006 (implicit any parameters)**

Iteratively add explicit types to function/method parameters flagged by TS7006. Prefer:
1. The schema-inferred type if the value comes from an API response.
2. A sibling type already defined.
3. A named local type if the parameter shape is unique.

Avoid:
- `any` (defeats the purpose).
- `unknown` unless narrowing at the call site is actually the right model.

Escape-hatch budget: **10 total across all Phase 3 batches** (tracked at `/tmp/dto-phase3-escapes.txt`). Each use is a `// @ts-expect-error` or `as unknown as X` with a one-line justification comment.

Gate after each batch (same as Phase 2 chunks).

- [ ] **Step 3.2.3: Batch 2 — TS7031 (implicit any in destructuring)**

Same approach.

- [ ] **Step 3.2.4: Batch 3+ — whatever TS codes are next most-frequent**

Walk `/tmp/dto-phase3-codes.txt` top-to-bottom. Each code = one commit batch.

- [ ] **Step 3.2.5: Final gate**

All four baseline gates + zero production errors under `noImplicitAny: true`.

- [ ] **Step 3.2.6: Commit the tsconfig change last (separate commit)**

```bash
git add src/frontend/tsconfig.json
git commit -m "feat(tsconfig): flip noImplicitAny to true

All production code now passes under noImplicitAny: true after the
Phase-3 batch fixes. Tests may still have residuals; those are Phase 4."
```

---

## Phase 4 — Test tsc cleanup

**Prereqs:** Phase 3 done. Schema-derived types now flow into test fixtures.

### Task 4.1 — Snapshot residual test errors

- [ ] **Step 4.1.1: Count**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04/src/frontend
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | grep -E "__tests__|\.test\.|\.spec\." | wc -l > /tmp/dto-phase4-test-count.txt
cat /tmp/dto-phase4-test-count.txt
```

Expected: dramatically reduced from the 235 baseline — most fixture-shape errors resolve because domain types now derive from schemas. Typical: 30–80 residuals.

### Task 4.2 — Batch fixes

Same approach as Phase 3: one commit per error code. Escape budget: 5 total.

- [ ] **Step 4.2.1..N**: one commit per top error code until the test count = 0.

### Task 4.3 — Final gate + merge

- [ ] **Step 4.3.1: Full-stack gate**

```bash
npx tsc --noEmit 2>&1 | grep -E "error TS[0-9]+:" | wc -l                     # total errors: 0
npm test -- --ci 2>&1 | tail -5                                               # ≥ baseline
npm run build 2>&1 | tail -5                                                   # clean
make tests_frontend 2>&1 | tail -10                                            # Playwright pass
```

---

## Phase 5 — Final validation + cleanup

### Task 5.1 — Overlay reevaluation

- [ ] **Step 5.1.1: Is the overlay still pulling weight?**

After Phase 3 flip, `ValidationError` events should be exceedingly rare. Decide with user:
- Keep the overlay as-is (admin-visible in prod).
- Hide it behind a `?debug=1` query flag.
- Remove entirely, rely on Sentry.

Implement whichever choice; commit.

### Task 5.2 — Commit log + merge prep

- [ ] **Step 5.2.1: Review the full branch**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/dto-boundary-2026-04
git log --oneline platform-multi-tenant..HEAD | wc -l
git log --oneline platform-multi-tenant..HEAD | head -50
```

Expected: many commits organized by phase. Spot-check for the pause-and-ask rule (no auto-commits without approval). If any commit looks like it was made without approval, flag it now.

- [ ] **Step 5.2.2: Merge any still-open phases back to platform-multi-tenant**

If Path B was chosen (one big merge at the end), do it here. Otherwise skip.

```bash
cd /Users/brycedeneen/dev/langflow
git checkout platform-multi-tenant
git merge --no-ff dto/boundary-types-2026-04 -m "merge: frontend DTO/boundary-types — final

<phase summary>

Production `any` surface: <baseline> → <final>. noImplicitAny: true.
Test tsc: 235 → 0. No new production errors. Jest + Playwright
baselines preserved."
```

- [ ] **Step 5.2.3: Remove the worktree**

```bash
git worktree remove .worktrees/dto-boundary-2026-04
git branch -d dto/boundary-types-2026-04
```

(If `-d` refuses, the branch didn't merge cleanly. Investigate before using `-D`.)

---

## Self-review

**Spec coverage:** every section in the spec maps to a phase. Architecture, library+tooling, directory layout, wrapper design, storage, stream, error handling, overlay, and the 11-chunk phase table are all implemented by concrete tasks. Non-goals (class-based DTOs, zodios, URL params, postMessage, property-based tests) are never scoped into any task. Standing constraints (worktree, no commits, explicit paths, no upstream PR) appear in every commit step.

**Placeholder scan:** no "TBD" / "TODO" / "handle edge cases". Phases 2.c-2.h use a reference to §Migration Pattern with per-chunk inventories and commit/merge hooks; the concrete code lives in §Migration Pattern and is copied into Phase 2.a's first migrated hook as an example. The pattern is mechanical enough that repeating the full code per chunk would be noise, not safety.

**Type consistency:** `validatedQueryFn`, `validatedMutationFn`, `validatedStorage`, `validatedEventStream`, `ValidationError`, `reportParseFailure`, `configureReporter`, `registerSchema`, `getMode` — all names used consistently across tasks.

**Stop-the-line:** §Migration Pattern step 8 carries the >10-call-site rule; Phase 3 escape-hatch budget (10) and Phase 4 escape-hatch budget (5) are explicit.

**Known gap (acknowledged, not ducked):** Sentry is assumed pluggable into `configureReporter` but not wired. If the user wants Sentry as a first-class deliverable, insert a task between Phase 1.5 and Phase 2.a that wires the existing frontend Sentry setup (or adds one). Leaving it out keeps Phase 0 scoped; flagged here so the engineer knows to ask.
