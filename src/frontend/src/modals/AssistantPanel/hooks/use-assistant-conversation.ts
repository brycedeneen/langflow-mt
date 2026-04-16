import { useEffect } from "react";
import { getConversation } from "@/controllers/API/queries/assistant/assistant-api";
import useAssistantStore from "@/stores/assistantStore";

export function useAssistantConversation(flowId: string) {
  useEffect(() => {
    let cancelled = false;

    async function loadConversation() {
      try {
        const data = await getConversation(flowId);
        if (cancelled) return;

        if (data?.messages) {
          useAssistantStore.getState().setMessages(data.messages);
        }
        if (data?.conversation_id) {
          useAssistantStore.getState().setConversationId(data.conversation_id);
        }
        if (data?.settings_configured !== undefined) {
          useAssistantStore
            .getState()
            .setSettingsConfigured(data.settings_configured);
        }
      } catch (err) {
        if (cancelled) return;
        console.error("Failed to load assistant conversation:", err);
      }
    }

    if (flowId) {
      loadConversation();
    }

    return () => {
      cancelled = true;
    };
  }, [flowId]);
}
