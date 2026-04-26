import { create } from "zustand";

export type AssistantMessageType = {
  id?: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: Array<{ id: string; name: string; args: Record<string, any> }>;
  tool_call_id?: string;
  /**
   * For tool-role messages: the human-readable tool name, populated by the
   * SSE stream when ``tool_call`` / ``tool_result`` events arrive. Lets
   * downstream consumers (e.g. the suggestion-card renderer) branch on
   * ``tool_name`` without rebuilding a tool_call_id → name lookup.
   */
  tool_name?: string;
  tool_result?: Record<string, any>;
  user_id?: string | null;
  created_at?: string;
};

export type FlowPatch = {
  added_nodes: any[];
  added_edges: any[];
  updated_nodes: any[];
  removed_ids: string[];
};

type AssistantStoreState = {
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
  togglePanel: () => void;
  messages: AssistantMessageType[];
  setMessages: (messages: AssistantMessageType[]) => void;
  addMessage: (message: AssistantMessageType) => void;
  appendToLastAssistant: (text: string) => void;
  /**
   * Patch an existing tool-role message identified by ``tool_call_id``. Used
   * by the SSE stream when a ``tool_result`` event arrives so the placeholder
   * "Calling …" message gets the tool name + result merged in. We do an
   * identity-stable patch (last-match wins) instead of replacing the array
   * wholesale so consumers using ``useShallow`` don't churn unnecessarily.
   */
  updateToolMessage: (
    toolCallId: string,
    patch: Partial<AssistantMessageType>,
  ) => void;
  clearMessages: () => void;
  /**
   * Set of tool_call_ids whose ``suggest_professional_services`` cards the
   * user has dismissed in the current session. Lives in-memory only — when
   * the panel reloads the conversation we re-show suggestions, matching the
   * "transient inline nudge" UX rather than persistent banners.
   */
  dismissedSuggestionIds: Set<string>;
  dismissSuggestion: (toolCallId: string) => void;
  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;
  settingsConfigured: boolean;
  setSettingsConfigured: (configured: boolean) => void;
  conversationId: string | null;
  setConversationId: (id: string | null) => void;
  pendingPatches: FlowPatch[];
  addPendingPatch: (patch: FlowPatch) => void;
  clearPendingPatches: () => void;
  layoutMode: "panel" | "fullscreen" | "test";
  setLayoutMode: (mode: "panel" | "fullscreen" | "test") => void;
  selectedTestComponent: string | null;
  setSelectedTestComponent: (id: string | null) => void;
  showToolCalls: boolean;
  setShowToolCalls: (show: boolean) => void;
  toggleShowToolCalls: () => void;
};

const useAssistantStore = create<AssistantStoreState>((set, get) => ({
  panelOpen: false,
  setPanelOpen: (open) => set({ panelOpen: open }),
  togglePanel: () => set({ panelOpen: !get().panelOpen }),

  messages: [],
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set({ messages: [...get().messages, message] }),
  appendToLastAssistant: (text) => {
    const messages = [...get().messages];
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") {
        messages[i] = {
          ...messages[i],
          content: (messages[i].content ?? "") + text,
        };
        break;
      }
    }
    set({ messages });
  },
  updateToolMessage: (toolCallId, patch) => {
    const messages = [...get().messages];
    for (let i = messages.length - 1; i >= 0; i--) {
      if (
        messages[i].role === "tool" &&
        messages[i].tool_call_id === toolCallId
      ) {
        messages[i] = { ...messages[i], ...patch };
        break;
      }
    }
    set({ messages });
  },
  clearMessages: () => set({ messages: [] }),
  dismissedSuggestionIds: new Set<string>(),
  dismissSuggestion: (toolCallId) =>
    set({
      dismissedSuggestionIds: new Set([
        ...get().dismissedSuggestionIds,
        toolCallId,
      ]),
    }),

  isStreaming: false,
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  settingsConfigured: false,
  setSettingsConfigured: (configured) =>
    set({ settingsConfigured: configured }),

  conversationId: null,
  setConversationId: (id) => set({ conversationId: id }),

  pendingPatches: [],
  addPendingPatch: (patch) =>
    set({ pendingPatches: [...get().pendingPatches, patch] }),
  clearPendingPatches: () => set({ pendingPatches: [] }),

  layoutMode: "panel",
  setLayoutMode: (mode) => set({ layoutMode: mode }),
  selectedTestComponent: null,
  setSelectedTestComponent: (id) => set({ selectedTestComponent: id }),

  showToolCalls: false,
  setShowToolCalls: (show) => set({ showToolCalls: show }),
  toggleShowToolCalls: () => set({ showToolCalls: !get().showToolCalls }),
}));

export default useAssistantStore;
