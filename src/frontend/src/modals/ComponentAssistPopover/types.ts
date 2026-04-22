export type ThreadMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; proposals?: ProposalPayload[] };

export type ProposalPayload = {
  id: string;
  nodeId: string;
  patch: Record<string, unknown>;
  rationale: string;
  applied?: { skippedKeys: string[] } | null;
};
