import { BuildStatus, EventDeliveryType } from "@/constants/enums";

jest.mock("@/utils/buildUtils", () => ({
  __esModule: true,
  buildFlowVerticesWithFallback: jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ currentFlow: { id: "flow-abc" } }),
  },
}));

jest.mock("@/stores/assistantStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(() => ({
      setSelectedTestComponent: jest.fn(),
    })),
  },
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      updateBuildStatus: jest.fn(),
      addDataToFlowPool: jest.fn(),
    }),
  },
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ addNotificationToHistory: jest.fn() }),
  },
}));

import { buildFlowVerticesWithFallback } from "@/utils/buildUtils";
import useAssistantStore from "@/stores/assistantStore";
import { runTestForAll, runTestForComponent } from "../test-runs";

describe("test-runs", () => {
  beforeEach(() => {
    (buildFlowVerticesWithFallback as jest.Mock).mockClear();
  });

  it("runTestForComponent sets selectedTestComponent and calls build with stopNodeId", async () => {
    const setSelected = jest.fn();
    (useAssistantStore.getState as jest.Mock).mockReturnValueOnce({
      setSelectedTestComponent: setSelected,
    });

    await runTestForComponent("node-42");

    expect(setSelected).toHaveBeenCalledWith("node-42");
    expect(buildFlowVerticesWithFallback).toHaveBeenCalledTimes(1);
    const args = (buildFlowVerticesWithFallback as jest.Mock).mock.calls[0][0];
    expect(args.flowId).toBe("flow-abc");
    expect(args.stopNodeId).toBe("node-42");
    expect(args.eventDelivery).toBe(EventDeliveryType.STREAMING);
    expect(typeof args.onBuildStart).toBe("function");
    expect(typeof args.onBuildUpdate).toBe("function");
    expect(typeof args.onBuildError).toBe("function");
  });

  it("runTestForAll clears selectedTestComponent and calls build with no stopNodeId", async () => {
    const setSelected = jest.fn();
    (useAssistantStore.getState as jest.Mock).mockReturnValueOnce({
      setSelectedTestComponent: setSelected,
    });

    await runTestForAll();

    expect(setSelected).toHaveBeenCalledWith(null);
    const args = (buildFlowVerticesWithFallback as jest.Mock).mock.calls[0][0];
    expect(args.stopNodeId).toBeNull();
    expect(args.flowId).toBe("flow-abc");
    expect(typeof args.onBuildStart).toBe("function");
    expect(typeof args.onBuildUpdate).toBe("function");
    expect(typeof args.onBuildError).toBe("function");
  });

  it("is a no-op when currentFlow is missing", async () => {
    // Override flowsManagerStore mock for this test only.
    const flowsManagerStore = require("@/stores/flowsManagerStore").default;
    flowsManagerStore.getState = () => ({ currentFlow: null });

    await runTestForComponent("node-42");

    expect(buildFlowVerticesWithFallback).not.toHaveBeenCalled();
  });
});
