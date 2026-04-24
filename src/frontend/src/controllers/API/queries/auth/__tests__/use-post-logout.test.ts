// Logout functionality tests

// Mock all dependencies before imports
const mockLogout = jest.fn();
const mockResetFlowState = jest.fn();
const mockResetFlowsManagerStore = jest.fn();
const mockResetFolderStore = jest.fn();
const mockQueryClient = {
  invalidateQueries: jest.fn(),
  clear: jest.fn(),
};
const mockApiPost = jest.fn();

jest.mock("@/stores/authStore", () => {
  const mockState = {};
  const mockStore = jest.fn((selector: any) => {
    if (selector.toString().includes("logout")) return mockLogout;
    return false;
  }) as any;
  mockStore.getState = jest.fn(() => mockState);
  return mockStore;
});

jest.mock("@/stores/flowStore", () => {
  const mockStore = jest.fn() as any;
  mockStore.getState = jest.fn(() => ({ resetFlowState: mockResetFlowState }));
  return mockStore;
});

jest.mock("@/stores/flowsManagerStore", () => {
  const mockStore = jest.fn() as any;
  mockStore.getState = jest.fn(() => ({
    resetStore: mockResetFlowsManagerStore,
  }));
  return mockStore;
});

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: {
    getState: jest.fn(() => ({ resetStore: mockResetFolderStore })),
  },
}));

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: mockApiPost,
  },
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn((_key, fn, options) => ({
      mutate: async () => {
        try {
          await fn();
          if (options?.onSuccess) options.onSuccess();
        } catch (error) {
          if (options?.onError) options.onError(error);
          throw error;
        }
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key) => `/api/v1/${key.toLowerCase()}`),
}));

import { useLogout } from "../use-post-logout";

describe("logout functionality", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("logout behavior", () => {
    it("should call API logout", async () => {
      mockApiPost.mockResolvedValue({ data: { success: true } });

      const logoutMutation = useLogout();
      await logoutMutation.mutate();

      expect(mockApiPost).toHaveBeenCalledWith(
        expect.stringContaining("logout"),
      );
    });

    it("should reset all stores on successful logout", async () => {
      mockApiPost.mockResolvedValue({ data: { success: true } });

      const logoutMutation = useLogout();
      await logoutMutation.mutate();

      expect(mockLogout).toHaveBeenCalled();
      expect(mockResetFlowState).toHaveBeenCalled();
      expect(mockResetFlowsManagerStore).toHaveBeenCalled();
      expect(mockResetFolderStore).toHaveBeenCalled();
    });

    it("should clear query cache on successful logout", async () => {
      mockApiPost.mockResolvedValue({ data: { success: true } });

      const logoutMutation = useLogout();
      await logoutMutation.mutate();

      expect(mockQueryClient.clear).toHaveBeenCalled();
    });
  });

  describe("error handling", () => {
    it("should handle API errors gracefully", async () => {
      const mockError = new Error("API Error");
      mockApiPost.mockRejectedValue(mockError);

      const logoutMutation = useLogout();
      await expect(logoutMutation.mutate()).rejects.toThrow("API Error");
    });
  });
});
