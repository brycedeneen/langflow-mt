import { Badge } from "@/components/ui/badge";
import type { TagRead } from "@/types/tag";
import { TAG_COLOR_BG_MAP } from "@/types/tag/colors";
import { cn } from "@/utils/utils";

interface TagChipProps {
  tag: Pick<TagRead, "id" | "name" | "color">;
  onRemove?: (id: string) => void;
  className?: string;
}

export default function TagChip({ tag, onRemove, className }: TagChipProps) {
  return (
    <Badge
      size="md"
      className={cn(
        "flex items-center gap-1 border-0 py-0.5 text-white",
        TAG_COLOR_BG_MAP[tag.color],
        className,
      )}
    >
      <span className="truncate">{tag.name}</span>
      {onRemove ? (
        <button
          type="button"
          aria-label={`remove ${tag.name}`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove(tag.id);
          }}
          className="-mr-1 inline-flex h-4 w-4 items-center justify-center rounded-full text-white/90 hover:bg-white/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white"
        >
          <span aria-hidden="true">×</span>
        </button>
      ) : null}
    </Badge>
  );
}
