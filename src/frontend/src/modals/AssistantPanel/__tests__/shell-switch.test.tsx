import { render, screen } from "@testing-library/react";
import AssistantPanel from "../index";
import useAssistantStore from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";

// Mock hooks so tests don't make network/SSE calls
jest.mock("../hooks/use-assistant-conversation", () => ({
  __esModule: true,
  useAssistantConversation: () => undefined,
}));
jest.mock("../hooks/use-assistant-stream", () => ({
  __esModule: true,
  useAssistantStream: () => ({ sendMessage: jest.fn() }),
}));

// Mock child components (default exports in this codebase).
jest.mock("../components/composer", () => ({
  __esModule: true,
  default: () => <div data-testid="composer" />,
}));
jest.mock("../components/message-list", () => ({
  __esModule: true,
  default: () => <div data-testid="message-list" />,
}));
jest.mock("../components/settings-required", () => ({
  __esModule: true,
  default: () => <div data-testid="settings-required" />,
}));
jest.mock("../components/panel-header", () => ({
  __esModule: true,
  default: () => <div data-testid="panel-header" />,
}));

describe("AssistantPanel shell switch", () => {
  beforeEach(() => {
    useAssistantStore.setState({
      panelOpen: true,
      layoutMode: "panel",
      settingsConfigured: true,
      messages: [],
    });
    useFlowStore.setState({
      nodes: [],
      edges: [],
      flowBuildStatus: {},
      flowPool: {},
    } as any);
  });

  it("renders the panel shell when layoutMode is 'panel'", () => {
    useAssistantStore.setState({ layoutMode: "panel" });
    render(<AssistantPanel flowId="flow-1" />);
    expect(screen.getByTestId("message-list")).toBeInTheDocument();
    // Fullscreen-specific close button should NOT be present
    expect(screen.queryByTestId("adp-assist-close-btn")).toBeNull();
  });

  it("renders the fullscreen shell when layoutMode is 'fullscreen'", () => {
    useAssistantStore.setState({ layoutMode: "fullscreen" });
    render(<AssistantPanel flowId="flow-1" />);
    expect(screen.getByTestId("adp-assist-close-btn")).toBeInTheDocument();
    expect(screen.getByTestId("adp-assist-test-btn")).toBeInTheDocument();
  });

  it("renders the test shell when layoutMode is 'test'", () => {
    useAssistantStore.setState({ layoutMode: "test" });
    render(<AssistantPanel flowId="flow-1" />);
    expect(screen.getByTestId("adp-assist-back-to-chat-btn")).toBeInTheDocument();
    expect(screen.getByText(/No components yet/i)).toBeInTheDocument();
  });

  it("renders nothing when panelOpen is false", () => {
    useAssistantStore.setState({ panelOpen: false });
    const { container } = render(<AssistantPanel flowId="flow-1" />);
    expect(container.firstChild).toBeNull();
  });
});
