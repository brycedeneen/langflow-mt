import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUpdateTemplate } from "@/controllers/API/queries/templates/use-update-template";
import useAlertStore from "@/stores/alertStore";
import IconPickerField from "@/modals/SaveAsTemplateModal/IconPickerField";
import GradientPickerField from "@/modals/SaveAsTemplateModal/GradientPickerField";
import CategoryChipPicker from "@/modals/templatesModal/components/CategoryChipPicker";
import type { TemplateRead } from "@/types/template";

type Props = {
  template: TemplateRead;
  open: boolean;
  onOpenChange(open: boolean): void;
};

export default function TemplateEditPanel({ template, open, onOpenChange }: Props) {
  const [name, setName] = useState(template.name);
  const [description, setDescription] = useState(template.description ?? "");
  const [icon, setIcon] = useState(template.icon ?? "FileText");
  const [gradient, setGradient] = useState(template.gradient ?? "0");
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>(
    template.categories.map((c) => c.id),
  );

  const { mutate: updateTemplate, isPending } = useUpdateTemplate();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  // Reset form when template changes or panel opens
  useEffect(() => {
    if (open) {
      setName(template.name);
      setDescription(template.description ?? "");
      setIcon(template.icon ?? "FileText");
      setGradient(template.gradient ?? "0");
      setSelectedCategoryIds(template.categories.map((c) => c.id));
    }
  }, [open, template]);

  const handleSave = () => {
    updateTemplate(
      {
        templateId: template.id,
        body: {
          name: name.trim() || template.name,
          description: description.trim() || null,
          icon,
          gradient,
          // Full-replace semantics: send the complete id array.
          category_ids: selectedCategoryIds,
        },
      },
      {
        onSuccess: () => {
          setSuccessData({ title: `Template "${name}" updated` });
          onOpenChange(false);
        },
        onError: (err: unknown) => {
          const msg =
            (err as { response?: { data?: { detail?: string } } })?.response?.data
              ?.detail ?? "Failed to update template";
          setErrorData({ title: msg });
        },
      },
    );
  };

  return (
    // No Sheet primitive available; using Dialog as slide-in fallback.
    // TODO: replace with a proper Sheet when one is added to ui/ primitives.
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Template</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          {/* Name */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tpl-edit-name">Name</Label>
            <Input
              id="tpl-edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Template name"
            />
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tpl-edit-desc">Description</Label>
            <Input
              id="tpl-edit-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          {/* Icon */}
          <div className="flex flex-col gap-1.5">
            <Label>Icon</Label>
            <IconPickerField value={icon} onChange={setIcon} />
          </div>

          {/* Gradient */}
          <div className="flex flex-col gap-1.5">
            <Label>Color</Label>
            <GradientPickerField value={gradient} onChange={setGradient} />
          </div>

          {/* Categories */}
          <div className="flex flex-col gap-1.5">
            <Label>Categories</Label>
            <CategoryChipPicker
              selectedIds={selectedCategoryIds}
              onChange={setSelectedCategoryIds}
              disabled={isPending}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isPending}>
            {isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
