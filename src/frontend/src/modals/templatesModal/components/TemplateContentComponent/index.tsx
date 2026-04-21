import Fuse from "fuse.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { useListTemplates } from "@/controllers/API/queries/templates/use-list-templates";
import type { ListTemplatesParams } from "@/controllers/API/queries/templates/use-list-templates";
import type { FlowType } from "@/types/flow";
import type { TemplateRead } from "@/types/template";
import { ForwardedIconComponent } from "../../../../components/common/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import type { TemplateContentProps } from "../../../../types/templates/types";
import { TemplateCategoryComponent } from "../TemplateCategoryComponent";

interface TemplateContentComponentProps extends TemplateContentProps {
  loading: boolean;
  onFlowCreating: (loading: boolean) => void;
  selectedTemplate: string | null;
  onSelectTemplate: (id: string | null) => void;
}

function adaptTemplateToFlowLike(template: TemplateRead): FlowType {
  return {
    id: `tpl:${template.id}`,
    name: template.name,
    description: template.description ?? "",
    icon: template.icon ?? undefined,
    gradient: template.gradient ?? undefined,
    data: null,
  };
}

function buildParams(currentTab: string): ListTemplatesParams | undefined {
  if (currentTab === "all-templates") {
    return undefined;
  }
  if (currentTab === "saved") {
    return { created_by_me: true };
  }
  // Any other tab id is a category name coming from the API categories
  return { category: currentTab };
}

export default function TemplateContentComponent({
  currentTab,
  categories,
  loading,
  onFlowCreating,
  selectedTemplate,
  onSelectTemplate,
}: TemplateContentComponentProps) {
  const params = useMemo(() => buildParams(currentTab), [currentTab]);

  const { data: templateData = [], isPending } = useListTemplates(params);

  const examples: FlowType[] = useMemo(
    () => templateData.map(adaptTemplateToFlowLike),
    [templateData],
  );

  const [searchQuery, setSearchQuery] = useState("");
  const [filteredExamples, setFilteredExamples] = useState(examples);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const fuse = useMemo(
    () => new Fuse(examples, { keys: ["name", "description"] }),
    [examples],
  );

  useEffect(() => {
    // Reset search query when currentTab changes
    setSearchQuery("");
  }, [currentTab]);

  useEffect(() => {
    if (searchQuery === "") {
      setFilteredExamples(examples);
    } else {
      const searchResults = fuse.search(searchQuery);
      setFilteredExamples(searchResults.map((result) => result.item));
    }
    // Scroll to the top when search query changes
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
  }, [searchQuery, currentTab, examples, fuse]);

  const handleClearSearch = () => {
    setSearchQuery("");
    if (searchInputRef.current) {
      searchInputRef.current.focus();
    }
  };

  const currentTabItem = categories.find((item) => item.id === currentTab);

  const searchInputRef = useRef<HTMLInputElement>(null);

  if (isPending) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {[0, 1, 2, 4].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-md bg-muted"
            aria-hidden
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-hidden">
      <div className="relative mx-3 flex-1 grow-0 py-px">
        <ForwardedIconComponent
          name="Search"
          className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          placeholder="Search..."
          icon={"SearchIcon"}
          data-testid="search-input-template"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          ref={searchInputRef}
          className="w-3/4 rounded-lg bg-background lg:w-2/3"
        />
      </div>
      <div
        ref={scrollContainerRef}
        className="flex flex-1 flex-col gap-6 overflow-auto scrollbar-hide"
      >
        {currentTabItem && filteredExamples.length > 0 ? (
          <TemplateCategoryComponent
            examples={filteredExamples}
            onCardClick={() => {}}
            loading={loading}
            selectedTemplate={selectedTemplate}
            onSelectTemplate={onSelectTemplate}
          />
        ) : (
          <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
            <p className="text-sm text-secondary-foreground">
              No templates found.{" "}
              <a
                className="cursor-pointer underline underline-offset-4"
                onClick={handleClearSearch}
              >
                Clear your search
              </a>{" "}
              and try a different query.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
