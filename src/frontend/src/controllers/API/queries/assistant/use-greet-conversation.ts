import { api } from "@/controllers/API/api";
import { UseRequestProcessor } from "@/controllers/API/services/request-processor";

export type AssistantMessageRead = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  created_at?: string;
};

/** POST a proactive greeting for an empty conversation. Returns the newly-created
 * assistant message. Frontend calls this on fullscreen mount when the conversation
 * is empty. Endpoint returns 409 if already greeted — caller catches and re-hydrates.
 */
export function useGreetConversation() {
  const { mutate } = UseRequestProcessor();
  const fn = async (flowId: string): Promise<AssistantMessageRead> => {
    const res = await api.post<AssistantMessageRead>(
      `/api/v1/assistant/flows/${flowId}/greet`,
    );
    return res.data;
  };
  return mutate(["assistant", "greet"], fn);
}
