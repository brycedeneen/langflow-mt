import type { NavigateFunction } from "react-router-dom";
import useAssistantStore from "@/stores/assistantStore";

/** Key on `location.state` that signals FlowPage should open the assistant
 * in fullscreen on mount. Lives in router state (not the URL) so it doesn't
 * survive a hard refresh — refreshes should reopen the canvas, not the
 * assist overlay. */
export const ASSIST_FULLSCREEN_STATE_KEY = "openInFullscreenAssist";

export type AssistEntryLocationState = {
  [ASSIST_FULLSCREEN_STATE_KEY]?: boolean;
};

/** Open a flow in fullscreen ADP Assist mode.
 *
 * Used by:
 *  - Template modal "Build with ADP Assist" button (new flow)
 *  - Flow list ADP Assist icon (existing flow)
 *  - (future) any "open in assistant" entry
 *
 * Sets layoutMode pre-emptively (so the panel doesn't briefly render in
 * "panel" mode if the assistant store happens to mount before the URL is
 * processed) AND encodes the intent in `location.state` so FlowPage can
 * re-apply it after the route unmount/remount drops the pre-set Zustand
 * state. Routing state (vs. a query param) avoids round-tripping the URL
 * through `setSearchParams`, which under react-router-dom v7 was navigating
 * us back to `/all`.
 */
export function openFlowInFullscreenAssist(
  flowId: string,
  navigate: NavigateFunction,
  folderId?: string,
): void {
  const store = useAssistantStore.getState();
  store.setPanelOpen(true);
  store.setLayoutMode("fullscreen");
  const path = `/flow/${flowId}${folderId ? `/folder/${folderId}` : ""}`;
  const state: AssistEntryLocationState = {
    [ASSIST_FULLSCREEN_STATE_KEY]: true,
  };
  navigate(path, { state });
}
