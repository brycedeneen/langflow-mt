import { useEffect, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import TagPicker from "@/components/common/TagPicker";
import { PSRequestButton } from "@/components/core/proServiceQuotes/PSRequestButton";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useAssignFlowTags } from "@/controllers/API/queries/tags";
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

function FlowTagsButton() {
  const currentFlow = useFlowsManagerStore((s) => s.currentFlow);
  const [open, setOpen] = useState(false);
  // currentSavedFlow.tags is populated by FlowRead (see 0b5d4aae7c). If
  // the toolbar mounts before the saved flow is available, start empty.
  const [selectedIds, setSelectedIds] = useState<string[]>(
    currentFlow?.tags?.map((t) => t.id) ?? [],
  );
  const assignFlowTags = useAssignFlowTags();

  // Re-sync when the underlying flow's tags change (e.g. assigned from
  // another surface like the save-as-template modal).
  useEffect(() => {
    setSelectedIds(currentFlow?.tags?.map((t) => t.id) ?? []);
  }, [currentFlow?.tags]);

  if (!currentFlow?.id) return null;

  const handleChange = (ids: string[]) => {
    setSelectedIds(ids);
    assignFlowTags.mutate({ flowId: currentFlow.id, tagIds: ids });
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <ShadTooltip content="Tags">
        <PopoverTrigger asChild>
          <button
            type="button"
            data-testid="flow-tags-btn"
            className="relative inline-flex h-8 items-center justify-center gap-1.5 rounded px-2 text-sm font-normal text-muted-foreground hover:bg-muted"
          >
            <ForwardedIconComponent name="Tag" className="h-4 w-4" />
            <span className="font-normal text-mmd">Tags</span>
          </button>
        </PopoverTrigger>
      </ShadTooltip>
      <PopoverContent align="end" className="w-80">
        <div className="flex flex-col gap-2">
          <div className="text-sm font-medium">Flow tags</div>
          <TagPicker
            selectedIds={selectedIds}
            onChange={handleChange}
            disabled={assignFlowTags.isPending}
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}

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
      <FlowTagsButton />
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
