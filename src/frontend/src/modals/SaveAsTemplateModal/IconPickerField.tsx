import { ChevronDown } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Command, CommandInput } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { filterIconNames } from "./iconPicker/filterIconNames";
import IconGrid from "./iconPicker/IconGrid";
import { LUCIDE_ICON_NAMES } from "./iconPicker/lucideIconNames";
import { useRecentIcons } from "./iconPicker/useRecentIcons";

const LUCIDE_NAME_SET = new Set(LUCIDE_ICON_NAMES);

type Props = {
  value: string;
  onChange: (iconName: string) => void;
};

export default function IconPickerField({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { recents, record } = useRecentIcons();

  const filtered = useMemo(() => filterIconNames(LUCIDE_ICON_NAMES, query), [query]);

  // Drop recents that no longer exist in the current lucide set.
  const validRecents = useMemo(
    () => recents.filter((n) => LUCIDE_NAME_SET.has(n)),
    [recents],
  );

  const showRecents = query.trim() === "" && validRecents.length > 0;

  const handleSelect = useCallback(
    (name: string) => {
      onChange(name);
      record(name);
      setOpen(false);
      setQuery("");
    },
    [onChange, record],
  );

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Choose icon"
          className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-accent"
        >
          <IconComponent name={value} className="h-4 w-4" />
          <span>{value}</span>
          <ChevronDown className="h-4 w-4 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[340px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search icons…"
            value={query}
            onValueChange={setQuery}
            autoFocus
          />
          <div className="p-2">
            {showRecents && (
              <div
                role="region"
                aria-label="Recents"
                className="mb-2 border-b pb-2"
              >
                <div className="mb-1 px-1 text-xs font-medium text-muted-foreground">
                  Recents
                </div>
                <div
                  role="listbox"
                  aria-label="Recent icons"
                  className="flex flex-wrap gap-1"
                >
                  {validRecents.map((name) => {
                    const isSelected = name === value;
                    return (
                      <button
                        key={name}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => handleSelect(name)}
                        title={name}
                        className={cn(
                          "flex h-9 w-9 items-center justify-center rounded-sm hover:bg-accent",
                          isSelected && "bg-accent text-accent-foreground",
                        )}
                      >
                        <IconComponent name={name} className="h-5 w-5" />
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {filtered.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No icons match "{query}"
              </div>
            ) : (
              <IconGrid
                names={filtered}
                selected={value}
                onSelect={handleSelect}
              />
            )}
          </div>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
