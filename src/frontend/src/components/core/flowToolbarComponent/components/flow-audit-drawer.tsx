import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { AuditLogListItem } from "@/controllers/API/queries/admin/use-get-audit-logs";
import { useGetFlowAuditLogs } from "@/controllers/API/queries/flows/use-get-flow-audit-logs";

type Props = {
  flowId: string;
  open: boolean;
  onClose: () => void;
};

const PAGE_SIZE = 50;

function summarize(entry: AuditLogListItem): string {
  const rawDiff = entry.diff;
  const diff =
    typeof rawDiff === "object" && rawDiff !== null
      ? (rawDiff as { changed?: Record<string, unknown>; truncated?: boolean })
      : {};
  if (diff.truncated) return "(diff truncated)";
  if (entry.action === "create") return "Created";
  if (entry.action === "delete") return "Deleted";
  const changedKeys = Object.keys(diff.changed ?? {});
  if (changedKeys.length > 0) return `Updated: ${changedKeys.join(", ")}`;
  return entry.action;
}

function AuditEntryRow({ entry }: { entry: AuditLogListItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left p-3 hover:bg-muted flex flex-col gap-1"
      >
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{new Date(entry.occurred_at).toLocaleString()}</span>
          <span className="uppercase tracking-wide">{entry.action}</span>
        </div>
        <div className="text-sm">{entry.actor_email}</div>
        <div className="text-xs text-muted-foreground">{summarize(entry)}</div>
      </button>
      {expanded && (
        <pre className="bg-muted p-3 mx-3 mb-3 rounded text-xs overflow-auto">
          {JSON.stringify(entry.diff, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function FlowAuditDrawer({ flowId, open, onClose }: Props) {
  if (!open) return null;
  return <FlowAuditDrawerContent flowId={flowId} onClose={onClose} />;
}

function FlowAuditDrawerContent({
  flowId,
  onClose,
}: {
  flowId: string;
  onClose: () => void;
}) {
  const { data, isPending, isError } = useGetFlowAuditLogs(
    { flowId, page: 1, size: PAGE_SIZE },
    { enabled: true },
  );
  const truncated = data ? data.total > data.items.length : false;

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-background border-l shadow-xl flex flex-col z-50">
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="font-semibold">Flow history</h2>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-auto text-sm">
        {isPending && <div className="p-4 text-muted-foreground">Loading…</div>}
        {!isPending && isError && (
          <div className="p-4 text-destructive">Failed to load flow history.</div>
        )}
        {!isPending && !isError && data && data.items.length === 0 && (
          <div className="p-4 text-muted-foreground">No history yet.</div>
        )}
        {!isPending && !isError && data && data.items.length > 0 && (
          <div className="flex flex-col">
            {data.items.map((entry) => (
              <AuditEntryRow key={entry.id} entry={entry} />
            ))}
            {truncated && (
              <div className="p-3 text-xs text-muted-foreground border-t">
                Showing first {data.items.length} of {data.total} entries.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
