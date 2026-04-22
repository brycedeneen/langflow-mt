import type { ProposalPayload } from "../types";

type Props = {
  proposal: ProposalPayload;
  currentTemplate: Record<string, { value?: unknown }>;
  onApply: (patch: Record<string, unknown>) => void;
  onDismiss: () => void;
};

export function ProposalBlock({ proposal, currentTemplate, onApply, onDismiss }: Props) {
  const { patch, rationale, applied } = proposal;
  const isApplied = !!applied;

  return (
    <div
      className="rounded-md border border-adp-red/50 bg-adp-red/5 p-3 text-sm"
      data-testid="proposal-block"
    >
      <div className="mb-2 font-semibold text-adp-red">⚡ Proposed change</div>

      {rationale && <div className="mb-2 text-muted-foreground italic">{rationale}</div>}

      <div className="font-mono text-xs">
        {Object.entries(patch).map(([key, value]) => {
          const current = currentTemplate[key]?.value;
          return (
            <div key={key} className="grid grid-cols-[auto_1fr_auto_1fr] gap-2 py-1">
              <span className="text-muted-foreground">{key}</span>
              <span className="line-through text-muted-foreground truncate">
                {JSON.stringify(current)}
              </span>
              <span className="text-adp-red">→</span>
              <span className="truncate">{JSON.stringify(value)}</span>
            </div>
          );
        })}
      </div>

      {isApplied ? (
        <div className="mt-2 text-xs italic text-muted-foreground">
          Applied ✓
          {applied!.skippedKeys.length > 0 && (
            <> — {applied!.skippedKeys.length} field(s) skipped ({applied!.skippedKeys.join(", ")})</>
          )}
        </div>
      ) : (
        <div className="mt-3 flex justify-end gap-2">
          <button
            onClick={onDismiss}
            className="rounded border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-muted"
          >
            Dismiss
          </button>
          <button
            onClick={() => onApply(patch)}
            className="rounded bg-adp-red px-3 py-1 text-xs font-semibold text-adp-red-foreground hover:opacity-90"
          >
            Apply ▸
          </button>
        </div>
      )}
    </div>
  );
}
