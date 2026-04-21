# Data Mapper — Heavy Auto-Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the `suggestionsSlot` extension seam in `DataMapperModal` with a working LLM-driven auto-mapping experience: click "Suggest mappings" → spinner → blue rows with per-row ✓/✗ or bulk Apply-all.

**Architecture:** A shipped Langflow flow (`DataMapperAutoMap.json`) invoked via the existing `POST /api/v1/session/DataMapperAutoMap/run` endpoint. A new `MappingSuggestions` React component renders in the modal's `suggestionsSlot`. The `MappingComponent` input renderer owns suggestion state (pending list, show toggle, request state) and passes it down to both the slot content and the modal's destination table. No new backend code beyond the flow JSON itself.

**Tech Stack:** React + Zustand, Jest + Playwright, Langflow's existing `session/run` endpoint, Anthropic/OpenAI provider SDKs via the org-scoped `assistant.api_key` Variable.

**Spec:** `docs/superpowers/specs/2026-04-21-data-mapper-heavy-auto-mapping-design.md`.

---

## Conventions & constraints

- **Always ask before `git commit`.** The user requires explicit authorization for every commit. Steps labeled "Commit" are tentative: surface the diff and message, wait for approval.
- **Stage explicit paths.** `git add <path> [<path> ...]` — never `git add -A`, `git add .`, or `git commit -a`.
- **Frontend test runner is Jest** (not Vitest). React Query v5 uses `isPending`, not `isLoading`.
- **Running specific tests:**
  - Frontend unit: `cd src/frontend && npx jest <pathspec> --no-coverage`
  - Playwright: `cd src/frontend && npx playwright test <spec>`
  - Backend unit: `cd src/backend && uv run pytest <pathspec> -v`
- **The spec's five UX states** (`idle`, `fetching`, `pending`, `empty`, `error`) map to the `suggestionRequestState` union type introduced in Task 4.
- **Never-overwrite rule** (spec §Scope): a destination is **eligible** for a suggestion iff its `MappingEntry` either doesn't exist or is exactly `{transform: "direct", sources: [], config: {}}`. Anything else → the entry is customized and gets skipped.

---

### Task 1: Pure utility — `filterEligibleSuggestions`

Purpose: given a `MapperConfig` and a list of proposed `MappingEntry` objects, return only those proposals that target eligible destinations (per the never-overwrite rule).

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/util/filterEligibleSuggestions.ts`
- Create: `src/frontend/src/modals/dataMapperModal/util/__tests__/filterEligibleSuggestions.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/frontend/src/modals/dataMapperModal/util/__tests__/filterEligibleSuggestions.test.ts
import { filterEligibleSuggestions } from "../filterEligibleSuggestions";
import type { MapperConfig, MappingEntry } from "../../types";

const baseConfig: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [] } }],
  destination_schema: [
    { name: "full_name", type: "str", required: true, default: null },
    { name: "email",     type: "str", required: true, default: null },
    { name: "user_id",   type: "str", required: false, default: null },
  ],
  mappings: [],
};

const proposal = (destination: string, extras: Partial<MappingEntry> = {}): MappingEntry => ({
  destination,
  transform: "direct",
  sources: [{ input: "users", field: destination }],
  config: {},
  ...extras,
});

describe("filterEligibleSuggestions", () => {
  it("keeps proposals for destinations with no existing mapping entry", () => {
    const out = filterEligibleSuggestions(baseConfig, [proposal("full_name")]);
    expect(out).toHaveLength(1);
    expect(out[0].destination).toBe("full_name");
  });

  it("keeps proposals for destinations with the default empty entry", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const, sources: [], config: {} },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(1);
  });

  it("drops proposals for customized entries (non-direct transform)", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "template" as const, sources: [], config: { template: "{x}" } },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(0);
  });

  it("drops proposals for customized entries (non-empty sources)", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const,
        sources: [{ input: "users", field: "name" }], config: {} },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(0);
  });

  it("drops proposals for customized entries (non-empty config)", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const, sources: [], config: { foo: 1 } },
    ]};
    expect(filterEligibleSuggestions(config, [proposal("full_name")])).toHaveLength(0);
  });

  it("drops proposals referencing unknown destinations", () => {
    expect(filterEligibleSuggestions(baseConfig, [proposal("does_not_exist")])).toHaveLength(0);
  });

  it("drops proposals with transform: 'expression'", () => {
    expect(filterEligibleSuggestions(baseConfig, [proposal("full_name", { transform: "expression" })])).toHaveLength(0);
  });

  it("handles mixed proposals correctly", () => {
    const config = { ...baseConfig, mappings: [
      { destination: "email", transform: "template" as const, sources: [], config: { template: "{x}" } },
    ]};
    const out = filterEligibleSuggestions(config, [
      proposal("full_name"),   // eligible — no entry
      proposal("email"),       // skip — customized
      proposal("user_id"),     // eligible — no entry
      proposal("nonexistent"), // skip — unknown dest
    ]);
    expect(out.map((e) => e.destination).sort()).toEqual(["full_name", "user_id"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/util/__tests__/filterEligibleSuggestions --no-coverage`
Expected: FAIL with "Cannot find module '../filterEligibleSuggestions'".

- [ ] **Step 3: Implement the utility**

```ts
// src/frontend/src/modals/dataMapperModal/util/filterEligibleSuggestions.ts
import type { MapperConfig, MappingEntry } from "../types";

const isDefaultEntry = (entry: MappingEntry): boolean =>
  entry.transform === "direct" &&
  entry.sources.length === 0 &&
  Object.keys(entry.config).length === 0;

export function filterEligibleSuggestions(
  config: MapperConfig,
  proposals: MappingEntry[],
): MappingEntry[] {
  const destNames = new Set(config.destination_schema.map((d) => d.name));

  return proposals.filter((proposal) => {
    if (proposal.transform === "expression") return false;
    if (!destNames.has(proposal.destination)) return false;

    const existing = config.mappings.find((m) => m.destination === proposal.destination);
    if (!existing) return true;
    return isDefaultEntry(existing);
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/util/__tests__/filterEligibleSuggestions --no-coverage`
Expected: PASS — 8 tests.

- [ ] **Step 5: Commit (ask first)**

```bash
git add src/frontend/src/modals/dataMapperModal/util/filterEligibleSuggestions.ts \
        src/frontend/src/modals/dataMapperModal/util/__tests__/filterEligibleSuggestions.test.ts
git commit -m "feat(data-mapper): filterEligibleSuggestions util for never-overwrite rule"
```

---

### Task 2: Pure utility — `applyMappingSuggestion`

Purpose: merge a single `MappingEntry` into a `MapperConfig`. If the destination already has a `MappingEntry` (which by the eligibility rule will be the default empty one), replace it; otherwise append.

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/util/applyMappingSuggestion.ts`
- Create: `src/frontend/src/modals/dataMapperModal/util/__tests__/applyMappingSuggestion.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// src/frontend/src/modals/dataMapperModal/util/__tests__/applyMappingSuggestion.test.ts
import { applyMappingSuggestion } from "../applyMappingSuggestion";
import type { MapperConfig, MappingEntry } from "../../types";

const baseConfig: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [] } }],
  destination_schema: [
    { name: "full_name", type: "str", required: true, default: null },
    { name: "email",     type: "str", required: true, default: null },
  ],
  mappings: [],
};

const entry: MappingEntry = {
  destination: "full_name",
  transform: "template",
  sources: [
    { input: "users", field: "first_name" },
    { input: "users", field: "last_name" },
  ],
  config: { template: "{first_name} {last_name}" },
};

describe("applyMappingSuggestion", () => {
  it("appends when the destination has no existing entry", () => {
    const out = applyMappingSuggestion(baseConfig, entry);
    expect(out.mappings).toHaveLength(1);
    expect(out.mappings[0]).toEqual(entry);
  });

  it("replaces when the destination has a default empty entry", () => {
    const input = { ...baseConfig, mappings: [
      { destination: "full_name", transform: "direct" as const, sources: [], config: {} },
    ]};
    const out = applyMappingSuggestion(input, entry);
    expect(out.mappings).toHaveLength(1);
    expect(out.mappings[0]).toEqual(entry);
  });

  it("does not mutate the input config", () => {
    const input: MapperConfig = JSON.parse(JSON.stringify(baseConfig));
    applyMappingSuggestion(input, entry);
    expect(input.mappings).toHaveLength(0);
  });

  it("leaves other mappings alone", () => {
    const otherEntry: MappingEntry = {
      destination: "email", transform: "direct",
      sources: [{ input: "users", field: "email_address" }], config: {},
    };
    const input = { ...baseConfig, mappings: [otherEntry] };
    const out = applyMappingSuggestion(input, entry);
    expect(out.mappings).toHaveLength(2);
    expect(out.mappings).toContainEqual(otherEntry);
    expect(out.mappings).toContainEqual(entry);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/util/__tests__/applyMappingSuggestion --no-coverage`
Expected: FAIL with "Cannot find module '../applyMappingSuggestion'".

- [ ] **Step 3: Implement**

```ts
// src/frontend/src/modals/dataMapperModal/util/applyMappingSuggestion.ts
import type { MapperConfig, MappingEntry } from "../types";

export function applyMappingSuggestion(
  config: MapperConfig,
  entry: MappingEntry,
): MapperConfig {
  const existingIdx = config.mappings.findIndex((m) => m.destination === entry.destination);
  const nextMappings = [...config.mappings];
  if (existingIdx >= 0) {
    nextMappings[existingIdx] = entry;
  } else {
    nextMappings.push(entry);
  }
  return { ...config, mappings: nextMappings };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/util/__tests__/applyMappingSuggestion --no-coverage`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit (ask first)**

```bash
git add src/frontend/src/modals/dataMapperModal/util/applyMappingSuggestion.ts \
        src/frontend/src/modals/dataMapperModal/util/__tests__/applyMappingSuggestion.test.ts
git commit -m "feat(data-mapper): applyMappingSuggestion util for merge logic"
```

---

### Task 3: Query hook — `use-data-mapper-auto-map`

Purpose: wrap the `POST /api/v1/session/DataMapperAutoMap/run` call with the same pattern `use-template-assistant.ts` uses.

**Files:**
- Create: `src/frontend/src/controllers/API/queries/assistant/use-data-mapper-auto-map.ts`
- Create: `src/frontend/src/controllers/API/queries/assistant/__tests__/use-data-mapper-auto-map.test.tsx`
- Reference pattern: `src/frontend/src/controllers/API/queries/assistant/use-template-assistant.ts` and `__tests__/use-greet-conversation.test.tsx`.

- [ ] **Step 1: Write the failing test**

```tsx
// src/frontend/src/controllers/API/queries/assistant/__tests__/use-data-mapper-auto-map.test.tsx
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDataMapperAutoMapMutation } from "../use-data-mapper-auto-map";
import { api } from "../../../api";

jest.mock("../../../api");
const mockPost = api.post as jest.Mock;

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("useDataMapperAutoMapMutation", () => {
  beforeEach(() => mockPost.mockReset());

  it("posts to /session/DataMapperAutoMap/run with the JSON input_value", async () => {
    mockPost.mockResolvedValue({ data: { outputs: [] } });
    const { result } = renderHook(() => useDataMapperAutoMapMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({ inputPayload: { driver: { alias: "users", fields: [] }, destinations: [] } });
    });

    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, options] = mockPost.mock.calls[0];
    expect(url).toContain("DataMapperAutoMap");
    expect(body.input_value).toBe(JSON.stringify({ driver: { alias: "users", fields: [] }, destinations: [] }));
    expect(body.stream).toBe(true);
    expect(body.input_type).toBe("chat");
    expect(body.output_type).toBe("chat");
  });

  it("forwards an AbortSignal to the axios call", async () => {
    mockPost.mockResolvedValue({ data: { outputs: [] } });
    const controller = new AbortController();
    const { result } = renderHook(() => useDataMapperAutoMapMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        inputPayload: { driver: { alias: "users", fields: [] }, destinations: [] },
        signal: controller.signal,
      });
    });

    const [,, options] = mockPost.mock.calls[0];
    expect(options.signal).toBe(controller.signal);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/controllers/API/queries/assistant/__tests__/use-data-mapper-auto-map --no-coverage`
Expected: FAIL with "Cannot find module '../use-data-mapper-auto-map'".

- [ ] **Step 3: Implement**

```ts
// src/frontend/src/controllers/API/queries/assistant/use-data-mapper-auto-map.ts
import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface DataMapperAutoMapInput {
  driver: { alias: string; fields: unknown[]; sample?: unknown };
  destinations: unknown[];
  lookups?: unknown[];
}

export interface AutoMapMutationArgs {
  inputPayload: DataMapperAutoMapInput;
  signal?: AbortSignal;
}

export const useDataMapperAutoMapMutation = () =>
  useMutation({
    mutationFn: async ({ inputPayload, signal }: AutoMapMutationArgs) =>
      api.post(
        getURL("RUN_SESSION", { assistantFlowId: "DataMapperAutoMap" }),
        {
          input_value: JSON.stringify(inputPayload),
          input_type: "chat",
          output_type: "chat",
          stream: true,
        },
        { signal },
      ),
  });
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/controllers/API/queries/assistant/__tests__/use-data-mapper-auto-map --no-coverage`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit (ask first)**

```bash
git add src/frontend/src/controllers/API/queries/assistant/use-data-mapper-auto-map.ts \
        src/frontend/src/controllers/API/queries/assistant/__tests__/use-data-mapper-auto-map.test.tsx
git commit -m "feat(data-mapper): useDataMapperAutoMapMutation hook"
```

---

### Task 4: `useMappingSuggestions` hook (state machine + parse/validate pipeline)

Purpose: own the state machine for the Suggest flow. Idle → fetching → {pending|empty|error} → back to idle. Parses the streamed response, validates entries, filters via the never-overwrite rule, exposes `{state, entries, error, run, cancel, reset}`.

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/hooks/useMappingSuggestions.ts`
- Create: `src/frontend/src/modals/dataMapperModal/hooks/__tests__/useMappingSuggestions.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// src/frontend/src/modals/dataMapperModal/hooks/__tests__/useMappingSuggestions.test.tsx
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMappingSuggestions } from "../useMappingSuggestions";
import * as autoMapModule from "../../../../controllers/API/queries/assistant/use-data-mapper-auto-map";
import type { MapperConfig } from "../../types";

jest.mock("../../../../controllers/API/queries/assistant/use-data-mapper-auto-map");

const config: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [{ name: "id", type: "str", required: true }] } }],
  destination_schema: [
    { name: "id", type: "str", required: true, default: null },
    { name: "email", type: "str", required: true, default: null },
  ],
  mappings: [],
};

const mockResponse = (text: string) => ({ data: { outputs: [{ outputs: [{ outputs: { message: { message: text } } }] }] } });

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("useMappingSuggestions", () => {
  const mockMutateAsync = jest.fn();
  beforeEach(() => {
    mockMutateAsync.mockReset();
    (autoMapModule.useDataMapperAutoMapMutation as jest.Mock).mockReturnValue({
      mutateAsync: mockMutateAsync,
    });
  });

  it("starts in idle state", () => {
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });
    expect(result.current.state).toBe("idle");
    expect(result.current.entries).toEqual([]);
  });

  it("transitions idle → fetching → pending on happy path", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([
      { destination: "id",    transform: "direct", sources: [{ input: "users", field: "id" }], config: {} },
      { destination: "email", transform: "direct", sources: [{ input: "users", field: "email_address" }], config: {} },
    ])));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("pending");
    expect(result.current.entries).toHaveLength(2);
  });

  it("strips markdown fences before parsing", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse("```json\n[{\"destination\":\"id\",\"transform\":\"direct\",\"sources\":[{\"input\":\"users\",\"field\":\"id\"}],\"config\":{}}]\n```"));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("pending");
    expect(result.current.entries).toHaveLength(1);
  });

  it("transitions to empty when filtered list is empty", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([])));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("empty");
  });

  it("transitions to error on unparseable output", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse("not json at all"));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("error");
    expect(result.current.error).toMatch(/parse/i);
  });

  it("transitions to error on HTTP failure", async () => {
    mockMutateAsync.mockRejectedValue(Object.assign(new Error("Request failed"), { response: { status: 404 } }));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("error");
    expect(result.current.error).toMatch(/not available|update Langflow/i);
  });

  it("cancel() reverts state to idle and aborts", async () => {
    let resolve!: (v: unknown) => void;
    mockMutateAsync.mockImplementation(() => new Promise((r) => { resolve = r; }));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    act(() => { result.current.run(); });
    await waitFor(() => expect(result.current.state).toBe("fetching"));

    act(() => { result.current.cancel(); });
    resolve(mockResponse(JSON.stringify([])));

    await waitFor(() => expect(result.current.state).toBe("idle"));
  });

  it("filters entries via never-overwrite rule (customized dest gets skipped)", async () => {
    const configWithCustom: MapperConfig = {
      ...config,
      mappings: [{ destination: "id", transform: "template", sources: [], config: { template: "x" } }],
    };
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([
      { destination: "id",    transform: "direct", sources: [{ input: "users", field: "id" }], config: {} },
      { destination: "email", transform: "direct", sources: [{ input: "users", field: "email_address" }], config: {} },
    ])));
    const { result } = renderHook(() => useMappingSuggestions({ config: configWithCustom }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.entries.map((e) => e.destination)).toEqual(["email"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/hooks/__tests__/useMappingSuggestions --no-coverage`
Expected: FAIL with "Cannot find module '../useMappingSuggestions'".

- [ ] **Step 3: Implement**

```ts
// src/frontend/src/modals/dataMapperModal/hooks/useMappingSuggestions.ts
import { useCallback, useRef, useState } from "react";
import { useDataMapperAutoMapMutation, DataMapperAutoMapInput }
  from "../../../controllers/API/queries/assistant/use-data-mapper-auto-map";
import type { MapperConfig, MappingEntry, TransformType } from "../types";
import { filterEligibleSuggestions } from "../util/filterEligibleSuggestions";

export type MappingSuggestionsState = "idle" | "fetching" | "pending" | "empty" | "error";

export interface UseMappingSuggestionsArgs {
  config: MapperConfig;
}

const ALLOWED_TRANSFORMS: readonly TransformType[] = ["direct", "static", "variable", "template", "array"];

const FENCE_RE = /^\s*```(?:json)?\s*|\s*```\s*$/g;

function extractJsonArray(raw: string): unknown {
  const stripped = raw.replace(FENCE_RE, "").trim();
  const start = stripped.indexOf("[");
  const end = stripped.lastIndexOf("]");
  if (start < 0 || end <= start) throw new Error("no JSON array found");
  return JSON.parse(stripped.slice(start, end + 1));
}

function coerceEntries(parsed: unknown, knownInputs: Set<string>): MappingEntry[] {
  if (!Array.isArray(parsed)) throw new Error("expected array");
  const out: MappingEntry[] = [];
  for (const raw of parsed) {
    if (!raw || typeof raw !== "object") continue;
    const e = raw as Record<string, unknown>;
    if (typeof e.destination !== "string") continue;
    if (typeof e.transform !== "string") continue;
    if (!ALLOWED_TRANSFORMS.includes(e.transform as TransformType)) continue;
    const sources = Array.isArray(e.sources) ? e.sources.filter((s: unknown) => {
      const r = s as Record<string, unknown>;
      return r && typeof r.input === "string" && typeof r.field === "string" && knownInputs.has(r.input as string);
    }) : [];
    const config = (e.config && typeof e.config === "object") ? e.config as Record<string, unknown> : {};
    out.push({ destination: e.destination, transform: e.transform as TransformType, sources: sources as MappingEntry["sources"], config });
  }
  return out;
}

function extractMessageText(response: unknown): string {
  const r = response as { data?: { outputs?: Array<{ outputs?: Array<{ outputs?: { message?: { message?: string } } }> }> } };
  const msg = r?.data?.outputs?.[0]?.outputs?.[0]?.outputs?.message?.message;
  if (typeof msg !== "string") throw new Error("no message in response");
  return msg;
}

export function useMappingSuggestions({ config }: UseMappingSuggestionsArgs) {
  const [state, setState] = useState<MappingSuggestionsState>("idle");
  const [entries, setEntries] = useState<MappingEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mutation = useDataMapperAutoMapMutation();

  const reset = useCallback(() => {
    setState("idle"); setEntries([]); setError(null);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    reset();
  }, [reset]);

  const run = useCallback(async () => {
    setState("fetching"); setError(null); setEntries([]);

    const controller = new AbortController();
    abortRef.current = controller;

    const inputPayload: DataMapperAutoMapInput = {
      driver: {
        alias: config.inputs[config.driver_index]?.alias ?? "driver",
        fields: config.inputs[config.driver_index]?.schema.fields ?? [],
        sample: config.inputs[config.driver_index]?.sample ?? undefined,
      },
      destinations: config.destination_schema,
      lookups: config.inputs
        .filter((_, idx) => idx !== config.driver_index)
        .map((inp) => ({
          alias: inp.alias, fields: inp.schema.fields, sample: inp.sample ?? undefined, join_fields: inp.join?.on ?? [],
        })),
    };

    try {
      const response = await mutation.mutateAsync({ inputPayload, signal: controller.signal });
      if (controller.signal.aborted) return;

      const text = extractMessageText(response);
      const parsed = extractJsonArray(text);
      const knownInputs = new Set(config.inputs.map((i) => i.alias));
      const coerced = coerceEntries(parsed, knownInputs);
      const filtered = filterEligibleSuggestions(config, coerced);

      if (controller.signal.aborted) return;
      setEntries(filtered);
      setState(filtered.length > 0 ? "pending" : "empty");
    } catch (err) {
      if (controller.signal.aborted) return;
      const anyErr = err as { response?: { status?: number }; message?: string };
      if (anyErr?.response?.status === 404) {
        setError("Auto-mapping isn't available in this environment. Ask your admin to update Langflow.");
      } else if (anyErr?.response?.status === 401 || anyErr?.response?.status === 403) {
        setError("Not authorized. Sign in and try again.");
      } else if (anyErr?.message?.match(/no JSON array|expected array|no message/)) {
        setError("Could not parse assistant output. Retry?");
      } else {
        setError(anyErr?.message || "Auto-mapping failed. Retry?");
      }
      setState("error");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [config, mutation]);

  return { state, entries, error, run, cancel, reset, setEntries, setState };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/hooks/__tests__/useMappingSuggestions --no-coverage`
Expected: PASS — 8 tests.

- [ ] **Step 5: Commit (ask first)**

```bash
git add src/frontend/src/modals/dataMapperModal/hooks/useMappingSuggestions.ts \
        src/frontend/src/modals/dataMapperModal/hooks/__tests__/useMappingSuggestions.test.tsx
git commit -m "feat(data-mapper): useMappingSuggestions hook with state machine"
```

---

### Task 5: `MappingSuggestions` component (slot content)

Purpose: the stateless component that renders inside the modal's `suggestionsSlot`. Renders different chrome per UX state. Takes state + handlers as props; owns zero internal state.

**Files:**
- Create: `src/frontend/src/modals/dataMapperModal/components/MappingSuggestions.tsx`
- Create: `src/frontend/src/modals/dataMapperModal/components/__tests__/MappingSuggestions.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// src/frontend/src/modals/dataMapperModal/components/__tests__/MappingSuggestions.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { MappingSuggestions } from "../MappingSuggestions";

const defaults = {
  state: "idle" as const,
  error: null,
  pendingCount: 0,
  showPending: true,
  allDestinationsCustomized: false,
  onSuggest: jest.fn(),
  onCancel: jest.fn(),
  onApplyAll: jest.fn(),
  onTogglePending: jest.fn(),
  onRetry: jest.fn(),
};

describe("MappingSuggestions", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders Suggest button in idle state", () => {
    render(<MappingSuggestions {...defaults} />);
    expect(screen.getByRole("button", { name: /suggest mappings/i })).toBeInTheDocument();
  });

  it("disables Suggest button when all destinations customized", () => {
    render(<MappingSuggestions {...defaults} allDestinationsCustomized />);
    expect(screen.getByRole("button", { name: /suggest mappings/i })).toBeDisabled();
  });

  it("calls onSuggest when Suggest clicked", () => {
    render(<MappingSuggestions {...defaults} />);
    fireEvent.click(screen.getByRole("button", { name: /suggest mappings/i }));
    expect(defaults.onSuggest).toHaveBeenCalled();
  });

  it("renders spinner + Cancel in fetching state", () => {
    render(<MappingSuggestions {...defaults} state="fetching" />);
    expect(screen.getByText(/analyzing schemas/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("renders tab toggle + Apply-all in pending state", () => {
    render(<MappingSuggestions {...defaults} state="pending" pendingCount={3} />);
    expect(screen.getByRole("button", { name: /current/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /suggested \(3\)/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /apply all/i })).toBeInTheDocument();
  });

  it("calls onTogglePending when Current clicked", () => {
    render(<MappingSuggestions {...defaults} state="pending" pendingCount={3} showPending={true} />);
    fireEvent.click(screen.getByRole("button", { name: /current/i }));
    expect(defaults.onTogglePending).toHaveBeenCalledWith(false);
  });

  it("renders error chip + Retry in error state", () => {
    render(<MappingSuggestions {...defaults} state="error" error="Connection lost. Retry?" />);
    expect(screen.getByText(/connection lost/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders empty chip in empty state", () => {
    render(<MappingSuggestions {...defaults} state="empty" />);
    expect(screen.getByText(/no new suggestions/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/components/__tests__/MappingSuggestions --no-coverage`
Expected: FAIL with "Cannot find module '../MappingSuggestions'".

- [ ] **Step 3: Implement**

```tsx
// src/frontend/src/modals/dataMapperModal/components/MappingSuggestions.tsx
import type { MappingSuggestionsState } from "../hooks/useMappingSuggestions";

export interface MappingSuggestionsProps {
  state: MappingSuggestionsState;
  error: string | null;
  pendingCount: number;
  showPending: boolean;
  allDestinationsCustomized: boolean;
  onSuggest: () => void;
  onCancel: () => void;
  onApplyAll: () => void;
  onTogglePending: (show: boolean) => void;
  onRetry: () => void;
}

export function MappingSuggestions({
  state, error, pendingCount, showPending, allDestinationsCustomized,
  onSuggest, onCancel, onApplyAll, onTogglePending, onRetry,
}: MappingSuggestionsProps) {

  if (state === "fetching") {
    return (
      <div className="mapping-suggestions mapping-suggestions--fetching" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="spinner" aria-hidden />
        <span>Analyzing schemas…</span>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    );
  }

  if (state === "pending") {
    return (
      <div className="mapping-suggestions mapping-suggestions--pending" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <button type="button" aria-pressed={!showPending} onClick={() => onTogglePending(false)}>Current</button>
          <button type="button" aria-pressed={showPending}  onClick={() => onTogglePending(true)} style={{ marginLeft: 4 }}>
            Suggested ({pendingCount})
          </button>
        </div>
        <button type="button" onClick={onApplyAll}>Apply all suggestions</button>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="mapping-suggestions mapping-suggestions--error" role="alert" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span>{error ?? "Something went wrong."}</span>
        <button type="button" onClick={onRetry}>Retry</button>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className="mapping-suggestions mapping-suggestions--empty">
        <span>No new suggestions — the assistant couldn't find matches for the remaining destinations.</span>
      </div>
    );
  }

  // idle
  return (
    <div className="mapping-suggestions mapping-suggestions--idle">
      <button
        type="button"
        onClick={onSuggest}
        disabled={allDestinationsCustomized}
        title={allDestinationsCustomized ? "Clear a row to get suggestions" : undefined}
      >
        Suggest mappings
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/components/__tests__/MappingSuggestions --no-coverage`
Expected: PASS — 8 tests.

- [ ] **Step 5: Commit (ask first)**

```bash
git add src/frontend/src/modals/dataMapperModal/components/MappingSuggestions.tsx \
        src/frontend/src/modals/dataMapperModal/components/__tests__/MappingSuggestions.test.tsx
git commit -m "feat(data-mapper): MappingSuggestions slot component"
```

---

### Task 6: DataMapperModal contract extension + DestinationTable blue-row rendering

Combined task — these land together to avoid a broken intermediate state. The modal just passes new props through to the table.

**Files:**
- Modify: `src/frontend/src/modals/dataMapperModal/index.tsx` (props interface at lines 15–24; the `<DestinationTable>` render site)
- Modify: `src/frontend/src/modals/dataMapperModal/components/DestinationTable.tsx` (props interface at lines 17–21; row loop at line 181)
- Create: `src/frontend/src/modals/dataMapperModal/components/__tests__/DestinationTable.pending.test.tsx`

- [ ] **Step 1: Write the failing test** (new test file; do not modify any existing DestinationTable tests)

```tsx
// src/frontend/src/modals/dataMapperModal/components/__tests__/DestinationTable.pending.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { DestinationTable } from "../DestinationTable";
import type { MapperConfig, MappingEntry } from "../../types";

const config: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [] } }],
  destination_schema: [
    { name: "full_name", type: "str", required: true,  default: null },
    { name: "email",     type: "str", required: false, default: null },
  ],
  mappings: [],
};

const pendingEntry: MappingEntry = {
  destination: "full_name",
  transform: "template",
  sources: [{ input: "users", field: "first_name" }],
  config: { template: "{first_name} {last_name}" },
};

describe("DestinationTable — pending row rendering", () => {
  it("renders proposed values in blue state when pendingSuggestions has entry for destination", () => {
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
        onAcceptSuggestion={jest.fn()}
        onRejectSuggestion={jest.fn()}
      />,
    );
    expect(screen.getByText(/{first_name} {last_name}/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accept suggestion for full_name/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject suggestion for full_name/i })).toBeInTheDocument();
  });

  it("renders unset state when showPendingSuggestions is false", () => {
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions={false}
      />,
    );
    expect(screen.queryByText(/{first_name} {last_name}/)).not.toBeInTheDocument();
  });

  it("calls onAcceptSuggestion with destination when ✓ clicked", () => {
    const onAccept = jest.fn();
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
        onAcceptSuggestion={onAccept}
        onRejectSuggestion={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /accept suggestion for full_name/i }));
    expect(onAccept).toHaveBeenCalledWith("full_name");
  });

  it("calls onRejectSuggestion with destination when ✗ clicked", () => {
    const onReject = jest.fn();
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
        onAcceptSuggestion={jest.fn()}
        onRejectSuggestion={onReject}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /reject suggestion for full_name/i }));
    expect(onReject).toHaveBeenCalledWith("full_name");
  });

  it("does not show pending UI for destinations with no proposed entry", () => {
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
      />,
    );
    // "email" row has no proposal → no ✓/✗
    expect(screen.queryByRole("button", { name: /accept suggestion for email/i })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/components/__tests__/DestinationTable.pending --no-coverage`
Expected: FAIL — props `pendingSuggestions`, `showPendingSuggestions`, etc. not on DestinationTable yet.

- [ ] **Step 3: Extend DestinationTable props and row rendering**

In `src/frontend/src/modals/dataMapperModal/components/DestinationTable.tsx`:

Replace the props interface (lines 17–21) with:

```ts
export interface DestinationTableProps {
  config: MapperConfig;
  errors?: MappingConfigError[];
  onConfigChange(next: MapperConfig): void;

  pendingSuggestions?: MappingEntry[];
  showPendingSuggestions?: boolean;
  onAcceptSuggestion?: (destination: string) => void;
  onRejectSuggestion?: (destination: string) => void;
}
```

Inside the row `.map` at line 181, add before the `return (`:

```ts
const pendingEntry =
  props.pendingSuggestions && props.showPendingSuggestions
    ? props.pendingSuggestions.find((p) => p.destination === dest.name)
    : undefined;
const effectiveMapping = pendingEntry ?? mapping;
```

**Render rule for pending rows (important):** when `pendingEntry` is truthy, the Transform cell and Source/Config cell must render as **read-only text** showing the proposed values — not as editable `<select>` / `<TransformCell>` inputs. This avoids the "user edits a pending row" ambiguity entirely. After the user clicks ✓, `acceptSuggestion` runs and the row becomes a normal committed mapping, which is fully editable again. Concretely:

- Transform cell when `pendingEntry`: render `<span style={{ color: "#a5a5a5" }}>{pendingEntry.transform}</span>`.
- Source/Config cell when `pendingEntry`: render a short `<span>` summary (e.g. `sources[0].input + "." + sources[0].field` for direct; `config.template` string for template; `config.value` for static; etc.) in `color: "#a5a5a5"`. Reuse the summarization logic from the existing node-level "Edit mapping · N fields" button if one exists, otherwise inline a small summarizer.
- For non-pending rows (either customized or empty): render exactly as today (`<select>` for transform, `<TransformCell>` for source/config).

At the end of the row (before `</tr>`), inject a pending-actions cell:

```tsx
{pendingEntry && (
  <td style={{ padding: "0.4rem 0.5rem", whiteSpace: "nowrap" }}>
    <button
      type="button"
      aria-label={`Accept suggestion for ${dest.name}`}
      onClick={() => props.onAcceptSuggestion?.(dest.name)}
    >✓</button>
    <button
      type="button"
      aria-label={`Reject suggestion for ${dest.name}`}
      onClick={() => props.onRejectSuggestion?.(dest.name)}
      style={{ marginLeft: 4 }}
    >✗</button>
  </td>
)}
```

Style the row: if `pendingEntry` is truthy, set `background: "#3b82f615"`, `borderLeft: "3px solid #3b82f6"`. Render source/transform/config cells in greyed style (`color: "#a5a5a5"`) when rendering a pending entry, so users can see it's a proposal.

Also: destructure `props` into a single object inside the component body so the closure captures the correct `pendingSuggestions` etc.

- [ ] **Step 4: Extend DataMapperModal props**

In `src/frontend/src/modals/dataMapperModal/index.tsx`, replace the props interface (lines 15–24) with:

```ts
export interface DataMapperModalProps {
  open: boolean;
  onClose(): void;
  value: string;
  onChange(newValue: string): void;
  nodeId: string;
  flowId: string;
  connectedUpstreams: { alias: string; vertexId: string }[];
  suggestionsSlot?: React.ReactNode;

  pendingSuggestions?: MappingEntry[];
  showPendingSuggestions?: boolean;
  onAcceptSuggestion?: (destination: string) => void;
  onRejectSuggestion?: (destination: string) => void;
}
```

Destructure the new props in the component signature. At the `<DestinationTable ...>` render site, forward the new props:

```tsx
<DestinationTable
  config={config}
  errors={validationErrors}
  onConfigChange={setConfig}
  pendingSuggestions={props.pendingSuggestions}
  showPendingSuggestions={props.showPendingSuggestions}
  onAcceptSuggestion={props.onAcceptSuggestion}
  onRejectSuggestion={props.onRejectSuggestion}
/>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/components/__tests__/DestinationTable.pending --no-coverage`
Expected: PASS — 5 tests.

Also run the existing DestinationTable + DataMapperModal test files to confirm no regressions:

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/ --no-coverage`
Expected: PASS — all pre-existing tests unaffected.

- [ ] **Step 6: Commit (ask first)**

```bash
git add src/frontend/src/modals/dataMapperModal/index.tsx \
        src/frontend/src/modals/dataMapperModal/components/DestinationTable.tsx \
        src/frontend/src/modals/dataMapperModal/components/__tests__/DestinationTable.pending.test.tsx
git commit -m "feat(data-mapper): modal + table contract extension for pending suggestions"
```

---

### Task 7: `MappingComponent` orchestration

Purpose: wire up the suggestion state in the input renderer. Mount `<MappingSuggestions>` in the modal's `suggestionsSlot`. Pass pending state + handlers to the modal.

**Files:**
- Modify: `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx`
- Create: `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/__tests__/suggestions.test.tsx`

- [ ] **Step 1: Write the failing integration test**

```tsx
// src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/__tests__/suggestions.test.tsx
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MappingComponent from "..";

jest.mock("../../../../../../controllers/API/queries/assistant/use-data-mapper-auto-map", () => ({
  useDataMapperAutoMapMutation: () => ({ mutateAsync: jest.fn().mockResolvedValue({
    data: { outputs: [{ outputs: [{ outputs: { message: { message: JSON.stringify([
      { destination: "full_name", transform: "direct", sources: [{ input: "users", field: "name" }], config: {} },
    ]) } } }] }] },
  }) }),
}));

// Mock the flow edges hook that provides connectedUpstreams (exact hook path depends on implementation — adjust if different)
jest.mock("../../../../../../stores/flowStore", () => ({
  __esModule: true,
  default: () => ({ edges: [], nodes: [{ id: "n1", data: { node: { id: "n1" } } }] }),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("MappingComponent suggestions integration", () => {
  const baseConfig = JSON.stringify({
    driver_index: 0,
    inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [{ name: "name", type: "str", required: true }] } }],
    destination_schema: [{ name: "full_name", type: "str", required: true, default: null }],
    mappings: [],
  });

  it("renders Suggest button via suggestionsSlot when modal is open", async () => {
    render(
      <MappingComponent
        value={baseConfig}
        handleOnNewValue={jest.fn()}
        nodeId="n1"
        disabled={false}
      />,
      { wrapper },
    );
    fireEvent.click(screen.getByRole("button")); // the edit-mapping trigger
    await waitFor(() => expect(screen.getByRole("button", { name: /suggest mappings/i })).toBeInTheDocument());
  });

  it("clicking Suggest → Apply-all merges entries into saved config", async () => {
    const handleOnNewValue = jest.fn();
    render(
      <MappingComponent
        value={baseConfig}
        handleOnNewValue={handleOnNewValue}
        nodeId="n1"
        disabled={false}
      />,
      { wrapper },
    );
    fireEvent.click(screen.getByRole("button")); // open modal
    await waitFor(() => screen.getByRole("button", { name: /suggest mappings/i }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /suggest mappings/i }));
    });

    await waitFor(() => screen.getByRole("button", { name: /apply all/i }));
    fireEvent.click(screen.getByRole("button", { name: /apply all/i }));

    // Save happens on a subsequent user click, not auto — we don't assert handleOnNewValue here.
    // Instead, assert the blue row is gone (apply-all clears pending).
    await waitFor(() => expect(screen.queryByRole("button", { name: /apply all/i })).not.toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/frontend && npx jest src/components/core/parameterRenderComponent/components/mappingComponent/__tests__/suggestions --no-coverage`
Expected: FAIL — Suggest button doesn't exist yet (slot is empty).

- [ ] **Step 3: Wire up the orchestration in MappingComponent**

In `src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx`, at the top of the component body (after `const [open, setOpen] = useState(false);`):

```tsx
import { useMappingSuggestions } from "@/modals/dataMapperModal/hooks/useMappingSuggestions";
import { applyMappingSuggestion } from "@/modals/dataMapperModal/util/applyMappingSuggestion";
import { MappingSuggestions } from "@/modals/dataMapperModal/components/MappingSuggestions";
import type { MapperConfig } from "@/modals/dataMapperModal/types";
import { EMPTY_MAPPER_CONFIG } from "@/modals/dataMapperModal/types";

// ...inside the component:
const parsedConfig: MapperConfig = useMemo(() => {
  try { return value ? JSON.parse(value) : EMPTY_MAPPER_CONFIG; }
  catch { return EMPTY_MAPPER_CONFIG; }
}, [value]);

const suggestions = useMappingSuggestions({ config: parsedConfig });
const [showPending, setShowPending] = useState(true);

const allCustomized = useMemo(
  () => parsedConfig.destination_schema.every((d) => {
    const m = parsedConfig.mappings.find((x) => x.destination === d.name);
    if (!m) return false;
    return !(m.transform === "direct" && m.sources.length === 0 && Object.keys(m.config).length === 0);
  }),
  [parsedConfig],
);

const acceptSuggestion = (destination: string) => {
  const entry = suggestions.entries.find((e) => e.destination === destination);
  if (!entry) return;
  const next = applyMappingSuggestion(parsedConfig, entry);
  handleChange(JSON.stringify(next));
  suggestions.setEntries(suggestions.entries.filter((e) => e.destination !== destination));
  if (suggestions.entries.length === 1) suggestions.reset();
};

const rejectSuggestion = (destination: string) => {
  const next = suggestions.entries.filter((e) => e.destination !== destination);
  suggestions.setEntries(next);
  if (next.length === 0) suggestions.reset();
};

const applyAllSuggestions = () => {
  let next = parsedConfig;
  for (const entry of suggestions.entries) next = applyMappingSuggestion(next, entry);
  handleChange(JSON.stringify(next));
  suggestions.reset();
};
```

Pass these to the modal (replace the existing `<DataMapperModal ...>` block with the one below):

```tsx
{open && (
  <DataMapperModal
    open={open}
    onClose={() => setOpen(false)}
    value={value ?? ""}
    onChange={handleChange}
    nodeId={nodeId ?? ""}
    flowId={flowId}
    connectedUpstreams={connectedUpstreams}
    suggestionsSlot={
      <MappingSuggestions
        state={suggestions.state}
        error={suggestions.error}
        pendingCount={suggestions.entries.length}
        showPending={showPending}
        allDestinationsCustomized={allCustomized}
        onSuggest={suggestions.run}
        onCancel={suggestions.cancel}
        onApplyAll={applyAllSuggestions}
        onTogglePending={setShowPending}
        onRetry={suggestions.run}
      />
    }
    pendingSuggestions={suggestions.entries}
    showPendingSuggestions={showPending}
    onAcceptSuggestion={acceptSuggestion}
    onRejectSuggestion={rejectSuggestion}
  />
)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/frontend && npx jest src/components/core/parameterRenderComponent/components/mappingComponent/ --no-coverage`
Expected: PASS — 2 new tests; no regressions on pre-existing tests.

Also run the modal tests one more time to make sure nothing drifted:

Run: `cd src/frontend && npx jest src/modals/dataMapperModal/ --no-coverage`
Expected: all PASS.

- [ ] **Step 5: Commit (ask first)**

```bash
git add src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx \
        src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/__tests__/suggestions.test.tsx
git commit -m "feat(data-mapper): MappingComponent wires suggestions into suggestionsSlot"
```

---

### Task 8: Author the shipped flow — `DataMapperAutoMap.json`

**This is a manual, UI-driven task — not a code edit.** The shipped flow is a 295KB exported blob from the Langflow builder, matching the existing `TemplateAssistant.json` pattern. The flow author boots Langflow, builds the graph visually, exports it, and drops the JSON in `agentic/flows/`.

**Files:**
- Create: `src/backend/base/langflow/agentic/flows/DataMapperAutoMap.json` (via UI export, not hand-written)

**Prerequisites:** `assistant.api_key` + `assistant.provider` + `assistant.model` Variables must already exist in the org (same setup as `TemplateAssistant`).

**The flow graph to build:**

```
Chat Input (name: "chat_input")
   │  receives input_value as a JSON string
   ▼
Parse JSON (Python code block or JSON parser component)
   │  deserializes input_value → {driver, destinations, lookups}
   │  on failure, emits {"error": "invalid_input"} and routes to Chat Output
   ▼
Prompt Template (with the system prompt — see below)
   │  interpolates {driver.fields}, {destinations}, {lookups}, {samples}
   ▼
LLM node (Anthropic or OpenAI Model component, configured via assistant.provider/model/api_key Variables)
   │  outputs the raw completion
   ▼
Output Cleaner (Python code block)
   │  1. regex-strip markdown fences (/^```(?:json)?\s*|\s*```$/g)
   │  2. find first balanced [...] region
   │  3. json.loads → validate each entry has destination/transform/sources/config
   │  on failure, emit {"error": "unparseable_output"}
   ▼
Chat Output
```

**System prompt content (lives in the Prompt Template node):**

```
You are an expert data-mapping assistant. For each destination field in the input below, propose a mapping from the driver input (and lookup inputs, if present) that best fills it.

ALLOWED TRANSFORMS (use one of these as the "transform" value):
  - direct: pull a single source field as-is.
  - static: emit a literal constant (put the value in config.value).
  - variable: pull a runtime variable by name (put the name in config.name).
  - template: render a Jinja template using 1+ source fields (put the template string in config.template).
  - array: aggregate multiple sources into a list.

DO NOT use "expression" as a transform type under any circumstances.

INPUT:
{{ input_json }}

OUTPUT FORMAT (return exactly this — a JSON array, nothing else, no markdown fences, no prose):
[
  { "destination": "<name>", "transform": "<allowed>", "sources": [{"input": "<alias>", "field": "<name>"}], "config": {...} }
]

RULES:
  1. Only propose mappings for destinations where a reasonable source exists. If a destination is ambiguous or unclear, SKIP IT — do not include it in the output. Never guess.
  2. Never output an "expression" transform. If you would otherwise use expression, skip the destination instead.
  3. For template transforms, include every referenced source field in the sources array.
  4. For static transforms, use config.value.
  5. For variable transforms, use config.name.
  6. Only reference input aliases and field names that appear in INPUT.

EXAMPLES:

Destination "full_name" where driver has {first_name, last_name}:
  { "destination": "full_name", "transform": "template",
    "sources": [{"input":"users","field":"first_name"},{"input":"users","field":"last_name"}],
    "config": {"template": "{first_name} {last_name}"} }

Destination "source_system" where no input field is available:
  { "destination": "source_system", "transform": "static",
    "sources": [], "config": {"value": "langflow"} }
```

- [ ] **Step 1: Boot the dev server**

Run (from repo root): `LFX_DEV=1 make run_cli`
Expected: server starts on `http://localhost:3000` (frontend) + backend on its usual port. Confirm by opening the UI.

- [ ] **Step 2: Open the Langflow builder and create a new flow**

Name it exactly `DataMapperAutoMap` (this becomes the slug the frontend uses).

- [ ] **Step 3: Build the flow graph as described above**

Nodes to add (in order):
- `Chat Input` component
- `Python Code` or equivalent JSON-parse component (check the component library for the canonical "Parse JSON" or use a Python Code block that does `json.loads(input_value)`)
- `Prompt Template` component, configured with the system prompt above
- `Anthropic` or `OpenAI` model component, configured to read the `assistant.provider` / `assistant.model` / `assistant.api_key` org Variables
- A second `Python Code` block for the output cleaner (content below)
- `Chat Output` component

Wire them in sequence: Chat Input → Parse → Prompt Template → LLM → Cleaner → Chat Output.

Output cleaner code (Python Code block body):

```python
import re, json

def clean_llm_output(raw: str) -> str:
    stripped = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', raw.strip())
    start = stripped.find('[')
    end = stripped.rfind(']')
    if start < 0 or end <= start:
        return json.dumps({"error": "unparseable_output"})
    candidate = stripped[start:end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return json.dumps({"error": "unparseable_output"})
    if not isinstance(parsed, list):
        return json.dumps({"error": "unparseable_output"})
    valid = []
    allowed = {"direct", "static", "variable", "template", "array"}
    for entry in parsed:
        if not isinstance(entry, dict): continue
        if not isinstance(entry.get("destination"), str): continue
        if entry.get("transform") not in allowed: continue
        sources = entry.get("sources", [])
        if not isinstance(sources, list): sources = []
        valid.append({
            "destination": entry["destination"],
            "transform": entry["transform"],
            "sources": [s for s in sources if isinstance(s, dict) and isinstance(s.get("input"), str) and isinstance(s.get("field"), str)],
            "config": entry.get("config", {}) if isinstance(entry.get("config"), dict) else {},
        })
    return json.dumps(valid)

result = clean_llm_output(llm_output)
```

- [ ] **Step 4: Test the flow interactively in the UI**

Use the Langflow playground to send a sample `input_value` — a JSON blob like:

```json
{
  "driver": {"alias": "users", "fields": [{"name": "first_name", "type": "str"}, {"name": "last_name", "type": "str"}]},
  "destinations": [{"name": "full_name", "type": "str", "required": true}]
}
```

Expected: a JSON array containing one `template` entry for `full_name`. If the output is wrong, iterate on the prompt or node config in the UI.

- [ ] **Step 5: Export the flow**

Use Langflow's "Export" function to download the flow JSON. Rename the exported file to `DataMapperAutoMap.json`.

- [ ] **Step 6: Drop into the agentic flows directory**

Move the exported file to `src/backend/base/langflow/agentic/flows/DataMapperAutoMap.json`.

- [ ] **Step 7: Open the JSON and sanity-check two top-level fields**

Open the file. Confirm:
- `"name": "DataMapperAutoMap"` — this is the slug the frontend POSTs to.
- `"endpoint_name"` is either `"DataMapperAutoMap"` or null.

If either is wrong, edit the JSON directly (these two fields are the only ones safe to hand-edit).

- [ ] **Step 8: Restart the dev server and confirm the flow loads**

Run: stop the dev server (Ctrl-C), then `LFX_DEV=1 make run_cli` again.
Expected: startup logs include a line like `loaded agentic flow: DataMapperAutoMap` (exact wording depends on the loader — check `src/backend/base/langflow/initial_setup/setup.py:693` for the `load_agentic_flows` implementation).

- [ ] **Step 9: Smoke test via curl**

```bash
curl -X POST http://localhost:<backend-port>/api/v1/session/DataMapperAutoMap/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <session-token>" \
  -d '{"input_value":"{\"driver\":{\"alias\":\"users\",\"fields\":[{\"name\":\"first_name\",\"type\":\"str\"},{\"name\":\"last_name\",\"type\":\"str\"}]},\"destinations\":[{\"name\":\"full_name\",\"type\":\"str\",\"required\":true}]}","input_type":"chat","output_type":"chat","stream":false}'
```

Expected: a 200 response with a message containing a JSON array with at least one entry.

- [ ] **Step 10: Commit (ask first)**

```bash
git add src/backend/base/langflow/agentic/flows/DataMapperAutoMap.json
git commit -m "feat(data-mapper): ship DataMapperAutoMap flow for auto-mapping"
```

---

### Task 9: Backend smoke test — flow registers at startup

Purpose: guard against the flow JSON being broken or moved. No LLM-provider mocking — just assert the loader picks it up.

**Files:**
- Create: `src/backend/tests/unit/initial_setup/test_agentic_flows_registration.py` (or extend the existing loader test if one exists — search first for any `test_load_agentic_flows` file)

- [ ] **Step 1: Search for an existing loader test**

Run: `grep -rn "load_agentic_flows" src/backend/tests/ src/lfx/tests/`
If a test exists, extend it. If not, create a new one.

- [ ] **Step 2: Write the test**

```python
# src/backend/tests/unit/initial_setup/test_agentic_flows_registration.py
import pytest
from langflow.initial_setup.setup import load_agentic_flows


@pytest.mark.asyncio
async def test_data_mapper_auto_map_flow_is_loaded():
    flows = await load_agentic_flows()
    names = {flow_data.get("name") for _, flow_data in flows}
    assert "DataMapperAutoMap" in names, f"DataMapperAutoMap flow missing from loaded flows; loaded: {names}"


@pytest.mark.asyncio
async def test_data_mapper_auto_map_flow_has_required_shape():
    flows = await load_agentic_flows()
    matched = [flow_data for _, flow_data in flows if flow_data.get("name") == "DataMapperAutoMap"]
    assert len(matched) == 1
    flow = matched[0]
    # Minimal structural assertions — don't over-specify the exported JSON's internal shape.
    assert "data" in flow
    assert "data" in flow["data"]
    assert "nodes" in flow["data"]["data"]
    assert len(flow["data"]["data"]["nodes"]) > 0
```

- [ ] **Step 3: Run the test**

Run: `cd src/backend && uv run pytest tests/unit/initial_setup/test_agentic_flows_registration.py -v`
Expected: PASS — both tests.

- [ ] **Step 4: Commit (ask first)**

```bash
git add src/backend/tests/unit/initial_setup/test_agentic_flows_registration.py
git commit -m "test(data-mapper): assert DataMapperAutoMap flow loads at startup"
```

---

### Task 10: Playwright E2E spec

Purpose: end-to-end coverage for the happy path and key failure paths. Route-intercept the session endpoint so the test doesn't need a real LLM.

**Files:**
- Create: `src/frontend/tests/core/unit/dataMapperAutoMapping.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
// src/frontend/tests/core/unit/dataMapperAutoMapping.spec.ts
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Helpers copied from dataMapperModal.spec.ts (src/frontend/tests/core/unit/dataMapperModal.spec.ts:12-66).
// Extract to a shared util file if both specs share too much duplication later.
async function addDataMapperToCanvas(page: import("@playwright/test").Page) {
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("Data Mapper");
  await page.waitForSelector('[data-testid="processingData Mapper"]', { timeout: 10000 });
  await page.getByTestId("processingData Mapper").hover().then(async () => {
    await page.getByTestId("add-component-button-data-mapper").click();
  });
  await adjustScreenView(page);
}

async function openMappingModal(page: import("@playwright/test").Page) {
  const btn = page.getByRole("button", { name: /configure mapping|edit mapping/i });
  await btn.waitFor({ state: "visible", timeout: 10000 });
  await btn.click();
  await page.waitForSelector("text=Data Mapper", { timeout: 5000 });
}

async function addDestinationField(
  page: import("@playwright/test").Page,
  opts: { name: string; required?: boolean },
) {
  await page.getByTestId("data-mapper-add-field-btn").click();
  await page.getByTestId("data-mapper-field-name-input").fill(opts.name);
  if (opts.required) {
    const cb = page.getByTestId("data-mapper-field-required-checkbox");
    if (!(await cb.isChecked())) await cb.check();
  }
  await page.getByTestId("data-mapper-field-add-submit").click();
}

test.describe("Data Mapper — heavy auto-mapping", () => {
  test.beforeEach(async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', { timeout: 30000 });
    await page.getByTestId("blank-flow").click();

    await addDataMapperToCanvas(page);
    await page.getByTestId("title-Data Mapper").click();
    await openMappingModal(page);

    // Set up driver input via paste-sample so we have schema fields without needing upstream wiring.
    // NOTE: paste-sample requires an input card to exist; if none do (no upstream), fall back to
    // adding destinations with "static" transforms to exercise the empty-suggestions path.
    await addDestinationField(page, { name: "full_name", required: true });
    await addDestinationField(page, { name: "email", required: false });
  });

  test("happy path: Suggest → Apply all → Save → verifies mapping_config", async ({ page }) => {
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          outputs: [{ outputs: [{ outputs: { message: { message: JSON.stringify([
            { destination: "full_name", transform: "template",
              sources: [{ input: "users", field: "first_name" }, { input: "users", field: "last_name" }],
              config: { template: "{first_name} {last_name}" } },
            { destination: "email", transform: "direct",
              sources: [{ input: "users", field: "email" }], config: {} },
          ]) } } }] }],
        }),
      }));

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(page.getByRole("button", { name: /apply all/i })).toBeVisible();
    await page.getByRole("button", { name: /apply all/i }).click();

    await expect(page.getByRole("button", { name: /apply all/i })).not.toBeVisible();
    await expect(page.getByText(/{first_name} {last_name}/)).toBeVisible();
  });

  test("per-row accept merges one entry and leaves others pending", async ({ page }) => {
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ outputs: [{ outputs: [{ outputs: { message: { message: JSON.stringify([
          { destination: "full_name", transform: "direct", sources: [{ input: "users", field: "first_name" }], config: {} },
          { destination: "email",     transform: "direct", sources: [{ input: "users", field: "email" }],      config: {} },
        ]) } } }] }] }) }));

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(page.getByRole("button", { name: /suggested \(2\)/i })).toBeVisible();

    await page.getByRole("button", { name: /accept suggestion for full_name/i }).click();
    await expect(page.getByRole("button", { name: /suggested \(1\)/i })).toBeVisible();
  });

  test("error state: retry after 404", async ({ page }) => {
    let callCount = 0;
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) => {
      callCount += 1;
      if (callCount === 1) return route.fulfill({ status: 404, body: "Not Found" });
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ outputs: [{ outputs: [{ outputs: { message: { message: JSON.stringify([]) } } }] }] }) });
    });

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(page.getByRole("alert")).toContainText(/not available|update Langflow/i);
    await page.getByRole("button", { name: /retry/i }).click();
    await expect(page.getByRole("alert")).not.toBeVisible();
  });

  test("empty result shows the 'no new suggestions' chip", async ({ page }) => {
    await page.route("**/api/v1/session/DataMapperAutoMap/run", (route) =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ outputs: [{ outputs: [{ outputs: { message: { message: "[]" } } }] }] }) }));

    await page.getByRole("button", { name: /suggest mappings/i }).click();
    await expect(page.getByText(/no new suggestions/i)).toBeVisible();
  });

  test("button is disabled when every destination is customized", async ({ page }) => {
    // Configure every destination with a non-default "static" mapping — mirrors the fill-in
    // pattern used in dataMapperModal.spec.ts:99-101.
    for (const field of ["full_name", "email"]) {
      await page.getByTestId(`data-mapper-transform-select-${field}`).selectOption("static");
      await page.locator("textarea").last().fill('"x"');
    }
    await expect(page.getByRole("button", { name: /suggest mappings/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the spec against a live dev server**

Prerequisites: `LFX_DEV=1 make run_cli` is running AND `DataMapperAutoMap.json` is present. If either is missing, the first test will hang on the `beforeEach` flow setup.

Run: `cd src/frontend && npx playwright test tests/core/unit/dataMapperAutoMapping.spec.ts`
Expected: 5 tests PASS. If they fail, iterate — the `beforeEach` is the likely failure point since it adapts from the existing `dataMapperModal.spec.ts`.

- [ ] **Step 3: Commit (ask first)**

```bash
git add src/frontend/tests/core/unit/dataMapperAutoMapping.spec.ts
git commit -m "test(data-mapper): Playwright e2e for auto-mapping happy path + errors"
```

---

### Task 11: Update README + manual smoke test

Purpose: document the slot is now filled in production; run a human-eyes smoke test.

**Files:**
- Modify: `src/frontend/src/modals/dataMapperModal/README.md`

- [ ] **Step 1: Update the README**

Replace the "Extension seam — `suggestionsSlot`" section (search for it in `src/frontend/src/modals/dataMapperModal/README.md`) with text like:

```markdown
## Extension seam — `suggestionsSlot`

The modal accepts an optional `suggestionsSlot?: React.ReactNode` prop that renders in the modal header above the destination table. In production, the `MappingComponent` input renderer populates this slot with a `<MappingSuggestions>` component that provides LLM-driven auto-mapping via the shipped `DataMapperAutoMap` flow.

See `docs/superpowers/specs/2026-04-21-data-mapper-heavy-auto-mapping-design.md` for the full design.

Callers can still pass a custom `suggestionsSlot` for bespoke integrations — the contract is just a `ReactNode`.

## Pending suggestions

When `pendingSuggestions` is non-empty and `showPendingSuggestions` is true, the destination table renders proposed rows in a blue "pending" state with per-row ✓/✗ handlers (`onAcceptSuggestion(destination)` / `onRejectSuggestion(destination)`). The modal is agnostic about how suggestions are generated — it only renders what it's given.
```

- [ ] **Step 2: Run the full frontend test suite and the backend suite**

Run: `cd src/frontend && npx jest src/modals/dataMapperModal src/components/core/parameterRenderComponent/components/mappingComponent src/controllers/API/queries/assistant --no-coverage`
Expected: ALL PASS.

Run: `cd src/backend && uv run pytest tests/unit/initial_setup/test_agentic_flows_registration.py -v`
Expected: PASS.

- [ ] **Step 3: Manual smoke test**

With `LFX_DEV=1 make run_cli` running and the flow shipped:
1. Open a flow, drop a Data Mapper component onto the canvas.
2. Connect a driver input with real fields (use an existing component output).
3. Define a destination schema in the modal (paste a sample or autodetect).
4. Click "Suggest mappings."
5. Confirm: spinner → blue rows → per-row ✓/✗ works, Apply-all works, tab toggle works, Save works.
6. Manually introduce failures: stop the backend mid-request (simulates timeout) and confirm the error state appears with a retry.

Record any regressions in the plan's open questions section.

- [ ] **Step 4: Commit (ask first)**

```bash
git add src/frontend/src/modals/dataMapperModal/README.md
git commit -m "docs(data-mapper): document suggestionsSlot implementation"
```

---

## Post-plan checklist

- [ ] All 11 tasks committed.
- [ ] Manual smoke test passed.
- [ ] Full `src/frontend && npx jest src/modals/dataMapperModal/ --no-coverage` passes.
- [ ] Full `cd src/backend && uv run pytest tests/unit/initial_setup/ -v` passes.
- [ ] Playwright spec `dataMapperAutoMapping.spec.ts` passes against a live server with the shipped flow.
- [ ] Heavy-auto-mapping follow-ups (confidence scores, conflict panel, row-level redo, per-org prompts, streaming rows) documented somewhere — either updated spec or new kickoff for Phase 2.
