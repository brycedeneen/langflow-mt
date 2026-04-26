import { useMemo, useState } from "react";
import TagChip from "@/components/common/TagChip";
import { Input } from "@/components/ui/input";
import { useListTags } from "@/controllers/API/queries/tags";
import type { TagRead } from "@/types/tag";
import { cn } from "@/utils/utils";

interface TagPickerProps {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  disabled?: boolean;
  emptyState?: string;
}

export default function TagPicker({
  selectedIds,
  onChange,
  disabled = false,
  emptyState = "No tags yet",
}: TagPickerProps) {
  const [search, setSearch] = useState("");
  const { data: allTags = [], isPending } = useListTags();

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const selectedTags: TagRead[] = useMemo(
    () => allTags.filter((t) => selectedSet.has(t.id)),
    [allTags, selectedSet],
  );

  const unselectedTags: TagRead[] = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allTags.filter(
      (t) =>
        !selectedSet.has(t.id) &&
        (q === "" || t.name.toLowerCase().includes(q)),
    );
  }, [allTags, selectedSet, search]);

  if (isPending) {
    return (
      <div
        className="text-xs text-muted-foreground"
        data-testid="tag-picker-loading"
      >
        Loading tags…
      </div>
    );
  }

  if (allTags.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="tag-picker-empty">
        {emptyState}
      </p>
    );
  }

  const addTag = (id: string) => {
    if (disabled) return;
    if (selectedSet.has(id)) return;
    onChange([...selectedIds, id]);
  };

  const removeTag = (id: string) => {
    if (disabled) return;
    onChange(selectedIds.filter((x) => x !== id));
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-2",
        disabled && "pointer-events-none opacity-60",
      )}
      data-testid="tag-picker"
    >
      {/* Selected chips (with remove button) */}
      {selectedTags.length > 0 && (
        <div
          className="flex flex-wrap gap-1.5"
          data-testid="tag-picker-selected"
        >
          {selectedTags.map((tag) => (
            <TagChip
              key={tag.id}
              tag={tag}
              onRemove={removeTag}
            />
          ))}
        </div>
      )}

      {/* Search input when vocabulary is large */}
      {allTags.length > 8 && (
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter tags…"
          disabled={disabled}
          aria-label="Filter tags"
          className="h-8 text-xs"
        />
      )}

      {/* Unselected chips (click to select) */}
      {unselectedTags.length > 0 && (
        <div
          className="flex flex-wrap gap-1.5"
          data-testid="tag-picker-unselected"
        >
          {unselectedTags.map((tag) => (
            <button
              key={tag.id}
              type="button"
              onClick={() => addTag(tag.id)}
              disabled={disabled}
              aria-label={`add ${tag.name}`}
              className="cursor-pointer rounded-full border-none bg-transparent p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
            >
              <TagChip
                tag={tag}
                className="opacity-70 hover:opacity-100"
              />
            </button>
          ))}
        </div>
      )}

      {unselectedTags.length === 0 &&
        selectedTags.length === 0 &&
        search !== "" && (
          <p className="text-xs text-muted-foreground">
            No tags match "{search}"
          </p>
        )}
    </div>
  );
}
