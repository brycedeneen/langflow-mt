import { useShallow } from "zustand/react/shallow";
import { PSRequestButton } from "@/components/core/proServiceQuotes/PSRequestButton";
import { useIsPlatformAdmin } from "@/hooks/use-is-platform-admin";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import AssistantToggleButton from "./assistant-toggle-button";
import CostEstimateBadge from "./cost-estimate-badge";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";

type FlowToolbarOptionsProps = {
  openApiModal: boolean;
  setOpenApiModal: (open: boolean | ((prev: boolean) => boolean)) => void;
};
const FlowToolbarOptions = ({
  openApiModal,
  setOpenApiModal,
}: FlowToolbarOptionsProps) => {
  const hasIO = useFlowStore((state) => state.hasIO);

  // Pro-Service Quote gating: render the Request PS button only for the
  // flow owner, an org admin, or a platform admin. Mirrors the backend
  // ``can_submit`` permission check in
  // ``services/professional_services/permissions.py`` so users without
  // backend permission don't see a CTA they'd just hit a 403 on.
  const { currentFlowId, currentFlowOwnerId, psRequestActive } =
    useFlowsManagerStore(
      useShallow((s) => ({
        currentFlowId: s.currentFlow?.id,
        currentFlowOwnerId: s.currentFlow?.user_id,
        psRequestActive: Boolean(s.currentFlow?.ps_request_active),
      })),
    );
  const isPlatformAdmin = useIsPlatformAdmin();
  const userId = useAuthStore((s) => s.userData?.id);
  // Owner check covers the common case; org-admin elevation lands when the
  // membership-list hook is wired in (intentionally deferred — frontend
  // currently lacks a synchronous ``isOrgAdmin(orgId)`` selector).
  const isFlowOwner = Boolean(
    userId && currentFlowOwnerId && userId === currentFlowOwnerId,
  );
  const canRequestPS = Boolean(currentFlowId) && (isFlowOwner || isPlatformAdmin);

  return (
    <div className="flex items-center gap-1">
      <AssistantToggleButton />
      <CostEstimateBadge />
      {currentFlowId && (
        <PSRequestButton
          flowId={currentFlowId}
          canRequest={canRequestPS}
          psRequestActive={psRequestActive}
        />
      )}
      <PlaygroundButton hasIO={hasIO} />
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
    </div>
  );
};

export default FlowToolbarOptions;
