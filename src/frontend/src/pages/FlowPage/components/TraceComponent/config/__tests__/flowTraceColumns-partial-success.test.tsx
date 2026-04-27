/**
 * Tests that the Status column cell renderer in flowTraceColumns correctly
 * renders a "Completed with errors" badge with amber styling and the expected
 * data-testid when the run status is "partial_success".
 */
import { render, screen } from "@testing-library/react";
import { createFlowTracesColumns } from "../flowTraceColumns";

// Stub IconComponent so tests don't need the full icon registry
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, ...props }: { name: string; [key: string]: unknown }) => (
    <span data-testid={`icon-${name}`} {...props} />
  ),
}));

jest.mock("@/utils/dateTime", () => ({
  formatSmartTimestamp: jest.fn(() => "mocked-timestamp"),
}));

jest.mock("@/utils/format-currency", () => ({
  formatUsdFromMicros: jest.fn(() => "$0.01"),
}));

function getStatusColDef() {
  const cols = createFlowTracesColumns();
  const statusCol = cols.find((c) => c.headerName === "Status");
  if (!statusCol) throw new Error("Status column not found");
  return statusCol;
}

describe("flowTraceColumns — Status cell renderer", () => {
  // Verifies that a run with status="partial_success" shows the amber badge
  // with the correct label text and the required data-testid attribute.
  it("renders 'Completed with errors' badge for partial_success", () => {
    const statusCol = getStatusColDef();
    const CellRenderer = statusCol.cellRenderer as (params: {
      value: string | null | undefined;
    }) => JSX.Element;

    render(<CellRenderer value="partial_success" />);

    const badge = screen.getByTestId("status-badge-partial-success");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Completed with errors");
    expect(badge).toHaveAttribute("aria-label", "Completed with errors");
  });

  // Verifies the badge uses an amber color token (not success green or error red).
  it("applies amber color class to the partial_success badge", () => {
    const statusCol = getStatusColDef();
    const CellRenderer = statusCol.cellRenderer as (params: {
      value: string | null | undefined;
    }) => JSX.Element;

    render(<CellRenderer value="partial_success" />);

    const badge = screen.getByTestId("status-badge-partial-success");
    expect(badge.className).toContain("text-amber-600");
  });

  // Verifies the AlertTriangle icon is rendered inside the badge.
  it("renders an AlertTriangle icon inside the partial_success badge", () => {
    const statusCol = getStatusColDef();
    const CellRenderer = statusCol.cellRenderer as (params: {
      value: string | null | undefined;
    }) => JSX.Element;

    render(<CellRenderer value="partial_success" />);

    expect(screen.getByTestId("icon-AlertTriangle")).toBeInTheDocument();
  });

  // Verifies that a successful run still renders the CircleCheck icon (regression guard).
  it("renders CircleCheck icon for ok status (regression guard)", () => {
    const statusCol = getStatusColDef();
    const CellRenderer = statusCol.cellRenderer as (params: {
      value: string | null | undefined;
    }) => JSX.Element;

    render(<CellRenderer value="ok" />);

    expect(screen.getByTestId("icon-CircleCheck")).toBeInTheDocument();
    expect(
      screen.queryByTestId("status-badge-partial-success"),
    ).not.toBeInTheDocument();
  });
});
