import { useState } from "react";
import { Wrench } from "lucide-react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { AssistantMessageType } from "@/stores/assistantStore";

interface ToolCallCardProps {
  message: AssistantMessageType;
  resolvedToolName?: string;
}

export default function ToolCallCard({ message, resolvedToolName }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);

  const toolName =
    message.tool_calls?.[0]?.name ??
    resolvedToolName ??
    message.tool_call_id ??
    "Tool Call";

  return (
    <div className="my-1 max-w-[90%] rounded-md border bg-muted/50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:bg-muted/80"
      >
        <ForwardedIconComponent
          name={expanded ? "ChevronDown" : "ChevronRight"}
          className="h-3 w-3 shrink-0"
        />
        <Wrench className="h-3 w-3 shrink-0" />
        <span className="truncate">{toolName}</span>
      </button>
      {expanded && (
        <div className="border-t px-3 py-2">
          {message.tool_calls?.[0]?.args && (
            <div className="mb-2">
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Arguments
              </p>
              <pre className="overflow-auto rounded bg-background p-2 text-xs">
                {JSON.stringify(message.tool_calls[0].args, null, 2)}
              </pre>
            </div>
          )}
          {message.tool_result && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Result
              </p>
              <pre className="overflow-auto rounded bg-background p-2 text-xs">
                {JSON.stringify(message.tool_result, null, 2)}
              </pre>
            </div>
          )}
          {message.content && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Output
              </p>
              <pre className="overflow-auto whitespace-pre-wrap rounded bg-background p-2 text-xs">
                {message.content}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
