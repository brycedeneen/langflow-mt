import type { AssistantMessageType } from "@/stores/assistantStore";
import { cn } from "@/utils/utils";
import ToolCallCard from "./tool-call-card";

interface MessageProps {
  message: AssistantMessageType;
}

export default function Message({ message }: MessageProps) {
  if (message.role === "tool") {
    return <ToolCallCard message={message} />;
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
