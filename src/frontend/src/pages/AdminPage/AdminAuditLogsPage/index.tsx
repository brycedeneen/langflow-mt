import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetAuditLogs } from "@/controllers/API/queries/admin/use-get-audit-logs";
import AuditLogDrawer from "./AuditLogDrawer";

const TARGET_TYPES = [
  "flow",
  "template",
  "variable",
  "organization",
  "membership",
  "api_key",
  "role_assignment",
];

const ACTIONS = ["create", "update", "delete", "archive", "unarchive", "assign_role"];

export default function AdminAuditLogsPage() {
  const [page, setPage] = useState(1);
  const [size] = useState(50);
  const [targetType, setTargetType] = useState<string | undefined>();
  const [action, setAction] = useState<string | undefined>();
  const [orgId, setOrgId] = useState<string>("");
  const [actorId, setActorId] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isPending } = useGetAuditLogs({
    page,
    size,
    target_type: targetType,
    action,
    org_id: orgId || undefined,
    actor_user_id: actorId || undefined,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / size)) : 1;

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl font-semibold">Audit Logs</h1>

      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="Actor user ID"
          value={actorId}
          onChange={(e) => { setActorId(e.target.value); setPage(1); }}
          className="max-w-xs"
        />
        <Input
          placeholder="Org ID"
          value={orgId}
          onChange={(e) => { setOrgId(e.target.value); setPage(1); }}
          className="max-w-xs"
        />
        <Select value={targetType ?? ""} onValueChange={(v) => { setTargetType(v || undefined); setPage(1); }}>
          <SelectTrigger className="max-w-xs"><SelectValue placeholder="All target types" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="">All target types</SelectItem>
            {TARGET_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={action ?? ""} onValueChange={(v) => { setAction(v || undefined); setPage(1); }}>
          <SelectTrigger className="max-w-xs"><SelectValue placeholder="All actions" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="">All actions</SelectItem>
            {ACTIONS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {isPending && <div>Loading…</div>}
      {!isPending && data && (
        <>
          <table className="w-full table-fixed border-collapse">
            <thead>
              <tr className="text-left text-sm text-muted-foreground border-b">
                <th className="py-2 px-3 w-48">Time</th>
                <th className="py-2 px-3 w-56">Actor</th>
                <th className="py-2 px-3 w-48">Org</th>
                <th className="py-2 px-3 w-36">Target</th>
                <th className="py-2 px-3 w-28">Action</th>
                <th className="py-2 px-3">Summary</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => {
                const changedFields = Object.keys((row.diff as any)?.changed ?? {});
                const summary = (row.diff as any)?.truncated
                  ? "(diff truncated)"
                  : row.action === "create"
                  ? "created"
                  : row.action === "delete"
                  ? "deleted"
                  : changedFields.length > 0
                  ? `${changedFields.length} field(s) changed`
                  : row.action;
                return (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    className="cursor-pointer border-b hover:bg-muted text-sm"
                  >
                    <td className="py-2 px-3">{new Date(row.occurred_at).toLocaleString()}</td>
                    <td className="py-2 px-3">{row.actor_email}</td>
                    <td className="py-2 px-3">{row.org_id ?? "—"}</td>
                    <td className="py-2 px-3">{row.target_type}</td>
                    <td className="py-2 px-3">{row.action}</td>
                    <td className="py-2 px-3">{summary}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="flex items-center gap-2">
            <Button disabled={page <= 1} onClick={() => setPage(page - 1)} variant="outline">
              <IconComponent name="ChevronLeft" className="h-4 w-4" /> Prev
            </Button>
            <div className="text-sm">Page {page} of {totalPages}</div>
            <Button disabled={page >= totalPages} onClick={() => setPage(page + 1)} variant="outline">
              Next <IconComponent name="ChevronRight" className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}

      {selectedId && (
        <AuditLogDrawer id={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
