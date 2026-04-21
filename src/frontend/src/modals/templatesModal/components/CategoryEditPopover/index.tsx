import { useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import IconPickerField from "@/modals/SaveAsTemplateModal/IconPickerField";
import { cn } from "@/utils/utils";

/** Tailwind palette swatches for category color. */
const COLOR_SWATCHES = [
  { name: "slate", bg: "bg-slate-500" },
  { name: "amber", bg: "bg-amber-500" },
  { name: "violet", bg: "bg-violet-500" },
  { name: "emerald", bg: "bg-emerald-500" },
  { name: "sky", bg: "bg-sky-500" },
  { name: "fuchsia", bg: "bg-fuchsia-500" },
  { name: "indigo", bg: "bg-indigo-500" },
  { name: "rose", bg: "bg-rose-500" },
] as const;

const DEFAULT_ICON = "Tag";
const DEFAULT_COLOR = "slate";

export type CategoryEditPayload = {
  name: string;
  icon: string;
  color: string;
  description: string | null;
};

type Props = {
  mode: "create" | "edit";
  initial?: CategoryEditPayload;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: CategoryEditPayload) => void;
  anchor?: React.ReactElement;
  busy?: boolean;
};

export function CategoryEditPopover({
  mode,
  initial,
  open,
  onOpenChange,
  onSubmit,
  anchor,
  busy = false,
}: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [icon, setIcon] = useState(initial?.icon ?? DEFAULT_ICON);
  const [color, setColor] = useState(initial?.color ?? DEFAULT_COLOR);
  const [description, setDescription] = useState(
    initial?.description ?? "",
  );

  // Reset form when open changes (e.g. opening create mode fresh)
  useEffect(() => {
    if (open) {
      setName(initial?.name ?? "");
      setIcon(initial?.icon ?? DEFAULT_ICON);
      setColor(initial?.color ?? DEFAULT_COLOR);
      setDescription(initial?.description ?? "");
    }
  }, [open, initial]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      icon,
      color,
      description: description.trim() || null,
    });
  };

  const selectedSwatch = COLOR_SWATCHES.find((s) => s.name === color) ?? COLOR_SWATCHES[0];

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      {anchor ? (
        <PopoverTrigger asChild>{anchor}</PopoverTrigger>
      ) : (
        <PopoverTrigger asChild>
          <span className="sr-only">Open category editor</span>
        </PopoverTrigger>
      )}
      <PopoverContent
        className="w-80 p-4"
        align="start"
        side="right"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <p className="text-sm font-semibold">
            {mode === "create" ? "New category" : "Edit category"}
          </p>

          {/* Name */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="cat-name"
              className="text-xs font-medium text-muted-foreground"
            >
              Name <span aria-hidden>*</span>
            </label>
            <input
              id="cat-name"
              type="text"
              required
              maxLength={64}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="nopan nodelete nodrag noflow primary-input"
              placeholder="Category name"
              autoFocus
            />
          </div>

          {/* Icon */}
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">
              Icon
            </span>
            <IconPickerField value={icon} onChange={setIcon} />
          </div>

          {/* Color */}
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">
              Color
            </span>
            <div role="radiogroup" aria-label="Color" className="flex gap-1.5">
              {COLOR_SWATCHES.map((swatch) => {
                const isSelected = swatch.name === color;
                return (
                  <button
                    key={swatch.name}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    aria-label={swatch.name}
                    title={swatch.name}
                    onClick={() => setColor(swatch.name)}
                    className={cn(
                      "h-6 w-6 rounded",
                      swatch.bg,
                      isSelected && "ring-2 ring-primary ring-offset-1",
                    )}
                  />
                );
              })}
            </div>
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="cat-description"
              className="text-xs font-medium text-muted-foreground"
            >
              Description (optional)
            </label>
            <textarea
              id="cat-description"
              maxLength={256}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="nopan nodelete nodrag noflow primary-input resize-none text-sm"
              placeholder="Short description…"
            />
          </div>

          {/* Preview + actions */}
          <div className="flex items-center justify-between gap-2 pt-1">
            {/* Mini preview */}
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
                selectedSwatch.bg,
              )}
              title={`Preview: ${icon} in ${color}`}
            >
              <IconComponent name={icon} className="h-4 w-4 text-white" />
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={!name.trim() || busy}
              >
                {busy ? "Saving…" : "Save"}
              </Button>
            </div>
          </div>
        </form>
      </PopoverContent>
    </Popover>
  );
}
