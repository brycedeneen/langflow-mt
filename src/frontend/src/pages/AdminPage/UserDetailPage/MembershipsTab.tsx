import { useState } from "react";
import RolePicker from "@/components/common/rolePicker";
import { Button } from "@/components/ui/button";
import { useRemoveMember } from "@/controllers/API/queries/admin";
import type { UserDetail } from "@/controllers/API/queries/admin/types";
import { useUpdateMemberRole } from "@/controllers/API/queries/admin/use-update-member-role";
import type { MembershipRole } from "@/constants/roles";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import AddToOrganizationDialog from "./AddToOrganizationDialog";

export default function MembershipsTab({ user }: { user: UserDetail }) {
  const [addOpen, setAddOpen] = useState(false);
  const { mutate: updateRole } = useUpdateMemberRole();
  const { mutate: removeMember } = useRemoveMember();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  // Platform admins always have the highest privilege when viewing this page.
  const callerRole = "platform_admin" as const;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          Organizations this user belongs to
        </span>
        <Button onClick={() => setAddOpen(true)}>+ Add to organization</Button>
      </div>
      <div className="overflow-hidden rounded-md border">
        <table className="w-full">
          <thead className="bg-muted/50 text-left text-sm">
            <tr>
              <th className="px-3 py-2">Organization</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Joined</th>
              <th className="w-28 px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {user.memberships.map((m) => (
              <tr
                key={m.organization_id}
                className="border-t text-sm"
                data-testid={`membership-row-${m.organization_id}`}
              >
                <td className="px-3 py-2">
                  {m.organization_name}
                  {m.is_personal && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      (personal)
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {m.is_personal ? (
                    <span>
                      Owner{" "}
                      <span className="text-xs text-muted-foreground">
                        (locked)
                      </span>
                    </span>
                  ) : (
                    <RolePicker
                      caller={callerRole}
                      current={m.role as MembershipRole}
                      onSelect={(next) =>
                        updateRole(
                          {
                            orgId: m.organization_id,
                            userId: user.id,
                            role: next,
                          } as any,
                          {
                            onSuccess: () =>
                              setSuccess({ title: "Role updated" }),
                            onError: (e: any) =>
                              setError({
                                title: "Role change failed",
                                list: [
                                  e?.response?.data?.detail ?? String(e),
                                ],
                              }),
                          },
                        )
                      }
                    />
                  )}
                </td>
                <td className="px-3 py-2">{m.joined_at?.slice(0, 10)}</td>
                <td className="px-3 py-2 text-right">
                  {m.is_personal ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    <ConfirmationModal
                      size="x-small"
                      title="Remove"
                      titleHeader="Remove from organization"
                      cancelText="Cancel"
                      confirmationText="Confirm"
                      icon="Trash2"
                      data={m}
                      index={0}
                      onConfirm={() =>
                        removeMember(
                          {
                            orgId: m.organization_id,
                            userId: user.id,
                          } as any,
                          {
                            onSuccess: () =>
                              setSuccess({ title: "Member removed" }),
                            onError: (e: any) =>
                              setError({
                                title: "Remove failed",
                                list: [
                                  e?.response?.data?.detail ?? String(e),
                                ],
                              }),
                          },
                        )
                      }
                    >
                      <ConfirmationModal.Content>
                        Remove this user from {m.organization_name}?
                      </ConfirmationModal.Content>
                      <ConfirmationModal.Trigger>
                        <span
                          role="presentation"
                          className="cursor-pointer text-red-600 hover:underline"
                          data-testid={`remove-${m.organization_id}`}
                        >
                          Remove
                        </span>
                      </ConfirmationModal.Trigger>
                    </ConfirmationModal>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <AddToOrganizationDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        user={user}
      />
    </div>
  );
}
