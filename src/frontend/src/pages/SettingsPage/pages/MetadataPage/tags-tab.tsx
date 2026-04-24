import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateTag,
  useDeleteTag,
  useListTagsAdmin,
  useUpdateTag,
} from "@/controllers/API/queries/admin";
import { useIsPlatformAdmin } from "@/hooks/use-is-platform-admin";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import { TAG_COLORS, type TagColor, type TagRead } from "@/types/tag";
import { cn } from "@/utils/utils";

const COLOR_BG_MAP: Record<TagColor, string> = {
  slate: "bg-slate-500",
  red: "bg-red-500",
  orange: "bg-orange-500",
  amber: "bg-amber-500",
  green: "bg-green-500",
  teal: "bg-teal-500",
  sky: "bg-sky-500",
  blue: "bg-blue-500",
  violet: "bg-violet-500",
  pink: "bg-pink-500",
};

const NAME_MAX = 64;
const DESCRIPTION_MAX = 1024;

type DialogState =
  | { mode: "create" }
  | { mode: "edit"; tag: TagRead }
  | null;

export function TagsTab() {
  const { data: tags = [], isPending } = useListTagsAdmin();
  const createTag = useCreateTag();
  const updateTag = useUpdateTag();
  const deleteTag = useDeleteTag();

  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  const isPlatformAdmin = useIsPlatformAdmin();

  const [dialog, setDialog] = useState<DialogState>(null);
  const [tagPendingDelete, setTagPendingDelete] = useState<TagRead | null>(
    null,
  );

  const confirmDelete = () => {
    if (!tagPendingDelete) return;
    const id = tagPendingDelete.id;
    deleteTag.mutate(
      { id },
      {
        onSuccess: () => setSuccess({ title: "Tag deleted" }),
        onError: (e: unknown) =>
          setError({
            title: "Delete failed",
            list: [extractDetail(e) ?? "Unknown error"],
          }),
      },
    );
    setTagPendingDelete(null);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col">
          <h2 className="text-lg font-semibold">Tags</h2>
          <p className="text-sm text-muted-foreground">
            Manage the tag vocabulary used across flows and templates.
          </p>
        </div>
        {isPlatformAdmin ? (
          <Button
            variant="default"
            size="sm"
            onClick={() => setDialog({ mode: "create" })}
          >
            New tag
          </Button>
        ) : null}
      </div>

      {isPending ? (
        <div className="text-sm text-muted-foreground">Loading tags…</div>
      ) : tags.length === 0 ? (
        <div className="border rounded-md p-6 text-center text-sm text-muted-foreground">
          No tags yet. Create the first one.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {tags.map((tag) => (
            <div
              key={tag.id}
              className="flex items-center justify-between border rounded-md p-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span
                  aria-hidden="true"
                  className={cn(
                    "inline-block h-3 w-3 rounded-full shrink-0",
                    COLOR_BG_MAP[tag.color],
                  )}
                />
                <div className="flex flex-col min-w-0">
                  <span className="font-medium truncate">{tag.name}</span>
                  {tag.description ? (
                    <span className="text-xs text-muted-foreground truncate">
                      {tag.description}
                    </span>
                  ) : null}
                </div>
              </div>
              {isPlatformAdmin ? (
                <div className="flex gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDialog({ mode: "edit", tag })}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setTagPendingDelete(tag)}
                  >
                    Delete
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {dialog ? (
        <TagDialog
          state={dialog}
          onClose={() => setDialog(null)}
          onCreate={(body) => createTag.mutateAsync(body)}
          onUpdate={(id, body) => updateTag.mutateAsync({ id, ...body })}
          onSuccessClose={(mode) => {
            setSuccess({
              title: mode === "create" ? "Tag created" : "Tag updated",
            });
            setDialog(null);
          }}
          isSubmitting={createTag.isPending || updateTag.isPending}
        />
      ) : null}

      {tagPendingDelete ? (
        <ConfirmationModal
          open={tagPendingDelete !== null}
          title="Delete tag"
          titleHeader={`Delete "${tagPendingDelete.name}"`}
          cancelText="Cancel"
          confirmationText="Delete"
          destructive
          icon="Trash2"
          onConfirm={confirmDelete}
          onClose={() => setTagPendingDelete(null)}
          onCancel={() => setTagPendingDelete(null)}
        >
          <ConfirmationModal.Content>
            <span>
              This will remove the tag from all flows and templates. This action
              cannot be undone.
            </span>
          </ConfirmationModal.Content>
        </ConfirmationModal>
      ) : null}
    </div>
  );
}

type TagDialogProps = {
  state: Exclude<DialogState, null>;
  onClose: () => void;
  onCreate: (body: {
    name: string;
    color: TagColor;
    description: string | null;
  }) => Promise<unknown>;
  onUpdate: (
    id: string,
    body: { name: string; color: TagColor; description: string | null },
  ) => Promise<unknown>;
  onSuccessClose: (mode: "create" | "edit") => void;
  isSubmitting: boolean;
};

function TagDialog({
  state,
  onClose,
  onCreate,
  onUpdate,
  onSuccessClose,
  isSubmitting,
}: TagDialogProps) {
  const initial: TagRead | null = state.mode === "edit" ? state.tag : null;
  const [name, setName] = useState(initial?.name ?? "");
  const [color, setColor] = useState<TagColor>(initial?.color ?? "slate");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError("Name is required.");
      return;
    }
    if (trimmedName.length > NAME_MAX) {
      setFormError(`Name must be ${NAME_MAX} characters or fewer.`);
      return;
    }
    if (description.length > DESCRIPTION_MAX) {
      setFormError(
        `Description must be ${DESCRIPTION_MAX} characters or fewer.`,
      );
      return;
    }
    const body = {
      name: trimmedName,
      color,
      description: description.trim() ? description.trim() : null,
    };
    try {
      if (state.mode === "create") {
        await onCreate(body);
      } else {
        await onUpdate(state.tag.id, body);
      }
      // Parent unmounts us on success; don't touch state afterward.
      onSuccessClose(state.mode);
    } catch (err: unknown) {
      const detail = extractDetail(err);
      if (detail && /already exists/i.test(detail)) {
        setFormError("A tag with that name already exists");
      } else if (detail) {
        setFormError(detail);
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    }
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {state.mode === "create" ? "New tag" : "Edit tag"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Name</span>
            <Input
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={NAME_MAX}
              required
            />
          </label>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Color</span>
            <div
              role="radiogroup"
              aria-label="Color"
              className="flex flex-wrap gap-2"
            >
              {TAG_COLORS.map((c) => {
                const selected = c === color;
                return (
                  <button
                    key={c}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    aria-label={c}
                    onClick={() => setColor(c)}
                    className={cn(
                      "h-7 w-7 rounded-full border-2 transition-all",
                      COLOR_BG_MAP[c],
                      selected
                        ? "border-foreground scale-110"
                        : "border-transparent hover:border-muted-foreground/40",
                    )}
                  />
                );
              })}
            </div>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Description</span>
            <Textarea
              aria-label="Description"
              placeholder="Optional short description."
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={DESCRIPTION_MAX}
            />
          </label>

          {formError ? (
            <div
              role="alert"
              className="text-sm text-destructive-foreground bg-destructive/10 border border-destructive/30 rounded-md px-3 py-2"
            >
              {formError}
            </div>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              {state.mode === "create" ? "Create" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function extractDetail(err: unknown): string | null {
  if (err && typeof err === "object") {
    const maybeAxios = err as {
      response?: { data?: { detail?: unknown } };
      message?: unknown;
    };
    const detail = maybeAxios.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first === "string") return first;
      if (first && typeof first === "object" && "msg" in first) {
        const msg = (first as { msg?: unknown }).msg;
        if (typeof msg === "string") return msg;
      }
    }
    if (typeof maybeAxios.message === "string") return maybeAxios.message;
  }
  return null;
}
