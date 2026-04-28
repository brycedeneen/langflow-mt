import { HandCoins } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  /** Free-form reason from the assistant (e.g. ``"Stuck on OAuth for 15 min"``). */
  reason: string;
  /**
   * Fired when the user clicks "Request Professional Services". The parent
   * decides whether to open the PreviewProposalModal directly or fan it out
   * via a shared header-button click.
   */
  onRequest: () => void;
  /** Fired when the user clicks "Dismiss". The parent removes the card from view. */
  onDismiss: () => void;
};

/**
 * Inline card the assistant chat renders when its
 * ``suggest_professional_services`` tool fires. Brand-red ADP styling so it
 * reads as adjacent-but-distinct from regular chat content.
 */
export function PSSuggestionCard({ reason, onRequest, onDismiss }: Props) {
  return (
    <div
      className="my-2 rounded-lg border border-adp-red/30 bg-adp-red/5 p-4"
      data-testid="ps-suggestion-card"
      role="region"
      aria-label="Professional Services suggestion"
    >
      <div className="flex items-start gap-3">
        <HandCoins
          className="mt-0.5 h-5 w-5 text-adp-red"
        />
        <div className="flex-1">
          <div className="font-medium">Need a hand?</div>
          <div className="mt-1 text-sm text-muted-foreground">{reason}</div>
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              onClick={onRequest}
              data-testid="ps-suggestion-request"
              ignoreTitleCase
            >
              Request Professional Services
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onDismiss}
              data-testid="ps-suggestion-dismiss"
            >
              Dismiss
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PSSuggestionCard;
