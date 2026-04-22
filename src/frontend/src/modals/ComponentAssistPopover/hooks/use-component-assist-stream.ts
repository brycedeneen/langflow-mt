import { useCallback } from "react";

import useComponentAssistStore from "@/stores/componentAssistStore";
import type { ProposalPayload } from "../types";

type NodeSnapshot = {
  node_id: string;
  type: string;
  display_name: string;
  description?: string | null;
  template: Record<string, unknown>;
  outputs: unknown[];
};

type SendArgs = {
  nodeSnapshot: NodeSnapshot;
  neighborSnapshots: NodeSnapshot[];
  userMessage: string;
};

const randomId = () =>
  (globalThis.crypto?.randomUUID?.() ?? String(Math.random())).slice(0, 12);

export function useComponentAssistStream(flowId: string) {
  const sendMessage = useCallback(
    async ({ nodeSnapshot, neighborSnapshots, userMessage }: SendArgs) => {
      const store = useComponentAssistStore.getState();
      store.appendUserMessage(userMessage);
      store.setStreaming(true);

      const controller = new AbortController();
      store.setAbortController(controller);

      try {
        const response = await fetch("/api/v1/assistant/components/messages", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            flow_id: flowId,
            node_id: nodeSnapshot.node_id,
            node_snapshot: nodeSnapshot,
            neighbor_snapshots: neighborSnapshots,
            thread: store.thread.map(({ role, content }) => ({ role, content })),
            user_message: userMessage,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data: ")) continue;
            const payload = trimmed.slice(6);
            if (!payload || payload === "[DONE]") continue;
            let event: any;
            try {
              event = JSON.parse(payload);
            } catch {
              continue;
            }
            const s = useComponentAssistStore.getState();
            switch (event.type) {
              case "token":
                s.appendAssistantDelta(event.text ?? "");
                break;
              case "tool_call":
                if (event.name === "propose_config_update") {
                  const proposal: ProposalPayload = {
                    id: randomId(),
                    nodeId: event.args?.node_id,
                    patch: event.args?.patch ?? {},
                    rationale: event.args?.rationale ?? "",
                  };
                  s.appendProposal(proposal);
                }
                break;
              case "error":
                s.appendAssistantDelta(`\n[Error] ${event.error ?? "Unknown error"}`);
                break;
              case "done":
                break;
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          const s = useComponentAssistStore.getState();
          s.appendAssistantDelta(`\n[Connection lost — please try again.]`);
        }
      } finally {
        const s = useComponentAssistStore.getState();
        s.setStreaming(false);
        s.setAbortController(null);
      }
    },
    [flowId],
  );

  return { sendMessage };
}
