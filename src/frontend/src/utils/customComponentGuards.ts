import useAuthStore from "@/stores/authStore";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";

/**
 * Returns true when the current caller is allowed to author or run
 * custom Python components. Platform admins always return true. Other
 * users return true only when the deployment has
 * LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true.
 *
 * See docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.
 */
export function useCustomComponentsAllowed(): boolean {
  const isPlatformAdmin = useAuthStore(
    (state: any) => state.userData?.is_platform_admin,
  );
  const { data: config } = useGetConfig({});
  return Boolean(isPlatformAdmin || config?.allow_custom_components);
}

/**
 * Walks a parsed flow JSON and returns true if it contains at least
 * one node with a custom-code payload. Used by the flow-import UX
 * precheck (Task 11) — the backend gate is the real enforcement.
 *
 * Accepts either a bare flow shape (``{nodes, edges}``) or the
 * wrapped shape (``{data: {nodes, edges}}``). A node is "custom" when
 * its ``data.node.template.code.value`` is a non-empty string.
 */
export function flowJsonHasCustomComponent(flow: unknown): boolean {
  if (!flow || typeof flow !== "object") return false;
  const nodes =
    (flow as any)?.data?.nodes ?? (flow as any)?.nodes;
  if (!Array.isArray(nodes)) return false;
  for (const node of nodes) {
    const code = node?.data?.node?.template?.code?.value;
    if (typeof code === "string" && code.trim().length > 0) {
      return true;
    }
  }
  return false;
}
