import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import TemplatesModal from "../index";

// Mocks — keep tight, only what the modal traverses.
jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => ({
    data: [],
    isPending: false,
    isError: false,
    refetch: jest.fn(),
  }),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ examples: [], setExamples: jest.fn() }),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  __esModule: true,
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  __esModule: true,
  track: jest.fn(),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: (props: { name?: string }) => <span data-testid={`icon-${props.name}`} />,
  ForwardedIconComponent: (props: { name?: string }) => (
    <span data-testid={`icon-${props.name}`} />
  ),
}));

// GetStartedComponent transitively imports PNG assets at module load, which Jest
// can't parse. Mock it out — this test doesn't traverse the get-started tab.
jest.mock("../components/GetStartedComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="get-started-stub" />,
}));

describe("TemplatesModal — Saved Templates tab", () => {
  it("shows the Saved Templates nav item and switches to it on click", () => {
    render(
      <MemoryRouter>
        <TooltipProvider>
          <TemplatesModal open={true} setOpen={jest.fn()} />
        </TooltipProvider>
      </MemoryRouter>,
    );
    const navItem = screen.getByTestId("side_nav_options_saved-templates");
    expect(navItem).toBeInTheDocument();

    fireEvent.click(navItem);
    // Empty-state copy from SavedTemplatesContent confirms the tab rendered.
    expect(screen.getByTestId("saved-templates-empty")).toBeInTheDocument();
  });
});
