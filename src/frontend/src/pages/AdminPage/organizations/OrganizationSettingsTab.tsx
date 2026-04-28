import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ConfirmByTypingDialog from "@/components/common/confirmByTypingDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useDeleteOrganization,
  useUpdateOrganization,
} from "@/controllers/API/queries/admin";
import type { OrgDetail } from "@/controllers/API/queries/admin";
import useAlertStore from "@/stores/alertStore";

export default function OrganizationSettingsTab({ org }: { org: OrgDetail }) {
  const [confirming, setConfirming] = useState(false);
  const [name, setName] = useState(org.name);
  const nav = useNavigate();
  const del = useDeleteOrganization();
  const update = useUpdateOrganization();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const trimmed = name.trim();
  const dirty = trimmed !== org.name;
  const canSave =
    dirty && trimmed.length > 0 && !update.isPending && !org.is_personal;

  function handleSave() {
    update.mutate(
      { orgId: org.id, name: trimmed },
      {
        onSuccess: (updated) => {
          setName(updated.name);
          setSuccessData({ title: "Organization renamed." });
        },
        onError: (error: any) => {
          setErrorData({
            title: "Failed to rename organization",
            list: [
              error?.response?.data?.detail ??
                "An unexpected error occurred.",
            ],
          });
        },
      },
    );
  }

  function handleCancel() {
    setName(org.name);
  }

  return (
    <div className="space-y-6">
      <div className="flex max-w-md flex-col gap-2">
        <label className="text-sm font-medium" htmlFor="org-name">
          Name
        </label>
        <Input
          id="org-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={org.is_personal || update.isPending}
          title={
            org.is_personal
              ? "Personal organizations cannot be renamed"
              : undefined
          }
          maxLength={200}
        />
        <div className="flex gap-2">
          <Button
            variant="primary"
            disabled={!canSave}
            onClick={handleSave}
          >
            {update.isPending ? "Saving..." : "Save"}
          </Button>
          <Button
            variant="outline"
            disabled={!dirty || update.isPending}
            onClick={handleCancel}
          >
            Cancel
          </Button>
        </div>
      </div>

      <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Slug</dt>
        <dd>{org.slug}</dd>
        <dt className="text-muted-foreground">Created</dt>
        <dd>{new Date(org.created_at).toLocaleString()}</dd>
      </dl>

      <div className="border-t pt-4">
        <h3 className="font-medium">Danger zone</h3>
        <p className="my-2 text-sm text-muted-foreground">
          Deleting an organization permanently removes it along with all of its
          flows, files, deployments, and memberships. This cannot be undone.
        </p>
        <Button
          variant="destructive"
          disabled={org.is_personal}
          onClick={() => setConfirming(true)}
          title={
            org.is_personal
              ? "Personal organizations cannot be deleted"
              : undefined
          }
        >
          Delete organization
        </Button>
      </div>
      <ConfirmByTypingDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete organization"
        description="This permanently deletes the organization and all flows, files, deployments, and memberships inside it."
        confirmText={org.name}
        onConfirm={async () => {
          await del.mutateAsync({ orgId: org.id, confirm_name: org.name });
          setConfirming(false);
          nav("/settings/organizations");
        }}
      />
    </div>
  );
}
