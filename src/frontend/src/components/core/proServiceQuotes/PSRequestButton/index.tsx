import { useState } from "react";
import { HandCoins } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { usePreviewQuote } from "@/controllers/API/queries/pro-service-quotes/use-preview-quote";
import type { PreviewResponse } from "@/types/pro-service-quote";
import { PreviewProposalModal } from "../PreviewProposalModal";

type Props = {
  flowId: string;
  /**
   * Whether the current viewer is allowed to request PS for this flow
   * (Owner, Org Admin, or Platform Admin per the backend permissions
   * module). When false the component renders nothing — no disabled-button
   * placeholder, no tooltip, just absent — so non-eligible viewers don't
   * see surface they can't act on.
   */
  canRequest: boolean;
  /**
   * Mirror of ``flow.ps_request_active``. When true the button is
   * disabled with a tooltip explaining there's already an open request.
   */
  psRequestActive: boolean;
};

/**
 * Header CTA that previews and (via the modal) submits a Pro-Service Quote
 * for the current flow. Does its own preview-then-open dance so the modal
 * always has a populated estimate when it appears.
 */
export function PSRequestButton({ flowId, canRequest, psRequestActive }: Props) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const previewMutation = usePreviewQuote(flowId);

  if (!canRequest) return null;

  const handleClick = () => {
    if (psRequestActive || previewMutation.isPending) return;
    previewMutation.mutate(undefined, {
      onSuccess: (data) => {
        setPreview(data);
        setOpen(true);
      },
    });
  };

  const button = (
    <Button
      variant="ghost"
      size="md"
      className="!px-2 !font-normal !gap-1.5"
      disabled={psRequestActive}
      loading={previewMutation.isPending}
      onClick={handleClick}
      ignoreTitleCase
      data-testid="ps-request-button"
    >
      <HandCoins className="h-4 w-4" />
      <span className="font-normal text-mmd">Request PS</span>
    </Button>
  );

  return (
    <>
      {psRequestActive ? (
        <Tooltip delayDuration={500}>
          <TooltipTrigger asChild>
            {/*
              Wrap in a span so the tooltip target stays interactive even when
              the inner button is disabled — disabled buttons swallow pointer
              events and Radix loses the trigger.
            */}
            <span tabIndex={0}>{button}</span>
          </TooltipTrigger>
          <TooltipContent
            className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
            side="bottom"
            avoidCollisions={false}
            sticky="always"
          >
            You already have an open Pro-Service request for this flow.
          </TooltipContent>
        </Tooltip>
      ) : (
        button
      )}
      <PreviewProposalModal
        open={open}
        flowId={flowId}
        preview={preview}
        onClose={() => setOpen(false)}
      />
    </>
  );
}

export default PSRequestButton;
