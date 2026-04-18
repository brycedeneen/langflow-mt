import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import useAlertStore from "@/stores/alertStore";
import {
  useListComponentMetadata,
  useUpsertComponentMetadata,
  useDeleteComponentMetadata,
} from "@/controllers/API/queries/metadata";
import { MetadataEditForm } from "./metadata-edit-form";
import { OrphanBadge } from "./orphan-badge";
import type { ComponentMetadataRow } from "@/types/metadata";

export function ComponentsTab() {
  const { data: rows = [], isLoading } = useListComponentMetadata();
  const upsert = useUpsertComponentMetadata();
  const del = useDeleteComponentMetadata();
  const [editing, setEditing] = useState<ComponentMetadataRow | null>(null);
  const [filter, setFilter] = useState("");
  const setSuccess = useAlertStore((s) => s.setSuccessData);

  const visible = useMemo(
    () =>
      rows.filter((r) =>
        (r.component_name + " " + (r.display_name ?? ""))
          .toLowerCase()
          .includes(filter.toLowerCase()),
      ),
    [rows, filter],
  );

  if (isLoading) return <div>Loading components…</div>;

  return (
    <div className="flex flex-col gap-2">
      <input
        className="border rounded-md px-2 py-1 text-sm"
        placeholder="Filter…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {visible.map((row) => (
        <div
          key={row.component_name}
          className="flex items-center justify-between border rounded-md p-3"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">
              {row.display_name ?? row.component_name}
            </span>
            {row.category ? (
              <span className="text-xs text-muted-foreground">
                ({row.category})
              </span>
            ) : null}
            {row.is_orphan ? <OrphanBadge /> : null}
          </div>
          <div className="flex gap-2">
            {row.is_orphan ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={() =>
                  del.mutate(
                    { componentName: row.component_name },
                    {
                      onSuccess: () => setSuccess({ title: "Orphan removed" }),
                    },
                  )
                }
              >
                Remove orphan
              </Button>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditing(row)}
            >
              {row.metadata ? "Edit" : "Add"}
            </Button>
          </div>
        </div>
      ))}

      <Dialog
        open={editing !== null}
        onOpenChange={(o) => {
          if (!o) setEditing(null);
        }}
      >
        <DialogContent>
          <DialogTitle>
            {editing?.display_name ?? editing?.component_name ?? ""}
          </DialogTitle>
          {editing ? (
            <MetadataEditForm
              initial={{
                agent_summary: editing.metadata?.agent_summary ?? null,
                agent_usage_notes: editing.metadata?.agent_usage_notes ?? null,
              }}
              onCancel={() => setEditing(null)}
              onSave={(body) =>
                upsert.mutate(
                  { componentName: editing.component_name, body },
                  {
                    onSuccess: () => {
                      setSuccess({ title: "Component metadata saved" });
                      setEditing(null);
                    },
                  },
                )
              }
              onDelete={
                editing.metadata
                  ? () =>
                      del.mutate(
                        { componentName: editing.component_name },
                        {
                          onSuccess: () => {
                            setSuccess({ title: "Component metadata deleted" });
                            setEditing(null);
                          },
                        },
                      )
                  : undefined
              }
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
