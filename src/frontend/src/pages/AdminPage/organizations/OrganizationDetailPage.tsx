import { useParams, useNavigate } from "react-router-dom";
import { useGetOrganization } from "@/controllers/API/queries/admin";
import { Building2, ChevronLeft, Loader2 } from "lucide-react";
import { Button } from "../../../components/ui/button";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../../../components/ui/tabs";
import OrganizationAlertRulesTab from "./OrganizationAlertRulesTab";
import OrganizationMembersTab from "./OrganizationMembersTab";
import OrganizationSettingsTab from "./OrganizationSettingsTab";
import OrganizationThresholdsTab from "./OrganizationThresholdsTab";
import OrganizationUsageTab from "./OrganizationUsageTab";

export default function OrganizationDetailPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const navigate = useNavigate();

  const { data: org, isLoading, isError } = useGetOrganization(
    { orgId: orgId! },
    { enabled: !!orgId },
  );

  return (
    <div className="flex h-full w-full flex-col gap-4">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex flex-col">
          <h2
            className="flex items-center gap-2 text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/settings/organizations")}
            >
              <ChevronLeft className="w-5" />
            </Button>
            <Building2 className="w-5" />
            {isLoading ? "Loading…" : isError ? "Organization" : org?.name}
          </h2>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-full w-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin" />
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
            <TabsTrigger value="usage">Usage</TabsTrigger>
            <TabsTrigger value="thresholds">Thresholds</TabsTrigger>
            <TabsTrigger value="alert-rules">Alert rules</TabsTrigger>
          </TabsList>
          <TabsContent value="members" className="flex-1 overflow-auto pt-4">
            <OrganizationMembersTab orgId={org.id} members={org.members} />
          </TabsContent>
          <TabsContent value="settings" className="flex-1 overflow-auto pt-4">
            <OrganizationSettingsTab org={org} />
          </TabsContent>
          <TabsContent value="usage" className="flex-1 overflow-auto pt-4">
            <OrganizationUsageTab orgId={org.id} />
          </TabsContent>
          <TabsContent value="thresholds" className="flex-1 overflow-auto pt-4">
            <OrganizationThresholdsTab orgId={org.id} />
          </TabsContent>
          <TabsContent value="alert-rules" className="flex-1 overflow-auto pt-4">
            <OrganizationAlertRulesTab orgId={org.id} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
