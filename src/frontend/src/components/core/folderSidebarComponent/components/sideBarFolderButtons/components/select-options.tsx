import IconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import type { FolderType } from "@/pages/MainPage/entities";
import { cn } from "@/utils/utils";
import { handleSelectChange } from "../helpers/handle-select-change";
import { FolderSelectItem } from "./folder-select-item";

export const SelectOptions = ({
  item,
  handleDeleteFolder,
  handleDownloadFolder,
  handleSelectFolderToRename,
  checkPathName,
}: {
  item: FolderType;
  handleDeleteFolder: ((folder: FolderType) => void) | undefined;
  handleDownloadFolder: (folderId: string) => void;
  handleSelectFolderToRename: (folder: FolderType) => void;
  checkPathName: (folderId: string) => boolean;
}) => {
  return (
    <div>
      <Select
        onValueChange={(value) =>
          handleSelectChange(
            value,
            item,
            handleDeleteFolder,
            handleDownloadFolder,
            handleSelectFolderToRename,
          )
        }
        value=""
      >
        <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <SelectTrigger
            className="w-fit"
            id={`options-trigger-${item.name}`}
            data-testid={
              "more-options-button" + `_${convertTestName(item?.name ?? "")}`
            }
          >
            <IconComponent
              name={"MoreHorizontal"}
              className={cn(
                `w-4 stroke-[1.5] px-0 text-muted-foreground group-hover/menu-button:block group-hover/menu-button:text-foreground`,
                checkPathName(item.id!) ? "block" : "hidden",
              )}
            />
          </SelectTrigger>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
          side="right"
          avoidCollisions={false}
          sticky="always"
        >
          Options
        </TooltipContent>
        </Tooltip>
        <SelectContent align="end" alignOffset={-16} position="popper">
          <SelectItem
            id="rename-button"
            value="rename"
            data-testid="btn-rename-project"
            className="text-xs"
          >
            <FolderSelectItem name="Rename" iconName="SquarePen" />
          </SelectItem>
          <SelectItem
            value="download"
            data-testid="btn-download-project"
            className="text-xs"
          >
            <FolderSelectItem name="Download" iconName="Download" />
          </SelectItem>
          <SelectItem
            value="delete"
            data-testid="btn-delete-project"
            className="text-xs"
          >
            <FolderSelectItem name="Delete" iconName="Trash2" />
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
};
