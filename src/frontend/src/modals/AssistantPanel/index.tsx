import { useCallback, useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  deleteConversation,
  getConversation,
} from "@/controllers/API/queries/assistant/assistant-api";
import useAssistantStore from "@/stores/assistantStore";
import { useAssistantConversation } from "./hooks/use-assistant-conversation";
import { useAssistantStream } from "./hooks/use-assistant-stream";
import Composer from "./components/composer";
import MessageList from "./components/message-list";
import PanelHeader from "./components/panel-header";
import SettingsRequired from "./components/settings-required";
import { FullscreenShell } from "./fullscreen-shell";
import { TestShell } from "./test-shell";

interface AssistantPanelProps {
  flowId: string;
}

export default function AssistantPanel({ flowId }: AssistantPanelProps) {
  const panelOpen = useAssistantStore((state) => state.panelOpen);
  const layoutMode = useAssistantStore((s) => s.layoutMode);
  const messages = useAssistantStore((state) => state.messages);
  const settingsConfigured = useAssistantStore(
    (state) => state.settingsConfigured,
  );
  const clearMessages = useAssistantStore((state) => state.clearMessages);
  const setMessages = useAssistantStore((state) => state.setMessages);
  const setPanelOpen = useAssistantStore((state) => state.setPanelOpen);
  const setConversationId = useAssistantStore(
    (state) => state.setConversationId,
  );

  useAssistantConversation(flowId);
  const { sendMessage } = useAssistantStream(flowId);

  // Stale history polling
  const lastSeenRef = useRef<string | null>(null);
  const [stale, setStale] = useState(false);

  // Track the latest message ID we've seen
  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      lastSeenRef.current = lastMsg.id ?? null;
    }
  }, [messages]);

  useEffect(() => {
    if (!panelOpen || !flowId || !settingsConfigured) return;

    const interval = setInterval(async () => {
      try {
        const data = await getConversation(flowId);
        if (data?.messages?.length) {
          const remoteLastId = data.messages[data.messages.length - 1].id;
          if (
            lastSeenRef.current &&
            remoteLastId &&
            remoteLastId !== lastSeenRef.current
          ) {
            setStale(true);
          }
        }
      } catch {
        // Ignore polling errors
      }
    }, 30_000);

    return () => clearInterval(interval);
  }, [panelOpen, flowId, settingsConfigured]);

  const handleRefresh = useCallback(async () => {
    try {
      const data = await getConversation(flowId);
      if (data?.messages) {
        setMessages(data.messages);
      }
      if (data?.conversation_id) {
        setConversationId(data.conversation_id);
      }
    } catch {
      // Ignore
    }
    setStale(false);
  }, [flowId, setMessages, setConversationId]);

  const handleClear = useCallback(async () => {
    try {
      await deleteConversation(flowId);
    } catch {
      // Ignore errors on delete
    }
    clearMessages();
    setConversationId(null);
    setStale(false);
  }, [flowId, clearMessages, setConversationId]);

  const handleClose = useCallback(() => {
    setPanelOpen(false);
  }, [setPanelOpen]);

  if (!panelOpen) return null;

  if (layoutMode === "fullscreen") {
    return <FullscreenShell flowId={flowId} onSend={sendMessage} />;
  }
  if (layoutMode === "test") {
    return <TestShell flowId={flowId} onSend={sendMessage} />;
  }

  return (
    <div
      className="flex h-full flex-col border-l bg-background"
      style={{ width: 400, minWidth: 300 }}
    >
      <PanelHeader onClear={handleClear} onClose={handleClose} />
      {stale && (
        <div className="flex items-center gap-2 border-b bg-yellow-50 px-4 py-2 text-xs text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
          <ForwardedIconComponent name="AlertTriangle" className="h-4 w-4 shrink-0" />
          <span className="flex-1">New messages from a teammate</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            className="h-6 px-2 text-xs"
          >
            Refresh
          </Button>
        </div>
      )}
      {!settingsConfigured ? (
        <SettingsRequired />
      ) : (
        <>
          <MessageList messages={messages} />
          <Composer onSend={sendMessage} />
        </>
      )}
    </div>
  );
}
