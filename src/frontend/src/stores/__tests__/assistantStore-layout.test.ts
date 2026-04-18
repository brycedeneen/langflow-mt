import useAssistantStore from "@/stores/assistantStore";

describe("assistantStore layout mode", () => {
  beforeEach(() => {
    // Reset to defaults between tests
    useAssistantStore.setState({
      layoutMode: "panel",
      selectedTestComponent: null,
      panelOpen: false,
    });
  });

  it("defaults layoutMode to 'panel'", () => {
    expect(useAssistantStore.getState().layoutMode).toBe("panel");
  });

  it("defaults selectedTestComponent to null", () => {
    expect(useAssistantStore.getState().selectedTestComponent).toBeNull();
  });

  it("setLayoutMode updates the state", () => {
    useAssistantStore.getState().setLayoutMode("fullscreen");
    expect(useAssistantStore.getState().layoutMode).toBe("fullscreen");
    useAssistantStore.getState().setLayoutMode("test");
    expect(useAssistantStore.getState().layoutMode).toBe("test");
    useAssistantStore.getState().setLayoutMode("panel");
    expect(useAssistantStore.getState().layoutMode).toBe("panel");
  });

  it("setSelectedTestComponent updates the state", () => {
    useAssistantStore.getState().setSelectedTestComponent("Webhook-abc");
    expect(useAssistantStore.getState().selectedTestComponent).toBe("Webhook-abc");
    useAssistantStore.getState().setSelectedTestComponent(null);
    expect(useAssistantStore.getState().selectedTestComponent).toBeNull();
  });
});
