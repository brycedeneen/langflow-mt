import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetAdminNotifications } from "@/controllers/API/queries/admin/use-get-admin-notifications";
import { useMarkAllNotificationsRead } from "@/controllers/API/queries/admin/use-mark-all-notifications-read";
import { useMarkNotificationRead } from "@/controllers/API/queries/admin/use-mark-notification-read";

export default function AdminNotificationsPage() {
  const [showUnreadOnly, setShowUnreadOnly] = useState(true);
  const { data, isPending } = useGetAdminNotifications({ unread: showUnreadOnly });
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Admin Notifications</h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowUnreadOnly(!showUnreadOnly)}
          >
            {showUnreadOnly ? "Show All" : "Show Unread"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => markAllRead.mutate(undefined)}
            disabled={markAllRead.isPending}
          >
            Mark All Read
          </Button>
        </div>
      </div>

      {isPending ? (
        <div>Loading...</div>
      ) : items.length === 0 ? (
        <div className="text-muted-foreground">No notifications.</div>
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((n) => (
            <div
              key={n.id}
              className={`rounded border p-4 flex justify-between items-start ${
                n.read_at ? "opacity-60" : ""
              }`}
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs rounded px-1 py-0.5 ${
                      n.severity === "critical"
                        ? "bg-red-100 text-red-700"
                        : n.severity === "warning"
                        ? "bg-yellow-100 text-yellow-700"
                        : "bg-blue-100 text-blue-700"
                    }`}
                  >
                    {n.severity}
                  </span>
                  <span className="font-medium">{n.title}</span>
                </div>
                <p className="text-sm text-muted-foreground">{n.body_md}</p>
                <span className="text-xs text-muted-foreground">
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </div>
              {!n.read_at && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => markRead.mutate({ id: n.id })}
                >
                  <IconComponent name="Check" className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
