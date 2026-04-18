import { useEffect, useRef } from "react";
import { getConversation } from "@/controllers/API/queries/assistant/assistant-api";
import { useGreetConversation } from "@/controllers/API/queries/assistant/use-greet-conversation";
import useAssistantStore from "@/stores/assistantStore";

export function useAssistantConversation(flowId: string) {
  const { mutateAsync: greet } = useGreetConversation();
  const greetedFor = useRef<string | null>(null);

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

        const layoutMode = useAssistantStore.getState().layoutMode;
        const messagesEmpty = !data?.messages || data.messages.length === 0;
        const alreadyGreeted = greetedFor.current === flowId;

        if (
          !alreadyGreeted &&
          messagesEmpty &&
          layoutMode === "fullscreen" &&
          data?.settings_configured !== false
        ) {
          greetedFor.current = flowId;
          try {
            await greet(flowId);
            // Re-fetch so the store picks up the persisted greeting
            const after = await getConversation(flowId);
            if (!cancelled && after?.messages) {
              useAssistantStore.getState().setMessages(after.messages);
            }
          } catch (err) {
            // 409 = already greeted in a sibling tab; swallow and let the
            // re-fetch (or next mount) sync the message
            if (!cancelled) {
              // eslint-disable-next-line no-console
              console.debug("greet failed or already greeted:", err);
            }
          }
        }
      } catch (err) {
        if (cancelled) return;
        // eslint-disable-next-line no-console
        console.error("Failed to load assistant conversation:", err);
      }
    }

    if (flowId) {
      loadConversation();
    }

    return () => {
      cancelled = true;
    };
  }, [flowId, greet]);
}
