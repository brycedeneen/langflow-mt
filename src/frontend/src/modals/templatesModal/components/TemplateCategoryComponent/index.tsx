import type { TemplateCategoryProps } from "../../../../types/templates/types";
import TemplateExampleCard from "../TemplateCardComponent";

interface TemplateCategoryComponentProps extends TemplateCategoryProps {
  loading: boolean;
  selectedTemplate?: string | null;
  onSelectTemplate?: (id: string | null) => void;
}

export function TemplateCategoryComponent({
  examples,
  onCardClick,
  loading,
  selectedTemplate,
  onSelectTemplate,
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
          />
        ))}
      </div>
    </>
  );
}
