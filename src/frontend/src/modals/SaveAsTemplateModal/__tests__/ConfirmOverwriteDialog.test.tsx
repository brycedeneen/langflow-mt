import { describe, expect, it, jest, beforeAll, afterAll } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import ConfirmOverwriteDialog from "../ConfirmOverwriteDialog";

// Fix "now" so the relative-date assertion is stable.
// Pin the system clock to just after NOW so formatRelativeTime returns "just now".
// Coupling note: the 30-second gap is under formatRelativeTime's < 60s "just now"
// threshold. If that threshold ever drops below 30s, this test flips to "N seconds
// ago" and fails. Shrink the gap here if that threshold changes.
const NOW = new Date("2026-04-21T12:00:00Z").toISOString();
const FAKE_NOW = new Date("2026-04-21T12:00:30Z"); // 30 s after NOW → "just now"

beforeAll(() => {
  jest.useFakeTimers();
  jest.setSystemTime(FAKE_NOW);
});

afterAll(() => {
  jest.useRealTimers();
});

function setup(overrides: Partial<Parameters<typeof ConfirmOverwriteDialog>[0]> = {}) {
  const onCancel = jest.fn();
  const onConfirm = jest.fn();
  const props = {
    open: true,
    templateName: "Customer Support",
    description: "Triage support tickets",
    updatedAt: NOW,
    submitting: false,
    onCancel,
    onConfirm,
    ...overrides,
  };
  render(
    <TooltipProvider>
      <ConfirmOverwriteDialog {...props} />
    </TooltipProvider>,
  );
  return { onCancel, onConfirm };
}

describe("ConfirmOverwriteDialog", () => {
  it("renders the template name in the header", () => {
    setup();
    expect(screen.getByText(/Customer Support/)).toBeInTheDocument();
  });

  it("renders the description body text", () => {
    setup();
    expect(screen.getByText(/Triage support tickets/)).toBeInTheDocument();
  });

  it("renders italic '(no description)' when description is null", () => {
    setup({ description: null });
    expect(screen.getByText(/\(no description\)/i)).toBeInTheDocument();
  });

  it("renders italic '(no description)' when description is empty string", () => {
    setup({ description: "" });
    expect(screen.getByText(/\(no description\)/i)).toBeInTheDocument();
  });

  it("renders a relative-date line", () => {
    setup();
    // NOW is fixed, so "just now" is the expected relative string.
    expect(screen.getByText(/just now/i)).toBeInTheDocument();
  });

  it("clicking Cancel fires onCancel", () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("clicking Overwrite fires onConfirm", () => {
    const { onConfirm } = setup();
    fireEvent.click(screen.getByRole("button", { name: /^overwrite$/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("Overwrite disabled and Cancel enabled while submitting", () => {
    setup({ submitting: true });
    expect(screen.getByRole("button", { name: /^overwrite$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeEnabled();
  });

  it("Cancel button receives focus on mount (safe-default)", () => {
    setup();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toHaveFocus();
  });

  it("does not render dialog DOM when open=false", () => {
    setup({ open: false });
    expect(screen.queryByRole("button", { name: /^overwrite$/i })).not.toBeInTheDocument();
  });
});
