import { Bot, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

export default function SettingsRequired() {
  const navigate = useCustomNavigate();

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
      <Bot
        className="h-12 w-12 text-muted-foreground"
      />
      <div>
        <h3 className="text-sm font-semibold">Assistant Not Configured</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          An LLM provider and API key must be configured before using the flow
          assistant.
        </p>
      </div>
      <Button
        variant="default"
        size="sm"
        onClick={() => navigate("/settings/assistant")}
      >
        <Settings className="mr-2 h-4 w-4" />
        Configure Assistant
      </Button>
    </div>
  );
}
