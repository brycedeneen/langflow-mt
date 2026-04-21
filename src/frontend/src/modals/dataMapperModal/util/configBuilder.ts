import {
  DestFieldDef,
  InputDef,
  JoinKey,
  MapperConfig,
  MappingEntry,
  SourceRef,
  TransformType,
} from "@/modals/dataMapperModal/types";

// Cheap deep clone that works for JSON-safe structures (our whole surface is).
function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

function defaultConfigForTransform(t: TransformType): Record<string, unknown> {
  switch (t) {
    case "template": return { template: "" };
    case "expression": return { expression: "" };
    case "static": return { value: "" };
    case "variable": return { variable: "" };
    case "array": return { skip_missing: false };
    case "direct": default: return {};
  }
}

export function addDestinationField(cfg: MapperConfig, field: DestFieldDef): MapperConfig {
  const next = clone(cfg);
  next.destination_schema.push(field);
  next.mappings.push({
    destination: field.name,
    transform: "direct",
    sources: [],
    config: {},
  });
  return next;
}

export function removeDestinationField(cfg: MapperConfig, name: string): MapperConfig {
  const next = clone(cfg);
  next.destination_schema = next.destination_schema.filter((d: DestFieldDef) => d.name !== name);
  next.mappings = next.mappings.filter((m: MappingEntry) => m.destination !== name);
  return next;
}

export function setTransformForDestination(cfg: MapperConfig, name: string, t: TransformType): MapperConfig {
  const next = clone(cfg);
  const m = next.mappings.find((mm: MappingEntry) => mm.destination === name);
  if (!m) return next;
  m.transform = t;
  m.config = defaultConfigForTransform(t);
  // `static` and `variable` don't use sources; others keep existing.
  if (t === "static" || t === "variable") m.sources = [];
  return next;
}

export function setSourcesForDestination(cfg: MapperConfig, name: string, sources: SourceRef[]): MapperConfig {
  const next = clone(cfg);
  const m = next.mappings.find((mm: MappingEntry) => mm.destination === name);
  if (m) m.sources = sources;
  return next;
}

export function addInput(cfg: MapperConfig, inp: InputDef): MapperConfig {
  const next = clone(cfg);
  next.inputs.push(inp);
  return next;
}

export function setDriverIndex(cfg: MapperConfig, idx: number): MapperConfig {
  if (idx < 0 || idx >= cfg.inputs.length) {
    throw new Error(`driver_index ${idx} out of range for ${cfg.inputs.length} inputs`);
  }
  const next = clone(cfg);
  next.driver_index = idx;
  return next;
}

function mutateJoin(cfg: MapperConfig, alias: string, fn: (keys: JoinKey[]) => JoinKey[]): MapperConfig {
  const next = clone(cfg);
  const inp = next.inputs.find((i: InputDef) => i.alias === alias);
  if (!inp || !inp.join) return next;
  inp.join.on = fn(inp.join.on);
  return next;
}

export function addJoinKey(cfg: MapperConfig, alias: string, key: JoinKey): MapperConfig {
  return mutateJoin(cfg, alias, (keys) => [...keys, key]);
}

export function setJoinKey(cfg: MapperConfig, alias: string, idx: number, key: JoinKey): MapperConfig {
  return mutateJoin(cfg, alias, (keys) => keys.map((k, i) => (i === idx ? key : k)));
}

export function removeJoinKey(cfg: MapperConfig, alias: string, idx: number): MapperConfig {
  return mutateJoin(cfg, alias, (keys) => keys.filter((_, i) => i !== idx));
}
