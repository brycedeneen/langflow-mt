import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import TemplateEditPanel from "../index";

// ---- Mocks -----------------------------------------------------------

const mockMutate = jest.fn();
jest.mock("@/controllers/API/queries/templates/use-update-template", () => ({
  __esModule: true,
  useUpdateTemplate: () => ({ mutate: mockMutate, isPending: false }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: jest.fn(),
      setNoticeData: jest.fn(),
    }),
}));

jest.mock(
  "@/modals/templatesModal/components/CategoryChipPicker",
  () => ({
    __esModule: true,
    default: () => <div data-testid="category-chip-picker" />,
  }),
);

jest.mock("@/modals/SaveAsTemplateModal/IconPickerField", () => ({
  __esModule: true,
  default: () => <div data-testid="icon-picker-field" />,
}));

jest.mock("@/modals/SaveAsTemplateModal/GradientPickerField", () => ({
  __esModule: true,
  default: () => <div data-testid="gradient-picker-field" />,
}));

// ---- Fixture --------------------------------------------------------

const baseTemplate = {
  id: "tpl-1",
  name: "Tpl",
  description: "desc",
  icon: "FileText",
  gradient: "0",
  archived_at: null,
  scope: "platform" as const,
  org_id: null,
  created_by: null,
  created_at: "2026-04-25",
  updated_at: "2026-04-25",
  categories: [],
  agent_summary: "old summary",
  agent_usage_notes: "old notes",
};

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>{ui}</TooltipProvider>
    </QueryClientProvider>,
  );
}

// ---- Tests ----------------------------------------------------------

describe("TemplateEditPanel agent fields", () => {
  beforeEach(() => mockMutate.mockReset());

  it("renders agent_summary + agent_usage_notes inputs", () => {
    renderWithClient(
      <TemplateEditPanel
        template={baseTemplate}
        open={true}
        onOpenChange={() => {}}
      />,
    );
    expect(screen.getByLabelText(/agent summary/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/agent usage notes/i)).toBeInTheDocument();
  });

  it("includes agent fields in the PATCH body on save", async () => {
    renderWithClient(
      <TemplateEditPanel
        template={baseTemplate}
        open={true}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/agent summary/i), {
      target: { value: "new summary" },
    });
    fireEvent.change(screen.getByLabelText(/agent usage notes/i), {
      target: { value: "new notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(mockMutate).toHaveBeenCalled());
    const [vars] = mockMutate.mock.calls[0] as [any, ...unknown[]];
    expect(vars.body.agent_summary).toBe("new summary");
    expect(vars.body.agent_usage_notes).toBe("new notes");
  });

  it("sends null when fields are cleared", async () => {
    renderWithClient(
      <TemplateEditPanel
        template={baseTemplate}
        open={true}
        onOpenChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText(/agent summary/i), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(mockMutate).toHaveBeenCalled());
    const [vars] = mockMutate.mock.calls[0] as [any, ...unknown[]];
    expect(vars.body.agent_summary).toBeNull();
  });
});
