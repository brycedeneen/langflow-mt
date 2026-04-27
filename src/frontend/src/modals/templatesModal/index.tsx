import { useState } from "react";
import { useParams } from "react-router-dom";
import { SidebarProvider } from "@/components/ui/sidebar";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useListCategories } from "@/controllers/API/queries/categories";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useIsPlatformAdmin } from "@/hooks/use-is-platform-admin";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import type { TemplateReadDetail } from "@/types/template";
import type { NavItem } from "@/types/templates/types";
import { updateIds } from "@/utils/reactflowUtils";
import { openFlowInFullscreenAssist } from "@/utils/assist-entry";
import type { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import { ActionBar } from "./components/actionBar";
import GetStartedComponent from "./components/GetStartedComponent";
import { Nav } from "./components/navComponent";
import SavedTemplatesContent from "./components/SavedTemplatesContent";
import TemplateContentComponent from "./components/TemplateContentComponent";

function adaptTemplateDetailToFlow(detail: TemplateReadDetail): FlowType {
  return {
    id: detail.id,
    name: detail.name,
    description: detail.description ?? "",
    data: {
      nodes: detail.nodes as unknown as AllNodeType[],
      edges: detail.edges as unknown as EdgeType[],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  };
}

const PERMANENT_ROWS: NavItem[] = [
  { id: "get-started", title: "Get started", icon: "SquarePlay" },
  { id: "all-templates", title: "All templates", icon: "LayoutPanelTop" },
  { id: "saved", title: "Saved Templates", icon: "Bookmark" },
];

export default function TemplatesModal({
  open,
  setOpen,
}: newFlowModalPropsType): JSX.Element {
  const [currentTab, setCurrentTab] = useState("get-started");
  const [loading, setLoading] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const examples = useFlowsManagerStore((state) => state.examples);

  const { data: apiCategories = [] } = useListCategories();
  const isAdmin = useIsPlatformAdmin();

  const handleFlowCreating = (isCreating: boolean) => {
    setLoading(isCreating);
  };

  const handleCreateFromSelection = async (withAssist: boolean) => {
    if (!selectedTemplate || loading) return;
    handleFlowCreating(true);
    try {
      let id: string;
      let templateAnalyticsName = selectedTemplate;

      if (selectedTemplate === "blank") {
        id = await addFlow({ new_blank: true, built_with_assist: withAssist });
        templateAnalyticsName = "Blank Flow";
      } else if (selectedTemplate.startsWith("tpl:")) {
        const templateId = selectedTemplate.slice("tpl:".length);
        const { data: detail } = await api.get<TemplateReadDetail>(
          `${getURL("TEMPLATES")}/${templateId}`,
        );
        const flowPayload = adaptTemplateDetailToFlow(detail);
        updateIds(flowPayload.data!);
        // based_on_template_id is the source template's id; detail.id is a fresh flow's id
        // Override the auto-fallback to avoid FK violations (detail.id is a template.id, not a flow.id).
        id = await addFlow({
          flow: flowPayload,
          built_with_assist: withAssist,
          based_on_template_id: null,
        });
        templateAnalyticsName = detail.name;
      } else {
        const example = examples.find((e) => e.id === selectedTemplate);
        if (!example) return;
        updateIds(example.data!);
        id = await addFlow({ flow: example, built_with_assist: withAssist });
        templateAnalyticsName = example.name;
      }

      track("New Flow Created", {
        template: templateAnalyticsName,
        entry: withAssist ? "build-with-assist" : "start-building",
      });
      setOpen(false);
      if (withAssist) {
        openFlowInFullscreenAssist(id, navigate, folderId);
      } else {
        navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
      }
    } finally {
      handleFlowCreating(false);
    }
  };

  const categoryNavItems: NavItem[] = [
    ...apiCategories
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((cat) => ({ id: cat.name, title: cat.name, icon: cat.icon })),
  ];

  const navItems: NavItem[] = [...PERMANENT_ROWS, ...categoryNavItems];

  return (
    <BaseModal size="templates" open={open} setOpen={setOpen} className="p-0">
      <BaseModal.Content className="flex flex-col p-0">
        <div className="flex flex-1 min-h-0">
          <SidebarProvider width="15rem" defaultOpen={false}>
            <Nav
              items={navItems}
              currentTab={currentTab}
              setCurrentTab={setCurrentTab}
              isAdmin={isAdmin}
              apiCategories={apiCategories}
            />
            <main className="flex flex-1 flex-col gap-4 overflow-auto p-6 md:gap-8">
              {(() => {
                switch (currentTab) {
                  case "get-started":
                    return (
                      <GetStartedComponent
                        loading={loading}
                        onFlowCreating={handleFlowCreating}
                        selectedTemplate={selectedTemplate}
                        onSelectTemplate={setSelectedTemplate}
                      />
                    );
                  case "saved":
                    return (
                      <SavedTemplatesContent
                        loading={loading}
                        selectedTemplate={selectedTemplate}
                        onSelectTemplate={setSelectedTemplate}
                        isAdmin={isAdmin}
                      />
                    );
                  default:
                    return (
                      <TemplateContentComponent
                        currentTab={currentTab}
                        categories={navItems}
                        loading={loading}
                        onFlowCreating={handleFlowCreating}
                        selectedTemplate={selectedTemplate}
                        onSelectTemplate={setSelectedTemplate}
                        isAdmin={isAdmin}
                      />
                    );
                }
              })()}
            </main>
          </SidebarProvider>
        </div>
        <BaseModal.Footer>
          <ActionBar
            selectedTemplate={selectedTemplate}
            onCancel={() => setOpen(false)}
            onStartBuilding={() => handleCreateFromSelection(false)}
            onBuildWithAssist={() => handleCreateFromSelection(true)}
          />
        </BaseModal.Footer>
      </BaseModal.Content>
    </BaseModal>
  );
}
