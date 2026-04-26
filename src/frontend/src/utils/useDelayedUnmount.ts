import { useEffect, useState } from "react";

/**
 * Drop-in replacement for framer-motion's `AnimatePresence` exit-gating
 * for purely decorative opacity / translate transitions.
 *
 * Mounts the element when `visible` flips to true (with a one-frame delay so
 * the enter transition runs from "hidden" to "visible") and keeps it mounted
 * after `visible` flips to false until the consumer signals exit completion
 * via `handleExitTransitionEnd` (typically wired to `onTransitionEnd`).
 *
 * Usage:
 * ```tsx
 * const { shouldRender, isVisible, handleExitTransitionEnd } = useDelayedUnmount(condition);
 * return shouldRender ? (
 *   <div
 *     className={cn("transition-opacity duration-200", isVisible ? "opacity-100" : "opacity-0")}
 *     onTransitionEnd={handleExitTransitionEnd}
 *   >…</div>
 * ) : null;
 * ```
 */
export function useDelayedUnmount(
  visible: boolean,
  options?: { onExited?: () => void },
): {
  shouldRender: boolean;
  isVisible: boolean;
  handleExitTransitionEnd: (event: React.TransitionEvent<HTMLElement>) => void;
} {
  const [shouldRender, setShouldRender] = useState(visible);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (visible) {
      setShouldRender(true);
      // Defer the visible flip to the next frame so the element first
      // commits with the "hidden" classes, then transitions to "visible".
      const id = requestAnimationFrame(() => setIsVisible(true));
      return () => cancelAnimationFrame(id);
    }
    setIsVisible(false);
  }, [visible]);

  const handleExitTransitionEnd = (
    event: React.TransitionEvent<HTMLElement>,
  ) => {
    // Only react to the element itself, not bubbled child transitions.
    if (event.target !== event.currentTarget) return;
    if (!visible) {
      setShouldRender(false);
      options?.onExited?.();
    }
  };

  return { shouldRender, isVisible, handleExitTransitionEnd };
}
