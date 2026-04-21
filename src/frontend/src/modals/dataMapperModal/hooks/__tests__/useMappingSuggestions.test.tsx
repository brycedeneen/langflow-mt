import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMappingSuggestions } from "../useMappingSuggestions";
import * as autoMapModule from "../../../../controllers/API/queries/assistant/use-data-mapper-auto-map";
import type { MapperConfig } from "../../types";

jest.mock("../../../../controllers/API/queries/assistant/use-data-mapper-auto-map");

const config: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [{ name: "id", type: "str", required: true }] } }],
  destination_schema: [
    { name: "id", type: "str", required: true, default: null },
    { name: "email", type: "str", required: true, default: null },
  ],
  mappings: [],
};

const mockResponse = (text: string) => ({ data: { outputs: [{ outputs: [{ outputs: { message: { message: text } } }] }] } });

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("useMappingSuggestions", () => {
  const mockMutateAsync = jest.fn();
  beforeEach(() => {
    mockMutateAsync.mockReset();
    (autoMapModule.useDataMapperAutoMapMutation as jest.Mock).mockReturnValue({
      mutateAsync: mockMutateAsync,
    });
  });

  it("starts in idle state", () => {
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });
    expect(result.current.state).toBe("idle");
    expect(result.current.entries).toEqual([]);
  });

  it("transitions idle → fetching → pending on happy path", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([
      { destination: "id",    transform: "direct", sources: [{ input: "users", field: "id" }], config: {} },
      { destination: "email", transform: "direct", sources: [{ input: "users", field: "email_address" }], config: {} },
    ])));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("pending");
    expect(result.current.entries).toHaveLength(2);
  });

  it("strips markdown fences before parsing", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse("```json\n[{\"destination\":\"id\",\"transform\":\"direct\",\"sources\":[{\"input\":\"users\",\"field\":\"id\"}],\"config\":{}}]\n```"));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("pending");
    expect(result.current.entries).toHaveLength(1);
  });

  it("transitions to empty when filtered list is empty", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([])));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("empty");
  });

  it("transitions to error on unparseable output", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse("not json at all"));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("error");
    expect(result.current.error).toMatch(/parse/i);
  });

  it("transitions to error on HTTP failure", async () => {
    mockMutateAsync.mockRejectedValue(Object.assign(new Error("Request failed"), { response: { status: 404 } }));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("error");
    expect(result.current.error).toMatch(/not available|update Langflow/i);
  });

  it("cancel() reverts state to idle and aborts", async () => {
    let resolve!: (v: unknown) => void;
    mockMutateAsync.mockImplementation(() => new Promise((r) => { resolve = r; }));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    act(() => { result.current.run(); });
    await waitFor(() => expect(result.current.state).toBe("fetching"));

    act(() => { result.current.cancel(); });
    resolve(mockResponse(JSON.stringify([])));

    await waitFor(() => expect(result.current.state).toBe("idle"));
  });

  it("filters entries via never-overwrite rule (customized dest gets skipped)", async () => {
    const configWithCustom: MapperConfig = {
      ...config,
      mappings: [{ destination: "id", transform: "template", sources: [], config: { template: "x" } }],
    };
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([
      { destination: "id",    transform: "direct", sources: [{ input: "users", field: "id" }], config: {} },
      { destination: "email", transform: "direct", sources: [{ input: "users", field: "email_address" }], config: {} },
    ])));
    const { result } = renderHook(() => useMappingSuggestions({ config: configWithCustom }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.entries.map((e) => e.destination)).toEqual(["email"]);
  });

  it("handles partially-malformed arrays by dropping bad entries and keeping good ones", async () => {
    mockMutateAsync.mockResolvedValue(mockResponse(JSON.stringify([
      { destination: "id", transform: "direct", sources: [{ input: "users", field: "id" }], config: {} },
      { garbage: true },                                                 // invalid — missing required fields
      { destination: "email", transform: "direct", sources: [{ input: "users", field: "email_address" }], config: {} },
    ])));
    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    await act(async () => { await result.current.run(); });

    expect(result.current.state).toBe("pending");
    expect(result.current.entries).toHaveLength(2);
    expect(result.current.entries.map((e) => e.destination).sort()).toEqual(["email", "id"]);
  });

  it("second run() aborts the first in-flight request", async () => {
    let firstResolve!: (v: unknown) => void;
    let secondResolve!: (v: unknown) => void;
    mockMutateAsync
      .mockImplementationOnce(() => new Promise((r) => { firstResolve = r; }))
      .mockImplementationOnce(() => new Promise((r) => { secondResolve = r; }));

    const { result } = renderHook(() => useMappingSuggestions({ config }), { wrapper });

    act(() => { result.current.run(); });
    await waitFor(() => expect(result.current.state).toBe("fetching"));

    // First call's AbortController is the current ref.
    // Second run() fires while first is still pending — should abort the first.
    act(() => { result.current.run(); });
    await waitFor(() => expect(result.current.state).toBe("fetching"));

    // Now resolve the SECOND call first (simulating order-swap where the first was aborted).
    secondResolve(mockResponse(JSON.stringify([
      { destination: "id", transform: "direct", sources: [{ input: "users", field: "id" }], config: {} },
    ])));

    await waitFor(() => expect(result.current.state).toBe("pending"));
    expect(result.current.entries).toHaveLength(1);

    // Resolve the first (which was aborted by the second run) — should not change state,
    // because the hook's post-await `signal.aborted` guard bails out.
    firstResolve(mockResponse(JSON.stringify([
      { destination: "email", transform: "direct", sources: [{ input: "users", field: "email_address" }], config: {} },
    ])));

    // Give React a tick to process. State and entries should still reflect the second call.
    await new Promise((r) => setTimeout(r, 10));
    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0].destination).toBe("id");
  });
});
