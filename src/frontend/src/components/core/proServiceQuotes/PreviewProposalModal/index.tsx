import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useSubmitQuote } from "@/controllers/API/queries/pro-service-quotes/use-submit-quote";
import type {
  PreviewResponse,
  QuoteRead,
  QuoteSubmitRequest,
} from "@/types/pro-service-quote";
import { formatUSD } from "@/utils/formatMoney";

type Props = {
  open: boolean;
  flowId: string;
  preview: PreviewResponse | null;
  onClose: () => void;
  onSuccess?: (quote: QuoteRead) => void;
};

/**
 * Render an estimated-time string from a (low, high) minutes pair.
 *
 * Anything strictly under one hour stays in minutes ("X min – Y min");
 * once the upper bound reaches 60 minutes we flip to hours with one
 * decimal place. This matches the plan's UX rule and keeps small flows
 * from rendering as misleading "0.5 hr – 1.0 hr".
 */
function renderMinutesRange(minutesLow: number, minutesHigh: number): string {
  if (minutesHigh < 60) {
    return `${minutesLow} min – ${minutesHigh} min`;
  }
  const hoursLow = (minutesLow / 60).toFixed(1);
  const hoursHigh = (minutesHigh / 60).toFixed(1);
  return `${hoursLow} hr – ${hoursHigh} hr`;
}

export function PreviewProposalModal({
  open,
  flowId,
  preview,
  onClose,
  onSuccess,
}: Props) {
  const [headline, setHeadline] = useState("");
  const [narrative, setNarrative] = useState("");
  const [conversationSummary, setConversationSummary] = useState("");
  const [orgNotes, setOrgNotes] = useState("");

  const submit = useSubmitQuote(flowId);

  // Reseed the form whenever the modal opens with a fresh preview. We don't
  // depend on `preview` identity alone because the parent re-renders may pass
  // the same object across modal open/close cycles.
  useEffect(() => {
    if (open && preview) {
      setHeadline(preview.headline_summary ?? "");
      setNarrative(preview.narrative ?? "");
      setConversationSummary(preview.conversation_summary ?? "");
      setOrgNotes("");
    }
  }, [open, preview]);

  if (!preview) return null;

  const showCost =
    preview.rate_low_per_hour !== null && preview.rate_high_per_hour !== null;

  const canSubmit =
    headline.trim().length > 0 &&
    narrative.trim().length > 0 &&
    !submit.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const payload: QuoteSubmitRequest = {
      minutes_low: preview.minutes_low,
      minutes_high: preview.minutes_high,
      headline_summary: headline.trim(),
      narrative: narrative.trim(),
      conversation_summary:
        preview.conversation_summary !== null
          ? conversationSummary.trim() || null
          : null,
      org_notes: orgNotes.trim() || null,
    };
    submit.mutate(payload, {
      onSuccess: (quote: QuoteRead) => {
        onSuccess?.(quote);
        onClose();
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        className="max-w-xl"
        data-testid="preview-proposal-modal"
      >
        <DialogHeader>
          <DialogTitle>Request Professional Services</DialogTitle>
          <DialogDescription>
            Review the AI-generated estimate, edit the summary, and submit
            the request to the PS team.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div
            role="alert"
            className="rounded border border-accent-amber-foreground/40 bg-accent-amber/40 p-3 text-sm text-warning-text"
            data-testid="ps-ai-disclaimer"
          >
            This is an AI-generated ballpark estimate, not a commitment. The PS
            team will follow up with a formal scope.
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                Estimated time
              </div>
              <div
                className="text-base font-medium"
                data-testid="ps-time-range"
              >
                {renderMinutesRange(
                  preview.minutes_low,
                  preview.minutes_high,
                )}
              </div>
            </div>
            {showCost && (
              <div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Estimated cost
                </div>
                <div
                  className="text-base font-medium"
                  data-testid="ps-cost-range"
                >
                  {formatUSD(preview.cost_low)} – {formatUSD(preview.cost_high)}
                </div>
              </div>
            )}
          </div>

          {preview.component_breakdown.length > 0 && (
            <details className="rounded border p-2 text-sm">
              <summary className="cursor-pointer select-none">
                Component breakdown ({preview.component_breakdown.length})
              </summary>
              <ul className="mt-2 space-y-1">
                {preview.component_breakdown.map((c, i) => (
                  <li
                    key={`${c.type}-${i}`}
                    className="flex justify-between text-muted-foreground"
                  >
                    <span>{c.type}</span>
                    <span>
                      {c.minutes_low}–{c.minutes_high} min
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          <label className="block">
            <div className="mb-1 text-sm font-medium">Headline</div>
            <Input
              aria-label="Headline"
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              maxLength={240}
              data-testid="ps-headline-input"
            />
          </label>

          <label className="block">
            <div className="mb-1 text-sm font-medium">Narrative</div>
            <Textarea
              aria-label="Narrative"
              value={narrative}
              onChange={(e) => setNarrative(e.target.value)}
              rows={4}
              data-testid="ps-narrative-input"
            />
          </label>

          {preview.conversation_summary !== null && (
            <label className="block">
              <div className="mb-1 text-sm font-medium">
                Conversation summary
              </div>
              <Textarea
                aria-label="Conversation summary"
                value={conversationSummary}
                onChange={(e) => setConversationSummary(e.target.value)}
                rows={4}
                data-testid="ps-conversation-summary-input"
              />
            </label>
          )}

          <label className="block">
            <div className="mb-1 text-sm font-medium">
              Notes for PS (optional)
            </div>
            <Textarea
              aria-label="Notes for PS (optional)"
              value={orgNotes}
              onChange={(e) => setOrgNotes(e.target.value)}
              rows={2}
              data-testid="ps-org-notes-input"
            />
          </label>
        </div>

        <DialogFooter className="mt-4">
          <Button
            variant="outline"
            onClick={onClose}
            data-testid="ps-cancel-button"
          >
            Cancel
          </Button>
          <Button
            disabled={!canSubmit}
            loading={submit.isPending}
            onClick={handleSubmit}
            data-testid="ps-submit-button"
          >
            Submit Request
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default PreviewProposalModal;
