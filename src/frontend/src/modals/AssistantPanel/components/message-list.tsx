import { useEffect, useMemo, useRef } from "react";
import useAssistantStore, {
  type AssistantMessageType,
} from "@/stores/assistantStore";
import Message from "./message";

interface MessageListProps {
  messages: AssistantMessageType[];
}

export default function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const showToolCalls = useAssistantStore((s) => s.showToolCalls);

  // Build a lookup of tool_call_id -> tool name from assistant messages
  // so tool result cards can render the human-readable name instead of
  // the cryptic tool_call_id (e.g. "toolu_01AbCd...").
  const toolNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of messages) {
      if (m.tool_calls) {
        for (const tc of m.tool_calls) {
          if (tc.id && tc.name) map[tc.id] = tc.name;
        }
      }
    }
    return map;
  }, [messages]);

  // When tool calls are hidden, drop tool result messages and assistant
  // messages whose only payload is a tool_calls request (no text). Keep
  // user messages and any assistant message that has visible content.
  const visibleMessages = useMemo(() => {
    if (showToolCalls) return messages;
    return messages.filter((m) => {
      if (m.role === "tool") return false;
      if (m.role === "assistant" && m.tool_calls && !m.content?.trim()) {
        return false;
      }
      return true;
    });
  }, [messages, showToolCalls]);

  const hiddenCount = messages.length - visibleMessages.length;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleMessages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
        No messages yet. Ask the assistant to help build your flow.
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {visibleMessages.map((msg, i) => (
        <Message
          key={msg.id ?? i}
          message={msg}
          resolvedToolName={
            msg.tool_call_id ? toolNameById[msg.tool_call_id] : undefined
          }
        />
      ))}
      {!showToolCalls && hiddenCount > 0 && (
        <div className="text-center text-xs text-muted-foreground">
          {hiddenCount} tool {hiddenCount === 1 ? "call" : "calls"} hidden
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
