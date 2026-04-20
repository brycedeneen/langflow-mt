import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Checkbox } from "@/components/ui/checkbox";
import useDuplicateFlows from "@/pages/MainPage/hooks/use-handle-duplicate";
import useFlowStore from "@/stores/flowStore";
import type { ComponentsToUpdateType } from "@/types/zustand/flow";
import { cn } from "@/utils/utils";
import BaseModal from "../baseModal";
import ChangelogPanel from "./changelogPanel";

export default function UpdateComponentModal({
  open,
  setOpen,
  onUpdateNode,
  children,
  components,
  isMultiple = false,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  onUpdateNode: (updatedComponents?: string[]) => void;
  children?: React.ReactNode;
  components: ComponentsToUpdateType[];
  isMultiple?: boolean;
}) {
  const [backupFlow, setBackupFlow] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedComponents, setSelectedComponents] = useState<Set<string>>(
    new Set(components.filter((c) => !c.breakingChange).map((c) => c.id)),
  );
  const [expandedRows, setExpandedRows] = useState<Set<string>>(
    new Set(components.filter((c) => c.breakingChange).map((c) => c.id)),
  );
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const { handleDuplicate } = useDuplicateFlows({
    flow: currentFlow
      ? { ...currentFlow, name: currentFlow.name + " (Backup)" }
      : undefined,
  });

  const handleUpdate = () => {
    setLoading(true);
    if (backupFlow) {
      handleDuplicate().then(() => {
        onUpdateNode(
          components.length > 0 ? Array.from(selectedComponents) : undefined,
        );
        setLoading(false);
        setOpen(false);
      });
    } else {
      onUpdateNode(
        components.length > 0 ? Array.from(selectedComponents) : undefined,
      );
      setLoading(false);
      setOpen(false);
    }
  };

  useEffect(() => {
    if (open) {
      setBackupFlow(true);
      setSelectedComponents(
        new Set(components.filter((c) => !c.breakingChange).map((c) => c.id)),
      );
      setExpandedRows(
        new Set(components.filter((c) => c.breakingChange).map((c) => c.id)),
      );
    }
  }, [open]);

  return (
    <BaseModal
      closeButtonClassName="!top-2 !right-3"
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="px-4 py-3"
    >
      <BaseModal.Trigger asChild>{children ?? <span />}</BaseModal.Trigger>
      <BaseModal.Header>
        <span className="">
          Update{" "}
          {isMultiple ? "components" : (components?.[0]?.display_name ?? "")}
        </span>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3 text-sm text-muted-foreground">
            {isMultiple ? (
              <p>
                Updates marked as{" "}
                <span className="font-semibold text-accent-amber-foreground">
                  breaking
                </span>{" "}
                may change inputs, outputs, or component behavior. In some
                cases, they will disconnect components from your flow, requiring
                you to review or reconnect them afterward. Components added from
                the sidebar always use the latest version.
              </p>
            ) : (
              <>
                <p>
                  This update may change inputs, outputs, or component behavior.
                  In some cases, it will{" "}
                  <span className="font-semibold text-accent-amber-foreground">
                    disconnect this component from your flow
                  </span>
                  , requiring you to review or reconnect it afterward.
                </p>
                <p>
                  Components added from the sidebar always use the latest
                  version.
                </p>
              </>
            )}
          </div>
          {!isMultiple &&
            components[0]?.outdated &&
            components[0].changelogEntries.length > 0 && (
              <ChangelogPanel
                userVersion={components[0].userVersion}
                latestVersion={components[0].latestVersion}
                entries={components[0].changelogEntries}
                breaking={components[0].breakingChange}
              />
            )}
          {isMultiple && (
            <div className="-mx-4 max-h-[320px] overflow-y-auto">
              <div className="grid grid-cols-[28px_28px_1fr_100px] items-center gap-2 border-b px-4 py-1 text-[11px] text-muted-foreground">
                <span />
                <Checkbox
                  checked={
                    components.length > 0 &&
                    selectedComponents.size === components.length
                  }
                  onCheckedChange={(checked) => {
                    if (checked === true) {
                      setSelectedComponents(
                        new Set(components.map((c) => c.id)),
                      );
                    } else {
                      setSelectedComponents(new Set());
                    }
                  }}
                  aria-label="Select all"
                />
                <span>Component</span>
                <span>Update Type</span>
              </div>

              {components.map((c) => {
                const isSelected = selectedComponents.has(c.id);
                const isOpen = expandedRows.has(c.id);
                return (
                  <div
                    key={c.id}
                    className="border-b px-4 py-2 last:border-b-0"
                  >
                    <div className="grid grid-cols-[28px_28px_1fr_100px] items-center gap-2">
                      <button
                        type="button"
                        aria-label={isOpen ? "Collapse" : "Expand"}
                        className="text-muted-foreground"
                        onClick={() =>
                          setExpandedRows((prev) => {
                            const next = new Set(prev);
                            if (next.has(c.id)) next.delete(c.id);
                            else next.add(c.id);
                            return next;
                          })
                        }
                      >
                        <ForwardedIconComponent
                          name={isOpen ? "ChevronDown" : "ChevronRight"}
                          className="h-4 w-4"
                        />
                      </button>
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={(checked) => {
                          setSelectedComponents((prev) => {
                            const next = new Set(prev);
                            if (checked === true) next.add(c.id);
                            else next.delete(c.id);
                            return next;
                          });
                        }}
                        aria-label={`Select ${c.display_name}`}
                      />
                      <div className="flex items-center gap-2">
                        {c.icon && (
                          <ForwardedIconComponent
                            name={c.icon}
                            className="h-4 w-4"
                          />
                        )}
                        <span>{c.display_name}</span>
                      </div>
                      <span
                        className={cn(
                          "text-mmd",
                          c.breakingChange
                            ? "font-semibold text-accent-amber-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        {c.breakingChange ? "Breaking" : "Standard"}
                      </span>
                    </div>

                    {isOpen && c.outdated && (
                      <div className="ml-14 mt-2">
                        <ChangelogPanel
                          userVersion={c.userVersion}
                          latestVersion={c.latestVersion}
                          entries={c.changelogEntries}
                          breaking={c.breakingChange}
                          showEmptyFallback
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          <div
            className={cn(
              "mb-3 flex items-center gap-3 rounded-md border p-3 text-sm transition-all",
              !backupFlow && "border-accent-amber-foreground bg-accent-amber",
            )}
          >
            <Checkbox
              checked={backupFlow}
              onCheckedChange={(checked) =>
                setBackupFlow(checked === "indeterminate" ? false : checked)
              }
              className="bg-muted"
              id="backupFlow"
              data-testid="backup-flow-checkbox"
            />
            <label htmlFor="backupFlow" className="cursor-pointer select-none">
              Create backup flow before updating
            </label>
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Update Component" + (components.length > 1 ? "s" : ""),
          onClick: handleUpdate,
          disabled: isMultiple && selectedComponents.size === 0,
          loading,
        }}
      ></BaseModal.Footer>
    </BaseModal>
  );
}
