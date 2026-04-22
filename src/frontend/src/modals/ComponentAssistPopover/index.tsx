import { useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useComponentAssistStore from "@/stores/componentAssistStore";
import useFlowStore from "@/stores/flowStore";

import { ProposalBlock } from "./components/ProposalBlock";
import { useComponentAssistStream } from "./hooks/use-component-assist-stream";

export default function ComponentAssistPopover() {
  const {
    activeNodeId,
    openedOnFlowId,
    position,
    size,
    thread,
    isStreaming,
    close,
    setPosition,
    setSize,
  } = useComponentAssistStore(
    useShallow((s) => ({
      activeNodeId: s.activeNodeId,
      openedOnFlowId: s.flowId,
      position: s.position,
      size: s.size,
      thread: s.thread,
      isStreaming: s.isStreaming,
      close: s.close,
      setPosition: s.setPosition,
      setSize: s.setSize,
    })),
  );

  const flowId = useFlowStore((s) => s.currentFlow?.id ?? "");
  const node = useFlowStore(
    (s) => (activeNodeId ? s.nodes.find((n) => n.id === activeNodeId) ?? null : null),
  );
  const neighborNodes = useFlowStore(
    useShallow((s) => {
      if (!activeNodeId) return [] as typeof s.nodes;
      const neighborIds = new Set<string>();
      for (const edge of s.edges) {
        if (edge.source === activeNodeId) neighborIds.add(edge.target);
        if (edge.target === activeNodeId) neighborIds.add(edge.source);
      }
      return s.nodes.filter((n) => neighborIds.has(n.id));
    }),
  );
  const setNode = useFlowStore((s) => s.setNode);

  const [input, setInput] = useState("");
  const bodyRef = useRef<HTMLDivElement>(null);

  const { sendMessage } = useComponentAssistStream(flowId);

  useEffect(() => {
    // Depend on `thread` (the whole array reference) rather than `thread.length`
    // so we re-scroll on streaming delta appends too — appendAssistantDelta
    // mutates the trailing message in place, leaving length unchanged.
    if (bodyRef.current && activeNodeId) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [thread, isStreaming, activeNodeId]);

  // Close (and wipe the stale thread) when the visible flow no longer matches
  // the flow the popover was opened on — covers both "flow switched while the
  // popover stayed mounted" and "navigated to /all then into a different flow"
  // (the store is app-scoped so activeNodeId survives the remount).
  useEffect(() => {
    if (activeNodeId && openedOnFlowId && flowId && openedOnFlowId !== flowId) {
      close();
    }
  }, [flowId, openedOnFlowId, activeNodeId, close]);

  if (!activeNodeId) return null;

  const displayName = node?.data?.node?.display_name ?? "Component";
  const template = (node?.data?.node?.template ?? {}) as Record<string, { value?: unknown }>;

  const handleSend = async () => {
    if (!input.trim() || isStreaming || !node) return;
    const text = input;
    setInput("");
    const nodeSnapshot = {
      node_id: node.id,
      type: node.data?.type ?? "",
      display_name: displayName,
      description: node.data?.node?.description ?? null,
      template,
      outputs: node.data?.node?.outputs ?? [],
    };
    const neighborSnapshots = neighborNodes.map((n) => ({
      node_id: n.id,
      type: n.data?.type ?? "",
      display_name: n.data?.node?.display_name ?? "Component",
      description: n.data?.node?.description ?? null,
      template: (n.data?.node?.template ?? {}) as Record<string, unknown>,
      outputs: n.data?.node?.outputs ?? [],
    }));
    await sendMessage({ nodeSnapshot, neighborSnapshots, userMessage: text });
  };

  const applyPatch = (patch: Record<string, unknown>, proposalId: string) => {
    if (!node) return;
    const skipped: string[] = [];
    setNode(node.id, (old: any) => {
      const tpl = { ...(old.data?.node?.template ?? {}) };
      for (const [k, v] of Object.entries(patch)) {
        if (!(k in tpl)) {
          skipped.push(k);
          continue;
        }
        tpl[k] = { ...tpl[k], value: v };
      }
      return {
        ...old,
        data: { ...old.data, node: { ...old.data.node, template: tpl } },
      };
    });
    useComponentAssistStore.getState().markProposalApplied(proposalId, skipped);
  };

  return (
    <div
      data-testid="component-assist-popover"
      className="fixed z-50 flex flex-col rounded-lg border border-adp-red/60 bg-background shadow-2xl"
      style={{ left: position.x, top: position.y, width: size.w, height: size.h }}
    >
      {/* Header / drag handle */}
      <div
        className="flex cursor-grab items-center justify-between border-b border-adp-red/30 bg-adp-red/10 px-3 py-2"
        onMouseDown={(e) => {
          const startX = e.clientX - position.x;
          const startY = e.clientY - position.y;
          const onMove = (ev: MouseEvent) =>
            setPosition({ x: ev.clientX - startX, y: ev.clientY - startY });
          const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
          };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        }}
      >
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-2.5 rounded-full bg-adp-red" />
          <span className="text-sm font-semibold">Assist · {displayName}</span>
          <span className="text-xs italic text-amber-500">ephemeral</span>
        </div>
        <button
          aria-label="Close"
          onClick={close}
          className="text-muted-foreground hover:text-foreground"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div ref={bodyRef} className="flex-1 space-y-3 overflow-y-auto p-3 text-sm">
        {thread.length === 0 && (
          <div className="rounded bg-muted p-2 text-muted-foreground">
            Hi! I'll help configure {displayName}. Paste a spec, describe rules, or ask me
            anything.
          </div>
        )}
        {thread.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            <div
              className={
                m.role === "user"
                  ? "max-w-[85%] rounded-lg bg-muted px-3 py-2"
                  : "max-w-[95%] space-y-2"
              }
            >
              {m.content && <div className="whitespace-pre-wrap">{m.content}</div>}
              {m.role === "assistant" &&
                m.proposals?.map((p) => (
                  <ProposalBlock
                    key={p.id}
                    proposal={p}
                    currentTemplate={template}
                    onApply={(patch) => applyPatch(patch, p.id)}
                    onDismiss={() => useComponentAssistStore.getState().dismissProposal(p.id)}
                  />
                ))}
            </div>
          </div>
        ))}
        {isStreaming && (
          <div className="text-xs italic text-muted-foreground">Assistant is thinking…</div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border p-2">
        <div className="flex items-center gap-2 rounded border border-border bg-muted/50 px-2 py-1">
          <ForwardedIconComponent name="Sparkles" className="h-4 w-4 text-adp-red" />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask anything about this component…"
            className="flex-1 bg-transparent text-sm outline-none"
          />
        </div>
        <div className="mt-1 text-center text-[10px] italic text-muted-foreground">
          This conversation won't be saved when you close.
        </div>
      </div>

      {/* Resize handle (bottom-right corner) */}
      <div
        aria-label="Resize"
        role="separator"
        className="absolute bottom-0 right-0 h-3 w-3 cursor-nwse-resize"
        style={{
          background:
            "linear-gradient(135deg, transparent 50%, hsl(var(--adp-red)) 50%)",
        }}
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          const startX = e.clientX;
          const startY = e.clientY;
          const startW = size.w;
          const startH = size.h;
          const MIN_W = 320;
          const MIN_H = 360;
          const onMove = (ev: MouseEvent) => {
            setSize({
              w: Math.max(MIN_W, startW + (ev.clientX - startX)),
              h: Math.max(MIN_H, startH + (ev.clientY - startY)),
            });
          };
          const onUp = () => {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
          };
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        }}
      />
    </div>
  );
}
