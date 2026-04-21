import { useState } from "react";
import { useParams } from "react-router-dom";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { Category } from "@/types/templates/types";
import { updateIds } from "@/utils/reactflowUtils";
import { openFlowInFullscreenAssist } from "@/utils/assist-entry";
import type { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import { ActionBar } from "./components/actionBar";
import GetStartedComponent from "./components/GetStartedComponent";
import { Nav } from "./components/navComponent";
import SavedTemplatesContent from "./components/SavedTemplatesContent";
import TemplateContentComponent from "./components/TemplateContentComponent";

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

  const handleFlowCreating = (isCreating: boolean) => {
    setLoading(isCreating);
  };

  const handleCreateFromSelection = async (withAssist: boolean) => {
    if (!selectedTemplate || loading) return;
    handleFlowCreating(true);
    try {
      let id: string;
      if (selectedTemplate === "blank") {
        id = await addFlow({ new_blank: true, built_with_assist: withAssist });
      } else {
        const example = examples.find((e) => e.id === selectedTemplate);
        if (!example) return;
        updateIds(example.data!);
        id = await addFlow({ flow: example, built_with_assist: withAssist });
      }
      track("New Flow Created", {
        template:
          selectedTemplate === "blank" ? "Blank Flow" : selectedTemplate,
        entry: withAssist ? "build-with-assist" : "start-building",
      });
      setOpen(false);
      if (withAssist) {
        openFlowInFullscreenAssist(id, navigate);
      } else {
        navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
      }
    } finally {
      handleFlowCreating(false);
    }
  };

  // Define categories and their items
  const categories: Category[] = [
    {
      title: "Templates",
      items: [
        { title: "Get started", icon: "SquarePlay", id: "get-started" },
        { title: "All templates", icon: "LayoutPanelTop", id: "all-templates" },
        { title: "Saved Templates", icon: "Bookmark", id: "saved" },
      ],
    },
    {
      title: "Use Cases",
      items: [
        { title: "Assistants", icon: "BotMessageSquare", id: "assistants" },
        { title: "Classification", icon: "Tags", id: "classification" },
        { title: "Coding", icon: "TerminalIcon", id: "coding" },
        {
          title: "Content Generation",
          icon: "Newspaper",
          id: "content-generation",
        },
        { title: "Q&A", icon: "Database", id: "q-a" },
        // { title: "Summarization", icon: "Bot", id: "summarization" },
        // { title: "Web Scraping", icon: "CodeXml", id: "web-scraping" },
      ],
    },
    {
      title: "Methodology",
      items: [
        { title: "Prompting", icon: "MessagesSquare", id: "chatbots" },
        { title: "RAG", icon: "Database", id: "rag" },
        { title: "Agents", icon: "Bot", id: "agents" },
      ],
    },
  ];

  return (
    <BaseModal size="templates" open={open} setOpen={setOpen} className="p-0">
      <BaseModal.Content className="flex flex-col p-0">
        <div className="flex flex-1 min-h-0">
          <SidebarProvider width="15rem" defaultOpen={false}>
            <Nav
              categories={categories}
              currentTab={currentTab}
              setCurrentTab={setCurrentTab}
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
                      />
                    );
                  default:
                    return (
                      <TemplateContentComponent
                        currentTab={currentTab}
                        categories={categories.flatMap((c) => c.items)}
                        loading={loading}
                        onFlowCreating={handleFlowCreating}
                        selectedTemplate={selectedTemplate}
                        onSelectTemplate={setSelectedTemplate}
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
