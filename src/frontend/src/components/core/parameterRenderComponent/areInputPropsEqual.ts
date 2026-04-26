/**
 * Default-shallow-equal comparator for `memo()` of ParameterRenderComponent
 * leaves, with two keys deliberately ignored:
 *
 *   - `handleOnNewValue`: stabilized at the hook level — `useHandleOnNewValue`
 *     reads the live `node` from a ref, so the handler is reference-stable
 *     across renders AND always sees the latest template. Skipping this key
 *     here is now both safe and necessary (without the skip, sibling fields
 *     would over-render).
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
