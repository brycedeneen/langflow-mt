import { useEffect, useState } from "react";
import TagPicker from "@/components/common/TagPicker";
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
import { Textarea } from "@/components/ui/textarea";
import { useAssignTemplateTags } from "@/controllers/API/queries/tags";
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
  const [agentSummary, setAgentSummary] = useState(template.agent_summary ?? "");
  const [agentUsageNotes, setAgentUsageNotes] = useState(template.agent_usage_notes ?? "");
  // template.tags is now populated by TemplateRead (see 0b5d4aae7c).
  // Mirror the pattern used for selectedCategoryIds.
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>(
    template.tags?.map((t) => t.id) ?? [],
  );

  const { mutate: updateTemplate, isPending } = useUpdateTemplate();
  const assignTemplateTags = useAssignTemplateTags();
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
      setAgentSummary(template.agent_summary ?? "");
      setAgentUsageNotes(template.agent_usage_notes ?? "");
      setSelectedTagIds(template.tags?.map((t) => t.id) ?? []);
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
          agent_summary: agentSummary.trim() === "" ? null : agentSummary,
          agent_usage_notes: agentUsageNotes.trim() === "" ? null : agentUsageNotes,
        },
      },
      {
        onSuccess: () => {
          const finish = () => {
            setSuccessData({ title: `Template "${name}" updated` });
            onOpenChange(false);
          };
          // The edit panel now shows the user the current tag state before saving,
          // so an empty picker means "clear all tags" — let the server know.
          assignTemplateTags.mutate(
            { templateId: template.id, tagIds: selectedTagIds },
            {
              onSuccess: finish,
              onError: () => {
                setErrorData({
                  title: "Template updated, but tag assignment failed",
                });
                onOpenChange(false);
              },
            },
          );
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
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-hidden">
        <DialogHeader>
          <DialogTitle>Edit Template</DialogTitle>
        </DialogHeader>

        <div className="-mx-6 min-h-0 flex-1 overflow-y-auto px-6">
          <div className="grid grid-cols-2 gap-x-6 gap-y-4 py-2">
            {/* Name */}
            <div className="col-span-2 flex flex-col gap-1.5">
              <Label htmlFor="tpl-edit-name">Name</Label>
              <Input
                id="tpl-edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Template name"
              />
            </div>

            {/* Description */}
            <div className="col-span-2 flex flex-col gap-1.5">
              <Label htmlFor="tpl-edit-desc">Description</Label>
              <Textarea
                id="tpl-edit-desc"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                className="resize-y"
              />
            </div>

            {/* Icon */}
            <div className="flex flex-col gap-1.5">
              <Label>Icon</Label>
              <IconPickerField value={icon} onChange={setIcon} />
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

            {/* Gradient */}
            <div className="col-span-2 flex flex-col gap-1.5">
              <Label>Color</Label>
              <GradientPickerField value={gradient} onChange={setGradient} />
            </div>

            {/* Agent Summary */}
            <div className="col-span-2 flex flex-col gap-1.5">
              <Label htmlFor="tpl-edit-agent-summary">Agent summary</Label>
              <Textarea
                id="tpl-edit-agent-summary"
                rows={2}
                value={agentSummary}
                onChange={(e) => setAgentSummary(e.target.value)}
                placeholder="Short description the assistant uses to match this template to user requests."
              />
            </div>

            {/* Agent Usage Notes */}
            <div className="col-span-2 flex flex-col gap-1.5">
              <Label htmlFor="tpl-edit-agent-usage-notes">
                Agent usage notes
              </Label>
              <Textarea
                id="tpl-edit-agent-usage-notes"
                rows={6}
                value={agentUsageNotes}
                onChange={(e) => setAgentUsageNotes(e.target.value)}
                placeholder="Guidance the assistant injects when a user works with a flow created from this template."
                className="resize-y"
              />
            </div>

            {/* Tags */}
            <div className="col-span-2 flex flex-col gap-1.5">
              <Label>Tags</Label>
              <TagPicker
                selectedIds={selectedTagIds}
                onChange={setSelectedTagIds}
                disabled={isPending}
              />
            </div>
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
