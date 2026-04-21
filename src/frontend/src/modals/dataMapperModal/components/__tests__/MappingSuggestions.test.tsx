import { render, screen, fireEvent } from "@testing-library/react";
import { MappingSuggestions } from "../MappingSuggestions";

const defaults = {
  state: "idle" as const,
  error: null,
  pendingCount: 0,
  showPending: true,
  allDestinationsCustomized: false,
  onSuggest: jest.fn(),
  onCancel: jest.fn(),
  onApplyAll: jest.fn(),
  onTogglePending: jest.fn(),
  onRetry: jest.fn(),
};

describe("MappingSuggestions", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders Suggest button in idle state", () => {
    render(<MappingSuggestions {...defaults} />);
    expect(screen.getByRole("button", { name: /suggest mappings/i })).toBeInTheDocument();
  });

  it("disables Suggest button when all destinations customized", () => {
    render(<MappingSuggestions {...defaults} allDestinationsCustomized />);
    expect(screen.getByRole("button", { name: /suggest mappings/i })).toBeDisabled();
  });

  it("calls onSuggest when Suggest clicked", () => {
    render(<MappingSuggestions {...defaults} />);
    fireEvent.click(screen.getByRole("button", { name: /suggest mappings/i }));
    expect(defaults.onSuggest).toHaveBeenCalled();
  });

  it("renders spinner + Cancel in fetching state", () => {
    render(<MappingSuggestions {...defaults} state="fetching" />);
    expect(screen.getByText(/analyzing schemas/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("renders tab toggle + Apply-all in pending state", () => {
    render(<MappingSuggestions {...defaults} state="pending" pendingCount={3} />);
    expect(screen.getByRole("button", { name: /current/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /suggested \(3\)/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /apply all/i })).toBeInTheDocument();
  });

  it("calls onTogglePending when Current clicked", () => {
    render(<MappingSuggestions {...defaults} state="pending" pendingCount={3} showPending={true} />);
    fireEvent.click(screen.getByRole("button", { name: /current/i }));
    expect(defaults.onTogglePending).toHaveBeenCalledWith(false);
  });

  it("renders error chip + Retry in error state", () => {
    render(<MappingSuggestions {...defaults} state="error" error="Connection lost. Retry?" />);
    expect(screen.getByText(/connection lost/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders empty chip in empty state", () => {
    render(<MappingSuggestions {...defaults} state="empty" />);
    expect(screen.getByText(/no new suggestions/i)).toBeInTheDocument();
  });

  it("calls onApplyAll when Apply all suggestions clicked", () => {
    render(<MappingSuggestions {...defaults} state="pending" pendingCount={3} />);
    fireEvent.click(screen.getByRole("button", { name: /apply all/i }));
    expect(defaults.onApplyAll).toHaveBeenCalled();
  });

  it("calls onCancel when Cancel clicked in fetching state", () => {
    render(<MappingSuggestions {...defaults} state="fetching" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(defaults.onCancel).toHaveBeenCalled();
  });

  it("calls onRetry when Retry clicked in error state", () => {
    render(<MappingSuggestions {...defaults} state="error" error="X" />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(defaults.onRetry).toHaveBeenCalled();
  });
});
