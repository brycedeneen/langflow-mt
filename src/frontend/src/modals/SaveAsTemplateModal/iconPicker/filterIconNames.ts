/**
 * Substring-match filter with a starts-with boost.
 * Names that start with the query rank above mid-string matches.
 * Within each rank tier, results are alphabetical (case-insensitive).
 */
export function filterIconNames(names: string[], query: string): string[] {
  const q = query.trim().toLowerCase();
  if (!q) return names;

  const startsWith: string[] = [];
  const contains: string[] = [];

  for (const name of names) {
    const lower = name.toLowerCase();
    if (lower.startsWith(q)) {
      startsWith.push(name);
    } else if (lower.includes(q)) {
      contains.push(name);
    }
  }

  const cmp = (a: string, b: string) =>
    a.toLowerCase().localeCompare(b.toLowerCase());
  startsWith.sort(cmp);
  contains.sort(cmp);

  return [...startsWith, ...contains];
}
