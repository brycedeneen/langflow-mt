import { useUpdateNodeInternals } from "@xyflow/react";
import _, { cloneDeep } from "lodash";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import useHandleNodeClass from "@/CustomNodes/hooks/use-handle-node-class";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import ToggleShadComponent from "@/components/core/parameterRenderComponent/components/toggleShadComponent";
import { Button } from "@/components/ui/button";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { usePostRetrieveVertexOrder } from "@/controllers/API/queries/vertex";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import useAddFlow from "@/hooks/flows/use-add-flow";
import type { APIClassType } from "@/types/api";
import { Delete, Hammer, MoreHorizontal, Trash2 } from "lucide-react";
import {
  Select,
  SelectContentWithoutPortal,
  SelectItem,
  SelectTrigger,
} from "../../../../components/ui/select-custom";
import useAlertStore from "../../../../stores/alertStore";
import useAuthStore from "../../../../stores/authStore";
import { canViewCodeButton } from "./utils/can-view-code-button";
import useComponentAssistStore from "../../../../stores/componentAssistStore";
import { useDarkStore } from "../../../../stores/darkStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useStoreStore } from "../../../../stores/storeStore";
import type { nodeToolbarPropsType } from "../../../../types/components";
import type { FlowType } from "../../../../types/flow";
import {
  checkHasToolMode,
  createFlowComponent,
  downloadNode,
  expandGroupNode,
  updateFlowPosition,
} from "../../../../utils/reactflowUtils";
import { cn, getNodeLength } from "../../../../utils/utils";
import { ToolbarButton } from "./components/toolbar-button";
import ToolbarModals from "./components/toolbar-modals";
import useShortcuts from "./hooks/use-shortcuts";
import ShortcutDisplay from "./shortcutDisplay";
import ToolbarSelectItem from "./toolbarSelectItem";

const NodeToolbarComponent = memo(
  ({
    data,
    deleteNode,
    setShowNode,
    numberOfOutputHandles,
    showNode,
    name = "code",
    onCloseAdvancedModal,
    updateNode,
    isOutdated,
    isUserEdited,
    hasBreakingChange,
    setOpenShowMoreOptions,
    openDropdownOnRightClick = false,
  }: nodeToolbarPropsType & {
    openDropdownOnRightClick?: boolean;
  }): JSX.Element => {
    const version = useDarkStore((state) => state.version);
    const [showModalAdvanced, setShowModalAdvanced] = useState(false);
    const [showconfirmShare, setShowconfirmShare] = useState(false);
    const [showOverrideModal, setShowOverrideModal] = useState(false);
    const [flowComponent, setFlowComponent] = useState<FlowType>(
      createFlowComponent(cloneDeep(data), version),
    );
    const updateFreezeStatus = useFlowStore(
      (state) => state.updateFreezeStatus,
    );
    const { hasStore, hasApiKey, validApiKey } = useStoreStore(
      useShallow((state) => ({
        hasStore: state.hasStore,
        hasApiKey: state.hasApiKey,
        validApiKey: state.validApiKey,
      })),
    );
    const shortcuts = useShortcutsStore((state) => state.shortcuts);
    const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
    const [openModal, setOpenModal] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const frozen = data.node?.frozen ?? false;
    const updateNodeInternals = useUpdateNodeInternals();

    const paste = useFlowStore((state) => state.paste);
    const setNodes = useFlowStore((state) => state.setNodes);
    const setEdges = useFlowStore((state) => state.setEdges);
    const edges = useFlowStore((state) => state.edges);
    const getNodePosition = useFlowStore((state) => state.getNodePosition);
    const flows = useFlowsManagerStore((state) => state.flows);
    const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
    const { mutate: FreezeAllVertices } = usePostRetrieveVertexOrder({
      onSuccess: ({ vertices_to_run }) => {
        updateFreezeStatus(vertices_to_run, !data.node?.frozen);
        vertices_to_run.forEach((vertex) => {
          updateNodeInternals(vertex);
        });
      },
    });

    const postToolModeValue = usePostTemplateValue({
      node: data.node!,
      nodeId: data.id,
      parameterId: "tool_mode",
    });

    const isSaved = flows?.some((flow) =>
      Object.values(flow).includes(data.node?.display_name!),
    );

    const userData = useAuthStore((state) => state.userData);

    const nodeLength = useMemo(() => getNodeLength(data), [data]);
    const hasCode = useMemo(
      () => Object.keys(data.node!.template).includes("code"),
      [data.node],
    );
    const canViewCode = useMemo(
      () => canViewCodeButton({ hasCode, isSuperuser: userData?.is_superuser }),
      [hasCode, userData?.is_superuser],
    );

    // ADP Assist opt-in: suppressed when the component sets assist_enabled=False
    // (e.g., DataMapperComponent, which ships with its own bespoke agent).
    const assistEnabled = data.node?.assist_enabled !== false;
    const openComponentAssist = useComponentAssistStore((s) => s.open);
    const toolbarAnchorRef = useRef<HTMLDivElement>(null);
    const isGroup = useMemo(
      () => (data.node?.flow ? true : false),
      [data.node],
    );

    const hasToolMode = useMemo(
      () => checkHasToolMode(data.node?.template ?? {}) && !isGroup,
      [data.node?.template, isGroup],
    );
    const addFlow = useAddFlow();

    const hasGroupOutputs = data.node?.outputs?.some?.(
      (output) => output.group_outputs,
    );
    const hasOutputs =
      data.node?.outputs?.length && data.node?.outputs?.length > 1;

    const hasSelectOutput = hasOutputs && !hasGroupOutputs;
    const hasOnlyOneOutput = data.node?.outputs?.length === 1;
    const hasMaximumOneConnectedInput =
      edges.filter((edge) => edge.target === data.id).length <= 1;

    const isMinimal =
      (hasSelectOutput || hasOnlyOneOutput) && hasMaximumOneConnectedInput;

    const [toolMode, setToolMode] = useState(
      () =>
        data.node?.tool_mode ||
        data.node?.outputs?.some(
          (output) => output.name === "component_as_tool",
        ) ||
        false,
    );

    useEffect(() => {
      if (data.node?.tool_mode !== undefined) {
        setToolMode(
          data.node?.tool_mode ||
            data.node?.outputs?.some(
              (output) => output.name === "component_as_tool",
            ) ||
            false,
        );
      }
    }, [data.node?.tool_mode, data.node?.outputs]);

    const { handleNodeClass: handleNodeClassHook } = useHandleNodeClass(
      data.id,
    );

    const handleNodeClass = (newNodeClass: APIClassType, type: string) => {
      handleNodeClassHook(newNodeClass, type);
    };

    const handleActivateToolMode = () => {
      const newValue = !toolMode;
      setToolMode(newValue);
      mutateTemplate(
        newValue,
        data.id,
        data.node!,
        handleNodeClass,
        postToolModeValue,
        setErrorData,
        "tool_mode",
        () => updateNodeInternals(data.id),
        newValue,
      );
    };

    const handleMinimize = useCallback(() => {
      if (isMinimal || !showNode) {
        setShowNode(!showNode);
        updateNodeInternals(data.id);
        return;
      }
      setNoticeData({
        title:
          "Minimization is only available for components with one active connection or fewer.",
      });
    }, [isMinimal, showNode, data.id]);

    useEffect(() => {
      if (!isMinimal && !showNode) {
        setShowNode(true);
        updateNodeInternals(data.id);
        return;
      }
    }, [isMinimal, showNode, data.id]);

    const handleungroup = useCallback(() => {
      if (isGroup) {
        takeSnapshot();
        expandGroupNode(
          data.id,
          updateFlowPosition(getNodePosition(data.id), data.node?.flow!),
          data.node!.template,
          setNodes,
          setEdges,
          data.node?.outputs,
        );
      }
    }, [
      isGroup,
      data.id,
      data.node?.flow,
      data.node?.template,
      data.node?.outputs,
      setNodes,
      setEdges,
      takeSnapshot,
      getNodePosition,
      updateFlowPosition,
      expandGroupNode,
    ]);

    const shareComponent = useCallback(() => {
      if (hasApiKey || hasStore) {
        setShowconfirmShare((state) => !state);
      }
    }, [hasApiKey, hasStore]);

    const handleCodeModal = useCallback(() => {
      if (!canViewCode) {
        setNoticeData({ title: `You can not access ${data.id} code` });
        return;
      }
      setOpenModal((state) => !state);
    }, [canViewCode, data.id]);

    const saveComponent = useCallback(() => {
      if (isSaved) {
        setShowOverrideModal((state) => !state);
        return;
      }
      addFlow({
        flow: flowComponent,
        override: false,
      });
      setSuccessData({ title: `${data.id} saved successfully` });
    }, [isSaved, data.id, flowComponent, addFlow]);

    const openDocs = useCallback(() => {
      if (data.node?.documentation) {
        return customOpenNewTab(data.node.documentation);
      }
      setNoticeData({
        title: `${data.id} docs is not available at the moment.`,
      });
    }, [data.id, data.node?.documentation]);

    const handleDownloadNode = useCallback(async () => {
      try {
        await downloadNode(flowComponent!);
        setSuccessData({
          title: `${flowComponent?.name || "Node"} downloaded successfully`,
        });
      } catch (error) {
        console.error("Error downloading node:", error);
        const nodeName = flowComponent?.name || "Node";
        setErrorData({
          title: `Failed to download ${nodeName}`,
          list: [error instanceof Error ? error.message : "Unknown error"],
        });
      }
    }, [flowComponent]);

    useShortcuts({
      showOverrideModal,
      showModalAdvanced,
      openModal,
      showconfirmShare,
      FreezeAllVertices: () => {
        FreezeAllVertices({ flowId: currentFlowId, stopNodeId: data.id });
      },
      downloadFunction: () => downloadNode(flowComponent!),
      displayDocs: openDocs,
      saveComponent,
      showAdvance: () => setShowModalAdvanced((state) => !state),
      handleCodeModal,
      shareComponent,
      ungroup: handleungroup,
      minimizeFunction: handleMinimize,
      activateToolMode: handleActivateToolMode,
      hasToolMode,
    });

    useEffect(() => {
      if (!showModalAdvanced) {
        onCloseAdvancedModal!(false);
      }
    }, [showModalAdvanced]);

    // Open dropdown when right-clicked
    useEffect(() => {
      if (openDropdownOnRightClick) {
        setDropdownOpen(true);
      } else {
        setDropdownOpen(false);
      }
    }, [openDropdownOnRightClick]);

    const setLastCopiedSelection = useFlowStore(
      (state) => state.setLastCopiedSelection,
    );

    const setSuccessData = useAlertStore((state) => state.setSuccessData);
    const setNoticeData = useAlertStore((state) => state.setNoticeData);
    const setErrorData = useAlertStore((state) => state.setErrorData);

    useEffect(() => {
      setFlowComponent(createFlowComponent(cloneDeep(data), version));
    }, [
      data,
      data.node,
      data.node?.display_name,
      data.node?.description,
      data.node?.template,
      showModalAdvanced,
      showconfirmShare,
    ]);

    const [selectedValue, setSelectedValue] = useState(null);

    const handleSelectChange = useCallback(
      (event) => {
        let nodes;
        setSelectedValue(event);

        // Clear right-clicked state when user selects an option
        if (openDropdownOnRightClick) {
          const setRightClickedNodeId =
            useFlowStore.getState().setRightClickedNodeId;
          setRightClickedNodeId(null);
        }

        switch (event) {
          case "save":
            saveComponent();
            break;
          case "freezeAll":
            takeSnapshot();
            FreezeAllVertices({ flowId: currentFlowId, stopNodeId: data.id });
            break;
          case "code":
            setOpenModal(!openModal);
            break;
          case "advanced":
            setShowModalAdvanced(true);
            break;
          case "show":
            takeSnapshot();
            handleMinimize();
            break;
          case "Share":
            shareComponent();
            break;
          case "Download":
            handleDownloadNode();
            break;
          case "SaveAll":
            addFlow({
              flow: flowComponent,
              override: false,
            });
            break;
          case "documentation":
            openDocs();
            break;
          case "disabled":
            break;
          case "ungroup":
            handleungroup();
            break;
          case "override":
            setShowOverrideModal(true);
            break;
          case "delete":
            deleteNode(data.id);
            break;
          case "update":
            updateNode();
            break;
          case "copy": {
            nodes = useFlowStore.getState().nodes;
            const node = nodes.filter((node) => node.id === data.id);
            setLastCopiedSelection({ nodes: _.cloneDeep(node), edges: [] });
            break;
          }
          case "duplicate":
            nodes = useFlowStore.getState().nodes;
            paste(
              {
                nodes: [nodes.find((node) => node.id === data.id)!],
                edges: [],
              },
              {
                x: 50,
                y: 10,
                paneX: nodes.find((node) => node.id === data.id)?.position.x,
                paneY: nodes.find((node) => node.id === data.id)?.position.y,
              },
            );
            break;
          case "toolMode":
            handleActivateToolMode();
            break;
        }

        setSelectedValue(null);
      },
      [
        saveComponent,
        FreezeAllVertices,
        setOpenModal,
        setShowModalAdvanced,
        handleMinimize,
        shareComponent,
        downloadNode,
        addFlow,
        openDocs,
        handleungroup,
        setShowOverrideModal,
        deleteNode,
        updateNode,
        setLastCopiedSelection,
        paste,
        handleActivateToolMode,
        toolMode,
      ],
    );

    const { handleOnNewValue: handleOnNewValueHook } = useHandleOnNewValue({
      node: data.node!,
      nodeId: data.id,
      name,
    });

    const handleOnNewValue = (value: string | string[]) => {
      handleOnNewValueHook({ value });
    };

    const inspectionPanelVisible = useFlowStore(
      (state) => state.inspectionPanelVisible,
    );

    const selectTriggerRef = useRef(null);

    const handleButtonClick = () => {
      (selectTriggerRef.current! as HTMLElement)?.click();
    };

    const handleOpenChange = (open: boolean) => {
      setOpenShowMoreOptions && setOpenShowMoreOptions(open);
      setDropdownOpen(open);

      // Clear right-clicked state when dropdown closes without selection
      if (!open && openDropdownOnRightClick) {
        const setRightClickedNodeId =
          useFlowStore.getState().setRightClickedNodeId;
        setRightClickedNodeId(null);
      }
    };

    const isCustomComponent = useMemo(() => {
      const isCustom = data.type === "CustomComponent" && !data.node?.edited;
      if (isCustom && !inspectionPanelVisible) {
        data.node.edited = true;
      }
      return isCustom;
    }, [data.type, data.node]);

    const renderToolbarButtons = useMemo(
      () => (
        <>
          {assistEnabled && (
            <ToolbarButton
              className="text-adp-red"
              icon="Sparkles"
              label="Assist"
              onClick={() => {
                const rect =
                  toolbarAnchorRef.current?.getBoundingClientRect() ?? null;
                openComponentAssist(data.id, rect, currentFlowId || null);
              }}
              dataTestId="component-assist-button"
            />
          )}
          {canViewCode && (
            <ToolbarButton
              className={isCustomComponent ? "animate-pulse-pink" : ""}
              icon="Code"
              label="Code"
              onClick={() => setOpenModal(true)}
              shortcut={shortcuts.find((s) =>
                s.name.toLowerCase().startsWith("code"),
              )}
              dataTestId="code-button-modal"
            />
          )}
          {nodeLength > 0 && !inspectionPanelVisible && (
            <ToolbarButton
              icon="SlidersHorizontal"
              label="Controls"
              onClick={() => setShowModalAdvanced(true)}
              shortcut={shortcuts.find((s) =>
                s.name.toLowerCase().startsWith("advanced"),
              )}
              dataTestId="edit-button-modal"
            />
          )}
          {(!hasToolMode || inspectionPanelVisible) && (
            <ToolbarButton
              icon="FreezeAll"
              label="Freeze"
              dataTestId="freeze-all-button-modal"
              onClick={() => {
                takeSnapshot();
                FreezeAllVertices({
                  flowId: currentFlowId,
                  stopNodeId: data.id,
                });
              }}
              shortcut={shortcuts.find((s) =>
                s.name.toLowerCase().startsWith("freeze"),
              )}
              className={cn(
                "node-toolbar-buttons",
                frozen && "text-accent-indigo-foreground",
              )}
            />
          )}
          {hasToolMode && (
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <Button
                  asChild
                  className={cn(
                    "node-toolbar-buttons h-[2rem]",
                    toolMode && "text-primary",
                  )}
                  variant="ghost"
                  size="node-toolbar"
                  data-testid="tool-mode-button"
                >
                  <div
                    className="flex items-center gap-2"
                    role="button"
                    tabIndex={0}
                    onClick={(event) => {
                      event.preventDefault();
                      takeSnapshot();
                      handleSelectChange("toolMode");
                    }}
                  >
                    <Hammer
                      className={cn(
                        "h-4 w-4 transition-all",
                        toolMode ? "text-primary" : "",
                      )}
                    />
                    <span className="text-mmd font-medium">Tool Mode</span>
                    <ToggleShadComponent
                      value={toolMode}
                      editNode={false}
                      handleOnNewValue={() => {
                        takeSnapshot();
                        handleSelectChange("toolMode");
                      }}
                      disabled={false}
                      size="medium"
                      showToogle={false}
                      id="tool-mode-toggle"
                    />
                  </div>
                </Button>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                side="top"
                avoidCollisions={false}
                sticky="always"
              >
                <ShortcutDisplay
                  {...shortcuts.find(
                    ({ name }) => name.toLowerCase() === "tool mode",
                  )!}
                />
              </TooltipContent>
            </Tooltip>
          )}
        </>
      ),
      [
        assistEnabled,
        canViewCode,
        nodeLength,
        hasToolMode,
        toolMode,
        data.id,
        takeSnapshot,
        FreezeAllVertices,
        currentFlowId,
        shortcuts,
        frozen,
        handleSelectChange,
        openComponentAssist,
        isCustomComponent,
        inspectionPanelVisible,
      ],
    );

    return (
      <>
        <div className="noflow nopan nodelete nodrag">
          <div ref={toolbarAnchorRef} className="flex h-10 items-center gap-1 rounded-xl border border-border bg-background p-1 shadow-xs">
            {renderToolbarButtons}
            <Select
              onValueChange={handleSelectChange}
              value={selectedValue!}
              onOpenChange={handleOpenChange}
              open={dropdownOpen}
            >
              <SelectTrigger className="w-auto">
                <Tooltip delayDuration={500}>
                  <TooltipTrigger asChild>
                    <div data-testid="more-options-modal">
                      <Button
                        className="node-toolbar-buttons h-[2rem] w-[2rem]"
                        variant="ghost"
                        onClick={handleButtonClick}
                        size="node-toolbar"
                        asChild
                      >
                        <MoreHorizontal
                          className="h-4 w-4"
                        />
                      </Button>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent
                    className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                    side="top"
                    avoidCollisions={false}
                    sticky="always"
                  >
                    Show More
                  </TooltipContent>
                </Tooltip>
              </SelectTrigger>
              <SelectContentWithoutPortal
                className={"relative top-1 w-56 bg-background"}
              >
                <SelectItem value={"save"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Save Component")
                        ?.shortcut!
                    }
                    value={"Save"}
                    icon={"SaveAll"}
                    dataTestId="save-button-modal"
                  />
                </SelectItem>
                <SelectItem value={"duplicate"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Duplicate")
                        ?.shortcut!
                    }
                    value={"Duplicate"}
                    icon={"Copy"}
                    dataTestId="copy-button-modal"
                  />
                </SelectItem>
                <SelectItem value={"copy"}>
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Copy")?.shortcut!
                    }
                    value={"Copy"}
                    icon={"Clipboard"}
                    dataTestId="copy-button-modal"
                  />
                </SelectItem>
                {isOutdated && (
                  <SelectItem value={"update"}>
                    <ToolbarSelectItem
                      shortcut={
                        shortcuts.find((obj) => obj.name === "Update")
                          ?.shortcut!
                      }
                      style={
                        hasBreakingChange ? "text-accent-amber-foreground" : ""
                      }
                      value={isUserEdited ? "Restore" : "Update"}
                      icon={isUserEdited ? "RefreshCcwDot" : "CircleArrowUp"}
                      dataTestId="update-button-modal"
                    />
                  </SelectItem>
                )}
                {hasStore && (
                  <SelectItem
                    value={"Share"}
                    disabled={!hasApiKey || !validApiKey}
                  >
                    <ToolbarSelectItem
                      shortcut={
                        shortcuts.find((obj) => obj.name === "Component Share")
                          ?.shortcut!
                      }
                      value={"Share"}
                      icon={"Share3"}
                      dataTestId="share-button-modal"
                    />
                  </SelectItem>
                )}

                <SelectItem
                  value={"documentation"}
                  disabled={data.node?.documentation === ""}
                >
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Docs")?.shortcut!
                    }
                    value={"Docs"}
                    icon={"FileText"}
                    dataTestId="docs-button-modal"
                  />
                </SelectItem>

                {(isMinimal || !showNode) && (
                  <SelectItem
                    value={"show"}
                    data-testid={`${
                      showNode ? "minimize" : "expand"
                    }-button-modal`}
                  >
                    <ToolbarSelectItem
                      shortcut={
                        shortcuts.find((obj) => obj.name === "Minimize")
                          ?.shortcut!
                      }
                      value={showNode ? "Minimize" : "Expand"}
                      icon={showNode ? "Minimize2" : "Maximize2"}
                    />
                  </SelectItem>
                )}
                {isGroup && (
                  <SelectItem value="ungroup">
                    <ToolbarSelectItem
                      shortcut={
                        shortcuts.find((obj) => obj.name === "Group")?.shortcut!
                      }
                      value={"Ungroup"}
                      icon={"Ungroup"}
                      dataTestId="group-button-modal"
                    />
                  </SelectItem>
                )}
                {hasToolMode && !inspectionPanelVisible && (
                  <SelectItem
                    value="freezeAll"
                    data-testid="freeze-all-button-modal"
                  >
                    <ToolbarSelectItem
                      shortcut={
                        shortcuts.find((obj) =>
                          obj.name.toLowerCase().startsWith("freeze"),
                        )?.shortcut!
                      }
                      value={"Freeze"}
                      icon={"FreezeAll"}
                      dataTestId="freeze-path-button"
                      style={`${frozen ? " text-ice" : ""} transition-all`}
                    />
                  </SelectItem>
                )}
                <SelectItem value="Download">
                  <ToolbarSelectItem
                    shortcut={
                      shortcuts.find((obj) => obj.name === "Download")
                        ?.shortcut!
                    }
                    value={"Download"}
                    icon={"Download"}
                    dataTestId="download-button-modal"
                  />
                </SelectItem>
                <SelectItem
                  value={"delete"}
                  className="focus:bg-destructive/[.20]"
                >
                  <div className="font-red flex text-status-red">
                    <Trash2
                      className="relative top-0.5 mr-2 h-4 w-4"
                    />{" "}
                    <span className="">Delete</span>{" "}
                    <span
                      className={`absolute right-2 top-2 flex items-center justify-center rounded-sm px-1 py-[0.2]`}
                    >
                      <Delete
                        className="h-4 w-4 stroke-2 text-destructive"
                      />
                    </span>
                  </div>
                </SelectItem>
              </SelectContentWithoutPortal>
            </Select>
          </div>

          <ToolbarModals
            showModalAdvanced={showModalAdvanced}
            showconfirmShare={showconfirmShare}
            showOverrideModal={showOverrideModal}
            openModal={openModal}
            hasCode={canViewCode}
            setShowModalAdvanced={setShowModalAdvanced}
            setShowconfirmShare={setShowconfirmShare}
            setShowOverrideModal={setShowOverrideModal}
            setOpenModal={setOpenModal}
            data={data}
            flowComponent={flowComponent}
            handleOnNewValue={handleOnNewValue}
            handleNodeClass={handleNodeClass}
            setToolMode={setToolMode}
            setSuccessData={setSuccessData}
            addFlow={addFlow}
            name={name}
          />
        </div>
      </>
    );
  },
);

NodeToolbarComponent.displayName = "NodeToolbarComponent";

export default NodeToolbarComponent;
