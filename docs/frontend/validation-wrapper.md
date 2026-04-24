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

When the existing hook uses `UseRequestProcessor` (the repo's internal react-query shim), the pattern is the same — wrap the fetcher passed to `mutate` / `query`. See `src/controllers/API/queries/flows/use-get-flow.ts` for the walking-skeleton example.

## HTTP mutations (POST / PATCH / DELETE)

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

`validatedMutationFn` validates **both** the request body (before firing) and the response (on return). In strict mode a bad request body throws before axios is called; in permissive mode it logs + proceeds.

## Storage (Zustand persist)

```ts
import { FlowsSliceSchema } from "@/schemas/app/storage/flowsSlice";
import { validatedStorage } from "@/lib/validated-storage";

persist(..., {
  name: "flows-storage",
  storage: createJSONStorage(() =>
    validatedStorage("storage.flowsSlice", FlowsSliceSchema),
  ),
});
```

Corrupt localStorage in strict mode → key is removed, slice initializes from defaults. Permissive mode → raw value passes through + reporter logs.

## SSE / EventSource

```ts
import { BuildEventSchema } from "@/schemas/app/stream/buildEvents";
import { validatedEventStream } from "@/lib/validated-stream";

const es = new EventSource(`/api/v1/build/${flowId}/stream`);
validatedEventStream("stream.buildEvents", BuildEventSchema, es, (event) => {
  // event is narrowed via discriminated union
  if (event.type === "vertex_build_end") {
    /* ... */
  }
});
```

Malformed JSON always routes to `onInvalid` (shape drift never silently looks like a valid event).

## Schema id naming

- **HTTP:** `api.<tag>.<operation>` — e.g. `api.flows.getFlow`, `api.templates.list`.
- **Storage:** `storage.<slice>` — e.g. `storage.flowsSlice`, `storage.authSlice`.
- **Stream:** `stream.<name>` — e.g. `stream.buildEvents`, `stream.chatMessages`.

The id is the only string at the call site; everything else is imported.

## Flipping to strict

When a domain's 1-week permissive bake completes with zero `ValidationError` events for its schema ids (check Sentry once wired, or the admin overlay under smoke traffic), add entries to `src/schemas/api/generated.meta.ts`:

```ts
export const SCHEMA_MODES: Array<[string, "permissive" | "strict"]> = [
  ["api.flows.getFlow", "strict"],
  ["api.flows.listFlows", "strict"],
  // ...
];
```

Commit the flip as its own PR so it's easy to revert if the bake was optimistic.

## Admin diagnostic overlay

The `<ValidationErrorOverlay />` is mounted at App root and self-gates on `authStore.isAdmin || authStore.isPlatformAdmin`. Non-admins pay zero cost — the component early-returns before subscribing to the error store.

Features:

- List of recent `ValidationError`s with schema id + boundary + mode.
- Detail view with full zod issue list + raw payload.
- **Copy payload** — one-click JSON copy for attaching to a backend bug.
- **Mute** — silence a specific schema id for the rest of the browser session. Mute state lives in `sessionStorage` so it doesn't survive a new session (prevents admins from silently skipping fresh regressions after an issue is fixed).

## When NOT to use the wrapper

- **Third-party HTTP** (OpenAI, Hugging Face, etc. — anything not our backend). Out of scope; the point of this project is our FastAPI boundary.
- **Build-time config** (Vite env vars, static JSON imports). Already type-checked at build time.
- **postMessage receivers** — deferred to a later chunk if ever prioritized.
- **URL query params** — deferred.
