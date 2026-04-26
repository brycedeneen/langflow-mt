import { useState } from "react";
import { usePreviewQuote } from "@/controllers/API/queries/pro-service-quotes/use-preview-quote";
import type { PreviewResponse } from "@/types/pro-service-quote";
import { PreviewProposalModal } from "../PreviewProposalModal";
import { PSSuggestionCard } from "./index";

type Props = {
  flowId: string;
  reason: string;
  onDismiss: () => void;
};

/**
 * Stream-connected wrapper around ``PSSuggestionCard``. Shares the same
 * "preview-then-open" sequencing as ``PSRequestButton`` — extracted out
 * so the assistant-chat renderer can reuse it without dragging in the
 * header-button shell. Kept as a separate file from the presentational
 * card so the card itself stays trivially testable without mocking the
 * preview hook.
 */
export function PSSuggestionCardConnected({ flowId, reason, onDismiss }: Props) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const previewMutation = usePreviewQuote(flowId);

  const handleRequest = () => {
    if (previewMutation.isPending) return;
    previewMutation.mutate(undefined, {
      onSuccess: (data) => {
        setPreview(data);
        setOpen(true);
      },
    });
  };

  return (
    <>
      <PSSuggestionCard
        reason={reason}
        onRequest={handleRequest}
        onDismiss={onDismiss}
      />
      <PreviewProposalModal
        open={open}
        flowId={flowId}
        preview={preview}
        onClose={() => setOpen(false)}
      />
    </>
  );
}

export default PSSuggestionCardConnected;
