import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useFolderStore } from "@/stores/foldersStore";

type EmptyFolderProps = {
  setOpenModal: (open: boolean) => void;
};

export const EmptyFolder = ({ setOpenModal }: EmptyFolderProps) => {
  const folders = useFolderStore((state) => state.folders);

  return (
    <div className="flex min-h-0 w-full flex-1 items-center justify-center self-stretch">
      <div className="flex flex-col items-center justify-center gap-2 text-center">
        <h3
          className="pt-5 font-chivo text-2xl font-semibold"
          data-testid="mainpage_title"
        >
          {folders?.length > 1 ? "Empty project" : "Start building"}
        </h3>
        <p className="pb-5 text-sm text-secondary-foreground">
          Begin with a template, or start from scratch.
        </p>
        <Button
          variant="default"
          onClick={() => setOpenModal(true)}
          id="new-project-btn"
          data-testid="new_project_btn_empty_page"
        >
          <ForwardedIconComponent
            name="plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="whitespace-nowrap font-semibold">New Flow</span>
        </Button>
      </div>
    </div>
  );
};

export default EmptyFolder;
