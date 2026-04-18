import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useGreetConversation } from "../use-greet-conversation";

// Mock axios/api
const mockPost = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => mockPost(...args) },
}));

// Mock UseRequestProcessor
jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => {
    const { useMutation } = require("@tanstack/react-query");
    return {
      mutate: (mutationKey: unknown, fn: unknown) =>
        useMutation({ mutationKey, mutationFn: fn }),
      queryClient: new QueryClient(),
    };
  }),
}));

describe("useGreetConversation", () => {
  beforeEach(() => mockPost.mockReset());

  const wrapper = ({ children }: { children: ReactNode }) => {
    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };

  it("POSTs to /api/v1/assistant/flows/{flowId}/greet", async () => {
    mockPost.mockResolvedValue({ data: { role: "assistant", content: "Hi!" } });

    const { result } = renderHook(() => useGreetConversation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("flow-123");
    });

    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe(
      "/api/v1/assistant/flows/flow-123/greet",
    );
  });

  it("surfaces the response data on success", async () => {
    mockPost.mockResolvedValue({
      data: { role: "assistant", content: "Welcome!" },
    });
    const { result } = renderHook(() => useGreetConversation(), { wrapper });
    let returned: unknown;
    await act(async () => {
      returned = await result.current.mutateAsync("flow-abc");
    });
    expect(returned).toMatchObject({ role: "assistant", content: "Welcome!" });
  });
});
