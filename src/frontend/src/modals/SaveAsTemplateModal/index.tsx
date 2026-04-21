import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { useCreateTemplate } from "@/controllers/API/queries/templates";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import type { BlankedField } from "@/types/template";
import GradientPickerField from "./GradientPickerField";
import IconPickerField from "./IconPickerField";
import StripPanel from "./StripPanel";
import {
  scanBlankableFields,
  type BlankableFieldInfo,
} from "./scanBlankableFields";

type FlowLike = {
  id?: string;
  description?: string | null;
  data?: { nodes?: unknown[]; edges?: unknown[] };
};

type Props = {
  open: boolean;
  onClose: () => void;
  /** Current flow — typically from useFlowStore. */
  flow: FlowLike;
};

const DEFAULT_ICON = "FileText";
const DEFAULT_GRADIENT = "0";

export default function SaveAsTemplateModal({ open, onClose, flow }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState(DEFAULT_ICON);
  const [gradient, setGradient] = useState(DEFAULT_GRADIENT);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [keptFieldKeys, setKeptFieldKeys] = useState<Set<string>>(new Set());

  // Reset state whenever the modal opens.
  useEffect(() => {
    if (open) {
      setName("");
      setDescription(flow.description ?? "");
      setIcon(DEFAULT_ICON);
      setGradient(DEFAULT_GRADIENT);
      setDetailsOpen(false);
      setNameError(null);
      setKeptFieldKeys(new Set());
    }
  }, [open, flow.description]);

  const blankableFields: BlankableFieldInfo[] = useMemo(() => {
    const nodes = Array.isArray(flow.data?.nodes) ? flow.data!.nodes : [];
    return scanBlankableFields({ nodes });
  }, [flow.data?.nodes]);

  const canSubmit = name.trim().length > 0;

  const createTemplate = useCreateTemplate();
  const submitting = createTemplate.isPending;
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const toggleField = useCallback((node_id: string, field_name: string) => {
    setKeptFieldKeys((prev) => {
      const next = new Set(prev);
      const key = `${node_id}:${field_name}`;
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  function handleSubmit() {
    if (!canSubmit) return;
    if (!flow.id) return;

    const blanked_fields: BlankedField[] = blankableFields
      .filter((f) => !keptFieldKeys.has(`${f.node_id}:${f.field_name}`))
      .map((f) => ({
        node_id: f.node_id,
        field_name: f.field_name,
      }));

    createTemplate.mutate(
      {
        source_flow_id: flow.id,
        name: name.trim(),
        description: description.trim() || null,
        icon,
        gradient,
        blanked_fields,
      },
      {
        onSuccess: () => {
          setSuccessData({ title: `Template "${name.trim()}" saved` });
          onClose();
        },
        onError: (err: any) => {
          if (err?.response?.status === 409) {
            setNameError(
              "A template with that name already exists — pick a different one.",
            );
          } else {
            setErrorData({
              title: "Failed to save template",
              list: [err?.response?.data?.detail ?? "Please try again."],
            });
          }
        },
      },
    );
  }

  return (
    <BaseModal
      open={open}
      setOpen={(o: boolean) => (!o ? onClose() : undefined)}
      size="medium-tall"
    >
      <BaseModal.Header description="Save the current flow as a reusable platform template.">
        Save as Template
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">
              Name <span className="text-red-600">*</span>
            </span>
            <input
              type="text"
              autoFocus
              maxLength={255}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError(null);
              }}
              placeholder="e.g. Customer Support Agent"
              aria-label="Name"
              className={`w-full rounded-md border px-3 py-2 text-sm ${
                nameError ? "border-red-500" : ""
              }`}
            />
            {nameError && (
              <p className="mt-1 text-sm text-red-600" role="alert">
                {nameError}
              </p>
            )}
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">Description</span>
            <textarea
              rows={3}
              maxLength={1000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short summary of what this template does."
              aria-label="Description"
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
          </label>

          <div className="space-y-2">
            <span className="block text-sm font-medium">Icon</span>
            <IconPickerField value={icon} onChange={setIcon} />
          </div>

          <div className="space-y-2">
            <span className="block text-sm font-medium">Gradient</span>
            <GradientPickerField value={gradient} onChange={setGradient} />
          </div>

          <StripPanel
            fields={blankableFields}
            keptKeys={keptFieldKeys}
            onToggle={toggleField}
            open={detailsOpen}
            onOpenChange={setDetailsOpen}
          />
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end gap-3">
          <Button variant="outline" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!canSubmit || submitting}
            onClick={handleSubmit}
          >
            {submitting ? "Saving…" : "Save as Template"}
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
