import { fireEvent, render, screen } from "@testing-library/react";

import { ProposalBlock } from "../components/ProposalBlock";
import type { ProposalPayload } from "../types";

const makeProposal = (overrides: Partial<ProposalPayload> = {}): ProposalPayload => ({
  id: "p1",
  nodeId: "n1",
  patch: { x: 5, y: "hello" },
  rationale: "because you asked",
  applied: null,
  ...overrides,
});

describe("ProposalBlock", () => {
  it("renders each patch field", () => {
    render(
      <ProposalBlock
        proposal={makeProposal()}
        currentTemplate={{ x: { value: 0 }, y: { value: "" } }}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText(/x/)).toBeInTheDocument();
    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText(/because you asked/)).toBeInTheDocument();
  });

  it("calls onApply with the full patch when Apply is clicked", () => {
    const onApply = jest.fn();
    render(
      <ProposalBlock
        proposal={makeProposal()}
        currentTemplate={{ x: { value: 0 }, y: { value: "" } }}
        onApply={onApply}
        onDismiss={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /apply/i }));
    expect(onApply).toHaveBeenCalledWith({ x: 5, y: "hello" });
  });

  it("shows Applied state with skipped keys", () => {
    render(
      <ProposalBlock
        proposal={makeProposal({ applied: { skippedKeys: ["y"] } })}
        currentTemplate={{ x: { value: 0 } }}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText(/Applied/i)).toBeInTheDocument();
    expect(screen.getByText(/skipped/i)).toBeInTheDocument();
  });
});
