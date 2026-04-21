import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDataMapperAutoMapMutation } from "../use-data-mapper-auto-map";
import { api } from "../../../api";

jest.mock("../../../api");
const mockPost = api.post as jest.Mock;

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("useDataMapperAutoMapMutation", () => {
  beforeEach(() => mockPost.mockReset());

  it("posts to /session/DataMapperAutoMap/run with the JSON input_value", async () => {
    mockPost.mockResolvedValue({ data: { outputs: [] } });
    const { result } = renderHook(() => useDataMapperAutoMapMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({ inputPayload: { driver: { alias: "users", fields: [] }, destinations: [] } });
    });

    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body, options] = mockPost.mock.calls[0];
    expect(url).toContain("DataMapperAutoMap");
    expect(body.input_value).toBe(JSON.stringify({ driver: { alias: "users", fields: [] }, destinations: [] }));
    expect(body.stream).toBe(true);
    expect(body.input_type).toBe("chat");
    expect(body.output_type).toBe("chat");
  });

  it("forwards an AbortSignal to the axios call", async () => {
    mockPost.mockResolvedValue({ data: { outputs: [] } });
    const controller = new AbortController();
    const { result } = renderHook(() => useDataMapperAutoMapMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        inputPayload: { driver: { alias: "users", fields: [] }, destinations: [] },
        signal: controller.signal,
      });
    });

    const [,, options] = mockPost.mock.calls[0];
    expect(options.signal).toBe(controller.signal);
  });
});
