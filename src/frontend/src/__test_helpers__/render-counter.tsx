import type { ComponentType } from "react";

/**
 * Wrap a component to count its render invocations during a test. Increments
 * `counts[label]` on every render of the wrapped component.
 *
 * Use for perf-invariant tests — e.g., asserting that typing into one field
 * does not re-render a sibling field's leaf component.
 */
export function withRenderCount<P extends object>(
  Component: ComponentType<P>,
  label: string,
  counts: Record<string, number>,
) {
  const Wrapped = (props: P) => {
    counts[label] = (counts[label] ?? 0) + 1;
    return <Component {...props} />;
  };
  Wrapped.displayName = `RenderCounted(${label})`;
  return Wrapped;
}
