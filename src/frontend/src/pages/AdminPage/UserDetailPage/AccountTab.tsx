import { useNavigate } from "react-router-dom";
import { Switch } from "@/components/ui/switch";
import {
  useDeleteUsers,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import type { UserDetail } from "@/controllers/API/queries/admin/types";
import ConfirmationModal from "@/modals/confirmationModal";
import useAlertStore from "@/stores/alertStore";

export default function AccountTab({ user }: { user: UserDetail }) {
  const navigate = useNavigate();
  const { mutate: updateUser } = useUpdateUser();
  const { mutate: deleteUser } = useDeleteUsers();
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  const patch = (fields: Record<string, unknown>) =>
    updateUser(
      { user_id: user.id, user: fields } as any,
      {
        onSuccess: () => setSuccess({ title: "User updated" }),
        onError: (e: any) =>
          setError({
            title: "Update failed",
            list: [e?.response?.data?.detail ?? String(e)],
          }),
      },
    );

  return (
    <div className="flex max-w-2xl flex-col gap-8">
      <section>
        <h3 className="mb-3 text-lg font-semibold">Status</h3>
        <div className="grid grid-cols-2 gap-4">
          <ToggleRow
            testId="active-toggle"
            label="Active"
            description="Can log in and access the system"
            checked={user.is_active}
            onChange={(v) => patch({ is_active: v })}
          />
          <ToggleRow
            testId="platform-admin-toggle"
            label="Platform admin"
            description="Access to /settings admin console"
            checked={user.is_platform_admin}
            onChange={(v) => patch({ is_platform_admin: v })}
          />
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-lg font-semibold">Identity</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <Facts label="Username" value={user.username} />
          <Facts
            label="User ID"
            value={<span className="font-mono">{user.id}</span>}
          />
          <Facts
            label="Created"
            value={user.create_at?.slice(0, 10) ?? "—"}
          />
          <Facts
            label="Last login"
            value={
              user.last_login_at?.slice(0, 16).replace("T", " ") ?? "—"
            }
          />
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-lg font-semibold text-red-600">
          Danger zone
        </h3>
        <div className="flex items-center justify-between rounded-md border border-red-200 p-4">
          <div>
            <div className="font-semibold">Delete user</div>
            <div className="text-sm text-muted-foreground">
              Permanent. Removes the account and their personal organization.
            </div>
          </div>
          <ConfirmationModal
            size="x-small"
            title="Delete user"
            titleHeader="Delete user"
            modalContentTitle="Attention!"
            cancelText="Cancel"
            confirmationText="Delete"
            icon="UserMinus2"
            destructive
            data={user}
            index={0}
            onConfirm={() =>
              deleteUser(
                { user_id: user.id } as any,
                {
                  onSuccess: () => {
                    setSuccess({ title: "User deleted" });
                    navigate("/settings/users");
                  },
                  onError: (e: any) =>
                    setError({
                      title: "Delete failed",
                      list: [e?.response?.data?.detail ?? String(e)],
                    }),
                },
              )
            }
          >
            <ConfirmationModal.Content>
              Are you sure you want to delete this user? This cannot be
              undone.
            </ConfirmationModal.Content>
            <ConfirmationModal.Trigger>
              <span
                className="inline-flex h-10 items-center justify-center rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
                role="presentation"
              >
                Delete user
              </span>
            </ConfirmationModal.Trigger>
          </ConfirmationModal>
        </div>
      </section>
    </div>
  );
}

function ToggleRow({
  testId,
  label,
  description,
  checked,
  onChange,
}: {
  testId: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium">{label}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
        <Switch
          checked={checked}
          onCheckedChange={onChange}
          data-testid={testId}
        />
      </div>
    </div>
  );
}

function Facts({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div>{value}</div>
    </div>
  );
}
