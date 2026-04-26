import Fuse from "fuse.js";
import { useEffect, useMemo, useRef, useState } from "react";
import TagFilterChips from "@/components/common/TagFilterChips";
import { useListTags } from "@/controllers/API/queries/tags";
import { useListTemplates } from "@/controllers/API/queries/templates/use-list-templates";
import type { ListTemplatesParams } from "@/controllers/API/queries/templates/use-list-templates";
import type { FlowType } from "@/types/flow";
import type { TemplateRead } from "@/types/template";
import { Search } from "lucide-react";
import { Input } from "../../../../components/ui/input";
import { Switch } from "../../../../components/ui/switch";
import { Label } from "../../../../components/ui/label";
import type { TemplateContentProps } from "../../../../types/templates/types";
import { TemplateCategoryComponent } from "../TemplateCategoryComponent";

interface TemplateContentComponentProps extends TemplateContentProps {
  loading: boolean;
  onFlowCreating: (loading: boolean) => void;
  selectedTemplate: string | null;
  onSelectTemplate: (id: string | null) => void;
  isAdmin?: boolean;
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

function buildParams(
  currentTab: string,
  includeArchived: boolean,
  selectedTagIds: string[],
): ListTemplatesParams | undefined {
  const base: ListTemplatesParams = {};
  if (includeArchived) base.include_archived = true;
  if (selectedTagIds.length > 0) base.tag_id = selectedTagIds;

  if (currentTab === "all-templates") {
    return Object.keys(base).length ? base : undefined;
  }
  if (currentTab === "saved") {
    return { created_by_me: true, ...base };
  }
  // Any other tab id is a category name coming from the API categories
  return { category: currentTab, ...base };
}

export default function TemplateContentComponent({
  currentTab,
  categories,
  loading,
  onFlowCreating,
  selectedTemplate,
  onSelectTemplate,
  isAdmin = false,
}: TemplateContentComponentProps) {
  // "Show archived" toggle is visible for admins on any tab, or for anyone on the
  // "saved" (Saved Templates) tab (pairs with created_by_me so the server allows it).
  const showArchivedToggleVisible = isAdmin || currentTab === "saved";
  const [showArchived, setShowArchived] = useState(false);

  // Tag filter state — threaded into useListTemplates via the ?tag_id= query
  // param. The chip row shows the full tag vocabulary from useListTags() so
  // users can pick any defined tag, even after a filter narrows the grid.
  const { data: allTags = [] } = useListTags();
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  const params = useMemo(
    () =>
      buildParams(
        currentTab,
        showArchivedToggleVisible && showArchived,
        selectedTagIds,
      ),
    [currentTab, showArchived, showArchivedToggleVisible, selectedTagIds],
  );

  const { data: templateData = [], isPending } = useListTemplates(params);

  const examples: FlowType[] = useMemo(
    () => templateData.map(adaptTemplateToFlowLike),
    [templateData],
  );

  const [searchQuery, setSearchQuery] = useState("");
  const [filteredExamples, setFilteredExamples] = useState(examples);
  const [filteredRaw, setFilteredRaw] = useState<TemplateRead[]>(templateData);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const fuse = useMemo(
    () => new Fuse(examples, { keys: ["name", "description"] }),
    [examples],
  );

  useEffect(() => {
    // Reset search query and showArchived when currentTab changes
    setSearchQuery("");
    setShowArchived(false);
  }, [currentTab]);

  useEffect(() => {
    if (searchQuery === "") {
      setFilteredExamples(examples);
      setFilteredRaw(templateData);
    } else {
      const searchResults = fuse.search(searchQuery);
      const indices = searchResults.map((r) =>
        examples.findIndex((e) => e.id === r.item.id),
      );
      setFilteredExamples(searchResults.map((result) => result.item));
      setFilteredRaw(indices.map((i) => templateData[i]).filter(Boolean));
    }
    // Scroll to the top when search query changes
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
  }, [searchQuery, currentTab, examples, templateData, fuse]);

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
        <Search
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

      {/* Show archived toggle — visible for admins everywhere, or for anyone on the Saved tab */}
      {showArchivedToggleVisible && (
        <div className="mx-3 flex items-center gap-2">
          <Switch
            id="show-archived-toggle"
            checked={showArchived}
            onCheckedChange={setShowArchived}
          />
          <Label htmlFor="show-archived-toggle" className="cursor-pointer text-sm text-muted-foreground">
            Show archived
          </Label>
        </div>
      )}

      {/* Tag filter row — renders nothing when no tags exist in the workspace. */}
      {allTags.length > 0 && (
        <TagFilterChips
          availableTags={allTags}
          selected={selectedTagIds}
          onChange={setSelectedTagIds}
          className="mx-3"
        />
      )}

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
            rawTemplates={filteredRaw}
            isAdmin={isAdmin}
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
