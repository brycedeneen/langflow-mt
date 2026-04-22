import { create } from "zustand";
import type {
  ProposalPayload,
  ThreadMessage,
} from "@/modals/ComponentAssistPopover/types";

type ComponentAssistState = {
  activeNodeId: string | null;
  flowId: string | null;
  anchorRect: DOMRect | null;
  position: { x: number; y: number };
  size: { w: number; h: number };
  thread: ThreadMessage[];
  isStreaming: boolean;
  abortController: AbortController | null;

  open: (nodeId: string, anchorRect: DOMRect | null, flowId: string | null) => void;
  close: () => void;
  setPosition: (p: { x: number; y: number }) => void;
  setSize: (s: { w: number; h: number }) => void;
  appendUserMessage: (text: string) => void;
  appendAssistantDelta: (delta: string) => void;
  appendProposal: (proposal: ProposalPayload) => void;
  markProposalApplied: (proposalId: string, skippedKeys: string[]) => void;
  dismissProposal: (proposalId: string) => void;
  setStreaming: (v: boolean) => void;
  setAbortController: (c: AbortController | null) => void;
};

const INITIAL_POSITION = { x: 120, y: 120 };
const INITIAL_SIZE = { w: 420, h: 500 };

const useComponentAssistStore = create<ComponentAssistState>((set, get) => ({
  activeNodeId: null,
  flowId: null,
  anchorRect: null,
  position: INITIAL_POSITION,
  size: INITIAL_SIZE,
  thread: [],
  isStreaming: false,
  abortController: null,

  open: (nodeId, anchorRect, flowId) => {
    const position = anchorRect
      ? { x: Math.min(anchorRect.right + 12, window.innerWidth - 440), y: anchorRect.top }
      : INITIAL_POSITION;
    set({
      activeNodeId: nodeId,
      flowId,
      anchorRect,
      position,
      size: INITIAL_SIZE,
      thread: [],
      isStreaming: false,
    });
  },

  close: () => {
    get().abortController?.abort();
    set({
      activeNodeId: null,
      flowId: null,
      anchorRect: null,
      thread: [],
      isStreaming: false,
      abortController: null,
    });
  },

  setPosition: (position) => set({ position }),
  setSize: (size) => set({ size }),

  appendUserMessage: (content) =>
    set((s) => ({ thread: [...s.thread, { role: "user", content }] })),

  appendAssistantDelta: (delta) =>
    set((s) => {
      const last = s.thread[s.thread.length - 1];
      if (last && last.role === "assistant") {
        const updated = { ...last, content: last.content + delta };
        return { thread: [...s.thread.slice(0, -1), updated] };
      }
      return {
        thread: [...s.thread, { role: "assistant", content: delta }],
      };
    }),

  appendProposal: (proposal) =>
    set((s) => {
      const last = s.thread[s.thread.length - 1];
      if (last && last.role === "assistant") {
        const updated = {
          ...last,
          proposals: [...(last.proposals ?? []), proposal],
        };
        return { thread: [...s.thread.slice(0, -1), updated] };
      }
      return {
        thread: [...s.thread, { role: "assistant", content: "", proposals: [proposal] }],
      };
    }),

  markProposalApplied: (proposalId, skippedKeys) =>
    set((s) => ({
      thread: s.thread.map((m) =>
        m.role === "assistant" && m.proposals
          ? {
              ...m,
              proposals: m.proposals.map((p) =>
                p.id === proposalId ? { ...p, applied: { skippedKeys } } : p,
              ),
            }
          : m,
      ),
    })),

  dismissProposal: (proposalId) =>
    set((s) => ({
      thread: s.thread.map((m) =>
        m.role === "assistant" && m.proposals
          ? { ...m, proposals: m.proposals.filter((p) => p.id !== proposalId) }
          : m,
      ),
    })),

  setStreaming: (v) => set({ isStreaming: v }),
  setAbortController: (c) => set({ abortController: c }),
}));

export default useComponentAssistStore;
