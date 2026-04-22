import { useNavigate, useParams } from "react-router-dom";
import RolePicker from "@/components/common/rolePicker";
import type { MembershipRole } from "@/constants/roles";
import {
  useGetOrganization,
  useRemoveMember,
} from "@/controllers/API/queries/admin";
import { useUpdateMemberRole } from "@/controllers/API/queries/admin/use-update-member-role";
import CustomLoader from "@/customization/components/custom-loader";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";

export default function OrgMemberDetailPage() {
  const { orgId = "", userId = "" } = useParams();
  const navigate = useNavigate();
  const { data: org, isPending } = useGetOrganization({ orgId });
  const { mutate: updateRole } = useUpdateMemberRole();
  const { mutate: removeMember } = useRemoveMember();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  const currentUser = useAuthStore((s) => s.userData);
  const callerMembership = org?.members.find(
    (m: any) => m.user_id === currentUser?.id,
  );
  const callerRole: MembershipRole | "platform_admin" = currentUser?.is_platform_admin
    ? "platform_admin"
    : ((callerMembership?.role as MembershipRole) ?? "viewer");

  if (isPending) return <CustomLoader remSize={12} />;
  if (!org) return <div className="p-6">Organization not found.</div>;
  const member = org.members.find((m: any) => m.user_id === userId);
  if (!member) return <div className="p-6">Member not found.</div>;

  return (
    <div className="max-w-2xl p-6">
      <button
        className="mb-4 text-sm text-muted-foreground hover:underline"
        onClick={() => navigate(`/settings/organizations/${orgId}`)}
      >
        ← Back to {org.name}
      </button>
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground">
          {member.username.slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="font-semibold">{member.username}</div>
          <div className="text-sm text-muted-foreground">
            Member of {org.name}
          </div>
        </div>
        {"is_active" in member && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              (member as any).is_active
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
            data-testid="status-pill"
          >
            ● {(member as any).is_active ? "Active" : "Inactive"}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded border p-3">
          <div className="mb-1 text-xs uppercase text-muted-foreground">
            Role in {org.name}
          </div>
          <RolePicker
            caller={callerRole}
            current={member.role as MembershipRole}
            onSelect={(next) =>
              updateRole(
                { orgId, userId, role: next } as any,
                {
                  onSuccess: () => setSuccess({ title: "Role updated" }),
                  onError: (e: any) =>
                    setError({
                      title: "Role change failed",
                      list: [e?.response?.data?.detail ?? String(e)],
                    }),
                },
              )
            }
          />
        </div>
        <div className="rounded border border-red-200 p-3">
          <div className="mb-1 text-xs uppercase text-red-600">
            Remove from org
          </div>
          <ConfirmationModal
            size="x-small"
            title="Remove"
            titleHeader="Remove from organization"
            cancelText="Cancel"
            confirmationText="Confirm"
            icon="Trash2"
            data={member}
            index={0}
            onConfirm={() =>
              removeMember(
                { orgId, userId } as any,
                {
                  onSuccess: () => {
                    setSuccess({ title: "Member removed" });
                    navigate(`/settings/organizations/${orgId}`);
                  },
                  onError: (e: any) =>
                    setError({
                      title: "Remove failed",
                      list: [e?.response?.data?.detail ?? String(e)],
                    }),
                },
              )
            }
          >
            <ConfirmationModal.Content>
              Remove {member.username} from {org.name}?
            </ConfirmationModal.Content>
            <ConfirmationModal.Trigger>
              <span
                role="presentation"
                className="inline-block cursor-pointer rounded bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
                data-testid="remove-member-trigger"
              >
                Remove
              </span>
            </ConfirmationModal.Trigger>
          </ConfirmationModal>
        </div>
      </div>
      <p className="mt-6 text-xs text-muted-foreground">
        Org admins cannot toggle Active, Platform Admin, or see memberships in
        other orgs.
      </p>
    </div>
  );
}
