import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import {
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from "@/controllers/API/queries/categories";
import useAlertStore from "@/stores/alertStore";
import type { ApiCategory, NavProps } from "@/types/templates/types";
import { cn } from "@/utils/utils";
import { useIsMobile } from "../../../../hooks/use-mobile";
import type { CategoryEditPayload } from "../CategoryEditPopover";
import { CategoryEditPopover } from "../CategoryEditPopover";

/** IDs for the three permanent nav rows that never show admin affordances */
const PERMANENT_IDS = new Set(["get-started", "all-templates", "saved"]);

export function Nav({
  items,
  currentTab,
  setCurrentTab,
  isAdmin = false,
  apiCategories = [],
}: NavProps) {
  const isMobile = useIsMobile();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  // ── Create state ───────────────────────────────────────────────
  const [createOpen, setCreateOpen] = useState(false);
  const createMutation = useCreateCategory();

  // ── Edit state ─────────────────────────────────────────────────
  const [editTarget, setEditTarget] = useState<ApiCategory | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const updateMutation = useUpdateCategory();

  // ── Delete state ───────────────────────────────────────────────
  const [deleteTarget, setDeleteTarget] = useState<ApiCategory | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const deleteMutation = useDeleteCategory();

  // ── Helpers ────────────────────────────────────────────────────
  /** Find the full Category object by nav item id (which equals cat.name) */
  const apiCatByNavId = (navId: string): ApiCategory | undefined =>
    apiCategories.find((c) => c.name === navId);

  const handleCreate = (payload: CategoryEditPayload) => {
    createMutation.mutate(
      {
        name: payload.name,
        icon: payload.icon,
        color: payload.color,
        description: payload.description ?? undefined,
      },
      {
        onSuccess: (created) => {
          setCreateOpen(false);
          setSuccessData({ title: `Category "${created.name}" created` });
          setCurrentTab(created.name);
        },
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : "Failed to create category";
          setErrorData({ title: msg });
        },
      },
    );
  };

  const handleEdit = (payload: CategoryEditPayload) => {
    if (!editTarget) return;
    updateMutation.mutate(
      {
        categoryId: editTarget.id,
        body: {
          name: payload.name,
          icon: payload.icon,
          color: payload.color,
          description: payload.description ?? undefined,
        },
      },
      {
        onSuccess: (updated) => {
          setEditOpen(false);
          setEditTarget(null);
          setSuccessData({ title: `Category "${updated.name}" updated` });
          // If the user is viewing the old name tab, switch to the new name
          if (currentTab === editTarget.name) {
            setCurrentTab(updated.name);
          }
        },
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : "Failed to update category";
          setErrorData({ title: msg });
        },
      },
    );
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate(
      { categoryId: deleteTarget.id },
      {
        onSuccess: () => {
          setDeleteDialogOpen(false);
          setSuccessData({
            title: `Category "${deleteTarget.name}" deleted`,
          });
          // If we were viewing the deleted category, fall back to all-templates
          if (currentTab === deleteTarget.name) {
            setCurrentTab("all-templates");
          }
          setDeleteTarget(null);
        },
        onError: (err: unknown) => {
          const msg =
            err instanceof Error ? err.message : "Failed to delete category";
          setErrorData({ title: msg });
        },
      },
    );
  };

  return (
    <>
      <Sidebar collapsible={isMobile ? "icon" : "none"} className="max-w-[230px]">
        <SidebarContent className="gap-0 p-2">
          <div
            className={cn("relative flex items-center gap-2 px-2 py-3 md:px-4")}
            data-testid="modal-title"
          >
            <SidebarTrigger
              className={cn(
                "flex h-8 shrink-0 items-center rounded-md text-lg font-semibold leading-none tracking-tight text-primary outline-hidden ring-ring transition-[margin,opa] duration-200 ease-linear focus-visible:ring-1 md:hidden [&>svg]:size-4 [&>svg]:shrink-0",
              )}
            />
            <div
              className={cn(
                "text-base-semibold flex h-8 shrink-0 items-center rounded-md leading-none tracking-tight text-primary outline-hidden ring-ring transition-[margin,opa] duration-200 ease-linear focus-visible:ring-1 [&>svg]:size-4 [&>svg]:shrink-0",
                "group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0",
              )}
            >
              Templates
            </div>
          </div>

          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {items.map((link) => {
                  const isPermanent = PERMANENT_IDS.has(link.id);
                  const apiCat = !isPermanent
                    ? apiCatByNavId(link.id)
                    : undefined;
                  const showAdminControls = isAdmin && !isPermanent && !!apiCat;

                  return (
                    <SidebarMenuItem key={link.id}>
                      <div className="group/nav-item relative flex w-full items-center">
                        <SidebarMenuButton
                          onClick={() => setCurrentTab(link.id)}
                          isActive={currentTab === link.id}
                          data-testid={`side_nav_options_${link.title.toLowerCase().replace(/\s+/g, "-")}`}
                          tooltip={link.title}
                          className={cn(
                            "flex-1",
                            showAdminControls && "pr-7",
                          )}
                        >
                          <ForwardedIconComponent
                            name={link.icon}
                            className={`h-4 w-4 stroke-2 ${
                              currentTab === link.id
                                ? "text-accent-pink-foreground"
                                : "text-muted-foreground"
                            }`}
                          />
                          <span
                            data-testid={`category_title_${convertTestName(link.title)}`}
                          >
                            {link.title}
                          </span>
                        </SidebarMenuButton>

                        {showAdminControls && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button
                                type="button"
                                aria-label={`Options for ${link.title}`}
                                className={cn(
                                  "absolute right-1 flex h-6 w-6 items-center justify-center rounded opacity-0 transition-opacity",
                                  "hover:bg-accent hover:text-accent-foreground",
                                  "group-hover/nav-item:opacity-100 focus:opacity-100",
                                )}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <ForwardedIconComponent
                                  name="Ellipsis"
                                  className="h-3.5 w-3.5"
                                />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" side="right">
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditTarget(apiCat!);
                                  setEditOpen(true);
                                }}
                              >
                                <ForwardedIconComponent
                                  name="Pencil"
                                  className="mr-2 h-4 w-4"
                                />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeleteTarget(apiCat!);
                                  setDeleteDialogOpen(true);
                                }}
                              >
                                <ForwardedIconComponent
                                  name="Trash2"
                                  className="mr-2 h-4 w-4"
                                />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    </SidebarMenuItem>
                  );
                })}

                {/* "+ New category" row — admin only */}
                {isAdmin && (
                  <SidebarMenuItem>
                    <CategoryEditPopover
                      mode="create"
                      open={createOpen}
                      onOpenChange={setCreateOpen}
                      onSubmit={handleCreate}
                      busy={createMutation.isPending}
                      anchor={
                        <SidebarMenuButton
                          onClick={() => setCreateOpen(true)}
                          data-testid="side_nav_new_category"
                          tooltip="New category"
                        >
                          <ForwardedIconComponent
                            name="Plus"
                            className="h-4 w-4 stroke-2 text-muted-foreground"
                          />
                          <span className="text-muted-foreground">
                            New category
                          </span>
                        </SidebarMenuButton>
                      }
                    />
                  </SidebarMenuItem>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>

      {/* Edit popover — rendered outside the sidebar to avoid stacking context issues */}
      {editTarget && (
        <CategoryEditPopover
          mode="edit"
          initial={{
            name: editTarget.name,
            icon: editTarget.icon,
            color: editTarget.color,
            description: editTarget.description,
          }}
          open={editOpen}
          onOpenChange={(o) => {
            setEditOpen(o);
            if (!o) setEditTarget(null);
          }}
          onSubmit={handleEdit}
          busy={updateMutation.isPending}
        />
      )}

      {/* Delete confirm dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete category?</DialogTitle>
            <DialogDescription>
              Delete &ldquo;{deleteTarget?.name}&rdquo;? Templates tagged with
              it will be untagged.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
