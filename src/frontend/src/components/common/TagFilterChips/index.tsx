import TagChip from "@/components/common/TagChip";
import type { TagRead } from "@/types/tag";
import { cn } from "@/utils/utils";

interface TagFilterChipsProps {
  availableTags: TagRead[];
  selected: string[];
  onChange: (ids: string[]) => void;
  className?: string;
}

/**
 * A presentational row of tag chips used as a client-side filter.
 * - Click a chip to toggle it in/out of the `selected` list.
 * - Selected chips are fully opaque; unselected chips are dimmed.
 * - Renders nothing when `availableTags` is empty so the parent row collapses.
 */
export default function TagFilterChips({
  availableTags,
  selected,
  onChange,
  className,
}: TagFilterChipsProps) {
  if (!availableTags || availableTags.length === 0) {
    return null;
  }

  const visible = availableTags;

  const selectedSet = new Set(selected);

  const toggle = (id: string) => {
    if (selectedSet.has(id)) {
      onChange(selected.filter((x) => x !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <div
      className={cn("flex flex-wrap gap-1.5", className)}
      data-testid="tag-filter-chips"
      role="group"
      aria-label="Filter by tag"
    >
      {visible.map((tag) => {
        const isSelected = selectedSet.has(tag.id);
        return (
          <button
            key={tag.id}
            type="button"
            onClick={() => toggle(tag.id)}
            aria-pressed={isSelected}
            aria-label={`${isSelected ? "remove" : "add"} filter ${tag.name}`}
            className={cn(
              "cursor-pointer rounded-full border-none bg-transparent p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            <TagChip
              tag={tag}
              className={cn(
                isSelected
                  ? "opacity-100 ring-2 ring-ring ring-offset-1 ring-offset-background"
                  : "opacity-50 hover:opacity-80",
              )}
            />
          </button>
        );
      })}
    </div>
  );
}
