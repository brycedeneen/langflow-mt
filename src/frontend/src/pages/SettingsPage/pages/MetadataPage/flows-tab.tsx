import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import useAlertStore from "@/stores/alertStore";
import {
  useListTemplateMetadata,
  useUpsertTemplateMetadata,
  useDeleteTemplateMetadata,
} from "@/controllers/API/queries/metadata";
import { MetadataEditForm } from "./metadata-edit-form";
import type { TemplateMetadataRow } from "@/types/metadata";

export function FlowsTab() {
  const { data: rows = [], isLoading } = useListTemplateMetadata();
  const upsert = useUpsertTemplateMetadata();
  const del = useDeleteTemplateMetadata();
  const [editing, setEditing] = useState<TemplateMetadataRow | null>(null);
  const setSuccess = useAlertStore((s) => s.setSuccessData);
  const setError = useAlertStore((s) => s.setErrorData);

  if (isLoading) return <div>Loading flows…</div>;

  return (
    <div className="flex flex-col gap-2">
      {rows.map((row) => (
        <div
          key={row.flow_id}
          className="flex items-center justify-between border rounded-md p-3"
        >
          <div className="flex flex-col">
            <span className="font-medium">{row.flow_name}</span>
            <span className="text-xs text-muted-foreground">
              {row.metadata ? "has metadata" : "no metadata"}
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={() => setEditing(row)}>
            {row.metadata ? "Edit" : "Add"}
          </Button>
        </div>
      ))}

      <Dialog
        open={editing !== null}
        onOpenChange={(o) => {
          if (!o) setEditing(null);
        }}
      >
        <DialogContent>
          <DialogTitle>{editing?.flow_name ?? ""}</DialogTitle>
          {editing ? (
            <MetadataEditForm
              initial={{
                agent_summary: editing.metadata?.agent_summary ?? null,
                agent_usage_notes: editing.metadata?.agent_usage_notes ?? null,
              }}
              onCancel={() => setEditing(null)}
              onSave={(body) =>
                upsert.mutate(
                  { flowId: editing.flow_id, body },
                  {
                    onSuccess: () => {
                      setSuccess({ title: "Flow metadata saved" });
                      setEditing(null);
                    },
                    onError: (e: unknown) =>
                      setError({ title: "Save failed", list: [String(e)] }),
                  },
                )
              }
              onDelete={
                editing.metadata
                  ? () =>
                      del.mutate(
                        { flowId: editing.flow_id },
                        {
                          onSuccess: () => {
                            setSuccess({ title: "Flow metadata deleted" });
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
