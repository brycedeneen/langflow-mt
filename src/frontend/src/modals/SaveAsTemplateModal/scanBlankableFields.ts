/**
 * Pure, non-mutating scanner. Walks a flow's nodes and identifies every
 * template field that should be blanked server-side when the flow is saved
 * as a template. The server performs the actual blanking when given
 * `source_flow_id` + this list of `{node_id, field_name}` entries — this
 * util just tells us WHICH fields qualify and attaches display metadata for
 * the "What gets stripped?" UI surface.
 *
 * Blanking rule — a field qualifies if ANY of:
 *   - _input_type ∈ {SecretStrInput, TextFileSecretInput, MultilineSecretInput}
 *   - auto_promote === true
 *   - password === true
 *   - value is a string starting with "__autosecret_"
 *
 * The scan does NOT mutate the input.
 */

import type { BlankedField } from "@/types/template";

export type BlankableFieldInfo = BlankedField & {
  component_display_name: string;
  field_display_name: string;
};

const SECRET_INPUT_TYPES = new Set([
  "SecretStrInput",
  "TextFileSecretInput",
  "MultilineSecretInput",
]);

const AUTOSECRET_PREFIX = "__autosecret_";

function fieldQualifies(field: unknown): boolean {
  if (!field || typeof field !== "object") return false;
  const f = field as Record<string, unknown>;
  if (typeof f._input_type === "string" && SECRET_INPUT_TYPES.has(f._input_type)) return true;
  if (f.auto_promote === true) return true;
  if (f.password === true) return true;
  if (typeof f.value === "string" && f.value.startsWith(AUTOSECRET_PREFIX)) return true;
  return false;
}

export function scanBlankableFields(
  flowData: { nodes: unknown[] },
): BlankableFieldInfo[] {
  const out: BlankableFieldInfo[] = [];
  const nodes = Array.isArray(flowData?.nodes) ? flowData.nodes : [];
  for (const node of nodes) {
    if (!node || typeof node !== "object") continue;
    const n = node as Record<string, any>;
    const nodeId: string | undefined = n.id;
    const nodeInner = n.data?.node;
    if (!nodeId || !nodeInner || typeof nodeInner !== "object") continue;
    const template = nodeInner.template;
    if (!template || typeof template !== "object") continue;
    for (const [fieldName, field] of Object.entries(template)) {
      if (!fieldQualifies(field)) continue;
      const f = field as Record<string, unknown>;
      out.push({
        node_id: nodeId,
        field_name: fieldName,
        component_display_name: (nodeInner.display_name as string) ?? "",
        field_display_name: (f.display_name as string) ?? fieldName,
      });
    }
  }
  return out;
}
