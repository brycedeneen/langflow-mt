import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import useAssistantStore from "@/stores/assistantStore";

/** Toggle between panel and fullscreen layout modes. Only rendered in panel mode. */
export function ModeToggleButton() {
  const layoutMode = useAssistantStore((s) => s.layoutMode);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);

  if (layoutMode !== "panel") return null;

  return (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>
        <button
          aria-label="Enter full-screen ADP Assist"
          onClick={() => setLayoutMode("fullscreen")}
          className="inline-flex h-7 w-7 items-center justify-center rounded hover:bg-muted"
        >
          <ForwardedIconComponent name="Maximize2" className="h-4 w-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent
        className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
        avoidCollisions={false}
        sticky="always"
      >
        Enter full-screen ADP Assist
      </TooltipContent>
    </Tooltip>
  );
}
