import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChangelogEntry } from "@/types/api";
import { cn } from "@/utils/utils";

type Props = {
  userVersion: number;
  latestVersion: number;
  entries: ChangelogEntry[];
  breaking: boolean;
  showEmptyFallback?: boolean;
  className?: string;
};

export default function ChangelogPanel({
  userVersion,
  latestVersion,
  entries,
  breaking,
  showEmptyFallback = false,
  className,
}: Props) {
  if (entries.length === 0) {
    if (!showEmptyFallback) return null;
    return (
      <div
        className={cn(
          "rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground",
          breaking && "border-l-2 border-l-accent-amber-foreground",
          className,
        )}
      >
        No changelog entries available. This update may still change behavior — see the Breaking/Standard label.
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border bg-muted/40 p-3 text-xs",
        breaking && "border-l-2 border-l-accent-amber-foreground",
        className,
      )}
      data-testid="changelog-panel"
    >
      <div className="mb-2 flex items-baseline justify-between">
        <strong className="text-sm">What's changed</strong>
        <span className="text-[10px] text-muted-foreground">
          v{userVersion} → v{latestVersion}
        </span>
      </div>

      {entries.map((entry, i) => (
        <div
          key={entry.version}
          className={cn(
            i > 0 && "mt-2 border-t border-dashed border-border pt-2",
          )}
        >
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
            v{entry.version}
          </div>
          <div className="mb-1 font-semibold">Changes</div>
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <Markdown remarkPlugins={[remarkGfm]}>{entry.changes}</Markdown>
          </div>
          {entry.notes ? (
            <>
              <div className="mt-2 mb-1 font-semibold">Notes</div>
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <Markdown remarkPlugins={[remarkGfm]}>{entry.notes}</Markdown>
              </div>
            </>
          ) : null}
        </div>
      ))}
    </div>
  );
}
