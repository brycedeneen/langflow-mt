import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TagFilterChips from "@/components/common/TagFilterChips";
import CardsWrapComponent from "@/components/core/cardsWrapComponent";
import { IS_MAC } from "@/constants/constants";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useListTags } from "@/controllers/API/queries/tags";
import { CustomBanner } from "@/customization/components/custom-banner";
import { CustomMcpServerTab } from "@/customization/components/custom-McpServerTab";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_MCP,
} from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { FlowType } from "@/types/flow";
import HeaderComponent from "../../components/header";
import ListComponent from "../../components/list";
import ListSkeleton from "../../components/listSkeleton";
import ModalsComponent from "../../components/modalsComponent";
import useFileDrop from "../../hooks/use-on-file-drop";
import EmptyFolder from "../emptyFolder";

const HomePage = ({ type }: { type: "flows" | "components" | "mcp" }) => {
  const [view, setView] = useState<"grid" | "list">(() => {
    const savedView = localStorage.getItem("view");
    return savedView === "grid" || savedView === "list" ? savedView : "list";
  });
  const [newProjectModal, setNewProjectModal] = useState(false);
  const { folderId } = useParams();
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [search, setSearch] = useState("");
  const [isEmptyFolder, setIsEmptyFolder] = useState(true);
  const navigate = useCustomNavigate();

  const [flowType, setFlowType] = useState<"flows" | "components" | "mcp">(
    type,
  );
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folders = useFolderStore((state) => state.folders);
  const folderName =
    folders.find((folder) => folder.id === folderId)?.name ??
    folders[0]?.name ??
    "";
  const flows = useFlowsManagerStore((state) => state.flows);

  const redirectedForFolderId = useRef<string | null>(null);
  useEffect(() => {
    if (folderId && folders && folders.length > 0) {
      const folderExists = folders.find((folder) => folder.id === folderId);
      if (!folderExists && redirectedForFolderId.current !== folderId) {
        redirectedForFolderId.current = folderId;
        console.debug("Invalid folderId, redirecting to /all");
        navigate("/all");
      }
    }
  }, [folderId, folders, navigate]);

  const { data: folderData, isLoading } = useGetFolderQuery({
    id: folderId ?? myCollectionId!,
    page: pageIndex,
    size: pageSize,
    is_component: flowType === "components",
    is_flow: flowType === "flows",
    search,
  });

  // Tag filter state — local to this page. We filter the folder response's
  // flow list client-side by intersecting each flow's `tags[].id` with
  // `selectedTagIds`. `flow.tags` is populated by FlowRead (0b5d4aae7c).
  const { data: allTags = [] } = useListTags();
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  const allFlowItems: FlowType[] = folderData?.flows?.items ?? [];
  const visibleFlowItems =
    selectedTagIds.length === 0
      ? allFlowItems
      : allFlowItems.filter((f) =>
          f.tags?.some((t) => selectedTagIds.includes(t.id)),
        );

  // Tags actually present on flows in the current folder response. We pass
  // this (rather than `allTags`) to the filter chip row so users don't see
  // chips they cannot possibly toggle against. If a selected id is no longer
  // in `tagsInUse` (last tagged flow deleted), we intentionally keep it in
  // `selectedTagIds` so re-tagging a flow restores the user's filter state.
  const tagsInUse = useMemo(() => {
    const inUse = new Set<string>();
    allFlowItems.forEach((f) => f.tags?.forEach((t) => inUse.add(t.id)));
    return allTags.filter((t) => inUse.has(t.id));
  }, [allFlowItems, allTags]);

  const data = {
    flows: visibleFlowItems,
    name: folderData?.folder?.name ?? "",
    description: folderData?.folder?.description ?? "",
    parent_id: folderData?.folder?.parent_id ?? "",
    components: folderData?.folder?.components ?? [],
    pagination: {
      page: folderData?.flows?.page ?? 1,
      size: folderData?.flows?.size ?? 12,
      total: folderData?.flows?.total ?? 0,
      pages: folderData?.flows?.pages ?? 0,
    },
  };

  useEffect(() => {
    localStorage.setItem("view", view);
  }, [view]);

  const handlePageChange = useCallback((newPageIndex, newPageSize) => {
    setPageIndex(newPageIndex);
    setPageSize(newPageSize);
  }, []);

  const onSearch = useCallback((newSearch) => {
    setSearch(newSearch);
    setPageIndex(1);
  }, []);

  useEffect(() => {
    const isEmpty =
      flows?.find(
        (flow) =>
          flow.folder_id === (folderId ?? myCollectionId) &&
          (ENABLE_MCP ? flow.is_component === false : true),
      ) === undefined;
    setIsEmptyFolder(isEmpty);
  }, [flows, folderId, myCollectionId]);

  const handleFileDrop = useFileDrop(isEmptyFolder ? undefined : flowType);

  useEffect(() => {
    if (
      !isEmptyFolder &&
      flows?.find(
        (flow) =>
          flow.folder_id === (folderId ?? myCollectionId) &&
          flow.is_component === (flowType === "components"),
      ) === undefined
    ) {
      const otherTabHasItems =
        flows?.find(
          (flow) =>
            flow.folder_id === (folderId ?? myCollectionId) &&
            flow.is_component === (flowType === "flows"),
        ) !== undefined;

      if (otherTabHasItems) {
        setFlowType(flowType === "flows" ? "components" : "flows");
      }
    }
  }, [isEmptyFolder]);

  const [selectedFlows, setSelectedFlows] = useState<string[]>([]);
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(
    null,
  );

  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [isCtrlPressed, setIsCtrlPressed] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only track these keys when we're in list/selection mode and not when a modal is open
      // or when an input field is focused
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target instanceof HTMLElement && e.target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "Shift") {
        setIsShiftPressed(true);
      } else if ((!IS_MAC && e.key === "Control") || e.key === "Meta") {
        setIsCtrlPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target instanceof HTMLElement && e.target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "Shift") {
        setIsShiftPressed(false);
      } else if ((!IS_MAC && e.key === "Control") || e.key === "Meta") {
        setIsCtrlPressed(false);
      }
    };

    // Reset key states when window loses focus
    const handleBlur = () => {
      setIsShiftPressed(false);
      setIsCtrlPressed(false);
    };

    // Only add listeners if we're in flows or components mode, not MCP mode
    if (flowType === "flows" || flowType === "components") {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("keyup", handleKeyUp);
      window.addEventListener("blur", handleBlur);
    }

    // Clean up event listeners when component unmounts
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", handleBlur);

      // Reset key states on unmount
      setIsShiftPressed(false);
      setIsCtrlPressed(false);
    };
  }, [flowType]);

  const setSelectedFlow = useCallback(
    (selected: boolean, flowId: string, index: number) => {
      setLastSelectedIndex(index);
      if (isShiftPressed && lastSelectedIndex !== null) {
        // Find the indices of the last selected and current flow
        const flows = data.flows;

        // Determine the range to select
        const start = Math.min(lastSelectedIndex, index);
        const end = Math.max(lastSelectedIndex, index);
        // Get all flow IDs in the range
        const flowsToSelect = flows
          .slice(start, end + 1)
          .map((flow) => flow.id);

        // Update selection
        if (selected) {
          setSelectedFlows((prev) =>
            Array.from(new Set([...prev, ...flowsToSelect])),
          );
        } else {
          setSelectedFlows((prev) =>
            prev.filter((id) => !flowsToSelect.includes(id)),
          );
        }
      } else {
        if (selected) {
          setSelectedFlows([...selectedFlows, flowId]);
        } else {
          setSelectedFlows(selectedFlows.filter((id) => id !== flowId));
        }
      }
    },
    [selectedFlows, lastSelectedIndex, data.flows, isShiftPressed],
  );

  useEffect(() => {
    setSelectedFlows((old) =>
      old.filter((id) => data.flows.some((flow) => flow.id === id)),
    );
  }, [folderData?.flows?.items]);

  // Reset key states when navigating away
  useEffect(() => {
    return () => {
      setIsShiftPressed(false);
      setIsCtrlPressed(false);
    };
  }, [folderId]);

  return (
    <CardsWrapComponent
      onFileDrop={flowType === "mcp" ? undefined : handleFileDrop}
      dragMessage={`Drop your ${isEmptyFolder ? "flows or components" : flowType} here`}
    >
      <div
        className="flex h-full w-full flex-col overflow-y-auto"
        data-testid="cards-wrapper"
      >
        <div className="flex h-full w-full flex-col 3xl:container">
          {ENABLE_DATASTAX_LANGFLOW && <CustomBanner />}
          <div className="flex flex-1 flex-col justify-start p-4">
            <div className="flex h-full flex-col justify-start">
              <HeaderComponent
                folderName={folderName}
                flowType={flowType}
                setFlowType={setFlowType}
                view={view}
                setView={setView}
                setNewProjectModal={setNewProjectModal}
                setSearch={onSearch}
                isEmptyFolder={isEmptyFolder}
                selectedFlows={selectedFlows}
              />
              {isEmptyFolder ? (
                <EmptyFolder setOpenModal={setNewProjectModal} />
              ) : (
                <div className="flex h-full flex-col">
                  {/* Tag filter row — renders tags actually in use by flows
                      in the current folder response. Selection filters the
                      list client-side via `visibleFlowItems` above. */}
                  {(flowType === "flows" || flowType === "components") &&
                    tagsInUse.length > 0 && (
                      <TagFilterChips
                        availableTags={tagsInUse}
                        selected={selectedTagIds}
                        onChange={setSelectedTagIds}
                        className="mt-2 px-1"
                      />
                    )}
                  {isLoading ? (
                    view === "grid" ? (
                      <div className="mt-4 grid grid-cols-1 gap-1 md:grid-cols-2 lg:grid-cols-3">
                        <ListSkeleton />
                        <ListSkeleton />
                      </div>
                    ) : (
                      <div className="mt-4 flex flex-col gap-1">
                        <ListSkeleton />
                        <ListSkeleton />
                      </div>
                    )
                  ) : flowType === "mcp" ? (
                    <CustomMcpServerTab folderName={folderName} />
                  ) : (flowType === "flows" || flowType === "components") &&
                    data &&
                    data.pagination.total > 0 ? (
                    view === "grid" ? (
                      <div className="mt-4 grid grid-cols-1 gap-1 md:grid-cols-2 lg:grid-cols-3">
                        {data.flows.map((flow, index) => (
                          <ListComponent
                            key={flow.id}
                            flowData={flow}
                            selected={selectedFlows.includes(flow.id)}
                            setSelected={(selected) =>
                              setSelectedFlow(selected, flow.id, index)
                            }
                            shiftPressed={isShiftPressed || isCtrlPressed}
                            selectedTagIds={selectedTagIds}
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="mt-4 flex flex-col gap-1">
                        {data.flows.map((flow, index) => (
                          <ListComponent
                            key={flow.id}
                            flowData={flow}
                            selected={selectedFlows.includes(flow.id)}
                            setSelected={(selected) =>
                              setSelectedFlow(selected, flow.id, index)
                            }
                            shiftPressed={isShiftPressed || isCtrlPressed}
                            selectedTagIds={selectedTagIds}
                          />
                        ))}
                      </div>
                    )
                  ) : (
                    <div className="pt-24 text-center text-sm text-secondary-foreground">
                      {flowType} not supported
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {(flowType === "flows" || flowType === "components") &&
            !isLoading &&
            !isEmptyFolder &&
            data.pagination.total >= 10 && (
              <div className="flex justify-end px-3 py-4">
                <PaginatorComponent
                  pageIndex={data.pagination.page}
                  pageSize={data.pagination.size}
                  rowsCount={[12, 24, 48, 96]}
                  totalRowsCount={data.pagination.total}
                  paginate={handlePageChange}
                  pages={data.pagination.pages}
                  isComponent={flowType === "components"}
                />
              </div>
            )}
        </div>
      </div>

      <ModalsComponent
        openModal={newProjectModal}
        setOpenModal={setNewProjectModal}
        openDeleteFolderModal={false}
        setOpenDeleteFolderModal={() => {}}
        handleDeleteFolder={() => {}}
      />
    </CardsWrapComponent>
  );
};

export default HomePage;
