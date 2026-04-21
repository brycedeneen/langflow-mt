import { AlertTriangle } from "lucide-react";
import { useMemo } from "react";
import { cn } from "@/utils/utils";
import type { BlankableFieldInfo } from "./scanBlankableFields";

type Props = {
  fields: BlankableFieldInfo[];
  keptKeys: Set<string>;
  onToggle: (node_id: string, field_name: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function fieldKey(f: { node_id: string; field_name: string }): string {
  return `${f.node_id}:${f.field_name}`;
}

function groupByComponent(
  fields: BlankableFieldInfo[],
): { component: string; items: BlankableFieldInfo[] }[] {
  const groups = new Map<string, BlankableFieldInfo[]>();
  for (const f of fields) {
    const list = groups.get(f.component_display_name) ?? [];
    list.push(f);
    groups.set(f.component_display_name, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.toLowerCase().localeCompare(b.toLowerCase()))
    .map(([component, items]) => ({ component, items }));
}

function warningCopy(keptCount: number): string {
  return keptCount === 1
    ? "1 credential will be saved with this template"
    : `${keptCount} credentials will be saved with this template`;
}

export default function StripPanel({
  fields,
  keptKeys,
  onToggle,
  open,
  onOpenChange,
}: Props) {
  const groups = useMemo(() => groupByComponent(fields), [fields]);
  const total = fields.length;
  const keptCount = useMemo(
    () => fields.filter((f) => keptKeys.has(fieldKey(f))).length,
    [fields, keptKeys],
  );
  const blankedCount = total - keptCount;

  const showCount = !(total > 0 && keptCount === total); // hide count when K = N
  const showWarning = keptCount > 0;

  let countCopy = "";
  if (showCount) {
    countCopy =
      keptCount === 0
        ? `What gets stripped (${total})`
        : `What gets stripped (${blankedCount} of ${total})`;
  }

  return (
    <details
      open={open}
      onToggle={(e) =>
        onOpenChange((e.target as HTMLDetailsElement).open)
      }
    >
      <summary className="cursor-pointer text-sm font-medium">
        <span className="inline-flex items-center gap-2">
          {showCount && <span>{countCopy}</span>}
          {showWarning && (
            <span
              role="alert"
              className="inline-flex items-center gap-1 text-yellow-600"
            >
              <AlertTriangle className="h-4 w-4" />
              {warningCopy(keptCount)}
            </span>
          )}
        </span>
      </summary>
      {open && (
      <div className="mt-2 space-y-3">
        {showWarning && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-sm border border-yellow-300 bg-yellow-50 px-2 py-1 text-sm text-yellow-700"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{warningCopy(keptCount)}</span>
          </div>
        )}
        {fields.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            No credential fields detected.
          </p>
        ) : (
          <div className="space-y-2">
            {groups.map(({ component, items }) => (
              <div key={component} className="space-y-1">
                <h4 className="text-sm font-medium">{component}</h4>
                <ul className="space-y-1 pl-4">
                  {items.map((f) => {
                    const k = fieldKey(f);
                    const checked = !keptKeys.has(k);
                    return (
                      <li key={k}>
                        <label
                          className={cn(
                            "flex cursor-pointer items-center gap-2 text-sm",
                            !checked && "text-yellow-700",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => onToggle(f.node_id, f.field_name)}
                          />
                          {f.field_display_name}
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
      )}
    </details>
  );
}
