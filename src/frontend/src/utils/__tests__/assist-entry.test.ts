import useAssistantStore from "@/stores/assistantStore";
import {
  ASSIST_FULLSCREEN_STATE_KEY,
  openFlowInFullscreenAssist,
} from "../assist-entry";

describe("openFlowInFullscreenAssist", () => {
  beforeEach(() => {
    useAssistantStore.setState({ panelOpen: false, layoutMode: "panel" });
  });

  it("pre-sets the assistant store and navigates with router state", () => {
    const navigate = jest.fn();
    openFlowInFullscreenAssist("flow-123", navigate);

    expect(useAssistantStore.getState().panelOpen).toBe(true);
    expect(useAssistantStore.getState().layoutMode).toBe("fullscreen");
    expect(navigate).toHaveBeenCalledWith("/flow/flow-123", {
      state: { [ASSIST_FULLSCREEN_STATE_KEY]: true },
    });
  });

  it("includes folder segment when folderId provided", () => {
    const navigate = jest.fn();
    openFlowInFullscreenAssist("flow-123", navigate, "folder-abc");

    expect(navigate).toHaveBeenCalledWith("/flow/flow-123/folder/folder-abc", {
      state: { [ASSIST_FULLSCREEN_STATE_KEY]: true },
    });
  });
});
