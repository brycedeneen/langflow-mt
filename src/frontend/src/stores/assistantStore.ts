import { create } from "zustand";

export type AssistantMessageType = {
  id?: string;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_calls?: Array<{ id: string; name: string; args: Record<string, any> }>;
  tool_call_id?: string;
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
  clearMessages: () => void;
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
  clearMessages: () => set({ messages: [] }),

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
}));

export default useAssistantStore;
