# ParameterRenderComponent Leaf Memoization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the per-keystroke render storm in `GenericNode` so typing into one parameter field does not re-render every other field's leaf component, by replacing per-keystroke `cloneDeep` calls in node-update hooks with structural sharing and wrapping `ParameterRenderComponent` leaves in `memo()`.

**Architecture:** Three layers landed in dependency order: (1) hot-path fix — extract a pure `applyTemplateChange` helper from `useHandleOnNewValue` and use it to replace the per-keystroke `cloneDeep`s; (2) cold-path audit — same-PR rewrite of the other `cloneDeep` sites in `CustomNodes/hooks/` and `GenericNode/index.tsx`; (3) defensive `memo()` on every leaf in `parameterRenderComponent/components/**` plus `useMemo` lifts in the parent for array-literal props. Verification is via unit tests on the helper + one render-count canary test + manual Profiler capture.

**Tech Stack:** React 18, Zustand v5, Jest + React Testing Library, Biome, TypeScript 5.x, Vite 5.

**Spec:** `docs/superpowers/specs/2026-04-25-parameter-render-leaf-memoization-design.md` — read before starting.

**Standing constraints (repeat from spec):**
- No upstream PR; local `platform-multi-tenant` only.
- **No git commits without explicit user approval** — every "Commit" step must pause and ask. Do not use `git add -A` / `git add .` / `git commit -a`. Stage explicit paths only.
- Jest, not Vitest.
- Working directory for all commands: `.worktrees/perf-parameter-render-memo/src/frontend/` unless noted.

---

## File Structure

**Create:**
- `src/frontend/src/CustomNodes/hooks/applyTemplateChange.ts` — pure helper for the per-keystroke node-update path (Task 3)
- `src/frontend/src/CustomNodes/hooks/__tests__/applyTemplateChange.test.ts` — unit tests for the helper (Task 2)
- `src/frontend/src/components/core/parameterRenderComponent/areInputPropsEqual.ts` — shared memo equality comparator (Task 10)
- `src/frontend/src/components/core/parameterRenderComponent/__tests__/areInputPropsEqual.test.ts` — comparator unit tests (Task 10)
- `src/frontend/src/__test_helpers__/render-counter.tsx` — render-counting wrapper (Task 14)
- `src/frontend/src/CustomNodes/GenericNode/components/parameterRenderComponent/__tests__/sibling-render-isolation.test.tsx` — render-count canary (Task 14)
- `src/frontend/__perf_fixtures__/large-flow.json` — Profiler reproduction fixture (Task 15)
- `docs/superpowers/plans/notes/mutation-audit-2026-04-25.md` — checklist of grep findings from Task 1

**Modify:**
- `src/frontend/src/CustomNodes/hooks/use-handle-new-value.ts` — wire in helper, drop both `cloneDeep` sites (Task 4)
- `src/frontend/src/CustomNodes/hooks/use-handle-node-class.ts` — drop both `cloneDeep` sites (Task 5)
- `src/frontend/src/CustomNodes/hooks/use-update-node-code.ts` — drop `cloneDeep` site (Task 6)
- `src/frontend/src/CustomNodes/hooks/use-update-all-nodes.ts` — add `TODO(perf):` comment (Task 8)
- `src/frontend/src/CustomNodes/GenericNode/index.tsx` — rewrite output-selector handler at line 309 (Task 7)
- `src/frontend/src/components/core/parameterRenderComponent/index.tsx` — add `useMemo` lifts for array-literal props (Task 9)
- `src/frontend/src/components/core/parameterRenderComponent/components/<each-leaf>/index.tsx` — wrap default export in `memo()` with `areInputPropsEqual` (Tasks 11–13)

---

## Task 1: Pre-implementation discovery — mutation audit

**Files:**
- Create: `docs/superpowers/plans/notes/mutation-audit-2026-04-25.md`

**Purpose:** Identify any code that currently mutates `node.template[*]` or `node.outputs[*]` after `handleOnNewValue` returns. Killing the `cloneDeep`s exposes these as bugs (dev `Object.freeze` will throw). Build a checklist of suspect sites so they can be reviewed during Tasks 4–7 and fixed if real.

- [ ] **Step 1: Run the grep**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/perf-parameter-render-memo
grep -rEn '\.template\[[^\]]+\]\s*=|\.template\[[^\]]+\]\.[A-Za-z_]+\s*=|\.outputs\[[^\]]+\]\s*=|\.outputs\[[^\]]+\]\.[A-Za-z_]+\s*=' src/frontend/src/CustomNodes src/frontend/src/components/core 2>/dev/null
```

Expected: a list of lines that perform direct property assignment into template/outputs subscripts.

- [ ] **Step 2: Triage each hit and write the audit doc**

For each grep hit, classify:
- **SAFE** — assignment is on a fresh local object (e.g., `const newTemplate = {...}; newTemplate[name] = ...`). Mark `[ok]`.
- **MUTATES STORE** — assignment writes through `data.node.template[...]` or `node.template[...]` where `node` is the parameter passed in. Mark `[fix-needed]` and note the line.
- **AMBIGUOUS** — needs read of surrounding code. Mark `[review]` with a one-line question.

Write the file as:

```markdown
# Node-mutation audit — 2026-04-25

Generated for the cloneDeep removal in `use-handle-new-value.ts`. Each entry is a hit from the grep at the top of Task 1, classified per the mutation-safety rule in the spec.

## Findings

- `path/to/file.ts:LINE` — `[ok|fix-needed|review]` — one-line note.
- ...

## Action items

- [ ] None / List of files to revisit during Task <N>.
```

- [ ] **Step 3: Commit (PAUSE)**

Pause and ask the user: "Mutation audit complete. Commit this and continue, or hold off?" Do not commit without explicit approval. If approved:

```bash
git add docs/superpowers/plans/notes/mutation-audit-2026-04-25.md
git commit -m "docs(perf): node-mutation audit for parameter-render-leaf-memoization"
```

---

## Task 2: Failing unit tests for `applyTemplateChange`

**Files:**
- Create: `src/frontend/src/CustomNodes/hooks/__tests__/applyTemplateChange.test.ts`

**Purpose:** Strict TDD — write the test file referencing a not-yet-created `applyTemplateChange` helper. Verify the suite fails with a module-resolution error before any implementation lands.

- [ ] **Step 1: Create the test file**

```ts
// src/frontend/src/CustomNodes/hooks/__tests__/applyTemplateChange.test.ts
import { applyTemplateChange } from "../applyTemplateChange";
import type { APIClassType } from "@/types/api";

const baseNode = (): APIClassType =>
  ({
    template: {
      query: { type: "str", value: "hello", show: true } as any,
      count: { type: "int", value: 1, show: true } as any,
      operations: { type: "str", value: [], show: true } as any,
      filter_key: { type: "str", value: "", show: true } as any,
      operator: { type: "str", value: "", show: true } as any,
    },
    display_name: "Test Node",
  }) as unknown as APIClassType;

describe("applyTemplateChange", () => {
  it("returns a new node reference (not the input)", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", { value: "world" });
    expect(result).not.toBe(node);
  });

  it("returns a new template[name] reference with the merged change", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", { value: "world" });
    expect(result.template.query).not.toBe(node.template.query);
    expect(result.template.query.value).toBe("world");
  });

  it("preserves reference identity for sibling template entries (structural sharing)", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", { value: "world" });
    expect(result.template.count).toBe(node.template.count);
    expect(result.template.operations).toBe(node.template.operations);
  });

  it("strips undefined entries from changes", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "query", {
      value: "world",
      placeholder: undefined as any,
    });
    expect(result.template.query.value).toBe("world");
    expect("placeholder" in result.template.query).toBe(
      "placeholder" in node.template.query,
    );
  });

  it("hides Data Operations operation-fields when operations is cleared and display_name matches", () => {
    const node = { ...baseNode(), display_name: "Data Operations" };
    const result = applyTemplateChange(node, "operations", { value: [] });
    expect(result.template.filter_key.show).toBe(false);
    expect(result.template.operator.show).toBe(false);
  });

  it("does NOT hide operation-fields when display_name is not Data Operations", () => {
    const node = baseNode();
    const result = applyTemplateChange(node, "operations", { value: [] });
    expect(result.template.filter_key.show).toBe(true);
    expect(result.template.operator.show).toBe(true);
  });

  it("does NOT hide operation-fields when changes.value is non-empty", () => {
    const node = { ...baseNode(), display_name: "Data Operations" };
    const result = applyTemplateChange(node, "operations", { value: ["x"] });
    expect(result.template.filter_key.show).toBe(true);
  });

  it("freezes the returned node and template in dev mode (mutations throw)", () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = "development";
    try {
      const node = baseNode();
      const result = applyTemplateChange(node, "query", { value: "world" });
      expect(() => {
        (result as any).template = {};
      }).toThrow();
      expect(() => {
        (result.template as any).query = {};
      }).toThrow();
    } finally {
      process.env.NODE_ENV = prev;
    }
  });

  it("does NOT freeze in production mode", () => {
    const prev = process.env.NODE_ENV;
    process.env.NODE_ENV = "production";
    try {
      const node = baseNode();
      const result = applyTemplateChange(node, "query", { value: "world" });
      expect(Object.isFrozen(result)).toBe(false);
    } finally {
      process.env.NODE_ENV = prev;
    }
  });
});
```

- [ ] **Step 2: Run the suite, verify the import fails**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx jest src/CustomNodes/hooks/__tests__/applyTemplateChange.test.ts 2>&1 | tail -20
```

Expected: failure with `Cannot find module '../applyTemplateChange'` or similar — proves the helper doesn't exist yet.

- [ ] **Step 3: Commit (PAUSE)**

Ask the user before committing. Stage explicit paths.

```bash
git add src/frontend/src/CustomNodes/hooks/__tests__/applyTemplateChange.test.ts
git commit -m "test(perf): failing tests for applyTemplateChange helper"
```

---

## Task 3: Implement `applyTemplateChange` to make tests pass

**Files:**
- Create: `src/frontend/src/CustomNodes/hooks/applyTemplateChange.ts`

**Purpose:** Pure helper that returns a new `APIClassType` with structural sharing. Includes the Data Operations special case and dev-mode `Object.freeze`. No `cloneDeep`.

- [ ] **Step 1: Create the helper**

```ts
// src/frontend/src/CustomNodes/hooks/applyTemplateChange.ts
import type { APIClassType, InputFieldType } from "@/types/api";

// Must match ALL_OPERATION_FIELDS in data_operations.py — kept in sync with
// the same constant in use-handle-new-value.ts. If you change one, change both.
const DATA_OPERATIONS_OPERATION_FIELDS = [
  "select_keys_input",
  "filter_key",
  "operator",
  "filter_values",
  "append_update_data",
  "remove_keys_input",
  "rename_keys_input",
  "mapped_json_display",
  "selected_key",
  "query",
];

const stripUndefined = <T extends Record<string, unknown>>(obj: T): Partial<T> =>
  Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined),
  ) as Partial<T>;

/**
 * Builds a new APIClassType with `template[name]` replaced by a shallow merge
 * of the original entry and `changes` (undefined entries filtered out).
 *
 * Sibling template entries keep their original reference (structural sharing),
 * which is what enables shallow-equality memo() on ParameterRenderComponent
 * leaves to skip re-renders. Replaces a per-keystroke `cloneDeep(node)` with
 * the same observable behavior at near-zero allocation cost.
 *
 * Includes the Data Operations special case from `use-handle-new-value.ts`:
 * clearing the `operations` list on a node named "Data Operations" hides the
 * operation-specific fields by setting their `show: false`.
 */
export function applyTemplateChange(
  node: APIClassType,
  name: string,
  changes: Partial<InputFieldType>,
): APIClassType {
  const cleanChanges = stripUndefined(changes);
  const mergedField = { ...node.template[name], ...cleanChanges };
  let newTemplate: typeof node.template = {
    ...node.template,
    [name]: mergedField,
  };

  if (
    name === "operations" &&
    Array.isArray(changes.value) &&
    changes.value.length === 0 &&
    node.display_name === "Data Operations"
  ) {
    const ops = { ...newTemplate };
    for (const field of DATA_OPERATIONS_OPERATION_FIELDS) {
      const entry = ops[field];
      if (entry && typeof entry === "object" && "show" in entry) {
        ops[field] = { ...entry, show: false };
      }
    }
    newTemplate = ops;
  }

  const newNode: APIClassType = { ...node, template: newTemplate };

  if (process.env.NODE_ENV !== "production") {
    Object.freeze(newNode);
    Object.freeze(newNode.template);
  }

  return newNode;
}
```

- [ ] **Step 2: Run the suite, verify all tests pass**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx jest src/CustomNodes/hooks/__tests__/applyTemplateChange.test.ts 2>&1 | tail -20
```

Expected: 9 tests pass.

- [ ] **Step 3: Run typecheck**

```bash
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -20
```

Expected: 0 errors.

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add src/frontend/src/CustomNodes/hooks/applyTemplateChange.ts
git commit -m "feat(perf): applyTemplateChange — structural-sharing helper for node updates"
```

---

## Task 4: Wire `applyTemplateChange` into `useHandleOnNewValue` (hot path fix)

**Files:**
- Modify: `src/frontend/src/CustomNodes/hooks/use-handle-new-value.ts`

**Purpose:** Replace the inner `cloneDeep(node)` + mutation block (lines 96–145) with a call to `applyTemplateChange`. Replace the outer `cloneDeep(oldNode.data)` (line 76) with shallow object spread. Drop the `cloneDeep` import — only `debounce` from lodash remains.

- [ ] **Step 1: Replace `updateNodeState` body (lines 71–90 in current file)**

Find the existing block:

```ts
  // Memoize the node update function
  const updateNodeState = useCallback(
    (newNode: APIClassType) => {
      setNode(
        nodeId,
        (oldNode) => {
          const newData = cloneDeep(oldNode.data);
          newData.node = newNode;
          return {
            ...oldNode,
            data: newData,
          };
        },
        true,
        () => {
          updateNodeInternals(nodeId);
        },
      );
    },
    [nodeId, setNode, updateNodeInternals],
  );
```

Replace with:

```ts
  // Memoize the node update function
  const updateNodeState = useCallback(
    (newNode: APIClassType) => {
      setNode(
        nodeId,
        (oldNode) => ({
          ...oldNode,
          data: { ...oldNode.data, node: newNode },
        }),
        true,
        () => {
          updateNodeInternals(nodeId);
        },
      );
    },
    [nodeId, setNode, updateNodeInternals],
  );
```

- [ ] **Step 2: Replace the inner cloneDeep + mutation block in `handleOnNewValue` (current lines 94–185)**

Find the existing block from `const handleOnNewValue: handleOnNewValueType = useCallback(` through `updateNodeState(newNode);` at the end of the inner async function. Specifically, the block that does:

```ts
      const newNode = cloneDeep(node);
      const template = newNode.template;
      // ... track + guard + parameter mutation + Data Operations + setNodeClass + debounce ...
      updateNodeState(newNode);
```

Replace the section that builds + mutates `newNode` with a call to `applyTemplateChange`. The new structure of `handleOnNewValue` is:

```ts
  const debouncedMutateRef = useRef<any>(null);

  const handleOnNewValue: handleOnNewValueType = useCallback(
    async (changes, options?) => {
      // Debounced tracking
      track("Component Edited", { nodeId });

      if (nodeId.toLowerCase().includes("astra") && name === "database_name") {
        track("Database Selected", { nodeId, databaseName: changes.value });
      }

      if (!node.template) {
        setErrorData({ title: "Template not found in the component" });
        return;
      }

      const parameter = node.template[name];

      if (!parameter) {
        setErrorData({ title: "Parameter not found in the template" });
        return;
      }

      const shouldDebounce = DEBOUNCE_FIELD_LIST.includes(
        (parameter?._input_type as string) ?? "",
      );

      if (!options?.skipSnapshot) takeSnapshot();

      const newNode = applyTemplateChange(node, name, changes);

      const shouldUpdate = newNode.template[name].real_time_refresh;

      const setNodeClass = (newNodeClass: APIClassType) => {
        options?.setNodeClass?.(newNodeClass);
        updateNodeState(newNodeClass);
      };

      if (shouldUpdate && changes.value !== undefined) {
        if (!debouncedMutateRef.current) {
          debouncedMutateRef.current = debounce(
            async (
              value,
              node,
              setNodeClassFn,
              postTemplateFn,
              setErrorDataFn,
            ) => {
              await mutateTemplate(
                value,
                nodeId,
                node,
                setNodeClassFn,
                postTemplateFn,
                setErrorDataFn,
              );
            },
            shouldDebounce ? DEBOUNCE_TIME_1_SECOND : 0,
          );
        }
        debouncedMutateRef.current(
          changes.value,
          newNode,
          setNodeClass,
          postTemplateValue,
          setErrorData,
        );
      }

      updateNodeState(newNode);
    },
    [
      node,
      nodeId,
      name,
      takeSnapshot,
      postTemplateValue,
      setErrorData,
      updateNodeState,
    ],
  );
```

Notes for the engineer:
- The original code did `parameter[key] = value` after `cloneDeep(node)`, then read `parameter.real_time_refresh` later. After the rewrite, read `real_time_refresh` from the merged result: `newNode.template[name].real_time_refresh` (the post-merge value, equivalent semantics).
- The `parameter` variable now points at the *original* (un-merged) template entry — used only for the existence guard and the `_input_type` debounce check, which both look at fields that don't change in `changes`. Behavior is preserved.
- The Data Operations branch lived in the original mutation block — `applyTemplateChange` handles it internally, so it disappears from this file.
- The original `template = newNode.template` local is no longer needed.

- [ ] **Step 3: Update imports**

At the top of `use-handle-new-value.ts`, change:

```ts
import { cloneDeep, debounce } from "lodash";
```

to:

```ts
import { debounce } from "lodash";
```

And add:

```ts
import { applyTemplateChange } from "./applyTemplateChange";
```

- [ ] **Step 4: Remove the now-dead `DATA_OPERATIONS_OPERATION_FIELDS` constant**

The constant moved to `applyTemplateChange.ts`. Delete the duplicate at the top of `use-handle-new-value.ts` (current lines 16–28, including the comment above it).

- [ ] **Step 5: Run typecheck and existing tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 type errors. All existing tests still pass (currently 19 suites / 199 tests).

- [ ] **Step 6: Commit (PAUSE)**

```bash
git add src/frontend/src/CustomNodes/hooks/use-handle-new-value.ts
git commit -m "perf(react): replace per-keystroke cloneDeep in useHandleOnNewValue"
```

---

## Task 5: Cold path — rewrite `use-handle-node-class.ts`

**Files:**
- Modify: `src/frontend/src/CustomNodes/hooks/use-handle-node-class.ts`

**Purpose:** The handler fires on refresh-button / dropdown picks where the API returns a fresh `nodeClass`. Replace both `cloneDeep` calls with shallow object spread.

- [ ] **Step 1: Read current state**

Read the file to confirm the structure before editing. The relevant block (lines 16–32 approximately) does:

```ts
setNode(nodeId, (oldNode) => {
  const newNode = cloneDeep(oldNode);
  newNode.data = {
    ...newNode.data,
    node: cloneDeep(newNodeClass),
  };
  return newNode;
}, ...);
```

- [ ] **Step 2: Replace with shallow spread**

```ts
setNode(nodeId, (oldNode) => ({
  ...oldNode,
  data: { ...oldNode.data, node: newNodeClass },
}), ...);
```

The `cloneDeep(newNodeClass)` is removed because `newNodeClass` is the API response — already a fresh object, no other holders.

- [ ] **Step 3: Drop the `cloneDeep` import**

Change:

```ts
import { cloneDeep } from "lodash";
```

to: delete the line entirely (no other lodash usage in this file).

- [ ] **Step 4: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 errors, all tests pass.

- [ ] **Step 5: Commit (PAUSE)**

```bash
git add src/frontend/src/CustomNodes/hooks/use-handle-node-class.ts
git commit -m "perf(react): drop cloneDeep in useHandleNodeClass — structural sharing instead"
```

---

## Task 6: Cold path — rewrite `use-update-node-code.ts`

**Files:**
- Modify: `src/frontend/src/CustomNodes/hooks/use-update-node-code.ts`

**Purpose:** Handler fires on code-editor save. Same pattern as Task 5.

- [ ] **Step 1: Read the file to find the cloneDeep**

The relevant block does:

```ts
setNode(nodeId, (oldNode) => {
  const newNode = cloneDeep(oldNode);
  newNode.data = { ...newNode.data, node: newNodeClass };
  return newNode;
}, ...);
```

- [ ] **Step 2: Replace with shallow spread**

```ts
setNode(nodeId, (oldNode) => ({
  ...oldNode,
  data: { ...oldNode.data, node: newNodeClass },
}), ...);
```

- [ ] **Step 3: Drop the `cloneDeep` import**

Delete:

```ts
import { cloneDeep } from "lodash"; // or any other deep cloning library you prefer
```

(Yes — that's the actual current line including the trailing comment.)

- [ ] **Step 4: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 errors.

- [ ] **Step 5: Commit (PAUSE)**

```bash
git add src/frontend/src/CustomNodes/hooks/use-update-node-code.ts
git commit -m "perf(react): drop cloneDeep in useUpdateNodeCode"
```

---

## Task 7: Cold path — rewrite output-selector handler in `GenericNode/index.tsx`

**Files:**
- Modify: `src/frontend/src/CustomNodes/GenericNode/index.tsx`

**Purpose:** The output-selector click handler (around line 309 in the current file) does `cloneDeep(oldNode)` then mutates `outputs[i].selected` and `outputs[i].hidden`. Replace with map + shallow clone of the changed entry only.

- [ ] **Step 1: Locate the handler**

Open `src/frontend/src/CustomNodes/GenericNode/index.tsx` and find `cloneDeep(oldNode)` (currently line 309, inside `handleSelectOutput`). The current block (lines 308–333):

```ts
setNode(data.id, (oldNode) => {
  const newNode = cloneDeep(oldNode);
  if (newNode.data.node?.outputs) {
    newNode.data.node.outputs.forEach((out) => {
      if (out.selected) {
        out.selected = undefined;
      }
    });

    const outputIndex = newNode.data.node.outputs.findIndex(
      (o) => o.name === output.name,
    );
    if (outputIndex !== -1) {
      const outputTypes = output.types || [];
      const defaultType =
        outputTypes.length > 0 ? outputTypes[0] : undefined;
      newNode.data.node.outputs[outputIndex].selected =
        output.selected ?? defaultType;
    }

    const selectedOutput = newNode.data.node.outputs[outputIndex]?.name;
    (newNode.data as NodeDataType).selected_output = selectedOutput;
  }

  return newNode;
});
```

Original logic: clear `selected` on every output, then set `selected` on the target output, then update `data.selected_output`. If the target is not found (`outputIndex === -1`), the only effect is "all selected cleared, selected_output → undefined".

- [ ] **Step 2: Rewrite with structural sharing**

Replace the block with the following. Behavior preserved: target gets `newSelected`; non-target outputs that were previously selected get cleared; outputs that were already unselected pass through unchanged. The `outputs[-1]?.name` lookup naturally yields `undefined` when the target is missing.

```ts
setNode(data.id, (oldNode) => {
  const oldOutputs = oldNode.data.node?.outputs;
  if (!oldOutputs) return oldNode;

  const targetIdx = oldOutputs.findIndex((o) => o.name === output.name);
  const outputTypes = output.types || [];
  const defaultType = outputTypes.length > 0 ? outputTypes[0] : undefined;
  const newSelected = output.selected ?? defaultType;

  const newOutputs = oldOutputs.map((out, i) => {
    if (i === targetIdx) return { ...out, selected: newSelected };
    if (out.selected) return { ...out, selected: undefined };
    return out;
  });

  const selectedOutput = newOutputs[targetIdx]?.name;

  return {
    ...oldNode,
    data: {
      ...oldNode.data,
      node: { ...oldNode.data.node!, outputs: newOutputs },
      selected_output: selectedOutput,
    } as NodeDataType,
  };
});
```

- [ ] **Step 3: Verify `cloneDeep` import can be removed**

```bash
grep -n "cloneDeep" src/frontend/src/CustomNodes/GenericNode/index.tsx
```

If line 309 was the only reference, delete the import:

```ts
import { cloneDeep } from "lodash";
```

If there are other references, leave the import.

- [ ] **Step 4: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 errors.

- [ ] **Step 5: Manual smoke test — output selector**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npm run start
```

In a browser at `http://localhost:3000`:
1. Open any flow with a node that has multiple outputs (e.g., a flow with an Agent component or a Tool component with output dropdown).
2. Click the output dropdown / selector.
3. Pick a different output.
4. Confirm: the selection updates visually; the canvas does not crash; the new output shows as selected after a re-render.

If the smoke test fails, the cloneDeep replacement broke a path the spec missed — stop and investigate before continuing.

- [ ] **Step 6: Commit (PAUSE)**

```bash
git add src/frontend/src/CustomNodes/GenericNode/index.tsx
git commit -m "perf(react): drop cloneDeep in GenericNode output-selector handler"
```

---

## Task 8: Cold path — `TODO(perf):` comment in `use-update-all-nodes.ts`

**Files:**
- Modify: `src/frontend/src/CustomNodes/hooks/use-update-all-nodes.ts`

**Purpose:** Bulk-update path retains `cloneDeep` pending dedicated refactor. Mark with a comment so future readers (and grep-based tooling) know it was reviewed and intentionally left.

- [ ] **Step 1: Read the file**

Find the line:

```ts
const newNodes = cloneDeep(oldNodes);
```

(currently around line 24).

- [ ] **Step 2: Add the TODO comment immediately above**

```ts
// TODO(perf): bulk path retains cloneDeep pending a dedicated refactor —
// rewriting to structural sharing is non-trivial because the function then
// mutates `newNodes[i].data.node.template[...]` in-place. See
// docs/superpowers/specs/2026-04-25-parameter-render-leaf-memoization-design.md
// (Section 2 — "use-update-all-nodes.ts — DEFER WITH TODO").
const newNodes = cloneDeep(oldNodes);
```

- [ ] **Step 3: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 errors.

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add src/frontend/src/CustomNodes/hooks/use-update-all-nodes.ts
git commit -m "docs(perf): mark useUpdateAllNodes cloneDeep as deferred refactor"
```

---

## Task 9: `useMemo` lifts in `parameterRenderComponent/index.tsx`

**Files:**
- Modify: `src/frontend/src/components/core/parameterRenderComponent/index.tsx`

**Purpose:** Several leaves (`MultiselectComponent`, `TableNodeComponent`, `TabComponent`, `ModelInputComponent`, `SortableListComponent`) currently receive array-from-template props built from inline literals. After Task 4 lands, `templateData` itself is stable across keystrokes — so these literals can be hoisted into `useMemo`s keyed on `templateData`, giving leaves stable prop refs.

The current file is a single function `ParameterRenderComponent` that builds `baseInputProps` and dispatches via a switch. Add the `useMemo`s before the `renderComponent()` definition, then reference them from inside the switch cases.

- [ ] **Step 1: Add `useMemo` lifts at the top of the function body**

Open `src/frontend/src/components/core/parameterRenderComponent/index.tsx`. After the existing `id` const declaration (around line 68–73) and before `const renderComponent = ...`, add:

```tsx
  const multiselectOptions = useMemo<string[]>(
    () =>
      ((Array.isArray(templateData.options)
        ? templateData.options
        : [templateData.options]) as string[]) || [],
    [templateData.options],
  );

  const tableNodeColumns = useMemo(
    () =>
      Array.isArray(templateData?.table_schema)
        ? templateData.table_schema
        : templateData?.table_schema?.columns,
    [templateData?.table_schema],
  );

  const tabOptions = useMemo<string[]>(
    () => (templateData?.options as string[] | undefined) || [],
    [templateData?.options],
  );

  const modelOptions = useMemo(
    () =>
      (templateData?.options as ComponentProps<
        typeof ModelInputComponent
      >["options"]) || [],
    [templateData?.options],
  );

  const sortableOptions = useMemo(
    () => templateData?.options,
    [templateData?.options],
  );
```

- [ ] **Step 2: Add the `useMemo` import**

Change the existing top-of-file import:

```ts
import type { ComponentProps } from "react";
```

to:

```ts
import type { ComponentProps } from "react";
import { useMemo } from "react";
```

- [ ] **Step 3: Replace the inline literals in the switch with the lifted refs**

In the switch body, find each call site and substitute:

`MultiselectComponent` (around lines 109–120):
```tsx
options={multiselectOptions}
```

`TableNodeComponent` `columns` prop (around lines 237–241):
```tsx
columns={tableNodeColumns}
```

`TabComponent` `options` prop (around line 315):
```tsx
options={tabOptions}
```

`ModelInputComponent` `options` prop (around lines 352–355):
```tsx
options={modelOptions}
```

`SortableListComponent` `options` prop (around line 281):
```tsx
options={sortableOptions}
```

The existing inline literals (the `Array.isArray(...) ? ... : ...` ternaries and `(... as ...) || []` casts) move into the `useMemo` factories — leaving the JSX cleaner and prop refs stable.

- [ ] **Step 4: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 errors.

- [ ] **Step 5: Commit (PAUSE)**

```bash
git add src/frontend/src/components/core/parameterRenderComponent/index.tsx
git commit -m "perf(react): lift array-literal leaf props into useMemo"
```

---

## Task 10: Shared memo equality comparator

**Files:**
- Create: `src/frontend/src/components/core/parameterRenderComponent/areInputPropsEqual.ts`
- Create: `src/frontend/src/components/core/parameterRenderComponent/__tests__/areInputPropsEqual.test.ts`

**Why this exists.** Even after Task 4's `cloneDeep` removal, two props passed into `ParameterRenderComponent` leaves are still per-keystroke unstable:

1. **`handleOnNewValue`** — `useCallback` in `useHandleOnNewValue` declares `node` in its deps. Every keystroke produces a new `node` ref, so the callback is re-issued. Skipping the dep would require a ref-pattern refactor of `useHandleOnNewValue` (and likely `usePostTemplateValue` too), which is out of scope.
2. **`nodeClass`** — `data.node` itself is a new object every keystroke. Structural sharing makes the inner `template[other_field]` refs stable, but the outer `node` reference must be new because we changed `template`. Cannot be fixed at the producer.

Neither instability reflects an observable behavior difference for a leaf:
- `handleOnNewValue` is a closure with semantically equivalent behavior across renders. Leaves call it on user events; identity has no effect.
- `nodeClass` is read by leaves only for keystroke-invariant fields (`!!nodeClass.flow`, `display_name`, `icon`, `template` for ToolsComponent). When a sibling field's value changes, none of those reads produce different output for the leaf.

The right fix is therefore a custom equality comparator that defaults to shallow-eq but skips these two keys. Used as the second arg to `memo()` for every leaf in Tasks 11–13.

- [ ] **Step 1: Write the failing comparator tests**

Create `src/frontend/src/components/core/parameterRenderComponent/__tests__/areInputPropsEqual.test.ts`:

```ts
import { areInputPropsEqual } from "../areInputPropsEqual";

describe("areInputPropsEqual", () => {
  it("returns true for the same object reference", () => {
    const props = { id: "a", value: 1 };
    expect(areInputPropsEqual(props, props)).toBe(true);
  });

  it("returns true when all compared props are Object.is-equal", () => {
    const a = { id: "a", value: 1, disabled: false };
    const b = { id: "a", value: 1, disabled: false };
    expect(areInputPropsEqual(a, b)).toBe(true);
  });

  it("returns false when a non-skipped prop differs", () => {
    const a = { id: "a", value: 1 };
    const b = { id: "a", value: 2 };
    expect(areInputPropsEqual(a, b)).toBe(false);
  });

  it("ignores handleOnNewValue identity (treats different refs as equal)", () => {
    const a = { id: "a", value: 1, handleOnNewValue: () => undefined };
    const b = { id: "a", value: 1, handleOnNewValue: () => undefined };
    expect(areInputPropsEqual(a, b)).toBe(true);
  });

  it("ignores nodeClass identity (treats different refs as equal)", () => {
    const a = { id: "a", value: 1, nodeClass: { template: {} } as any };
    const b = { id: "a", value: 1, nodeClass: { template: {} } as any };
    expect(areInputPropsEqual(a, b)).toBe(true);
  });

  it("returns false when prev has more keys than next", () => {
    const a = { id: "a", value: 1, extra: true };
    const b = { id: "a", value: 1 };
    expect(areInputPropsEqual(a, b)).toBe(false);
  });

  it("returns false when next has more keys than prev", () => {
    const a = { id: "a", value: 1 };
    const b = { id: "a", value: 1, extra: true };
    expect(areInputPropsEqual(a, b)).toBe(false);
  });

  it("uses Object.is semantics (NaN equals NaN, +0 ≠ -0)", () => {
    expect(areInputPropsEqual({ x: NaN }, { x: NaN })).toBe(true);
    expect(areInputPropsEqual({ x: +0 }, { x: -0 })).toBe(false);
  });
});
```

Run:

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx jest src/components/core/parameterRenderComponent/__tests__/areInputPropsEqual.test.ts 2>&1 | tail -10
```

Expected: failure with `Cannot find module '../areInputPropsEqual'`.

- [ ] **Step 2: Implement the comparator**

Create `src/frontend/src/components/core/parameterRenderComponent/areInputPropsEqual.ts`:

```ts
/**
 * Default-shallow-equal comparator for `memo()` of ParameterRenderComponent
 * leaves, with two keys deliberately ignored:
 *
 *   - `handleOnNewValue`: closure whose ref instability does not reflect any
 *     observable behavior change. Re-issued every render because
 *     `useHandleOnNewValue`'s `useCallback` deps include `node`. Stabilizing
 *     it at the hook level would require a ref-pattern refactor that is out
 *     of scope for the current change.
 *   - `nodeClass`: the top-level node reference is necessarily new every
 *     keystroke because structural sharing produces a new outer object.
 *     Leaves read only keystroke-invariant fields off it (`flow`,
 *     `display_name`, `icon`, `template`), so identity-skip is safe.
 *
 * Every other prop is compared via `Object.is`. Keep the skip list tight —
 * if a future leaf needs a true ref check on either skipped key, it should
 * pass its own equality function rather than expand this list.
 */
const SKIP_KEYS = new Set(["handleOnNewValue", "nodeClass"]);

export function areInputPropsEqual<P extends Record<string, unknown>>(
  prev: Readonly<P>,
  next: Readonly<P>,
): boolean {
  if (prev === next) return true;
  const prevKeys = Object.keys(prev);
  const nextKeys = Object.keys(next);
  if (prevKeys.length !== nextKeys.length) return false;
  for (const key of nextKeys) {
    if (SKIP_KEYS.has(key)) continue;
    if (!Object.is(prev[key], next[key])) return false;
  }
  return true;
}
```

Run:

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx jest src/components/core/parameterRenderComponent/__tests__/areInputPropsEqual.test.ts 2>&1 | tail -10
```

Expected: 8 tests pass.

- [ ] **Step 3: Typecheck**

```bash
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add \
  src/frontend/src/components/core/parameterRenderComponent/areInputPropsEqual.ts \
  src/frontend/src/components/core/parameterRenderComponent/__tests__/areInputPropsEqual.test.ts
git commit -m "feat(perf): areInputPropsEqual — shared memo() comparator for parameterRender leaves"
```

---

## Task 11: `memo()` wrappers — leaves batch 1 (simple primitives)

**Files:**
- Modify (one line each):
  - `src/frontend/src/components/core/parameterRenderComponent/components/floatComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/intComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/toggleShadComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/strRenderComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/inputComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/inputGlobalComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/linkComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/sliderComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/emptyParameterComponent/index.tsx`
  - `src/frontend/src/components/core/parameterRenderComponent/components/textAreaComponent/index.tsx`

**Purpose:** Wrap the simplest leaves first. These take only primitive props (after Task 9's lifts) and are the most straightforward to memoize.

For each file, the change pattern is uniform: import `memo` from `react`, import `areInputPropsEqual` from `parameterRenderComponent/areInputPropsEqual`, then wrap the default-export expression with `memo(Component, areInputPropsEqual)`. The exact form depends on the existing export:

**Pattern A — file ends with `export default ComponentName;`:**

Change:
```ts
export default ComponentName;
```
to:
```ts
export default memo(ComponentName, areInputPropsEqual);
```

**Pattern B — file ends with `export default function ComponentName(...) { ... }`:**

Change:
```ts
export default function ComponentName(...) { ... }
```
to:
```ts
function ComponentName(...) { ... }
export default memo(ComponentName, areInputPropsEqual);
```

**Pattern C — named export only (e.g., `StrRenderComponent`):**

Change:
```ts
export function StrRenderComponent(...) { ... }
```
to:
```ts
function StrRenderComponentInner(...) { ... }
export const StrRenderComponent = memo(StrRenderComponentInner, areInputPropsEqual);
```

(Note: rename internal — DON'T rename the exported symbol; consumers import `StrRenderComponent` and that name must remain.)

In all patterns, ensure the imports include both:

```ts
import { memo } from "react";
// or extend an existing react import:
// import { useState, memo } from "react";

import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
```

If the leaf file lives at `src/frontend/src/components/core/parameterRenderComponent/components/<name>/index.tsx`, the relative import `from "../../areInputPropsEqual"` works equivalently — pick whichever matches the file's existing import style.

- [ ] **Step 1: Open each file in batch 1, identify its export pattern, apply the matching transform**

Repeat for: floatComponent, intComponent, toggleShadComponent, strRenderComponent, inputComponent, inputGlobalComponent, linkComponent, sliderComponent, emptyParameterComponent, textAreaComponent.

For each file, after editing, briefly check that the component's display name is preserved — `memo()` accepts a display name arg if needed:

```ts
const FloatComponent = memo(FloatComponentInner);
FloatComponent.displayName = "FloatComponent";
```

This is only required if React DevTools shows the wrong name during the render-count canary in Task 14; otherwise skip.

- [ ] **Step 2: Run typecheck after the batch**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
```

Expected: 0 errors. If errors come from a renamed inner function colliding with consumers, fix the rename in that file.

- [ ] **Step 3: Run tests**

```bash
npx jest 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 4: Commit (PAUSE)**

Stage explicit paths:

```bash
git add \
  src/frontend/src/components/core/parameterRenderComponent/components/floatComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/intComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/toggleShadComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/strRenderComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/inputComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/inputGlobalComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/linkComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/sliderComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/emptyParameterComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/textAreaComponent/index.tsx
git commit -m "perf(react): memo() wrap simple parameterRender leaves (batch 1)"
```

---

## Task 12: `memo()` wrappers — leaves batch 2 (lifted-array consumers)

**Files:** Modify one line each:
- `src/frontend/src/components/core/parameterRenderComponent/components/multiselectComponent/index.tsx`
- `src/frontend/src/components/core/parameterRenderComponent/components/tableComponent/index.tsx`
- `src/frontend/src/components/core/parameterRenderComponent/components/TableNodeComponent/index.tsx`
- `src/frontend/src/components/core/parameterRenderComponent/components/tabComponent/index.tsx`
- `src/frontend/src/components/core/parameterRenderComponent/components/modelInputComponent/index.tsx`
- `src/frontend/src/components/core/parameterRenderComponent/components/dropdownComponent/index.tsx`

**Purpose:** Leaves that consume the array props lifted in Task 9 (or are array-heavy by nature — `dropdownComponent`, `tableComponent`). These can now memo correctly because the lifted props have stable refs.

- [ ] **Step 1: Apply the same transform pattern (A/B/C) from Task 11 to each file**

Verify each leaf's export style and apply the matching `memo()` wrap.

- [ ] **Step 2: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

Expected: 0 errors, all tests pass.

- [ ] **Step 3: Commit (PAUSE)**

```bash
git add \
  src/frontend/src/components/core/parameterRenderComponent/components/multiselectComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/tableComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/TableNodeComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/tabComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/modelInputComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/dropdownComponent/index.tsx
git commit -m "perf(react): memo() wrap lifted-array parameterRender leaves (batch 2)"
```

---

## Task 13: `memo()` wrappers — leaves batch 3 (complex / remainder)

**Files:** Modify one line each (full remainder of `parameterRenderComponent/components/**`, excluding `connectionComponent` and `sortableListComponent` which are already memo'd):
- `accordionPromptComponent/index.tsx`
- `codeAreaComponent/index.tsx`
- `copyFieldAreaComponent/index.tsx`
- `dictComponent/index.tsx`
- `helperTextComponent/index.tsx`
- `inputFileComponent/index.tsx`
- `inputListComponent/index.tsx`
- `keypairListComponent/index.tsx`
- `mappingComponent/index.tsx`
- `mcpComponent/index.tsx`
- `mustachePromptComponent/index.tsx`
- `promptComponent/index.tsx`
- `queryComponent/index.tsx`
- `searchBarComponent/index.tsx`
- `textFileSecretComponent/index.tsx`
- `ToolsComponent/index.tsx`
- `webhookFieldComponent/index.tsx`

(All paths under `src/frontend/src/components/core/parameterRenderComponent/components/`.)

- [ ] **Step 1: Apply the A/B/C transform pattern to each file**

For each: identify export style, ensure `memo` is imported from react, wrap the default export.

- [ ] **Step 2: Run typecheck + tests**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -10
npx jest 2>&1 | tail -10
```

- [ ] **Step 3: Run the build (catches Vite/JSX issues that tsc misses)**

```bash
npm run build 2>&1 | tail -10
```

Expected: build succeeds in under 5s.

- [ ] **Step 4: Commit (PAUSE)**

Stage all 17 files explicitly, e.g.:

```bash
git add \
  src/frontend/src/components/core/parameterRenderComponent/components/accordionPromptComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/codeAreaComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/copyFieldAreaComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/dictComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/helperTextComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/inputFileComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/inputListComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/keypairListComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/mappingComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/mcpComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/mustachePromptComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/promptComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/queryComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/searchBarComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/textFileSecretComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/ToolsComponent/index.tsx \
  src/frontend/src/components/core/parameterRenderComponent/components/webhookFieldComponent/index.tsx
git commit -m "perf(react): memo() wrap remaining parameterRender leaves (batch 3)"
```

---

## Task 14: Render-counter helper + canary render-count test

**Files:**
- Create: `src/frontend/src/__test_helpers__/render-counter.tsx`
- Create: `src/frontend/src/CustomNodes/GenericNode/components/parameterRenderComponent/__tests__/sibling-render-isolation.test.tsx`

**Purpose:** Establish the render-count test pattern; pin one canary that asserts a sibling field's leaf does not re-render when an unrelated field's value changes. The canary mocks the minimum surface to exercise `useHandleOnNewValue` end-to-end without booting Zustand / react-flow.

- [ ] **Step 1: Create the render-counter helper**

```tsx
// src/frontend/src/__test_helpers__/render-counter.tsx
import type { ComponentType } from "react";

/**
 * Wrap a component to count its render invocations during a test. Increments
 * `counts[label]` on every render of the wrapped component.
 *
 * Use for perf-invariant tests — e.g., asserting that typing into one field
 * does not re-render a sibling field's leaf component.
 */
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

- [ ] **Step 2: Create the canary test**

The test sets up a minimal harness:
- A wrapper component that owns `node` state via `useState`.
- A mock `setNode` that updates the `useState` store.
- Mocks for `useFlowStore`, `useFlowsManagerStore`, `useAlertStore`, `usePostTemplateValue`, `useUpdateNodeInternals`.
- Two `<NodeInputField>`-like wrappers: one for a `str` field (typed-into target), one for a `float` field (counter-wrapped).

```tsx
// src/frontend/src/CustomNodes/GenericNode/components/parameterRenderComponent/__tests__/sibling-render-isolation.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { withRenderCount } from "@/__test_helpers__/render-counter";
import { ParameterRenderComponent } from "@/components/core/parameterRenderComponent";
import FloatComponent from "@/components/core/parameterRenderComponent/components/floatComponent";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import type { APIClassType } from "@/types/api";

// Mock the stores that useHandleOnNewValue reaches into.
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({
      setNode: () => undefined, // overridden by harness via setNodeExternal
    }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ takeSnapshot: () => undefined }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: any) => any) =>
    selector({ setErrorData: () => undefined }),
}));
jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => undefined,
}));
jest.mock(
  "@/controllers/API/queries/nodes/use-post-template-value",
  () => ({
    usePostTemplateValue: () => ({ mutate: () => undefined }),
  }),
);

const buildNode = (): APIClassType =>
  ({
    template: {
      query: { type: "str", value: "hello", show: true } as any,
      count: { type: "float", value: 0.5, show: true } as any,
    },
    display_name: "Test",
  }) as unknown as APIClassType;

function Harness({
  counts,
  CountedFloat,
}: {
  counts: Record<string, number>;
  CountedFloat: typeof FloatComponent;
}) {
  const [node, setNode] = useState<APIClassType>(buildNode());

  // Custom setNode that matches the (id, updater, ...) signature
  const setNodeFn = (
    _id: string,
    update: (n: any) => any,
    _skip?: boolean,
    cb?: () => void,
  ) => {
    setNode((prev) =>
      typeof update === "function"
        ? update({ id: "node-1", data: { node: prev } }).data.node
        : prev,
    );
    cb?.();
  };

  const { handleOnNewValue: queryOnNewValue } = useHandleOnNewValue({
    node,
    nodeId: "node-1",
    name: "query",
    setNode: setNodeFn as any,
  });
  const { handleOnNewValue: countOnNewValue } = useHandleOnNewValue({
    node,
    nodeId: "node-1",
    name: "count",
    setNode: setNodeFn as any,
  });

  return (
    <div>
      <input
        data-testid="query-input"
        value={(node.template.query.value as string) ?? ""}
        onChange={(e) => queryOnNewValue({ value: e.target.value })}
      />
      <CountedFloat
        id="float_test"
        value={node.template.count.value as number}
        editNode={false}
        handleOnNewValue={countOnNewValue}
        disabled={false}
        nodeClass={node}
        handleNodeClass={() => undefined}
        nodeId="node-1"
      />
    </div>
  );
}

describe("ParameterRenderComponent — sibling render isolation", () => {
  it("does not re-render a sibling Float leaf when a sibling Str field is typed into", async () => {
    const counts: Record<string, number> = {};
    const CountedFloat = withRenderCount(FloatComponent, "FloatComponent", counts);
    render(<Harness counts={counts} CountedFloat={CountedFloat} />);

    const initial = counts["FloatComponent"];
    expect(initial).toBeGreaterThanOrEqual(1);

    const input = screen.getByTestId("query-input");
    await userEvent.type(input, "abc");

    // After 3 keystrokes into the *query* field, the FloatComponent should
    // not have re-rendered beyond its initial mount (allow <= 1 extra for
    // React batching variability, but no more).
    expect(counts["FloatComponent"] - initial).toBeLessThanOrEqual(1);
  });
});
```

- [ ] **Step 3: Run only the canary test, verify it passes**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx jest src/CustomNodes/GenericNode/components/parameterRenderComponent/__tests__/sibling-render-isolation.test.tsx 2>&1 | tail -20
```

Expected: 1 test passes.

If it fails ("FloatComponent rendered 4 times after initial"): a memo wrapper was missed in Tasks 10–12, or a prop is still unstable. Investigate by adding intermediate `withRenderCount` wrappers around `ParameterRenderComponent` itself and the `Harness` to localize. Do not paper over with looser thresholds.

- [ ] **Step 4: Run the full suite**

```bash
npx jest 2>&1 | tail -10
```

Expected: full suite green; the canary plus prior tests now total ≥ 200 tests passing.

- [ ] **Step 5: Commit (PAUSE)**

```bash
git add \
  src/frontend/src/__test_helpers__/render-counter.tsx \
  src/frontend/src/CustomNodes/GenericNode/components/parameterRenderComponent/__tests__/sibling-render-isolation.test.tsx
git commit -m "test(perf): render-count canary for sibling-leaf isolation"
```

---

## Task 15: Profiler reproduction fixture

**Files:**
- Create: `src/frontend/__perf_fixtures__/large-flow.json`

**Purpose:** A representative flow checked into the repo so anyone can reproduce the Profiler measurement. ~20 nodes, mix of leaf types — Float, Int, String, Toggle, Dropdown, Code, Prompt.

- [ ] **Step 1: Build the fixture by exporting a flow from the running app**

Easiest path: open the running app (`npm run start`), build a flow with ~20 nodes covering the leaf types in the spec, then export the flow JSON via the existing UI export button. Save the result to `src/frontend/__perf_fixtures__/large-flow.json`.

If building manually is too slow, copy an existing complex flow JSON (e.g., the agentic example) and trim to ~20 nodes.

The exact contents are not asserted by tests — this fixture is for the manual Profiler reproduction step in the spec (Section 4.A).

- [ ] **Step 2: Verify it loads in the app**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npm run start
```

In the browser, import `__perf_fixtures__/large-flow.json` and confirm the canvas renders without errors.

- [ ] **Step 3: Capture before/after Profiler numbers**

Per the spec (Section 4.A):
1. Stash all the perf changes locally (`git stash`) — this gives you the "before" baseline.
2. Open React DevTools → Profiler → Record. Type 5 characters into one StrRender field on a node with 6+ visible parameters. Stop. Capture: total commits, total render duration, top-N components.
3. `git stash pop` to restore the changes.
4. Repeat the recording.
5. Save both captures (screenshots / numeric summary) to `docs/superpowers/plans/notes/profiler-2026-04-25.md`.

- [ ] **Step 4: Commit (PAUSE)**

```bash
git add src/frontend/__perf_fixtures__/large-flow.json docs/superpowers/plans/notes/profiler-2026-04-25.md
git commit -m "test(perf): Profiler reproduction fixture + before/after capture"
```

---

## Task 16: Final verification + manual smoke pass

**Files:** None modified.

**Purpose:** Confirm everything still works end-to-end before declaring the work complete.

- [ ] **Step 1: Full typecheck**

```bash
cd .worktrees/perf-parameter-render-memo/src/frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 2: Full test suite**

```bash
npx jest 2>&1 | tail -10
```

Expected: ≥ 200 tests pass (199 prior + ≥1 canary + 9 helper unit tests).

- [ ] **Step 3: Production build**

```bash
npm run build 2>&1 | tail -10
```

Expected: build succeeds in under 5s.

- [ ] **Step 4: Lint**

```bash
npm run lint 2>&1 | tail -10
```

Expected: 0 errors. Fix any new warnings introduced by the diffs.

- [ ] **Step 5: Manual smoke pass (each leaf type)**

```bash
npm run start
```

In a browser, open a flow with one of each leaf type. For each, perform the most representative interaction and confirm correct behavior + no console errors:

- **StrRenderComponent / InputComponent** — type into an input field. Value updates as you type.
- **FloatComponent / IntComponent** — type a number. Value updates; range validation works if configured.
- **ToggleShadComponent** — flip a boolean toggle. State updates.
- **CodeAreaComponent** — open the code editor, edit, save. Code persists.
- **PromptAreaComponent / MustachePromptAreaComponent** — open prompt editor, edit, save.
- **TableNodeComponent** — open table editor, add a row, save.
- **TabComponent** — switch between tabs. Active state updates.
- **MultiselectComponent** — open dropdown, select multiple. Values appear as chips.
- **SliderComponent** — drag the slider. Value updates.
- **CodeAreaComponent + refresh button** — trigger a real_time_refresh field; confirm the post-template API call still fires.
- **Output selector** — click the output dropdown on a multi-output node, pick a different output. Selection persists; downstream re-renders correctly.
- **Refresh button (any node with one)** — click. New nodeClass arrives via `useHandleNodeClass`; node updates.

If anything misbehaves, the most likely cause is a leaf with stale-closure bugs that today are masked by the constant re-render loop. The fix is per-leaf, captured as an in-line code change with a one-line comment explaining why.

- [ ] **Step 6: Final commit (PAUSE)**

If any fixes were applied during the smoke pass, stage and commit each individually with descriptive messages. If no fixes were needed:

Ask the user: "All tasks complete and verified. Ready to consolidate / squash / push to a branch, or keep as-is?"

---

## Deferred / out-of-scope (recap from spec)

- `use-update-all-nodes.ts` refactor (TODO in code, Task 8).
- Per-leaf custom equality functions (only added if a canary test forces it — none currently).
- Profile-driven leaf tuning beyond the canary test.
- Memoization of `GenericNode` itself beyond `89b82b6138`.
