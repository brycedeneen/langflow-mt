import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import TagPicker from "@/components/common/TagPicker";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useAssignFlowTags } from "@/controllers/API/queries/tags";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import CostEstimateBadge from "./cost-estimate-badge";
import PublishDropdown from "./deploy-dropdown";
import PlaygroundButton from "./playground-button";
import AssistantToggleButton from "./assistant-toggle-button";

type FlowToolbarOptionsProps = {
  openApiModal: boolean;
  setOpenApiModal: (open: boolean | ((prev: boolean) => boolean)) => void;
};

function FlowTagsButton() {
  const currentFlow = useFlowsManagerStore((s) => s.currentFlow);
  const [open, setOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const assignFlowTags = useAssignFlowTags();

  // TODO: initialize from flow.tags once the backend Flow read shape exposes
  // the new flow_tag-backed tag IDs. Currently starts empty; users who add
  // a tag via this button will replace (via PUT-replaces-set) whatever the
  // server thinks the flow's tags are. Acceptable for now since (a) flows
  // seldom have tags today and (b) any stale tag state is visible via the
  // sidebar chip row that Task 10 will add.
  //
  // Note: firing `useAssignFlowTags.mutate` on EVERY change (see handleChange)
  // is the correct behavior here — the user clicking a chip = immediate intent,
  // not a form submit. No length-check gate (unlike the template modals).
  useEffect(() => {
    setSelectedIds([]);
  }, [currentFlow?.id]);

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

  return (
    <div className="flex items-center gap-1">
      <AssistantToggleButton />
      <FlowTagsButton />
      <CostEstimateBadge />
      <PlaygroundButton hasIO={hasIO} />
      <PublishDropdown
        openApiModal={openApiModal}
        setOpenApiModal={setOpenApiModal}
      />
    </div>
  );
};

export default FlowToolbarOptions;
