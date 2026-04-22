import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ConfirmByTypingDialog from "@/components/common/confirmByTypingDialog";
import { Button } from "@/components/ui/button";
import { useDeleteOrganization } from "@/controllers/API/queries/admin";
import type { OrgDetail } from "@/controllers/API/queries/admin";

export default function OrganizationSettingsTab({ org }: { org: OrgDetail }) {
  const [confirming, setConfirming] = useState(false);
  const nav = useNavigate();
  const del = useDeleteOrganization();

  return (
    <div className="space-y-6">
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
