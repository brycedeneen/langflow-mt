import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { useListTemplates } from "@/controllers/API/queries/templates/use-list-templates";
import type { FlowType } from "@/types/flow";
import type { TemplateRead } from "@/types/template";
import { TemplateCategoryComponent } from "../TemplateCategoryComponent";

type Props = {
  selectedTemplate: string | null;
  onSelectTemplate: (id: string | null) => void;
  loading: boolean;
};

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

export default function SavedTemplatesContent({
  selectedTemplate,
  onSelectTemplate,
  loading,
}: Props) {
  const { data, isPending, isError, refetch } = useListTemplates();

  const adapted = useMemo(
    () => (data ?? []).map(adaptTemplateToFlowLike),
    [data],
  );

  if (isPending) {
    return (
      <div
        data-testid="saved-templates-loading"
        className="grid grid-cols-1 gap-6 lg:grid-cols-2"
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-md bg-muted"
            aria-hidden
          />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        data-testid="saved-templates-error"
        className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center"
      >
        <p className="text-sm text-secondary-foreground">
          Couldn't load saved templates.
        </p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (adapted.length === 0) {
    return (
      <div
        data-testid="saved-templates-empty"
        className="flex flex-col items-center justify-center px-4 py-12 text-center"
      >
        <p className="text-sm text-secondary-foreground">
          No saved templates yet. Save a flow as a template from the flow
          toolbar to see it here.
        </p>
      </div>
    );
  }

  return (
    <TemplateCategoryComponent
      examples={adapted}
      onCardClick={() => {}}
      loading={loading}
      selectedTemplate={selectedTemplate}
      onSelectTemplate={onSelectTemplate}
    />
  );
}
