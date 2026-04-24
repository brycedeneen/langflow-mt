import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import TagChip from "@/components/common/TagChip";
import useDragStart from "@/components/core/cardComponent/hooks/use-on-drag-start";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import ExportModal from "@/modals/exportModal";
import FlowSettingsModal from "@/modals/flowSettingsModal";
import useAlertStore from "@/stores/alertStore";
import type { FlowType } from "@/types/flow";
import { coerceTagList } from "@/types/tag/runtime-validate";
import { downloadFlow } from "@/utils/reactflowUtils";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import useDescriptionModal from "../../hooks/use-description-modal";
import { useGetTemplateStyle } from "../../utils/get-template-style";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";
import { AdpAssistButton } from "./adp-assist-button";

const ListComponent = ({
  flowData,
  selected,
  setSelected,
  shiftPressed,
  selectedTagIds: _selectedTagIds,
}: {
  flowData: FlowType;
  selected: boolean;
  setSelected: (selected: boolean) => void;
  shiftPressed: boolean;
  // TODO: Filter flows by tag_id once FlowHeader/FlowRead exposes
  // the new flow_tag-backed tag list. Today the prop is accepted but
  // rendered as no-op filtering because `flow.tags` is not populated
  // by the backend. See Task 10 plan + the TODOs in Task 9 for the
  // same data gap.
  selectedTagIds?: string[];
}) => {
  const navigate = useCustomNavigate();
  const [openDelete, setOpenDelete] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { deleteFlow } = useDeleteFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { folderId } = useParams();
  const [openSettings, setOpenSettings] = useState(false);
  const [openExportModal, setOpenExportModal] = useState(false);
  const isComponent = flowData.is_component ?? false;

  const { getIcon } = useGetTemplateStyle(flowData);

  const editFlowLink = `/flow/${flowData.id}${folderId ? `/folder/${folderId}` : ""}`;

  const handleClick = async () => {
    if (shiftPressed) {
      setSelected(!selected);
    } else {
      if (!isComponent) {
        navigate(editFlowLink);
      }
    }
  };

  const handleDelete = () => {
    deleteFlow({ id: [flowData.id] })
      .then(() => {
        setSuccessData({
          title: "Selected items deleted successfully",
        });
      })
      .catch(() => {
        setErrorData({
          title: "Error deleting items",
          list: ["Please try again"],
        });
      });
  };

  const { onDragStart } = useDragStart(flowData);

  const descriptionModal = useDescriptionModal(
    [flowData?.id],
    flowData.is_component ? "component" : "flow",
  );

  const swatchIndex =
    (flowData.gradient && !isNaN(parseInt(flowData.gradient))
      ? parseInt(flowData.gradient)
      : getNumberFromString(flowData.gradient ?? flowData.id)) %
    swatchColors.length;

  const handleExport = () => {
    if (flowData.is_component) {
      downloadFlow(flowData, flowData.name, flowData.description);
      setSuccessData({ title: `${flowData.name} exported successfully` });
    } else {
      setOpenExportModal(true);
    }
  };

  const [icon, setIcon] = useState<string>("");

  useEffect(() => {
    getIcon().then(setIcon);
  }, [getIcon]);

  return (
    <>
      <Card
        key={flowData.id}
        draggable
        onDragStart={onDragStart}
        onClick={handleClick}
        className={`flex flex-row bg-background ${
          isComponent ? "cursor-default" : "cursor-pointer"
        } group justify-between rounded-lg border-none px-4 py-3 shadow-none hover:bg-muted`}
        data-testid="list-card"
      >
        <div
          className={`flex min-w-0 ${
            isComponent ? "cursor-default" : "cursor-pointer"
          } items-center gap-4`}
        >
          <div className="group/checkbox relative flex items-center">
            <div
              className={cn(
                "z-20 flex w-0 items-center transition-all duration-300",
                selected && "w-10",
              )}
            >
              <Checkbox
                checked={selected}
                onCheckedChange={(checked) => setSelected(checked as boolean)}
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "ml-2 transition-opacity focus-visible:ring-0",
                  !selected && "opacity-0 group-hover/checkbox:opacity-100",
                )}
                data-testid={`checkbox-${flowData.id}`}
              />
            </div>
            <div
              className={cn(
                `item-center flex justify-center rounded-lg p-1.5 transition-opacity duration-200`,
                swatchColors[swatchIndex],
                selected
                  ? "duration-300"
                  : "group-hover/checkbox:pointer-events-none group-hover/checkbox:opacity-0",
              )}
            >
              <ForwardedIconComponent
                name={flowData?.icon || icon}
                aria-hidden="true"
                className="flex h-5 w-5 items-center justify-center"
              />
            </div>
          </div>

          <div className="flex min-w-0 flex-col justify-start">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
              <div
                className="flex min-w-0 shrink truncate text-sm font-semibold"
                data-testid={`flow-name-div`}
              >
                <span
                  className="truncate"
                  data-testid={`flow-name-${flowData.id}`}
                >
                  {flowData.name}
                </span>
              </div>
              <div className="flex min-w-0 shrink text-xs text-muted-foreground">
                <span className="truncate">
                  Edited {timeElapsed(flowData.updated_at)} ago
                </span>
              </div>
            </div>
            {/* Tag chips — wrapped in truthy-length check so cards without
                tags don't render an empty row. */}
            {/* TODO: Server-side Flow/Template read shapes don't yet expose tags — see types/tag/runtime-validate.ts. */}
            {(() => {
              const rowTags = coerceTagList(
                (flowData as { tags?: unknown }).tags,
              );
              if (rowTags.length === 0) return null;
              const MAX = 2;
              const visible = rowTags.slice(0, MAX);
              const overflow = Math.max(0, rowTags.length - MAX);
              return (
                <div
                  className="mt-1 flex flex-wrap gap-1"
                  data-testid={`flow-tags-${flowData.id}`}
                >
                  {visible.map((t) => (
                    <TagChip key={t.id} tag={t} />
                  ))}
                  {overflow > 0 && (
                    <ShadTooltip
                      content={rowTags
                        .slice(MAX)
                        .map((t) => t.name)
                        .join(", ")}
                    >
                      <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                        +{overflow}
                      </span>
                    </ShadTooltip>
                  )}
                </div>
              );
            })()}
          </div>
        </div>

        <div className="ml-5 flex items-center gap-2">
          <AdpAssistButton
            flowId={flowData.id}
            builtWithAssist={!!flowData.built_with_assist}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="iconMd"
                data-testid="home-dropdown-menu"
                className="group"
              >
                <ForwardedIconComponent
                  name="Ellipsis"
                  aria-hidden="true"
                  className="h-5 w-5 text-muted-foreground group-hover:text-foreground"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="w-[185px]"
              sideOffset={5}
              side="bottom"
            >
              <DropdownComponent
                flowData={flowData}
                setOpenDelete={setOpenDelete}
                handleExport={handleExport}
                handleEdit={() => {
                  setOpenSettings(true);
                }}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </Card>
      {openDelete && (
        <DeleteConfirmationModal
          open={openDelete}
          setOpen={setOpenDelete}
          onConfirm={handleDelete}
          description={descriptionModal}
          note={!flowData.is_component ? "and its message history" : ""}
        />
      )}
      <ExportModal
        open={openExportModal}
        setOpen={setOpenExportModal}
        flowData={flowData}
      />
      <FlowSettingsModal
        open={openSettings}
        setOpen={setOpenSettings}
        flowData={flowData}
      />
    </>
  );
};

export default ListComponent;
