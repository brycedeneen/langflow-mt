import { describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen, fireEvent } from "@testing-library/react";
import StripPanel from "../StripPanel";
import type { BlankableFieldInfo } from "../scanBlankableFields";

const fields: BlankableFieldInfo[] = [
  {
    node_id: "n1",
    field_name: "api_key",
    component_display_name: "OpenAI",
    field_display_name: "API Key",
  },
  {
    node_id: "n1",
    field_name: "org_id",
    component_display_name: "OpenAI",
    field_display_name: "Org ID",
  },
  {
    node_id: "n2",
    field_name: "index_key",
    component_display_name: "Pinecone",
    field_display_name: "Index API Key",
  },
];

function noop() {}

describe("StripPanel", () => {
  it("renders the empty state when fields is empty", () => {
    render(
      <StripPanel
        fields={[]}
        keptKeys={new Set()}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    expect(screen.getByText(/no credential fields detected/i)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("summary reads 'What gets stripped (N)' when no fields are kept", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    const summary = screen.getByText(/what gets stripped/i);
    expect(summary).toHaveTextContent("What gets stripped (3)");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("summary reads 'What gets stripped (B of N)' when 1 ≤ K < N fields are kept", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n1:org_id"])}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    expect(screen.getByText(/what gets stripped \(2 of 3\)/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/1 credential will be saved/i);
  });

  it("summary reads only the warning when all N fields are kept (K = N)", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n1:api_key", "n1:org_id", "n2:index_key"])}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    expect(screen.queryByText(/what gets stripped/i)).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/3 credentials will be saved/i);
  });

  it("groups field rows by component_display_name, alphabetically", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    const headers = screen.getAllByRole("heading", { level: 4 });
    expect(headers.map((h) => h.textContent)).toEqual(["OpenAI", "Pinecone"]);
  });

  it("renders one checked checkbox per field by default; key in keptKeys renders unchecked", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n2:index_key"])}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    const apiKey = screen.getByRole("checkbox", { name: /^api key$/i });
    const orgId = screen.getByRole("checkbox", { name: /^org id$/i });
    const indexKey = screen.getByRole("checkbox", { name: /index api key/i });
    expect(apiKey).toBeChecked();
    expect(orgId).toBeChecked();
    expect(indexKey).not.toBeChecked();
  });

  it("clicking a checkbox calls onToggle(node_id, field_name) exactly once", () => {
    const onToggle = jest.fn();
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={onToggle}
        open={true}
        onOpenChange={noop}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: /index api key/i }));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledWith("n2", "index_key");
  });

  it("open={false} keeps the body collapsed; open={true} reveals it", () => {
    const { rerender } = render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    // Closed: no checkboxes in DOM (details hides children)
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    rerender(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("clicking the <summary> fires onOpenChange with the new state", () => {
    const onOpenChange = jest.fn();
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={false}
        onOpenChange={onOpenChange}
      />,
    );
    fireEvent.click(screen.getByText(/what gets stripped/i));
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it("warning row is also visible inside the open body when ≥1 field is kept", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n1:api_key"])}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    // Both the summary and inside-body status should be present.
    const statuses = screen.getAllByRole("status");
    expect(statuses.length).toBe(2);
    statuses.forEach((s) =>
      expect(s).toHaveTextContent(/1 credential will be saved/i),
    );
  });
});
