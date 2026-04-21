import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { useListCategories } from "@/controllers/API/queries/categories";
import type { Category } from "@/types/template";

type Props = {
  selectedIds: string[];
  onChange(ids: string[]): void;
  disabled?: boolean;
};

function CategoryChip({
  category,
  selected,
  onClick,
  disabled,
}: {
  category: Category;
  selected: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="cursor-pointer rounded-full border-none bg-transparent p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-pressed={selected}
    >
      <Badge
        variant={selected ? "default" : "outline"}
        size="md"
        className="flex cursor-pointer items-center gap-1 py-0.5 transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ForwardedIconComponent
          name={category.icon}
          className="h-3 w-3 shrink-0"
        />
        <span>{category.name}</span>
      </Badge>
    </button>
  );
}

export default function CategoryChipPicker({
  selectedIds,
  onChange,
  disabled = false,
}: Props) {
  const [search, setSearch] = useState("");
  const { data: allCategories = [] } = useListCategories();

  const selectedSet = new Set(selectedIds);

  const selectedCategories = allCategories.filter((c) => selectedSet.has(c.id));
  const unselectedCategories = allCategories.filter(
    (c) =>
      !selectedSet.has(c.id) &&
      (search === "" ||
        c.name.toLowerCase().includes(search.toLowerCase())),
  );

  const handleToggle = (id: string) => {
    if (disabled) return;
    if (selectedSet.has(id)) {
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  if (allCategories.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No categories defined</p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Selected chips */}
      {selectedCategories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedCategories.map((cat) => (
            <CategoryChip
              key={cat.id}
              category={cat}
              selected
              onClick={() => handleToggle(cat.id)}
              disabled={disabled}
            />
          ))}
        </div>
      )}

      {/* Search input for unselected */}
      {allCategories.length > 6 && (
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter categories…"
          disabled={disabled}
          className="w-full rounded-md border px-2.5 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-50"
        />
      )}

      {/* Unselected chips */}
      {unselectedCategories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {unselectedCategories.map((cat) => (
            <CategoryChip
              key={cat.id}
              category={cat}
              selected={false}
              onClick={() => handleToggle(cat.id)}
              disabled={disabled}
            />
          ))}
        </div>
      )}

      {unselectedCategories.length === 0 &&
        selectedCategories.length === 0 &&
        search !== "" && (
          <p className="text-xs text-muted-foreground">
            No categories match "{search}"
          </p>
        )}
    </div>
  );
}
