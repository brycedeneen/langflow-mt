export const WEBHOOK_LIKE_NODE_TYPES = ["webhook", "adptrigger"] as const;

export function isWebhookLikeNodeType(nodeType?: string | null): boolean {
  if (!nodeType) return false;
  return (WEBHOOK_LIKE_NODE_TYPES as readonly string[]).includes(
    nodeType.toLowerCase(),
  );
}
