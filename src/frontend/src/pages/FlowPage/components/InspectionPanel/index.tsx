import { Panel } from "@xyflow/react";
import { memo, useEffect, useState } from "react";
import { Separator } from "@/components/ui/separator";
import type { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import InspectionPanelFields from "./components/InspectionPanelFields";
import InspectionPanelHeader from "./components/InspectionPanelHeader";

interface InspectionPanelProps {
  selectedNode: AllNodeType | null;
}

const InspectionPanel = memo(function InspectionPanel({
  selectedNode,
}: InspectionPanelProps) {
  const [isEditingFields, setIsEditingFields] = useState(false);

  // Reset edit mode when panel closes or node changes
  useEffect(() => {
    setIsEditingFields(false);
  }, [selectedNode?.id]);

  if (!selectedNode || selectedNode.type !== "genericNode") {
    return null;
  }

  return (
    <Panel
      position="top-right"
      className={cn(
        "!top-[3rem] !-right-2 !bottom-10 relative",
        "w-[340px]",
        "pointer-events-none",
      )}
    >
      <div
        className={cn(
          "max-h-full w-[320px] ml-auto",
          "rounded-xl border bg-background shadow-lg",
          "overflow-y-auto overflow-x-visible flex flex-col pointer-events-auto",
        )}
      >
        <InspectionPanelHeader
          data={selectedNode.data}
          isEditingFields={isEditingFields}
          setIsEditingFields={setIsEditingFields}
        />
        <Separator className="my-0.5" />
        <InspectionPanelFields
          data={selectedNode.data}
          key={selectedNode.id}
          isEditingFields={isEditingFields}
        />
      </div>
    </Panel>
  );
});

export default InspectionPanel;
