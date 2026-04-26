import React, {
  type Dispatch,
  ReactNode,
  type SetStateAction,
  useState,
} from "react";
import { useHref } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import { CustomLink } from "@/customization/components/custom-link";
import { ENABLE_PUBLISH } from "@/customization/feature-flags";
import { customMcpOpen } from "@/customization/utils/custom-mcp-open";
import ApiModal from "@/modals/apiModal";
import ExportModal from "@/modals/exportModal";
import SaveAsTemplateModal from "@/modals/SaveAsTemplateModal";
import FlowAuditDrawer from "./flow-audit-drawer";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";

type PublishDropdownProps = {
  openApiModal: boolean;
  setOpenApiModal: Dispatch<SetStateAction<boolean>>;
  children?: ReactNode;
};

export default function PublishDropdown({
  openApiModal,
  setOpenApiModal,
  children,
}: PublishDropdownProps) {
  const location = useHref("/");
  const domain = window.location.origin + location;
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flowId = currentFlow?.id;
  const flowName = currentFlow?.name;
  const folderId = currentFlow?.folder_id;
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync } = usePatchUpdateFlow();
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const isPublished = currentFlow?.access_type === "PUBLIC";
  const hasIO = useFlowStore((state) => state.hasIO);
  const isSuperuser =
    useAuthStore((state) => state.userData?.is_superuser) === true;
  const [openExportModal, setOpenExportModal] = useState(false);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const [openAuditDrawer, setOpenAuditDrawer] = useState(false);

  const handlePublishedSwitch = async (checked: boolean) => {
    mutateAsync(
      {
        id: flowId ?? "",
        access_type: checked ? "PRIVATE" : "PUBLIC",
      },
      {
        onSuccess: (updatedFlow) => {
          if (flows) {
            setFlows(
              flows.map((flow) => {
                if (flow.id === updatedFlow.id) {
                  return updatedFlow;
                }
                return flow;
              }),
            );
            setCurrentFlow(updatedFlow);
          } else {
            setErrorData({
              title: "Failed to save flow",
              list: ["Flows variable undefined"],
            });
          }
        },
        onError: (e) => {
          setErrorData({
            title: "Failed to save flow",
            list: [e.message],
          });
        },
      },
    );
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="md"
            className="!px-2.5 font-normal"
            data-testid="publish-button"
          >
            More
            <IconComponent name="ChevronDown" className="!h-5 !w-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          forceMount
          sideOffset={7}
          alignOffset={-2}
          align="end"
          className="w-full min-w-[275px]"
        >
          <DropdownMenuItem
            className="deploy-dropdown-item group"
            onClick={() => setOpenApiModal(true)}
            data-testid="api-access-item"
          >
            <IconComponent name="Code2" className={`icon-size mr-2`} />
            <span>API access</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="deploy-dropdown-item group"
            onClick={() => setOpenExportModal(true)}
          >
            <IconComponent name="Download" className={`icon-size mr-2`} />
            <span>Export</span>
          </DropdownMenuItem>
          {isSuperuser && (
            <DropdownMenuItem
              className="deploy-dropdown-item group"
              onClick={() => setSaveTemplateOpen(true)}
            >
              <IconComponent name="FileText" className={`icon-size mr-2`} />
              <span>Save as Template</span>
            </DropdownMenuItem>
          )}
          <CustomLink
            className={cn("flex-1")}
            to={`/mcp/folder/${folderId}`}
            target={customMcpOpen()}
          >
            <DropdownMenuItem
              className="deploy-dropdown-item group"
              onClick={() => {}}
              data-testid="mcp-server-item"
            >
              <IconComponent name="Mcp" className={`icon-size mr-2`} />
              <span>MCP Server</span>
              <IconComponent
                name="ExternalLink"
                className={`icon-size ml-auto hidden group-hover:block`}
              />
            </DropdownMenuItem>
          </CustomLink>
          {flowId && (
            <DropdownMenuItem
              className="deploy-dropdown-item group"
              onClick={() => setOpenAuditDrawer(true)}
              data-testid="flow-history-item"
            >
              <IconComponent name="History" className="icon-size mr-2" />
              <span>Flow history</span>
            </DropdownMenuItem>
          )}
          {ENABLE_PUBLISH && (
            <DropdownMenuItem
              className="deploy-dropdown-item group"
              disabled={!hasIO}
              onClick={() => {}}
              data-testid="shareable-playground"
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center">
                  <Tooltip delayDuration={500}>
                    <TooltipTrigger asChild>
                      <div className="flex items-center">
                        <IconComponent
                          name="Globe"
                          className={cn(
                            `icon-size mr-2`,
                            !isPublished && "opacity-50",
                          )}
                        />

                        {isPublished ? (
                          <CustomLink
                            className="flex-1"
                            to={`/playground/${flowId}`}
                            target="_blank"
                          >
                            <span>Shareable Playground</span>
                          </CustomLink>
                        ) : (
                          <span className={cn(!isPublished && "opacity-50")}>
                            Shareable Playground
                          </span>
                        )}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent
                      className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground truncate"
                      side="left"
                      avoidCollisions={false}
                      sticky="always"
                    >
                      {hasIO
                        ? isPublished
                          ? encodeURI(`${domain}/playground/${flowId}`)
                          : "Activate to share a public version of this Playground"
                        : "Add a Chat Input or Chat Output to access your flow"}
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Switch
                  data-testid="publish-switch"
                  className="scale-[85%]"
                  checked={isPublished}
                  disabled={!hasIO}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handlePublishedSwitch(isPublished);
                  }}
                />
              </div>
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <ApiModal open={openApiModal} setOpen={setOpenApiModal}>
        <>{children}</>
      </ApiModal>
      <ExportModal open={openExportModal} setOpen={setOpenExportModal} />
      <SaveAsTemplateModal
        open={saveTemplateOpen}
        onClose={() => setSaveTemplateOpen(false)}
        flow={{
          id: currentFlow?.id,
          description: currentFlow?.description,
          data: {
            nodes: currentFlow?.data?.nodes ?? [],
            edges: currentFlow?.data?.edges ?? [],
          },
        }}
      />
      {flowId && (
        <FlowAuditDrawer
          flowId={flowId}
          open={openAuditDrawer}
          onClose={() => setOpenAuditDrawer(false)}
        />
      )}
    </>
  );
}
