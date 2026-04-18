import type { NavigateFunction } from "react-router-dom";
import useAssistantStore from "@/stores/assistantStore";

/** Open a flow in fullscreen ADP Assist mode.
 *
 * Used by:
 *  - Template modal "Build with ADP Assist" button (new flow)
 *  - Flow list ADP Assist icon (existing flow)
 *  - (future) any "open in assistant" entry
 *
 * Sets layoutMode before navigation so the assistant opens in fullscreen
 * without a flash of panel state while the new page mounts.
 */
export function openFlowInFullscreenAssist(
  flowId: string,
  navigate: NavigateFunction,
): void {
  const store = useAssistantStore.getState();
  store.setPanelOpen(true);
  store.setLayoutMode("fullscreen");
  navigate(`/flow/${flowId}`);
}
