const mockApiGet = jest.fn();
const mockGetURL = jest.fn((key: string) => `/api/v1/${key.toLowerCase()}`);
const mockQuery = jest.fn(
  (_key: unknown, fn: () => Promise<unknown>, _options?: unknown) => {
    const result: { data: unknown; isPending: boolean; error: unknown } = {
      data: null,
      isPending: false,
      error: null,
    };

    void fn().then((data) => {
      result.data = data;
    });

    return result;
  },
);

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: mockApiGet,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (...args: unknown[]) => mockGetURL(...(args as [string])),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: mockQuery,
  })),
}));

import { useListTags } from "../use-list-tags";

describe("useListTags", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("resolves the tags URL via the TAGS constant key", async () => {
    mockApiGet.mockResolvedValue({ data: [] });

    useListTags();

    await Promise.resolve();

    // Assert the hook passes the exact constant name to getURL — this catches
    // regressions if someone renames `TAGS` in helpers/constants.ts.
    expect(mockGetURL).toHaveBeenCalledWith("TAGS");
    // And that the URL produced by getURL is the one actually requested.
    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/tags");
  });
});
