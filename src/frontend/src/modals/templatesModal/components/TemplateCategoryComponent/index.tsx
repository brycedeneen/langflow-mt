import type { TemplateCategoryProps } from "../../../../types/templates/types";
import type { TemplateRead } from "@/types/template";
import TemplateExampleCard from "../TemplateCardComponent";

interface TemplateCategoryComponentProps extends TemplateCategoryProps {
  loading: boolean;
  selectedTemplate?: string | null;
  onSelectTemplate?: (id: string | null) => void;
  /** Raw TemplateRead objects, parallel-indexed with examples, for admin features. */
  rawTemplates?: TemplateRead[];
  isAdmin?: boolean;
}

export function TemplateCategoryComponent({
  examples,
  onCardClick,
  loading,
  selectedTemplate,
  onSelectTemplate,
  rawTemplates,
  isAdmin = false,
}: TemplateCategoryComponentProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {examples.map((example, index) => (
          <TemplateExampleCard
            key={index}
            example={example}
            onClick={() => onCardClick(example)}
            disabled={loading}
            selected={selectedTemplate === example.id}
            onSelect={() => onSelectTemplate?.(example.id)}
            templateData={rawTemplates?.[index]}
            isAdmin={isAdmin}
          />
        ))}
      </div>
    </>
  );
}
