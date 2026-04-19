import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../status-badge";

describe("StatusBadge", () => {
  it("renders 'Not tested' for not_tested status", () => {
    render(<StatusBadge status="not_tested" />);
    expect(screen.getByText("Not tested")).toBeInTheDocument();
  });

  it("renders 'Testing…' for testing status", () => {
    render(<StatusBadge status="testing" />);
    expect(screen.getByText(/Testing/)).toBeInTheDocument();
  });

  it("renders 'Passed' for passed status", () => {
    render(<StatusBadge status="passed" />);
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("renders error message for failed status", () => {
    render(<StatusBadge status="failed" errorMessage="invalid_auth" />);
    expect(screen.getByText(/invalid_auth/)).toBeInTheDocument();
  });

  it("renders 'Failed' when failed status has no error message", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows only the first line of a multi-line error message", () => {
    render(<StatusBadge status="failed" errorMessage={"line one\nline two"} />);
    expect(screen.getByText("line one")).toBeInTheDocument();
    expect(screen.queryByText("line two")).not.toBeInTheDocument();
  });
});
