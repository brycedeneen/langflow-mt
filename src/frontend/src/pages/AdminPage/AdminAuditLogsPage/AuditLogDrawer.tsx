import { useGetAuditLog } from "@/controllers/API/queries/admin/use-get-audit-log";
import { Button } from "@/components/ui/button";
import IconComponent from "@/components/common/genericIconComponent";

type Props = { id: string; onClose: () => void };

export default function AuditLogDrawer({ id, onClose }: Props) {
  const { data, isPending } = useGetAuditLog({ id });

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-background border-l shadow-xl flex flex-col z-50">
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="font-semibold">Audit log entry</h2>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <IconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-4 text-sm">
        {isPending && <div>Loading…</div>}
        {!isPending && data && (
          <div className="flex flex-col gap-3">
            <Row label="When" value={new Date(data.occurred_at).toLocaleString()} />
            <Row label="Actor" value={`${data.actor_email}${data.actor_is_super ? " (super)" : ""}`} />
            <Row label="Org" value={data.org_id ?? "—"} />
            <Row label="Target" value={`${data.target_type} · ${data.target_id}`} />
            <Row label="Action" value={data.action} />
            <div>
              <div className="text-muted-foreground mb-1">Diff</div>
              <pre className="bg-muted p-3 rounded text-xs overflow-auto">
                {JSON.stringify(data.diff, null, 2)}
              </pre>
            </div>
            <div>
              <div className="text-muted-foreground mb-1">Request metadata</div>
              <pre className="bg-muted p-3 rounded text-xs overflow-auto">
                {JSON.stringify(data.request_metadata, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <div className="text-muted-foreground min-w-24">{label}</div>
      <div className="flex-1 break-all">{value}</div>
    </div>
  );
}
