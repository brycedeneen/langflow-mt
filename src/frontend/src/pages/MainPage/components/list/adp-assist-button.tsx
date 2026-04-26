import { useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { openFlowInFullscreenAssist } from "@/utils/assist-entry";
import { cn } from "@/utils/utils";

type Props = {
  flowId: string;
  builtWithAssist: boolean;
};

export function AdpAssistButton({ flowId, builtWithAssist }: Props) {
  const navigate = useNavigate();
  return (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Open in ADP Assist"
          onClick={(e) => {
            e.stopPropagation();
            openFlowInFullscreenAssist(flowId, navigate);
          }}
          className={cn(
            "inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted",
            builtWithAssist && "text-primary",
          )}
        >
          <ForwardedIconComponent name="Bot" className="h-4 w-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent
        className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
        avoidCollisions={false}
        sticky="always"
      >
        Open in ADP Assist
      </TooltipContent>
    </Tooltip>
  );
}
