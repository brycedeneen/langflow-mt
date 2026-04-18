import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

type Props = {
  selected: boolean;
  onSelect: () => void;
};

/** First-in-grid "Blank Flow" card — selectable like any other template. */
export function BlankFlowCardComponent({ selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid="blank-flow-card"
      className={cn(
        "group relative flex h-full min-h-[170px] w-full flex-col items-start justify-between rounded-lg border-2 bg-background p-4 text-left transition-colors hover:bg-muted",
        selected ? "border-primary" : "border-border",
      )}
    >
      <div
        className={cn(
          "absolute right-3 top-3 h-4 w-4 rounded-full border-2",
          selected ? "border-primary bg-primary" : "border-muted-foreground",
        )}
        aria-hidden
      />
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-muted">
        <ForwardedIconComponent name="Plus" className="h-5 w-5" />
      </div>
      <div className="flex w-full flex-col gap-1">
        <div className="text-sm font-semibold">Blank Flow</div>
        <div className="text-xs text-muted-foreground">
          Start from scratch with an empty canvas.
        </div>
      </div>
    </button>
  );
}
