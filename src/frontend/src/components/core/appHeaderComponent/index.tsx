import { useContext, useEffect, useRef, useState } from "react";
import AlertDropdown from "@/alerts/alertDropDown";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import AdminNotificationBell from "@/components/core/adminNotificationBell";
import { AssistantButton } from "@/components/common/assistant";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ModelProviderCount from "@/components/common/modelProviderCountComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { AuthContext } from "@/contexts/authContext";
import CustomAccountMenu from "@/customization/components/custom-AccountMenu";
import { CustomOrgSelector } from "@/customization/components/custom-org-selector";
import { LANGFLOW_AGENTIC_EXPERIENCE } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import FlowMenu from "./components/FlowMenu";

export default function AppHeader(): JSX.Element {
  const notificationCenter = useAlertStore((state) => state.notificationCenter);
  const navigate = useCustomNavigate();
  const [activeState, setActiveState] = useState<"notifications" | null>(null);
  const notificationRef = useRef<HTMLButtonElement | null>(null);
  const notificationContentRef = useRef<HTMLDivElement | null>(null);
  const { userData } = useContext(AuthContext);
  const isAdmin = useAuthStore((state) => state.isAdmin);
  const isPlatformAdmin = userData?.is_platform_admin === true;
  const showAdminBell = Boolean(isAdmin || isPlatformAdmin);
  useTheme();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      const isNotificationButton = notificationRef.current?.contains(target);
      const isNotificationContent =
        notificationContentRef.current?.contains(target);

      if (!isNotificationButton && !isNotificationContent) {
        setActiveState(null);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const getNotificationBadge = () => {
    const baseClasses = "absolute h-1 w-1 rounded-full bg-destructive";
    return notificationCenter
      ? `${baseClasses} right-[0.3rem] top-[5px]`
      : "hidden";
  };

  return (
    <div
      className={`z-10 flex h-[48px] w-full items-center justify-between border-b pr-5 pl-2.5 dark:bg-background`}
      data-testid="app-header"
    >
      {/* Left Section */}
      <div
        className={`z-30 flex shrink-0 items-center gap-2`}
        data-testid="header_left_section_wrapper"
      >
        <Button
          unstyled
          onClick={() => navigate("/")}
          className="mr-1 flex h-16 w-16 cursor-pointer items-center"
          data-testid="icon-ChevronLeft"
        >
          <LangflowLogo className="h-10 w-10" />
        </Button>
        <CustomOrgSelector />
      </div>

      {/* Middle Section */}
      <div className="absolute left-1/2 -translate-x-1/2">
        <FlowMenu />
      </div>

      {/* Right Section */}
      <div
        className={`relative left-3 z-30 flex shrink-0 items-center gap-3`}
        data-testid="header_right_section_wrapper"
      >
        {false && <ModelProviderCount />}
        {LANGFLOW_AGENTIC_EXPERIENCE && <AssistantButton type="header" />}
        {showAdminBell && <AdminNotificationBell />}
        <AlertDropdown
          notificationRef={notificationContentRef}
          onClose={() => setActiveState(null)}
        >
          <Tooltip delayDuration={500}>
            <AlertDropdown onClose={() => setActiveState(null)}>
              <TooltipTrigger asChild>
                <Button
                  ref={notificationRef}
                  unstyled
                  onClick={() =>
                    setActiveState((prev) =>
                      prev === "notifications" ? null : "notifications",
                    )
                  }
                  data-testid="notification_button"
                >
                  <div className="hit-area-hover group relative items-center rounded-md px-2 py-2 text-muted-foreground">
                    <span className={getNotificationBadge()} />
                    <ForwardedIconComponent
                      name="Bell"
                      className={`side-bar-button-size h-4 w-4 ${
                        activeState === "notifications"
                          ? "text-primary"
                          : "text-muted-foreground group-hover:text-primary"
                      }`}
                      strokeWidth={2}
                    />
                    <span className="hidden whitespace-nowrap">
                      Notifications
                    </span>
                  </div>
                </Button>
              </TooltipTrigger>
            </AlertDropdown>
            <TooltipContent
              className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-10"
              side="bottom"
              avoidCollisions={false}
              sticky="always"
            >
              Notifications and errors
            </TooltipContent>
          </Tooltip>
        </AlertDropdown>
        <Separator
          orientation="vertical"
          className="my-auto h-7 dark:border-border"
        />

        <div className="flex">
          <CustomAccountMenu />
        </div>
      </div>
    </div>
  );
}
