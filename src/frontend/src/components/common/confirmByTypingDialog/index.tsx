import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ConfirmByTypingDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmText: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
  confirmLabel?: string;
}

export default function ConfirmByTypingDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmText,
  destructive = true,
  onConfirm,
  confirmLabel,
}: ConfirmByTypingDialogProps) {
  const [typed, setTyped] = useState("");
  const [pending, setPending] = useState(false);
  const enabled = typed === confirmText && !pending;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!pending) {
          setTyped("");
          onOpenChange(v);
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <p className="text-sm">
            Type{" "}
            <code className="rounded bg-muted px-1 py-0.5">{confirmText}</code>{" "}
            to confirm.
          </p>
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={confirmText}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            Cancel
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={!enabled}
            onClick={async () => {
              setPending(true);
              try {
                await onConfirm();
              } finally {
                setPending(false);
              }
            }}
          >
            {confirmLabel ?? (destructive ? "Delete" : "Confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
