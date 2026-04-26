import { useState } from "react";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useArchiveTemplate } from "@/controllers/API/queries/templates/use-archive-template";
import { useUnarchiveTemplate } from "@/controllers/API/queries/templates/use-unarchive-template";
import { useHardDeleteTemplate } from "@/controllers/API/queries/templates/use-hard-delete-template";
import { useListMyMemberships } from "@/controllers/API/queries/memberships";
import { useIsPlatformAdmin } from "@/hooks/use-is-platform-admin";
import useAuthStore from "@/stores/authStore";
import useAlertStore from "@/stores/alertStore";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/common/genericIconComponent";
import TagChip from "@/components/common/TagChip";
import type { TemplateCardComponentProps } from "../../../../types/templates/types";
import type { TemplateRead } from "@/types/template";
import { coerceTagList } from "@/types/tag/runtime-validate";
import TemplateCardAdminMenu from "../TemplateCardAdminMenu";
import TemplateEditPanel from "../TemplateEditPanel";

interface TemplateCardComponentExtendedProps
  extends TemplateCardComponentProps {
  disabled?: boolean;
  /** Full TemplateRead data for admin actions. If absent, no admin menu is shown. */
  templateData?: TemplateRead;
  isAdmin?: boolean;
}

/**
 * canEditTemplate: user may edit when they are (a) a platform admin, (b) an org
 * admin of the template's org, or (c) the template's creator (scope=org case).
 */
function canEditTemplate(
  template: TemplateRead,
  isPlatformAdmin: boolean,
  userId: string | undefined,
  orgAdminOfOrgIds: Set<string>,
): boolean {
  if (isPlatformAdmin) return true;
  if (template.scope !== "org" || template.org_id == null) return false;
  if (orgAdminOfOrgIds.has(template.org_id)) return true;
  return template.created_by === userId;
}

export default function TemplateCardComponent({
  example,
  onClick,
  disabled = false,
  selected = false,
  onSelect,
  templateData,
  isAdmin = false,
}: TemplateCardComponentExtendedProps) {
  const swatchIndex =
    (example.gradient && !isNaN(parseInt(example.gradient))
      ? parseInt(example.gradient)
      : getNumberFromString(example.gradient ?? example.name)) %
    swatchColors.length;

  const isPlatformAdmin = useIsPlatformAdmin();
  const userData = useAuthStore((s) => s.userData);
  const { data: memberships = [] } = useListMyMemberships();
  const orgAdminOfOrgIds = new Set<string>(
    memberships.filter((m) => m.is_org_admin).map((m) => m.organization.id),
  );
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const [editOpen, setEditOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteBlockedFlows, setDeleteBlockedFlows] = useState<string[] | null>(null);

  const { mutate: archiveMutate } = useArchiveTemplate();
  const { mutate: unarchiveMutate } = useUnarchiveTemplate();
  const { mutate: hardDeleteMutate, isPending: isDeleting } = useHardDeleteTemplate();

  const isArchived = templateData?.archived_at != null;

  const canEdit =
    templateData !== undefined &&
    canEditTemplate(
      templateData,
      isPlatformAdmin,
      userData?.id,
      orgAdminOfOrgIds,
    );

  // Archived cards are not selectable — clicks are blocked.
  const effectivelyDisabled = disabled || isArchived;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!effectivelyDisabled) onSelect?.();
    }
  };

  const handleArchiveToggle = () => {
    if (!templateData) return;
    if (isArchived) {
      unarchiveMutate(
        { templateId: templateData.id },
        {
          onSuccess: () =>
            setSuccessData({ title: `"${templateData.name}" unarchived` }),
          onError: () =>
            setErrorData({ title: `Failed to unarchive "${templateData.name}"` }),
        },
      );
    } else {
      archiveMutate(
        { templateId: templateData.id },
        {
          onSuccess: () =>
            setSuccessData({ title: `"${templateData.name}" archived` }),
          onError: () =>
            setErrorData({ title: `Failed to archive "${templateData.name}"` }),
        },
      );
    }
  };

  const handleDelete = () => {
    setDeleteBlockedFlows(null);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (!templateData) return;
    hardDeleteMutate(
      { templateId: templateData.id },
      {
        onSuccess: () => {
          setDeleteDialogOpen(false);
          setSuccessData({ title: `Template "${templateData.name}" deleted` });
        },
        onError: (err: unknown) => {
          const axiosErr = err as {
            response?: { status?: number; data?: { detail?: { referencing_flow_ids?: string[] } } };
          };
          if (axiosErr?.response?.status === 409) {
            const ids = axiosErr.response?.data?.detail?.referencing_flow_ids ?? [];
            setDeleteBlockedFlows(ids);
          } else {
            setDeleteDialogOpen(false);
            setErrorData({ title: `Failed to delete "${templateData?.name}"` });
          }
        },
      },
    );
  };

  const card = (
    <div
      data-testid={`template-${convertTestName(example.name)}`}
      className={cn(
        "group relative flex gap-3 overflow-hidden rounded-md p-3 hover:bg-muted focus-visible:bg-muted",
        effectivelyDisabled ? "cursor-default opacity-80" : "cursor-pointer",
        isArchived && "opacity-50",
        selected && "border-2 border-primary",
      )}
      tabIndex={effectivelyDisabled ? -1 : 0}
      onKeyDown={handleKeyDown}
      onClick={() => !effectivelyDisabled && onSelect?.()}
    >
      {/* Selection dot */}
      <div
        className={cn(
          "absolute right-3 top-3 h-4 w-4 rounded-full border-2 z-10",
          selected ? "border-primary bg-primary" : "border-muted-foreground",
        )}
        aria-hidden
      />

      {/* Archived badge */}
      {isArchived && (
        <div className="absolute left-2 top-2 z-10 rounded-sm bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Archived
        </div>
      )}

      {/* Archived overlay — blocks card-select interaction */}
      {isArchived && (
        <div className="absolute inset-0 z-10 rounded-md" aria-hidden />
      )}

      {/* Admin ⋯ menu — rendered above the archived overlay so it still works */}
      {canEdit && templateData && (
        <TemplateCardAdminMenu
          template={templateData}
          canEdit={canEdit}
          onEdit={() => setEditOpen(true)}
          onArchiveToggle={handleArchiveToggle}
          onDelete={handleDelete}
        />
      )}

      <div
        className={cn(
          "relative h-20 w-20 shrink-0 overflow-hidden rounded-md p-4 outline-hidden ring-ring",
          swatchColors[swatchIndex],
        )}
      >
        <IconComponent
          name={example.icon || "FileText"}
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 duration-300 group-hover:scale-105 group-focus-visible:scale-105"
        />
      </div>
      <div className="flex flex-1 flex-col justify-between">
        <div
          data-testid="text_card_container"
          role={convertTestName(example.name)}
        >
          <div className="flex w-full items-center">
            <h3
              className="line-clamp-3 font-semibold"
              data-testid={`template_${convertTestName(example.name)}`}
            >
              {example.name}
            </h3>
            {!isArchived && (
              <ForwardedIconComponent
                name="ArrowRight"
                className="mr-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
              />
            )}
          </div>
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
            {example.description}
          </p>
          {/* Tag chips — up to 3 with +N overflow (spec B.6). Wrapped in
              length > 0 so cards without tags do not render an empty row. */}
          {/* template.tags is populated by TemplateRead (0b5d4aae7c). */}
          {(() => {
            const cardTags = coerceTagList(
              (templateData as { tags?: unknown } | undefined)?.tags,
            );
            if (cardTags.length === 0) return null;
            const MAX = 3;
            const visible = cardTags.slice(0, MAX);
            const overflow = Math.max(0, cardTags.length - MAX);
            return (
              <div
                className="mt-2 flex flex-wrap gap-1"
                data-testid={`template-tags-${templateData?.id ?? example.id}`}
              >
                {visible.map((t) => (
                  <TagChip key={t.id} tag={t} />
                ))}
                {overflow > 0 && (
                  <Tooltip delayDuration={500}>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                        +{overflow}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent
                      className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                      avoidCollisions={false}
                      sticky="always"
                    >
                      {cardTags
                        .slice(MAX)
                        .map((t) => t.name)
                        .join(", ")}
                    </TooltipContent>
                  </Tooltip>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Wrap archived cards in a tooltip */}
      {isArchived ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>{card}</TooltipTrigger>
            <TooltipContent side="top">
              Unarchive to create flows from this template.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        card
      )}

      {/* Edit panel */}
      {templateData && (
        <TemplateEditPanel
          template={templateData}
          open={editOpen}
          onOpenChange={setEditOpen}
        />
      )}

      {/* Delete confirm dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Permanently delete &ldquo;{templateData?.name}&rdquo;?
            </DialogTitle>
            {deleteBlockedFlows !== null ? (
              <DialogDescription className="text-destructive">
                Cannot delete — {deleteBlockedFlows.length} flow
                {deleteBlockedFlows.length !== 1 ? "s" : ""} still reference
                this template.
              </DialogDescription>
            ) : (
              <DialogDescription>This cannot be undone.</DialogDescription>
            )}
          </DialogHeader>
          <DialogFooter>
            {deleteBlockedFlows !== null ? (
              <Button
                variant="outline"
                onClick={() => setDeleteDialogOpen(false)}
              >
                Close
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  onClick={() => setDeleteDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={confirmDelete}
                  disabled={isDeleting}
                >
                  {isDeleting ? "Deleting…" : "Delete"}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
