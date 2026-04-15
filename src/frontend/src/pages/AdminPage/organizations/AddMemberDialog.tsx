import { useState } from "react";
import { useAddMember, useSearchUsers } from "@/controllers/API/queries/admin";
import type { UserRow } from "@/controllers/API/queries/admin";
import { Button } from "../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../../../components/ui/dialog";
import { Input } from "../../../components/ui/input";
import IconComponent from "../../../components/common/genericIconComponent";

interface AddMemberDialogProps {
  orgId: string;
  open: boolean;
  onClose: () => void;
}

export default function AddMemberDialog({
  orgId,
  open,
  onClose,
}: AddMemberDialogProps) {
  const [search, setSearch] = useState("");

  const { data, isLoading } = useSearchUsers(
    { q: search || undefined, limit: 20 },
    { enabled: open },
  );

  const { mutate: addMember, isPending } = useAddMember({
    onSuccess: () => {
      onClose();
      setSearch("");
    },
  });

  const allUsers: UserRow[] = data?.items ?? [];
  // Filter out users already in this org
  const candidates = allUsers.filter(
    (u) => !u.memberships.some((m) => m.organization_id === orgId),
  );

  function handleAdd(user: UserRow) {
    addMember({ orgId, user_id: user.id });
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) {
      onClose();
      setSearch("");
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add member</DialogTitle>
        </DialogHeader>

        <Input
          placeholder="Search users…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />

        <div className="max-h-64 overflow-y-auto rounded-md border bg-background custom-scroll">
          {isLoading ? (
            <div className="flex items-center justify-center p-4">
              <IconComponent name="Loader2" className="h-5 w-5 animate-spin" />
            </div>
          ) : candidates.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              {search ? "No matching users." : "Start typing to search users."}
            </p>
          ) : (
            <ul>
              {candidates.map((user) => (
                <li
                  key={user.id}
                  className="flex items-center justify-between px-3 py-2 hover:bg-muted/50"
                >
                  <div>
                    <p className="text-sm font-medium">{user.username}</p>
                    {user.memberships.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {user.memberships
                          .map((m) => m.organization_name)
                          .join(", ")}
                      </p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={isPending}
                    onClick={() => handleAdd(user)}
                  >
                    Add
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
