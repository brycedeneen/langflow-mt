import { describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { AssistantMessageType } from "@/stores/assistantStore";
import Message from "../message";

// Mock the API hooks transitively pulled in by PSSuggestionCardConnected so
// we don't need a real QueryClientProvider.
jest.mock("@/controllers/API/queries/pro-service-quotes/use-preview-quote", () => ({
  usePreviewQuote: () => ({ mutate: jest.fn(), isPending: false }),
}));
jest.mock("@/controllers/API/queries/pro-service-quotes/use-submit-quote", () => ({
  useSubmitQuote: () => ({ mutate: jest.fn(), isPending: false }),
}));

function renderMessage(message: AssistantMessageType, flowId = "flow-1") {
  return render(
    <TooltipProvider>
      <Message message={message} flowId={flowId} />
    </TooltipProvider>,
  );
}

describe("Message — Pro-Service Quote suggestion branch", () => {
  it("renders the PSSuggestionCard when tool_name is suggest_professional_services", () => {
    renderMessage({
      role: "tool",
      content: null,
      tool_call_id: "tc-1",
      tool_name: "suggest_professional_services",
      tool_result: { result: { shown: true, reason: "Stuck on OAuth" } },
    });
    expect(screen.getByTestId("ps-suggestion-card")).toBeInTheDocument();
    expect(screen.getByText(/Stuck on OAuth/)).toBeInTheDocument();
  });

  it("renders nothing while waiting for the tool_result event", () => {
    const { container } = renderMessage({
      role: "tool",
      content: "Calling suggest_professional_services...",
      tool_call_id: "tc-2",
      tool_name: "suggest_professional_services",
      // tool_result intentionally absent — placeholder phase
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("falls back to ToolCallCard for non-PS tool messages", () => {
    renderMessage({
      role: "tool",
      content: null,
      tool_call_id: "tc-3",
      tool_name: "list_components",
      tool_result: { result: ["A", "B"] },
    });
    // ToolCallCard branch is in play (no PS card), and its toggle button
    // is visible.
    expect(screen.queryByTestId("ps-suggestion-card")).not.toBeInTheDocument();
    expect(screen.getByRole("button")).toBeInTheDocument();
  });
});
