import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useGetUnreadNotificationsCount } from "@/controllers/API/queries/admin/use-get-unread-notifications-count";

export default function AdminNotificationBell() {
  const navigate = useNavigate();
  const { data } = useGetUnreadNotificationsCount({} as never, {
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  });
  const unread = data?.unread ?? 0;

  return (
    <div className="relative" data-testid="admin-bell">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => navigate("/settings/notifications")}
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
      </Button>
      {unread > 0 && (
        <span
          className="absolute -top-1 -right-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white"
          data-testid="admin-bell-badge"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </div>
  );
}
