import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const runTestForAll = jest.fn().mockResolvedValue(undefined);
jest.mock("@/utils/test-runs", () => ({
  __esModule: true,
  runTestForAll: (...args: unknown[]) => runTestForAll(...args),
  runTestForComponent: jest.fn(),
}));

import { TestAllButton } from "../test-all-button";

describe("TestAllButton", () => {
  beforeEach(() => {
    runTestForAll.mockClear();
  });

  it("renders the 'Test All' label", () => {
    render(<TestAllButton anyTesting={false} />);
    expect(screen.getByRole("button", { name: /test all/i })).toBeInTheDocument();
  });

  it("calls runTestForAll when clicked", async () => {
    const user = userEvent.setup();
    render(<TestAllButton anyTesting={false} />);
    await user.click(screen.getByRole("button", { name: /test all/i }));
    expect(runTestForAll).toHaveBeenCalledTimes(1);
  });

  it("is disabled while any single test is in progress", async () => {
    const user = userEvent.setup();
    render(<TestAllButton anyTesting={true} />);
    const btn = screen.getByRole("button", { name: /test all/i });
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(runTestForAll).not.toHaveBeenCalled();
  });
});
