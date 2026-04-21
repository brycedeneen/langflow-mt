import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatRelativeTime } from "./formatRelativeTime";

type Props = {
  open: boolean;
  templateName: string;
  description: string | null;
  updatedAt: string; // ISO
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export default function ConfirmOverwriteDialog({
  open,
  templateName,
  description,
  updatedAt,
  submitting,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center gap-2">
              <AlertTriangle
                className="h-5 w-5 text-yellow-600"
                strokeWidth={2}
              />
              <span>Template "{templateName}" already exists</span>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-2 text-sm">
          {description ? (
            <p className="line-clamp-3 text-muted-foreground">{description}</p>
          ) : (
            <p className="italic text-muted-foreground">(no description)</p>
          )}
          <p className="text-xs text-muted-foreground">
            Last updated {formatRelativeTime(updatedAt)}
          </p>
        </div>

        <DialogFooter>
          <Button
            autoFocus
            variant="outline"
            type="button"
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            type="button"
            aria-label="Overwrite"
            disabled={submitting}
            onClick={onConfirm}
          >
            {submitting ? "Overwriting…" : "Overwrite"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
