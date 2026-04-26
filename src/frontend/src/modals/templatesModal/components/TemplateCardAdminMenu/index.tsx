import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Ellipsis, Pencil, Trash2 } from "lucide-react";
import IconComponent from "@/components/common/genericIconComponent";
import type { TemplateRead } from "@/types/template";

type Props = {
  template: TemplateRead;
  canEdit: boolean;
  onEdit(): void;
  onArchiveToggle(): void;
  onDelete(): void;
};

export default function TemplateCardAdminMenu({
  template,
  canEdit,
  onEdit,
  onArchiveToggle,
  onDelete,
}: Props) {
  if (!canEdit) return null;

  const isArchived = template.archived_at !== null;

  return (
    <div
      className="absolute right-8 top-2 z-20"
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 rounded-full opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
            aria-label="Template actions"
            onClick={(e) => e.stopPropagation()}
          >
            <Ellipsis className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
          >
            <Pencil className="mr-2 h-4 w-4" />
            Edit template
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              onArchiveToggle();
            }}
          >
            <IconComponent
              name={isArchived ? "ArchiveRestore" : "Archive"}
              className="mr-2 h-4 w-4"
            />
            {isArchived ? "Unarchive" : "Archive"}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
