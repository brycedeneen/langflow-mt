import { api } from "../../api";

export async function getConversation(flowId: string) {
  const response = await api.get(
    `/api/v1/assistant/flows/${flowId}/conversation`,
  );
  return response.data;
}

export async function deleteConversation(flowId: string) {
  const response = await api.delete(
    `/api/v1/assistant/flows/${flowId}/conversation`,
  );
  return response.data;
}

export async function getAssistantSettings() {
  const response = await api.get("/api/v1/assistant/settings");
  return response.data;
}

export async function putAssistantSettings(body: {
  provider: string;
  model: string;
  api_key?: string;
}) {
  const response = await api.put("/api/v1/assistant/settings", body);
  return response.data;
}

export function createMessageSSEUrl(flowId: string): string {
  return `/api/v1/assistant/flows/${flowId}/messages`;
}
