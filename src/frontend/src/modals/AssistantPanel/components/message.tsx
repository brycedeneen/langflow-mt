import { PSSuggestionCardConnected } from "@/components/core/proServiceQuotes/PSSuggestionCard/connected";
import useAssistantStore, {
  type AssistantMessageType,
} from "@/stores/assistantStore";
import { cn } from "@/utils/utils";
import ToolCallCard from "./tool-call-card";

interface MessageProps {
  message: AssistantMessageType;
  resolvedToolName?: string;
  flowId?: string;
}

/**
 * Pull the inner ``{shown, reason}`` payload out of the layered tool_result
 * envelope. The backend wraps the tool's return value in ``{result: ...}``
 * (see ``service.py::_execute_tool``), and the assistant tool itself
 * returns ``{shown, reason}``, so the actual reason lives at
 * ``message.tool_result.result.reason``.
 */
function extractSuggestionReason(message: AssistantMessageType): string | null {
  const outer = message.tool_result;
  if (!outer || typeof outer !== "object") return null;
  const inner = (outer as Record<string, unknown>).result;
  if (!inner || typeof inner !== "object") return null;
  const reason = (inner as Record<string, unknown>).reason;
  return typeof reason === "string" ? reason : null;
}

export default function Message({
  message,
  resolvedToolName,
  flowId,
}: MessageProps) {
  const dismissedSuggestionIds = useAssistantStore(
    (s) => s.dismissedSuggestionIds,
  );
  const dismissSuggestion = useAssistantStore((s) => s.dismissSuggestion);

  if (message.role === "tool") {
    const toolName = message.tool_name ?? resolvedToolName;
    if (toolName === "suggest_professional_services" && flowId) {
      const reason = extractSuggestionReason(message);
      const dismissed =
        message.tool_call_id != null &&
        dismissedSuggestionIds.has(message.tool_call_id);
      // While we're still waiting on the tool_result event the placeholder
      // tool message has no result yet — render nothing rather than the
      // generic ToolCallCard so the user doesn't see a "Calling …"
      // technicality flash for a UX-meant-to-be-quiet tool.
      if (reason === null) return null;
      if (dismissed) return null;
      return (
        <PSSuggestionCardConnected
          flowId={flowId}
          reason={reason}
          onDismiss={() => {
            if (message.tool_call_id) dismissSuggestion(message.tool_call_id);
          }}
        />
      );
    }
    return <ToolCallCard message={message} resolvedToolName={resolvedToolName} />;
  }

  const isUser = message.role === "user";

  return (
    <div
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        <p className="whitespace-pre-wrap break-words">
          {message.content ?? ""}
        </p>
      </div>
    </div>
  );
}
