import { useMemo, useState } from "react";
import * as LucideIcons from "lucide-react";

// Build the icon name list from lucide-react exports, filtering out
// duplicate "Icon"-suffixed aliases and non-component exports.
const ALL_ICON_NAMES: string[] = Object.keys(LucideIcons).filter(
  (name) =>
    !name.endsWith("Icon") &&
    name !== "createLucideIcon" &&
    name !== "LucideProvider" &&
    name !== "useLucideContext",
);

type Props = {
  value: string;
  onChange: (iconName: string) => void;
};

export default function IconPickerField({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const options = useMemo(() => {
    if (!query.trim()) return ALL_ICON_NAMES;
    const q = query.toLowerCase();
    return ALL_ICON_NAMES.filter((n) => n.toLowerCase().includes(q));
  }, [query]);

  const close = () => {
    setOpen(false);
    setQuery("");
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm"
      >
        {value}
      </button>
      {open && (
        <div className="absolute z-50 mt-2 w-72 rounded-md border bg-popover p-2 shadow-lg">
          <input
            autoFocus
            type="text"
            placeholder="Search icons…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="mb-2 w-full rounded-sm border px-2 py-1 text-sm"
          />
          <div
            role="listbox"
            className="grid max-h-60 grid-cols-5 gap-1 overflow-y-auto"
          >
            {options.map((name) => (
              <button
                key={name}
                type="button"
                role="option"
                aria-selected={name === value}
                onClick={() => {
                  onChange(name);
                  close();
                }}
                className={`rounded-sm px-2 py-1 text-xs ${
                  name === value ? "bg-accent" : ""
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
