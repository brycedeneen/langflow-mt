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
