import { render, screen } from "@testing-library/react";
import { ComponentsTab } from "../components-tab";

jest.mock("@/controllers/API/queries/metadata", () => ({
  useListComponentMetadata: () => ({
    data: [
      {
        component_name: "Webhook",
        display_name: "Webhook",
        category: "input_output",
        icon: "webhook",
        is_orphan: false,
        metadata: null,
      },
      {
        component_name: "StaleComponent",
        display_name: null,
        category: null,
        icon: null,
        is_orphan: true,
        metadata: {
          agent_summary: "Old",
          agent_usage_notes: null,
          updated_by: "user-1",
          updated_at: "2026-04-18T00:00:00Z",
        },
      },
    ],
    isLoading: false,
  }),
  useUpsertComponentMetadata: () => ({ mutate: jest.fn() }),
  useDeleteComponentMetadata: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: unknown) => unknown) =>
    selector({ setSuccessData: jest.fn(), setErrorData: jest.fn() }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("ComponentsTab", () => {
  it("renders live components without orphan badge, orphans with badge", () => {
    render(<ComponentsTab />);
    expect(screen.getByText("Webhook")).toBeInTheDocument();
    expect(screen.getByText("StaleComponent")).toBeInTheDocument();
    // Exactly one orphan badge — <span>Orphan</span> (not case-insensitive so
    // the "Remove Orphan" button label doesn't match).
    expect(screen.getAllByText("Orphan")).toHaveLength(1);
    expect(
      screen.getByRole("button", { name: /remove orphan/i }),
    ).toBeInTheDocument();
  });
});
