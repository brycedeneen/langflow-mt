import { useParams, useNavigate } from "react-router-dom";
import { useGetOrganization } from "@/controllers/API/queries/admin";
import IconComponent from "../../../components/common/genericIconComponent";
import { Button } from "../../../components/ui/button";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../../../components/ui/tabs";
import OrganizationMembersTab from "./OrganizationMembersTab";
import OrganizationSettingsTab from "./OrganizationSettingsTab";

export default function OrganizationDetailPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const navigate = useNavigate();

  const { data: org, isLoading, isError } = useGetOrganization(
    { orgId: orgId! },
    { enabled: !!orgId },
  );

  return (
    <div className="admin-page-panel flex h-full flex-col pb-8">
      <div className="main-page-nav-arrangement">
        <span className="main-page-nav-title">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <IconComponent name="ChevronLeft" className="w-5" />
          </Button>
          <IconComponent name="Building2" className="w-6" />
          {isLoading ? "Loading…" : isError ? "Organization" : org?.name}
        </span>
      </div>

      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <IconComponent name="Loader2" className="h-8 w-8 animate-spin" />
        </div>
      ) : isError || !org ? (
        <div className="m-4 text-sm text-muted-foreground">
          Failed to load organization.
        </div>
      ) : (
        <Tabs defaultValue="members" className="mt-4 flex flex-1 flex-col">
          <TabsList className="border-b">
            <TabsTrigger value="members">Members</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>
          <TabsContent value="members" className="flex-1 overflow-auto pt-4">
            <OrganizationMembersTab orgId={org.id} members={org.members} />
          </TabsContent>
          <TabsContent value="settings" className="flex-1 overflow-auto pt-4">
            <OrganizationSettingsTab org={org} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
