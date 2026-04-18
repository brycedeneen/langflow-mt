import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

type Props = {
  /** Id of the selected template, "blank" for the blank flow card, or null. */
  selectedTemplate: string | null;
  onCancel: () => void;
  onStartBuilding: () => void;
  onBuildWithAssist: () => void;
};

export function ActionBar({
  selectedTemplate,
  onCancel,
  onStartBuilding,
  onBuildWithAssist,
}: Props) {
  const disabled = selectedTemplate === null;
  return (
    <div className="flex w-full items-center justify-end gap-2 pb-4">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onCancel}
        data-testid="template-modal-cancel"
      >
        Cancel
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={disabled}
        onClick={onStartBuilding}
        data-testid="template-modal-start-building"
      >
        Start Building
      </Button>
      <Button
        type="button"
        size="sm"
        disabled={disabled}
        onClick={onBuildWithAssist}
        data-testid="template-modal-build-with-assist"
        className="px-4"
      >
        <ForwardedIconComponent name="Bot" className="mr-2 h-4 w-4" />
        Build with ADP Assist
      </Button>
    </div>
  );
}
