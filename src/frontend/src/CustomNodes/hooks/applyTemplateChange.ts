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
