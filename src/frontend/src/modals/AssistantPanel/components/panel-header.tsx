import { Bot, Trash2, Wrench, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import useAssistantStore from "@/stores/assistantStore";
import { ModeToggleButton } from "../mode-toggle-button";

interface PanelHeaderProps {
  onClear: () => void;
  onClose: () => void;
}

export default function PanelHeader({ onClear, onClose }: PanelHeaderProps) {
  const showToolCalls = useAssistantStore((s) => s.showToolCalls);
  const toggleShowToolCalls = useAssistantStore((s) => s.toggleShowToolCalls);

  const handleClear = () => {
    if (window.confirm("Clear the conversation history?")) {
      onClear();
    }
  };

  return (
    <div className="flex items-center justify-between border-b px-4 py-3">
      <div className="flex items-center gap-2">
        <Bot
          className="h-5 w-5 text-primary"
        />
        <h3 className="text-sm font-semibold">Flow Assistant</h3>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant={showToolCalls ? "secondary" : "ghost"}
          size="icon"
          onClick={toggleShowToolCalls}
          className="h-7 w-7"
          title={showToolCalls ? "Hide tool calls" : "Show tool calls"}
          aria-pressed={showToolCalls}
        >
          <Wrench className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClear}
          className="h-7 w-7"
          title="Clear conversation"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
        <ModeToggleButton />
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7"
          title="Close assistant"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
