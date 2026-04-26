import { Bot } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import useAssistantStore from "@/stores/assistantStore";

export default function AssistantToggleButton() {
  const togglePanel = useAssistantStore((state) => state.togglePanel);
  const panelOpen = useAssistantStore((state) => state.panelOpen);

  return (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>
        <button
          onClick={togglePanel}
          data-testid="assistant-toggle-btn"
          className={
            "relative inline-flex h-8 items-center justify-center gap-1.5 rounded px-2 text-sm font-normal hover:bg-muted " +
            (panelOpen ? "text-primary" : "text-muted-foreground")
          }
        >
          <Bot className="h-4 w-4" />
          <span className="font-normal text-mmd">Assistant</span>
        </button>
      </TooltipTrigger>
      <TooltipContent
        className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
        avoidCollisions={false}
        sticky="always"
      >
        Flow Assistant
      </TooltipContent>
    </Tooltip>
  );
}
