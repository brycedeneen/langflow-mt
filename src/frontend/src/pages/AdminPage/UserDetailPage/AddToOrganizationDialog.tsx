import { useState } from "react";
import RolePicker from "@/components/common/rolePicker";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  useAddMember,
  useGetOrganizations,
} from "@/controllers/API/queries/admin";
import type { UserDetail } from "@/controllers/API/queries/admin/types";
import type { MembershipRole } from "@/constants/roles";
import useAlertStore from "@/stores/alertStore";

export default function AddToOrganizationDialog({
  open,
  onClose,
  user,
}: {
  open: boolean;
  onClose: () => void;
  user: UserDetail;
}) {
  const [q, setQ] = useState("");
  const [selectedOrg, setSelectedOrg] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [role, setRole] = useState<MembershipRole>("member");

  const existingOrgIds = new Set(
    user.memberships.map((m) => m.organization_id),
  );

  const { data } = useGetOrganizations(
    { q: q || undefined, limit: 20 },
    { enabled: open },
  );

  const candidates = (data?.items ?? []).filter(
    (o) => !existingOrgIds.has(o.id),
  );

  const { mutate: addMember } = useAddMember();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  const resetAndClose = () => {
    setQ("");
    setSelectedOrg(null);
    setRole("member");
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && resetAndClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add to organization</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Search organizations..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <ul className="max-h-48 overflow-auto rounded border">
            {candidates.map((o) => (
              <li
                key={o.id}
                className={`cursor-pointer px-3 py-2 hover:bg-muted ${
                  selectedOrg?.id === o.id ? "bg-muted" : ""
                }`}
                onClick={() =>
                  setSelectedOrg({ id: o.id, name: o.name })
                }
                data-testid={`org-candidate-${o.id}`}
              >
                {o.name}
              </li>
            ))}
            {candidates.length === 0 && (
              <li className="px-3 py-2 text-muted-foreground">No matches.</li>
            )}
          </ul>
          <div>
            <div className="mb-1 text-xs uppercase text-muted-foreground">
              Role
            </div>
            <RolePicker
              caller="platform_admin"
              current={role}
              onSelect={setRole}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={resetAndClose}>
            Cancel
          </Button>
          <Button
            disabled={!selectedOrg}
            onClick={() =>
              selectedOrg &&
              addMember(
                {
                  orgId: selectedOrg.id,
                  user_id: user.id,
                  role,
                } as any,
                {
                  onSuccess: () => {
                    setSuccess({ title: "Added to org" });
                    resetAndClose();
                  },
                  onError: (e: any) =>
                    setError({
                      title: "Add failed",
                      list: [e?.response?.data?.detail ?? String(e)],
                    }),
                },
              )
            }
          >
            Add
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
