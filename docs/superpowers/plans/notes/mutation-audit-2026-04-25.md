# Node-mutation audit — 2026-04-25

Generated for the cloneDeep removal in `use-handle-new-value.ts`. Each entry is a hit from the grep at the top of Task 1, classified per the mutation-safety rule in the spec.

Grep command used:

```bash
grep -rEn '\.template\[[^\]]+\]\s*=|\.template\[[^\]]+\]\.[A-Za-z_]+\s*=|\.outputs\[[^\]]+\]\s*=|\.outputs\[[^\]]+\]\.[A-Za-z_]+\s*=' src/frontend/src/CustomNodes src/frontend/src/components/core
```

## Findings

- `src/frontend/src/CustomNodes/GenericNode/index.tsx:324` — `[ok]` — `newNode` is produced by `setNode(id, fn)` where the updater receives a draft; the surrounding block (lines 310–332) works entirely on `newNode` returned from the updater callback, which is a local clone. Both the `.outputs[outputIndex].selected` write and the `out.selected = undefined` writes at line 313 are on that local object.

- `src/frontend/src/CustomNodes/GenericNode/components/NodeDialogComponent/index.tsx:137` — `[fix-needed]` — `nodeTemplate` is assigned directly from `targetNode.data.node.template` where `targetNode` is a live node pulled from the React Flow `nodes` array (no `cloneDeep` in scope). The deep write `nodeTemplate[name].dialog_inputs.fields.data.node.template[key].value = ""` mutates the store object in place before `setNode` is called. After freeze, this will throw. Needs a `cloneDeep(targetNode)` before mutation, or a rewrite to pass the cleared value through a proper setter.

- `src/frontend/src/CustomNodes/hooks/use-update-node-code.ts:32` — `[ok]` — `newNode` is produced by `cloneDeep(oldNode)` inside the `setNode` updater (line 20). The template write on line 32 is on that private clone.

- `src/frontend/src/CustomNodes/hooks/use-update-all-nodes.ts:49` — `[ok]` — `newNodes` is produced by `cloneDeep(oldNodes)` (line 24); `updatedNode` is `newNodes[nodeIndex]`, a member of that clone array. The template write on line 49 is on a private clone.

- `src/frontend/src/CustomNodes/helpers/process-node-advanced-fields.ts:26` — `[ok]` — `newNode` is produced by `cloneDeep(resData)` on line 10. The `newNode.template[field].advanced = false` write on line 26 is on that private clone.

## Action items

- [ ] **During Task 4 verification (`npx jest` after wire-in):** watch for `TypeError: Cannot assign to read only property` errors. The most likely culprit is `NodeDialogComponent/index.tsx:137` (`handleCloseDialog`), which mutates `targetNode.data.node.template[name].dialog_inputs.fields.data.node.template[key].value = ""` directly through a live store reference. Whether it actually throws depends on whether the sub-node's template was independently frozen (our freeze is shallow — only the top-level node + template are frozen, so the deep chain may pass through unfrozen objects). If the dialog test path doesn't exercise this in jest, it will surface during Task 16 step 5 (manual smoke pass — the "dialog input" flow is not currently in the smoke checklist; add it there if the dev freeze starts firing during typical use).
- [ ] **If `NodeDialogComponent` does throw:** fix by `cloneDeep(targetNode)` before mutation, or rewrite the loop to build a new template via spread + `setNode(id, newNode)`. Out of scope to fix proactively here — the broader `NodeDialogComponent` mutation pattern is its own refactor candidate.
- [ ] No other `[fix-needed]` or `[review]` items. The remaining four hits are all safe (local clones only).
