import { render, screen } from "@testing-library/react";
import MetadataPage from "../index";

jest.mock("../components-tab", () => ({ ComponentsTab: () => <div>components-tab</div> }));

describe("MetadataPage", () => {
  it("renders only the Components section, no Flows tab", () => {
    render(<MetadataPage />);
    expect(screen.queryByRole("tab", { name: /flows/i })).toBeNull();
    expect(screen.getByText("components-tab")).toBeInTheDocument();
  });
});
