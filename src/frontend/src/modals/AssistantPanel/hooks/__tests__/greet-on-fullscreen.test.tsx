import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAssistantConversation } from "../use-assistant-conversation";
import useAssistantStore from "@/stores/assistantStore";

const mockGreet = jest.fn().mockResolvedValue({ role: "assistant", content: "Hi!" });
jest.mock(
  "@/controllers/API/queries/assistant/use-greet-conversation",
  () => ({
    useGreetConversation: () => ({ mutateAsync: mockGreet }),
  }),
);

const mockGetConversation = jest.fn();
jest.mock("@/controllers/API/queries/assistant/assistant-api", () => ({
  getConversation: (...args: unknown[]) => mockGetConversation(...args),
}));

const wrapper = ({ children }: { children: ReactNode }) => {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

describe("useAssistantConversation — greet-on-fullscreen", () => {
  beforeEach(() => {
    mockGreet.mockClear();
    mockGetConversation.mockReset();
    useAssistantStore.setState({
      layoutMode: "panel",
      messages: [],
      conversationId: null,
      settingsConfigured: true,
    });
  });

  it("fires greet when layoutMode is 'fullscreen' and conversation is empty", async () => {
    mockGetConversation.mockResolvedValue({
      conversation_id: "conv-1",
      messages: [],
      settings_configured: true,
    });
    useAssistantStore.setState({ layoutMode: "fullscreen" });

    renderHook(() => useAssistantConversation("flow-abc"), { wrapper });
    await waitFor(() => expect(mockGreet).toHaveBeenCalledTimes(1));
    expect(mockGreet).toHaveBeenCalledWith("flow-abc");
  });

  it("does NOT fire greet when layoutMode is 'panel'", async () => {
    mockGetConversation.mockResolvedValue({
      conversation_id: "conv-1",
      messages: [],
      settings_configured: true,
    });
    useAssistantStore.setState({ layoutMode: "panel" });

    renderHook(() => useAssistantConversation("flow-abc"), { wrapper });
    await waitFor(() => expect(mockGetConversation).toHaveBeenCalled());
    expect(mockGreet).not.toHaveBeenCalled();
  });

  it("does NOT fire greet when messages already exist", async () => {
    mockGetConversation.mockResolvedValue({
      conversation_id: "conv-1",
      messages: [{ role: "user", content: "hi" }],
      settings_configured: true,
    });
    useAssistantStore.setState({ layoutMode: "fullscreen" });

    renderHook(() => useAssistantConversation("flow-abc"), { wrapper });
    await waitFor(() => expect(mockGetConversation).toHaveBeenCalled());
    expect(mockGreet).not.toHaveBeenCalled();
  });
});
