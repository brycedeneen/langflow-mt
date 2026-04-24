import { useCallback, useEffect, useMemo, useState } from "react";
import TagPicker from "@/components/common/TagPicker";
import { Button } from "@/components/ui/button";
import { useAssignTemplateTags } from "@/controllers/API/queries/tags";
import {
  useCreateTemplate,
  useListTemplates,
  useUpdateTemplate,
} from "@/controllers/API/queries/templates";
import { useListMyMemberships } from "@/controllers/API/queries/memberships";
import { useIsPlatformAdmin } from "@/hooks/use-is-platform-admin";
import BaseModal from "@/modals/baseModal";
import CategoryChipPicker from "@/modals/templatesModal/components/CategoryChipPicker";
import useAlertStore from "@/stores/alertStore";
import type { BlankedField, TemplateRead } from "@/types/template";
import ConfirmOverwriteDialog from "./ConfirmOverwriteDialog";
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

function computeDefaultScope(
  isPlatformAdmin: boolean,
  memberships: { organization: { id: string } }[],
): string {
  if (isPlatformAdmin) return "platform";
  if (memberships.length > 0) return `org:${memberships[0].organization.id}`;
  return "platform"; // fallback — Save will be disabled in this case
}

export default function SaveAsTemplateModal({ open, onClose, flow }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState(DEFAULT_ICON);
  const [gradient, setGradient] = useState(DEFAULT_GRADIENT);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [keptFieldKeys, setKeptFieldKeys] = useState<Set<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [conflict, setConflict] = useState<TemplateRead | null>(null);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  const isPlatformAdmin = useIsPlatformAdmin();
  const { data: memberships = [], isPending: membershipsLoading } =
    useListMyMemberships();

  const [scope, setScope] = useState<string>(() =>
    computeDefaultScope(isPlatformAdmin, memberships),
  );

  // Update scope default once memberships/admin status loads.
  useEffect(() => {
    if (!isPlatformAdmin && memberships.length > 0 && scope === "platform") {
      setScope(`org:${memberships[0].organization.id}`);
    }
  }, [isPlatformAdmin, memberships.length]); // eslint-disable-line react-hooks/exhaustive-deps

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
      setConfirmOpen(false);
      setConflict(null);
      setSelectedCategoryIds([]);
      setSelectedTagIds([]);
      // Re-derive scope on open so it reflects the latest admin/membership state.
      setScope(computeDefaultScope(isPlatformAdmin, memberships));
    }
  }, [open, flow.description]); // eslint-disable-line react-hooks/exhaustive-deps

  const blankableFields: BlankableFieldInfo[] = useMemo(() => {
    const nodes = Array.isArray(flow.data?.nodes) ? flow.data!.nodes : [];
    return scanBlankableFields({ nodes });
  }, [flow.data?.nodes]);

  // A user can save if they are a platform admin OR a member of at least one org.
  const canSave = isPlatformAdmin || memberships.length > 0;
  const canSubmit = name.trim().length > 0 && canSave;

  // Show a radio selector when an admin is also a member of one or more orgs
  // so they can choose between Platform scope and a specific org scope.
  const showScopeSelector = isPlatformAdmin && memberships.length > 0;

  const createTemplate = useCreateTemplate();
  const { data: templatesList } = useListTemplates();
  const updateTemplate = useUpdateTemplate();
  const assignTemplateTags = useAssignTemplateTags();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const submitting = createTemplate.isPending || updateTemplate.isPending;

  const toggleField = useCallback((node_id: string, field_name: string) => {
    setKeptFieldKeys((prev) => {
      const next = new Set(prev);
      const key = `${node_id}:${field_name}`;
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const buildPayload = useCallback(() => {
    const blanked_fields: BlankedField[] = blankableFields
      .filter((f) => !keptFieldKeys.has(`${f.node_id}:${f.field_name}`))
      .map((f) => ({
        node_id: f.node_id,
        field_name: f.field_name,
      }));

    const scopeValue = scope === "platform" ? "platform" : "org";
    const orgId = scope.startsWith("org:") ? scope.slice(4) : null;

    return {
      source_flow_id: flow.id!,
      name: name.trim(),
      description: description.trim() || null,
      icon,
      gradient,
      blanked_fields,
      scope: scopeValue as "platform" | "org",
      org_id: orgId,
      category_ids: selectedCategoryIds,
    };
  }, [
    blankableFields,
    keptFieldKeys,
    flow.id,
    name,
    description,
    icon,
    gradient,
    selectedCategoryIds,
    scope,
  ]);

  function handleSubmit() {
    if (!canSubmit) return;
    if (!flow.id) return;

    createTemplate.mutate(buildPayload(), {
      onSuccess: (created: TemplateRead) => {
        const finish = () => {
          setSuccessData({ title: `Template "${name.trim()}" saved` });
          onClose();
        };
        // Create flow: no existing server-side state to preserve, so only PUT
        // when the user picked tags.
        if (selectedTagIds.length > 0 && created?.id) {
          assignTemplateTags.mutate(
            { templateId: created.id, tagIds: selectedTagIds },
            {
              onSuccess: finish,
              // Best-effort: template is already saved; surface an error but still close.
              onError: () => {
                setErrorData({
                  title: "Template saved, but tag assignment failed",
                  list: ["You can re-apply tags from the template edit panel."],
                });
                onClose();
              },
            },
          );
        } else {
          finish();
        }
      },
      onError: (err: any) => {
        if (err?.response?.status !== 409) {
          setErrorData({
            title: "Failed to save template",
            list: [err?.response?.data?.detail ?? "Please try again."],
          });
          return;
        }
        const match = templatesList?.find(
          (t) => t.name.trim() === name.trim(),
        );
        if (match) {
          setConflict(match);
          setConfirmOpen(true);
          return;
        }
        // Fallback: list not ready yet.
        setNameError(
          "A template with that name already exists — pick a different one.",
        );
      },
    });
  }

  function handleOverwriteConfirm() {
    if (!conflict) return;
    updateTemplate.mutate(
      { templateId: conflict.id, body: buildPayload() },
      {
        onSuccess: () => {
          const finish = () => {
            setSuccessData({ title: `Template "${name.trim()}" updated` });
            setConfirmOpen(false);
            setConflict(null);
            onClose();
          };
          // Overwrite flow: PUT replaces the tag set; only fire when the
          // user picked tags to avoid wiping any existing server-side state.
          if (selectedTagIds.length > 0) {
            assignTemplateTags.mutate(
              { templateId: conflict.id, tagIds: selectedTagIds },
              {
                onSuccess: finish,
                onError: () => {
                  setErrorData({
                    title: "Template updated, but tag assignment failed",
                    list: [
                      "You can re-apply tags from the template edit panel.",
                    ],
                  });
                  setConfirmOpen(false);
                  setConflict(null);
                  onClose();
                },
              },
            );
          } else {
            finish();
          }
        },
        onError: (err: any) => {
          setConfirmOpen(false);
          setConflict(null);
          setErrorData({
            title: "Failed to overwrite template",
            list: [err?.response?.data?.detail ?? "Please try again."],
          });
        },
      },
    );
  }

  function handleOverwriteCancel() {
    setConfirmOpen(false);
    setConflict(null);
    setNameError(
      "A template with that name already exists — pick a different one.",
    );
  }

  return (
    <>
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

            {/* Scope selector: only shown when a platform admin is also a member of >= 1 org */}
            {showScopeSelector && (
              <fieldset className="space-y-1">
                <legend className="mb-1 block text-sm font-medium">
                  Scope
                </legend>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="template-scope"
                    value="platform"
                    checked={scope === "platform"}
                    onChange={() => setScope("platform")}
                  />
                  Platform
                </label>
                {memberships.map((m) => (
                  <label
                    key={m.organization.id}
                    className="flex cursor-pointer items-center gap-2 text-sm"
                  >
                    <input
                      type="radio"
                      name="template-scope"
                      value={`org:${m.organization.id}`}
                      checked={scope === `org:${m.organization.id}`}
                      onChange={() => setScope(`org:${m.organization.id}`)}
                    />
                    Org: {m.organization.name}
                  </label>
                ))}
              </fieldset>
            )}

            <div className="space-y-2">
              <span className="block text-sm font-medium">Categories</span>
              <CategoryChipPicker
                selectedIds={selectedCategoryIds}
                onChange={setSelectedCategoryIds}
                disabled={submitting}
              />
            </div>

            <div className="space-y-2">
              <span className="block text-sm font-medium">Tags</span>
              <TagPicker
                selectedIds={selectedTagIds}
                onChange={setSelectedTagIds}
                disabled={submitting}
              />
            </div>

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

            {/* Notice when the user is neither a platform admin nor an org member */}
            {!isPlatformAdmin && memberships.length === 0 && !membershipsLoading && (
              <p className="text-xs text-muted-foreground">
                Only platform administrators or organization members can save
                templates. Contact your admin to create a template on your
                behalf.
              </p>
            )}
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
              title={
                !canSave
                  ? "You aren't a member of any organization. Ask a platform admin to create a template on your behalf."
                  : undefined
              }
              onClick={handleSubmit}
            >
              {submitting ? "Saving…" : "Save as Template"}
            </Button>
          </div>
        </BaseModal.Footer>
      </BaseModal>
      <ConfirmOverwriteDialog
        open={confirmOpen}
        templateName={conflict?.name ?? ""}
        description={conflict?.description ?? null}
        updatedAt={conflict?.updated_at ?? new Date().toISOString()}
        submitting={updateTemplate.isPending}
        onCancel={handleOverwriteCancel}
        onConfirm={handleOverwriteConfirm}
      />
    </>
  );
}
