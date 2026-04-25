# ParameterRenderComponent Leaf Memoization Design

**Date:** 2026-04-25
**Author:** brycedeneen (with Claude)
**Status:** Draft — pending user review

---

## Goal

Eliminate the per-keystroke render storm in `GenericNode` so that typing into one parameter field on a node does not re-render every other field's leaf component (Float / Int / Toggle / String / Code / Prompt / etc.). The outcome is a stable, enterprise-grade canvas: keystroke latency that does not scale with field count or node count.

This work captures the two deferrals from commits `89b82b6138` and `af6de04b77` and resolves them by fixing the root cause they both pointed at — `cloneDeep` calls that issue fresh `data.node` references on every keystroke — rather than by adding consumer-side memoization that those fresh refs would defeat.

## Non-goals

- Profiling-driven tuning of individual leaves before shipping. Verification is post-fix Profiler capture + canary unit tests, not a profile-first phase.
- Refactoring `use-update-all-nodes.ts`. Tracked as a `TODO(perf):` comment in code; scope of its own future plan.
- Per-leaf custom equality functions. Default `memo()` shallow equality is sufficient after the cloneDeep fix; custom equality is only added if a canary test demonstrates need.
- Memoization of upstream GenericNode itself beyond what `89b82b6138` already shipped.
- Feature flag / gradual rollout. Single PR, invariant-preserving change, gated by tests.
- Audit of `cloneDeep` outside `src/frontend/src/CustomNodes/`. Other call sites are out of scope.

## Standing constraints

- **No upstream PR.** Local `platform-multi-tenant` only.
- **No git commits without explicit approval.** Each commit step in the downstream plan must pause and ask.
- **Stage explicit paths.** Never `git add -A` / `git add .` / `git commit -a`.
- **Jest, not Vitest.** Frontend unit tests run with `npm run test` (jest).
- **Render-count tests are a new pattern in this repo.** No prior example to mirror; the pattern is established as part of this work.

---

## Background — the deferral chain

`89b82b6138` ("memoize 5 GenericNode subcomponents") wrapped five GenericNode subcomponents (`HandleTooltipComponent`, `NodeInputInfo`, `NodeUpdateComponent`, `NodeLegacyComponent`, `NodeOutputParameter`) in `memo()` and fixed an inline-`memo` bug in `NodeDescription`. It deferred memoization of `ParameterRenderComponent` leaves (Float / Int / Toggle / Link / etc.) noting that `baseInputProps` is rebuilt every render and that "memoization would in principle work but only if every upstream consumer of templateData/nodeClass/nodeInformationMetadata keeps stable refs — couldn't verify without profiling."

`af6de04b77` ("useCallback handleNodeClass") investigated further and identified the actual root cause: `GenericNode`'s downstream parents `cloneDeep` `data.node` on every typed character (specifically inside `useHandleOnNewValue`'s `updateNodeState` and `handleOnNewValue`), and `handleOnNewValue`'s `useCallback` includes `node` in its deps. Default shallow `memo()` on Float / Int / Toggle / etc. would not skip re-renders. The commit suggested two paths — custom equality functions per leaf, or an architectural shift where leaves subscribe to flowStore directly by `(nodeId, name)`.

This design takes a third path that neither commit fully called out: fix the producer instead of patching the consumers. After replacing the per-keystroke `cloneDeep` calls with structural sharing, default `memo()` shallow equality is sufficient on the leaves — no custom equality functions and no architectural shift required.

---

## Architecture overview

Three layers, in dependency order. Implementation order matches the section ordering below:

1. **Root cause fix (Section 1).** Replace the two per-keystroke `cloneDeep` calls in `useHandleOnNewValue` with structural sharing. After this lands, `data.node`, `template[name]`, and `nodeClass` references stay stable for any field the user is *not* typing into.
2. **Cold-path audit (Section 2).** Same-PR sweep of the other `cloneDeep` sites in `src/frontend/src/CustomNodes/hooks/` and `GenericNode/index.tsx`. Where the rewrite is mechanical, do it; where there is real deep mutation (`use-update-all-nodes.ts`), leave a `TODO(perf):` and ship the rest.
3. **Defensive `memo()` on the leaves (Section 3).** With stable refs flowing down, wrap the leaves in `ParameterRenderComponent` with default `memo()`. No custom equality. Lift array-literal props in the parent into `useMemo` so their refs stay stable too.

The principle: fix the producer, not the consumers. The 89b82b6 / af6de04 commits already proved consumer-side memoization cannot win when the producer reissues fresh refs every keystroke.

---

## Section 1 — Hot path fix (`use-handle-new-value.ts`)

File: `src/frontend/src/CustomNodes/hooks/use-handle-new-value.ts`

### Inner clone (current line 96)

```ts
const newNode = cloneDeep(node);
const template = newNode.template;
// ... later ...
parameter[key] = value;
```

Replace with structural sharing of just the path being mutated:

```ts
const stripUndefined = (obj: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));

const mergedField = { ...node.template[name], ...stripUndefined(changes) };
let newNode: APIClassType = {
  ...node,
  template: { ...node.template, [name]: mergedField },
};
```

### Data Operations special case (current lines 130–145)

The existing block mutates `template[field].show` for several sibling fields when the operations list is cleared. Same shallow-clone pattern:

```ts
if (
  name === "operations" &&
  Array.isArray(changes.value) &&
  changes.value.length === 0 &&
  node.display_name === "Data Operations"
) {
  const ops = { ...newNode.template };
  for (const field of DATA_OPERATIONS_OPERATION_FIELDS) {
    if (ops[field] && typeof ops[field] === "object" && "show" in ops[field]) {
      ops[field] = { ...ops[field], show: false };
    }
  }
  newNode = { ...newNode, template: ops };
}
```

### Outer clone (current line 76 in `updateNodeState`)

```ts
const newData = cloneDeep(oldNode.data);
newData.node = newNode;
```

The clone is wasted — only `data.node` changes. Replace with:

```ts
setNode(
  nodeId,
  (oldNode) => ({ ...oldNode, data: { ...oldNode.data, node: newNode } }),
  true,
  () => updateNodeInternals(nodeId),
);
```

### Dev-mode mutation guard

After construction, freeze the new node and template (one level deep) in dev only:

```ts
if (process.env.NODE_ENV !== "production") {
  Object.freeze(newNode);
  Object.freeze(newNode.template);
}
```

This catches the mutation regression class — anywhere downstream that today gets away with mutating because everything was a fresh clone — and surfaces it as a thrown error in dev / CI. Production NODE_ENV does not freeze; no perf cost in customer environments.

The freeze is one-level on purpose. Deep-freezing would defeat the perf goal and is unnecessary because the structural-sharing rewrites only ever produce new objects at the levels we've cloned shallowly.

---

## Section 2 — Cold path audit

Same-PR sweep, with explicit verdict per call site. All under `src/frontend/src/CustomNodes/`.

### `use-handle-node-class.ts:20,24` — REWRITE

Fires on refresh-button / dropdown picks where the API returns a new `nodeClass`. Current:

```ts
const newNode = cloneDeep(oldNode);
newNode.data = { ...newNode.data, node: cloneDeep(newNodeClass) };
```

Both clones are wasted. The API response is already a fresh object; nothing else holds a reference to it. Replace with:

```ts
return { ...oldNode, data: { ...oldNode.data, node: newNodeClass } };
```

### `use-update-node-code.ts:20` — REWRITE

Fires on code editor save. Same pattern, same rewrite — structural sharing of `data.node` only.

### `use-update-all-nodes.ts:24` — DEFER WITH TODO

Bulk update path. The function does `cloneDeep(oldNodes)` and then iterates with mutations into `newNodes[i].data.node.template[...]`. Refactoring to map + structural sharing is non-trivial (30+ lines) and not on the keystroke path. Action: leave a comment:

```ts
// TODO(perf): bulk path retains cloneDeep pending dedicated refactor.
// See docs/superpowers/specs/2026-04-25-parameter-render-leaf-memoization-design.md
const newNodes = cloneDeep(oldNodes);
```

### `GenericNode/index.tsx:309` — REWRITE

Fires on output-selector click. Mutation is constrained to `outputs[i].selected` and `outputs[i].hidden`. Replace with map + shallow clone of just the changed entry:

```ts
const oldOutputs = oldNode.data.node?.outputs ?? [];
const targetIdx = oldOutputs.findIndex(/* ...existing logic... */);
const newOutputs = oldOutputs.map((out, i) =>
  i === targetIdx ? { ...out, selected: /* ... */, hidden: /* ... */ } : out,
);
return {
  ...oldNode,
  data: {
    ...oldNode.data,
    node: { ...oldNode.data.node!, outputs: newOutputs },
  },
};
```

### Net change

4 rewrites + 1 `TODO(perf):` comment.

---

## Section 3 — `memo()` on `ParameterRenderComponent` leaves

File scope: `src/frontend/src/components/core/parameterRenderComponent/components/**`

### Coverage

**Already wrapped** — no change required (start working "for free" once Section 1 lands):

- `connectionComponent` (line 247: `export default memo(ConnectionComponent)`)
- `sortableListComponent` (line 229: `export default memo(SortableListComponent)`; also `SortableListItem` at line 22)

**To wrap with `memo()`**:

`accordionPromptComponent`, `codeAreaComponent`, `copyFieldAreaComponent`, `dictComponent`, `dropdownComponent`, `emptyParameterComponent`, `floatComponent`, `helperTextComponent`, `inputComponent`, `inputFileComponent`, `inputGlobalComponent`, `inputListComponent`, `intComponent`, `keypairListComponent`, `linkComponent`, `mappingComponent`, `mcpComponent`, `modelInputComponent`, `multiselectComponent`, `mustachePromptComponent`, `promptComponent`, `queryComponent`, `searchBarComponent`, `sliderComponent`, `strRenderComponent`, `tabComponent`, `tableComponent`, `TableNodeComponent`, `textAreaComponent`, `textFileSecretComponent`, `toggleShadComponent`, `ToolsComponent`, `webhookFieldComponent`.

Per-leaf change: a single-line `memo()` wrapper at the export site, preserving the existing default-vs-named export pattern. No custom equality functions in initial implementation.

### `useMemo` lifts in the parent

File: `src/frontend/src/components/core/parameterRenderComponent/index.tsx`

Several leaves receive array-literal or object-literal props built inline from `templateData`. After the cloneDeep fix, `templateData` is itself stable, so we can hoist the inline literals into `useMemo` keyed on `templateData`. Lifts required:

- `MultiselectComponent` `options` prop (current lines 113–115).
- `TableNodeComponent` `columns` prop (current lines 237–241).
- `TabComponent` `options` prop (current line 315).
- `ModelInputComponent` `options` prop (current lines 352–355).
- `SortableListComponent` `options` prop (current line 281).

Pattern:

```ts
const multiselectOptions = useMemo(
  () =>
    (Array.isArray(templateData.options)
      ? templateData.options
      : [templateData.options]) as string[] || [],
  [templateData.options],
);
```

These lifts move the array-build off the render path and give the leaves stable prop refs. They are mechanical; one `useMemo` per lift, dep array narrow.

### Custom equality exception list

Empty by default. Populated only if a Section 4 canary test fails — captured here with rationale per leaf, not added pre-emptively.

---

## Section 4 — Verification

### A. DevTools Profiler before/after (manual, captured in PR)

Reproduction fixture: a representative flow JSON checked into the repo at `src/frontend/__perf_fixtures__/large-flow.json` (~20 nodes, mix of leaf types — Float, Int, String, Toggle, Dropdown, Code, Prompt). Steps:

1. `npm run start`
2. Load the fixture flow.
3. Open React DevTools → Profiler → Record.
4. Type 5 characters into one StrRenderComponent field on a node with 6+ visible parameters.
5. Stop recording.
6. Capture: total commits, total render duration, top-N rendered components.

Pre-fix and post-fix screenshots / numeric diffs go in the PR description. Absolute numbers depend on machine; the *delta* is the artifact we ship.

### B. Render-count unit tests

Helper at `src/frontend/src/__test_helpers__/render-counter.tsx`:

```tsx
import type { ComponentType } from "react";

export function withRenderCount<P extends object>(
  Component: ComponentType<P>,
  label: string,
  counts: Record<string, number>,
) {
  const Wrapped = (props: P) => {
    counts[label] = (counts[label] ?? 0) + 1;
    return <Component {...props} />;
  };
  Wrapped.displayName = `RenderCounted(${label})`;
  return Wrapped;
}
```

Two canary tests at `src/frontend/src/CustomNodes/GenericNode/components/parameterRenderComponent/__tests__/sibling-render-isolation.test.tsx`:

1. **Sibling isolation.** Mount the smallest realistic harness with two fields — a `StrRenderComponent` and a `FloatComponent` (FloatComponent counter-wrapped). Type 3 characters into the StrRender field. Assert: `counts["FloatComponent"] <= 1` after initial mount.
2. **Self-render sanity.** Same setup, count the StrRender field itself. Type 3 characters. Assert: `counts["StrRenderComponent"] >= 4` (initial mount + 3 keystroke renders). Prevents the test from passing trivially because *nothing* rendered.

The `<= 1` ceiling on the sibling-isolation test (instead of `=== 0`) absorbs React's batching variability without admitting real regressions.

### C. Existing test suite

Must remain green: `npm run build`, `tsc --noEmit`, `npm run test` (currently 19 suites / 199 tests).

---

## Section 5 — Risks & rollout

### Risks, ranked

1. **Hidden mutations of the new node object.** Killing `cloneDeep` exposes any code path that mutates `node.template[other_field].*` after `handleOnNewValue` returns. The dev-mode `Object.freeze` catches one-level mutations and throws loudly during local dev / CI. Deeper-property mutations (e.g. `node.template.x.options.push(...)`) won't trip the freeze and need code review during the cold-path audit. Mitigation: pre-implementation grep for `.template[` and `.outputs[` writes across `src/frontend/src/CustomNodes/**` and `src/frontend/src/components/core/**`, captured as a checklist in the implementation plan.
2. **A leaf component breaks under shallow memo.** Some leaf may have stale-closure bugs that today are masked by the constant re-render loop. After `memo()` they would surface as "the component shows old data after some interaction." Mitigation: a manual smoke pass over each leaf type (typing, refresh, dropdown change, code edit, table edit, slider drag) is a required step in the implementation plan, not optional.
3. **Render-count test flakiness.** React's batching/scheduling can vary by environment. Mitigation: tests assert `<= 1` not `=== 0` for sibling renders; any flake in CI is treated as a real signal, not retried-and-merged.
4. **`Object.freeze` exposes a real production mutation.** Dev-only freeze means CI catches it but a customer running with `NODE_ENV=development` is unaffected. Production `NODE_ENV` does not freeze. Accepted.

### Rollout

Single PR, no feature flag. Reasoning:

- Change is invariant-preserving (same data flowing, just different references).
- Risk surface is bounded by the dev freeze + canary tests + manual smoke pass.
- A feature flag would mean shipping the cloneDeep version forever as the fallback path, which defeats the goal.

### Implementation order in the PR

Each stage independently verifiable — `npm run build` + `npm run test` after each.

1. Hot path cloneDeep fix + dev `Object.freeze` guard.
2. Cold path audit (4 rewrites + 1 `TODO(perf):` comment).
3. `useMemo` lifts for array-literal props in `ParameterRenderComponent`.
4. `memo()` wrappers across the leaf list.
5. Render-counter helper + two canary tests.
6. Perf fixture flow file + Profiler capture in the PR description.

If any stage fails verification, stop and re-evaluate rather than press on.

---

## Open questions

None at design time. Custom equality functions, additional leaves, and `use-update-all-nodes.ts` refactor are intentionally out of scope and tracked either inline (`TODO(perf):`) or as future plan candidates.
