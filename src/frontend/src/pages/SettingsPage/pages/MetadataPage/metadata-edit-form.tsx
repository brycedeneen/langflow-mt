import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type Initial = {
  agent_summary: string | null;
  agent_usage_notes: string | null;
};

type Payload = {
  agent_summary: string | null;
  agent_usage_notes: string | null;
};

type Props = {
  initial: Initial;
  onSave: (payload: Payload) => void;
  onCancel: () => void;
  onDelete?: () => void;
};

export function MetadataEditForm({ initial, onSave, onCancel, onDelete }: Props) {
  const [summary, setSummary] = useState(initial.agent_summary ?? "");
  const [notes, setNotes] = useState(initial.agent_usage_notes ?? "");

  const hasExistingRow =
    initial.agent_summary !== null || initial.agent_usage_notes !== null;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave({
          agent_summary: summary || null,
          agent_usage_notes: notes || null,
        });
      }}
      className="flex flex-col gap-4"
    >
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Agent summary</span>
        <Textarea
          aria-label="Agent summary"
          placeholder="Short AI-facing description used for matching and search."
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Agent usage notes</span>
        <Textarea
          aria-label="Agent usage notes"
          placeholder="Full free-form guidance for the assistant."
          rows={8}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        {hasExistingRow && onDelete ? (
          <Button type="button" variant="destructive" onClick={onDelete}>
            Delete metadata
          </Button>
        ) : null}
        <Button type="submit">Save</Button>
      </div>
    </form>
  );
}
