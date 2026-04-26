import { useState } from "react";
import { useNavigate } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetAdminNotifications } from "@/controllers/API/queries/admin/use-get-admin-notifications";
import { useMarkAllNotificationsRead } from "@/controllers/API/queries/admin/use-mark-all-notifications-read";
import { useMarkNotificationRead } from "@/controllers/API/queries/admin/use-mark-notification-read";

type NotificationItem = {
  id: string;
  category: string;
  severity: string;
  title: string;
  body_md: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  read_at?: string | null;
};

/**
 * Resolve the deep-link target for a notification based on its category.
 *
 * Adds professional-services-request routing in Phase G of the Pro-Service
 * Quotes feature: a notification with ``category === "professional_services_request"``
 * and ``metadata.quote_id`` deep-links to the quote detail page. Returns
 * ``null`` when no deep link is appropriate (the row should not be clickable).
 */
export function resolveNotificationLink(n: NotificationItem): string | null {
  if (n.category === "professional_services_request") {
    const qid =
      n.metadata && typeof (n.metadata as Record<string, unknown>).quote_id === "string"
        ? ((n.metadata as Record<string, unknown>).quote_id as string)
        : null;
    if (qid) return `/pro-service-quotes/${qid}`;
  }
  return null;
}

export default function AdminNotificationsPage() {
  const [showUnreadOnly, setShowUnreadOnly] = useState(true);
  const { data, isPending } = useGetAdminNotifications({ unread: showUnreadOnly });
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();
  const navigate = useNavigate();

  const items = (data?.items ?? []) as NotificationItem[];

  const handleClick = (n: NotificationItem) => {
    const target = resolveNotificationLink(n);
    if (!target) return;
    if (!n.read_at) markRead.mutate({ id: n.id });
    navigate(target);
  };

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
          {items.map((n) => {
            const target = resolveNotificationLink(n);
            const clickable = target !== null;
            return (
              <div
                key={n.id}
                data-testid={`notification-row-${n.id}`}
                className={`rounded border p-4 flex justify-between items-start ${
                  n.read_at ? "opacity-60" : ""
                } ${clickable ? "cursor-pointer hover:bg-muted/40" : ""}`}
                role={clickable ? "button" : undefined}
                tabIndex={clickable ? 0 : undefined}
                onClick={clickable ? () => handleClick(n) : undefined}
                onKeyDown={
                  clickable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleClick(n);
                        }
                      }
                    : undefined
                }
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
                    onClick={(e) => {
                      e.stopPropagation();
                      markRead.mutate({ id: n.id });
                    }}
                  >
                    <IconComponent name="Check" className="h-4 w-4" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
