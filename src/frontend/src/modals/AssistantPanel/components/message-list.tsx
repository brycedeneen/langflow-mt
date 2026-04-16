import { useEffect, useRef } from "react";
import type { AssistantMessageType } from "@/stores/assistantStore";
import Message from "./message";

interface MessageListProps {
  messages: AssistantMessageType[];
}

export default function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
        No messages yet. Ask the assistant to help build your flow.
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {messages.map((msg, i) => (
        <Message key={msg.id ?? i} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
