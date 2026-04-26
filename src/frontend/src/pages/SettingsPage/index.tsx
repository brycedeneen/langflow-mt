import { Outlet, type To } from "react-router-dom";
import SideBarButtonsComponent from "@/components/core/sidebarComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
import { CustomStoreSidebar } from "@/customization/components/custom-store-sidebar";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_LANGFLOW_STORE,
} from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import ForwardedIconComponent from "../../components/common/genericIconComponent";
import PageLayout from "../../components/common/pageLayout";
export default function SettingsPage(): JSX.Element {
  const userData = useAuthStore((state) => state.userData);
  const isAdmin = useAuthStore((state) => state.isAdmin);

  const sidebarNavItems: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[] = [];

  sidebarNavItems.push({
    title: "General",
    href: "/settings/general",
    icon: (
      <ForwardedIconComponent
        name="SlidersHorizontal"
        className="w-4 shrink-0 justify-start stroke-[1.5]"
      />
    ),
  });

  sidebarNavItems.push(
    {
      title: "MCP Servers",
      href: "/settings/mcp-servers",
      icon: (
        <ForwardedIconComponent
          name="Mcp"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Global Variables",
      href: "/settings/global-variables",
      icon: (
        <ForwardedIconComponent
          name="Globe"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Model Providers",
      href: "/settings/model-providers",
      icon: (
        <ForwardedIconComponent
          name="Brain"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },

    {
      title: "Shortcuts",
      href: "/settings/shortcuts",
      icon: (
        <ForwardedIconComponent
          name="Keyboard"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Messages",
      href: "/settings/messages",
      icon: (
        <ForwardedIconComponent
          name="MessagesSquare"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Flow Assistant",
      href: "/settings/assistant",
      icon: (
        <ForwardedIconComponent
          name="Bot"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
  );

  if (isAdmin || userData?.is_superuser) {
    sidebarNavItems.push({
      title: "Component Management",
      href: "/settings/metadata",
      icon: (
        <ForwardedIconComponent
          name="Database"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  if (userData?.is_superuser) {
    sidebarNavItems.push({
      title: "Professional Services",
      href: "/settings/professional-services",
      icon: (
        <ForwardedIconComponent
          name="HandCoins"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  if (isAdmin) {
    sidebarNavItems.push({
      title: "User Admin",
      href: "/settings/users",
      icon: (
        <ForwardedIconComponent
          name="Users"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  if (userData?.is_platform_admin) {
    sidebarNavItems.push({
      title: "Org Admin",
      href: "/settings/organizations",
      icon: (
        <ForwardedIconComponent
          name="Building2"
          className="w-4 shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  // TODO: Remove this on cleanup
  if (!ENABLE_DATASTAX_LANGFLOW) {
    const langflowItems = CustomStoreSidebar(true, ENABLE_LANGFLOW_STORE);
    sidebarNavItems.splice(2, 0, ...langflowItems);
  }

  return (
    <PageLayout
      backTo={-1 as To}
      title="Settings"
      description="Manage the general settings for Amplify."
    >
      <SidebarProvider width="15rem" defaultOpen={false}>
        <SideBarButtonsComponent items={sidebarNavItems} />
        <main className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col overflow-x-hidden pt-1">
            <Outlet />
          </div>
        </main>
      </SidebarProvider>
    </PageLayout>
  );
}
