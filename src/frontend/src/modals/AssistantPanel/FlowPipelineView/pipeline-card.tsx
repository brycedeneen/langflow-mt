import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import type { VertexBuildTypeAPI } from "@/types/api";
import { runTestForComponent } from "@/utils/test-runs";
import { RawOutput } from "./raw-output";
import { StatusBadge, type TestStatus } from "./status-badge";
import type { LayoutNode } from "./dag-layout";

type Props = {
  node: LayoutNode;
  groupedChildren: LayoutNode[];
  status: TestStatus;
  latestResult: VertexBuildTypeAPI | null;
  onSend: (text: string) => void;
};

function extractErrorMessage(result: VertexBuildTypeAPI | null): string {
  if (!result) return "";
  const data = result.data as Record<string, unknown> | undefined;
  if (!data) return "";
  const err = (data as { error?: unknown }).error;
  if (typeof err === "string") return err;
  const msg = (data as { message?: unknown }).message;
  if (typeof msg === "string") return msg;
  return "";
}

function extractOutputSummary(result: VertexBuildTypeAPI | null): string {
  if (!result) return "";
  const data = result.data as Record<string, unknown> | undefined;
  const msg = data?.["message"];
  return typeof msg === "string" ? msg : "";
}

export function PipelineCard({
  node,
  groupedChildren,
  status,
  latestResult,
  onSend,
}: Props) {
  const displayName = node.data.display_name || node.id;
  const typeName = node.data.type;
  const errorMessage = extractErrorMessage(latestResult);

  const handleTest = useCallback(() => {
    void runTestForComponent(node.id);
  }, [node.id]);

  const handleAskAssistant = useCallback(() => {
    const outputSummary = extractOutputSummary(latestResult);
    const showOutput = outputSummary && outputSummary !== errorMessage;
    const message =
      `[TEST_FAILURE] Component \`${displayName}\` (${typeName}) failed.\n` +
      `Error: ${errorMessage || "Unknown error"}\n` +
      (showOutput ? `Last output: ${outputSummary}\n` : "") +
      `Walk me through how to fix this.`;
    onSend(message);
  }, [displayName, typeName, errorMessage, latestResult, onSend]);

  return (
    <div className="rounded-md border bg-background p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{displayName}</div>
          {groupedChildren.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
              {groupedChildren.map((child) => (
                <li key={child.id}>
                  Tool: {child.data.display_name || child.id}
                </li>
              ))}
            </ul>
          )}
        </div>
        <StatusBadge status={status} errorMessage={errorMessage} />
      </div>

      {status === "failed" && errorMessage && (
        <div className="mt-2 truncate text-xs text-red-600" title={errorMessage}>
          {errorMessage}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {status === "not_tested" && (
          <Button size="sm" onClick={handleTest}>
            Test
          </Button>
        )}
        {status === "testing" && (
          <span className="text-xs text-muted-foreground">Running…</span>
        )}
        {status === "passed" && (
          <>
            <Button size="sm" variant="outline" onClick={handleTest}>
              Re-test
            </Button>
          </>
        )}
        {status === "failed" && (
          <>
            <Button size="sm" variant="outline" onClick={handleTest}>
              Re-test
            </Button>
            <Button size="sm" variant="destructive" onClick={handleAskAssistant}>
              Ask assistant
            </Button>
          </>
        )}
        {(status === "passed" || status === "failed") && latestResult && (
          <RawOutput value={latestResult.data} />
        )}
      </div>
    </div>
  );
}
