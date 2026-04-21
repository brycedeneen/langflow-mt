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
