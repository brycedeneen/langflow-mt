import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useListTemplates } from "@/controllers/API/queries/templates/use-list-templates";
import type { FlowType } from "@/types/flow";
import type { TemplateRead } from "@/types/template";
import { TemplateCategoryComponent } from "../TemplateCategoryComponent";

type Props = {
  selectedTemplate: string | null;
  onSelectTemplate: (id: string | null) => void;
  loading: boolean;
  isAdmin?: boolean;
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
  isAdmin = false,
}: Props) {
  // Saved Templates always shows the toggle (any user can see their own archived templates
  // via created_by_me=true pairing on the server).
  const [showArchived, setShowArchived] = useState(false);

  const { data, isPending, isError, refetch } = useListTemplates({
    created_by_me: true,
    include_archived: showArchived,
  });

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

  return (
    <div className="flex flex-col gap-4">
      {/* Show archived toggle — visible on Saved Templates for all users */}
      <div className="flex items-center gap-2">
        <Switch
          id="saved-show-archived-toggle"
          checked={showArchived}
          onCheckedChange={setShowArchived}
        />
        <Label
          htmlFor="saved-show-archived-toggle"
          className="cursor-pointer text-sm text-muted-foreground"
        >
          Show archived
        </Label>
      </div>

      {adapted.length === 0 ? (
        <div
          data-testid="saved-templates-empty"
          className="flex flex-col items-center justify-center px-4 py-12 text-center"
        >
          <p className="text-sm text-secondary-foreground">
            {showArchived
              ? "No templates found (including archived)."
              : "No saved templates yet. Save a flow as a template from the flow toolbar to see it here."}
          </p>
        </div>
      ) : (
        <TemplateCategoryComponent
          examples={adapted}
          onCardClick={() => {}}
          loading={loading}
          selectedTemplate={selectedTemplate}
          onSelectTemplate={onSelectTemplate}
          rawTemplates={data ?? []}
          isAdmin={isAdmin}
        />
      )}
    </div>
  );
}
