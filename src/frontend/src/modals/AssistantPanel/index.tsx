import { useCallback } from "react";
import { deleteConversation } from "@/controllers/API/queries/assistant/assistant-api";
import useAssistantStore from "@/stores/assistantStore";
import { useAssistantConversation } from "./hooks/use-assistant-conversation";
import { useAssistantStream } from "./hooks/use-assistant-stream";
import Composer from "./components/composer";
import MessageList from "./components/message-list";
import PanelHeader from "./components/panel-header";
import SettingsRequired from "./components/settings-required";

interface AssistantPanelProps {
  flowId: string;
}

export default function AssistantPanel({ flowId }: AssistantPanelProps) {
  const panelOpen = useAssistantStore((state) => state.panelOpen);
  const messages = useAssistantStore((state) => state.messages);
  const settingsConfigured = useAssistantStore(
    (state) => state.settingsConfigured,
  );
  const clearMessages = useAssistantStore((state) => state.clearMessages);
  const setPanelOpen = useAssistantStore((state) => state.setPanelOpen);
  const setConversationId = useAssistantStore(
    (state) => state.setConversationId,
  );

  useAssistantConversation(flowId);
  const { sendMessage } = useAssistantStream(flowId);

  const handleClear = useCallback(async () => {
    try {
      await deleteConversation(flowId);
    } catch {
      // Ignore errors on delete
    }
    clearMessages();
    setConversationId(null);
  }, [flowId, clearMessages, setConversationId]);

  const handleClose = useCallback(() => {
    setPanelOpen(false);
  }, [setPanelOpen]);

  if (!panelOpen) return null;

  return (
    <div
      className="flex h-full flex-col border-l bg-background"
      style={{ width: 400, minWidth: 300 }}
    >
      <PanelHeader onClear={handleClear} onClose={handleClose} />
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
