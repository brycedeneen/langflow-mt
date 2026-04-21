import type { MappingSuggestionsState } from "../hooks/useMappingSuggestions";

export interface MappingSuggestionsProps {
  state: MappingSuggestionsState;
  error: string | null;
  pendingCount: number;
  showPending: boolean;
  allDestinationsCustomized: boolean;
  onSuggest: () => void;
  onCancel: () => void;
  onApplyAll: () => void;
  onTogglePending: (show: boolean) => void;
  onRetry: () => void;
}

export function MappingSuggestions({
  state, error, pendingCount, showPending, allDestinationsCustomized,
  onSuggest, onCancel, onApplyAll, onTogglePending, onRetry,
}: MappingSuggestionsProps) {

  if (state === "fetching") {
    return (
      <div className="mapping-suggestions mapping-suggestions--fetching" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="spinner" aria-hidden />
        <span>Analyzing schemas…</span>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    );
  }

  if (state === "pending") {
    return (
      <div className="mapping-suggestions mapping-suggestions--pending" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <button type="button" aria-pressed={!showPending} onClick={() => onTogglePending(false)}>Current</button>
          <button type="button" aria-pressed={showPending}  onClick={() => onTogglePending(true)} style={{ marginLeft: 4 }}>
            Suggested ({pendingCount})
          </button>
        </div>
        <button type="button" onClick={onApplyAll}>Apply all suggestions</button>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="mapping-suggestions mapping-suggestions--error" role="alert" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span>{error ?? "Something went wrong."}</span>
        <button type="button" onClick={onRetry}>Retry</button>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className="mapping-suggestions mapping-suggestions--empty">
        <span>No new suggestions — the assistant couldn't find matches for the remaining destinations.</span>
      </div>
    );
  }

  // idle
  return (
    <div className="mapping-suggestions mapping-suggestions--idle">
      <button
        type="button"
        onClick={onSuggest}
        disabled={allDestinationsCustomized}
        title={allDestinationsCustomized ? "Clear a row to get suggestions" : undefined}
      >
        Suggest mappings
      </button>
    </div>
  );
}
