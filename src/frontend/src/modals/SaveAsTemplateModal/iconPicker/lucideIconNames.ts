import dynamicIconImports from "lucide-react/dynamicIconImports";

// lucide ships dynamicIconImports as the authoritative kebab-case map of
// every renderable icon component. Convert to PascalCase to match the
// names used by the existing IconComponent renderer.
function toPascalCase(kebab: string): string {
  return kebab
    .split("-")
    .map((part) => (part.length > 0 ? part[0].toUpperCase() + part.slice(1) : ""))
    .join("");
}

// A handful of kebab keys collapse to the same PascalCase name (e.g.
// "arrow-down-0-1" and "arrow-down-01" both → "ArrowDown01"). Dedupe so the
// picker doesn't render duplicate cells.
export const LUCIDE_ICON_NAMES: string[] = [
  ...new Set(Object.keys(dynamicIconImports).map(toPascalCase)),
].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
