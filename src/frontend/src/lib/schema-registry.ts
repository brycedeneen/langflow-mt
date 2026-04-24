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
