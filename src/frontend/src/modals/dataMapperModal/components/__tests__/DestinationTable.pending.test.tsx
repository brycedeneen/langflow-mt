import { render, screen, fireEvent } from "@testing-library/react";
import { DestinationTable } from "../DestinationTable";
import type { MapperConfig, MappingEntry } from "../../types";

const config: MapperConfig = {
  driver_index: 0,
  inputs: [{ alias: "users", schema_source: "autodetect", schema: { fields: [] } }],
  destination_schema: [
    { name: "full_name", type: "str", required: true,  default: null },
    { name: "email",     type: "str", required: false, default: null },
  ],
  mappings: [],
};

const pendingEntry: MappingEntry = {
  destination: "full_name",
  transform: "template",
  sources: [{ input: "users", field: "first_name" }],
  config: { template: "{first_name} {last_name}" },
};

describe("DestinationTable — pending row rendering", () => {
  it("renders proposed values in blue state when pendingSuggestions has entry for destination", () => {
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
        onAcceptSuggestion={jest.fn()}
        onRejectSuggestion={jest.fn()}
      />,
    );
    expect(screen.getByText(/{first_name} {last_name}/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accept suggestion for full_name/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject suggestion for full_name/i })).toBeInTheDocument();
  });

  it("renders unset state when showPendingSuggestions is false", () => {
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions={false}
      />,
    );
    expect(screen.queryByText(/{first_name} {last_name}/)).not.toBeInTheDocument();
  });

  it("calls onAcceptSuggestion with destination when ✓ clicked", () => {
    const onAccept = jest.fn();
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
        onAcceptSuggestion={onAccept}
        onRejectSuggestion={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /accept suggestion for full_name/i }));
    expect(onAccept).toHaveBeenCalledWith("full_name");
  });

  it("calls onRejectSuggestion with destination when ✗ clicked", () => {
    const onReject = jest.fn();
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
        onAcceptSuggestion={jest.fn()}
        onRejectSuggestion={onReject}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /reject suggestion for full_name/i }));
    expect(onReject).toHaveBeenCalledWith("full_name");
  });

  it("does not show pending UI for destinations with no proposed entry", () => {
    render(
      <DestinationTable
        config={config}
        onConfigChange={jest.fn()}
        pendingSuggestions={[pendingEntry]}
        showPendingSuggestions
      />,
    );
    // "email" row has no proposal → no ✓/✗
    expect(screen.queryByRole("button", { name: /accept suggestion for email/i })).not.toBeInTheDocument();
  });
});
