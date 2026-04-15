import type { OrgDetail } from "@/controllers/API/queries/admin";
import { Button } from "../../../components/ui/button";

interface OrganizationSettingsTabProps {
  org: OrgDetail;
}

export default function OrganizationSettingsTab({
  org,
}: OrganizationSettingsTabProps) {
  return (
    <div className="flex flex-col gap-6">
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-3 text-sm">
        <dt className="font-medium text-muted-foreground">Slug</dt>
        <dd>{org.slug}</dd>
        <dt className="font-medium text-muted-foreground">Created</dt>
        <dd>{new Date(org.created_at).toISOString().split("T")[0]}</dd>
      </dl>

      <div className="border-t pt-4">
        <p className="mb-3 text-sm text-muted-foreground">Danger zone</p>
        <Button variant="destructive" disabled title="Coming soon">
          Delete organization (coming soon)
        </Button>
      </div>
    </div>
  );
}
