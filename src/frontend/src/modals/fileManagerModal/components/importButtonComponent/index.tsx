// NOTE: The @/components/ui/morphing-menu module does not exist in this
// codebase. This component is currently unused (see
// modals/fileManagerModal/components/recentFilesComponent/index.tsx where
// it is commented out). The local `MorphingMenu` stub below keeps this file
// type-clean until a real implementation is restored.
type MorphingMenuItem = {
  icon: string;
  label: string;
  onClick: () => void;
};

function MorphingMenu(_props: {
  variant: "large" | "small";
  trigger: string;
  items: MorphingMenuItem[];
}) {
  return null;
}

export default function ImportButtonComponent({
  variant = "large",
}: {
  variant?: "large" | "small";
}) {
  const items: MorphingMenuItem[] = [
    {
      icon: "GoogleDrive",
      label: "Drive",
      onClick: () => {
        // Handle Google Drive click
      },
    },
    {
      icon: "OneDrive",
      label: "OneDrive",
      onClick: () => {
        // Handle OneDrive click
      },
    },
    {
      icon: "AWSInverted",
      label: "S3 Bucket",
      onClick: () => {
        // Handle S3 click
      },
    },
  ];

  return (
    <MorphingMenu variant={variant} trigger="Import from..." items={items} />
  );
}
