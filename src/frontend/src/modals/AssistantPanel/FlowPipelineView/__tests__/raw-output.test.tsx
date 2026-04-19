import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RawOutput } from "../raw-output";

describe("RawOutput", () => {
  it("is collapsed by default", () => {
    render(<RawOutput value={{ hello: "world" }} />);
    expect(screen.queryByText(/"hello": "world"/)).not.toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveTextContent(/View full output/i);
  });

  it("expands and shows JSON when clicked", async () => {
    const user = userEvent.setup();
    render(<RawOutput value={{ hello: "world" }} />);
    await user.click(screen.getByRole("button"));
    expect(screen.getByText(/"hello": "world"/)).toBeInTheDocument();
  });

  it("renders a string value verbatim when expanded", async () => {
    const user = userEvent.setup();
    render(<RawOutput value="plain text" />);
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("plain text")).toBeInTheDocument();
  });
});
