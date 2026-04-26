import { useCallback } from "react";
import { baseURL } from "@/customization/constants";
import useAssistantStore from "@/stores/assistantStore";
import type { FlowPatch } from "@/stores/assistantStore";
import useFlowStore from "@/stores/flowStore";

function applyFlowPatch(patch: FlowPatch) {
  const { nodes, edges, setNodes, setEdges } = useFlowStore.getState();

  // Remove nodes and edges by removed_ids
  let newNodes = nodes.filter((n) => !patch.removed_ids.includes(n.id));
  let newEdges = edges.filter((e) => !patch.removed_ids.includes(e.id));

  // Add new nodes
  if (patch.added_nodes?.length) {
    newNodes = [...newNodes, ...patch.added_nodes];
  }

  // Add new edges
  if (patch.added_edges?.length) {
    newEdges = [...newEdges, ...patch.added_edges];
  }

  // Update existing nodes
  if (patch.updated_nodes?.length) {
    const updateMap = new Map(patch.updated_nodes.map((n: any) => [n.id, n]));
    newNodes = newNodes.map((n) => {
      const update = updateMap.get(n.id);
      return update ? { ...n, ...update } : n;
    });
  }

  setNodes(newNodes);
  setEdges(newEdges);

  // Fit view after a short timeout to let React Flow process the changes
  setTimeout(() => {
    const instance = useFlowStore.getState().reactFlowInstance;
    if (instance) {
      instance.fitView();
    }
  }, 200);
}

export function useAssistantStream(flowId: string) {
  const sendMessage = useCallback(
    async (content: string) => {
      const store = useAssistantStore.getState();

      // Add user message and empty assistant message
      store.addMessage({ role: "user", content });
      store.addMessage({ role: "assistant", content: "" });
      store.setIsStreaming(true);

      try {
        const url = `${baseURL}/api/v1/assistant/flows/${flowId}/messages`;

        const response = await fetch(url, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE lines
          const lines = buffer.split("\n");
          // Keep the last (potentially incomplete) line in the buffer
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith("data: ")) continue;

            const jsonStr = trimmed.slice(6);
            if (jsonStr === "[DONE]") continue;

            try {
              const event = JSON.parse(jsonStr);
              const assistantStore = useAssistantStore.getState();

              switch (event.type) {
                case "token":
                  assistantStore.appendToLastAssistant(event.text ?? "");
                  break;

                case "tool_call":
                  assistantStore.addMessage({
                    role: "tool",
                    content: `Calling ${event.tool_name ?? "tool"}...`,
                    tool_call_id: event.tool_call_id,
                    tool_name: event.tool_name,
                  });
                  break;

                case "tool_result":
                  // Patch the placeholder tool message with the result so the
                  // renderer can branch on tool_name (e.g. show
                  // PSSuggestionCard for ``suggest_professional_services``).
                  if (event.tool_call_id) {
                    assistantStore.updateToolMessage(event.tool_call_id, {
                      tool_name: event.tool_name,
                      tool_result: event.result,
                    });
                  }
                  break;

                case "flow_patch":
                  if (event.patch) {
                    assistantStore.addPendingPatch(event.patch);
                    applyFlowPatch(event.patch);
                  }
                  break;

                case "error":
                  assistantStore.appendToLastAssistant(
                    `\n[Error] ${event.error ?? "Unknown error"}`,
                  );
                  break;

                case "message_complete":
                  // Stream is complete
                  break;
              }
            } catch {
              // Skip malformed JSON lines
            }
          }
        }
      } catch (err: any) {
        const assistantStore = useAssistantStore.getState();
        assistantStore.appendToLastAssistant(
          `\n[Error] ${err.message ?? "Failed to send message"}`,
        );
      } finally {
        useAssistantStore.getState().setIsStreaming(false);
      }
    },
    [flowId],
  );

  return { sendMessage };
}
