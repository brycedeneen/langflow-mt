import { useEffect, useState } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { EditNodeComponent } from "@/modals/editNodeModal/components/editNodeComponent";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";

export function TweakComponent({
  open,
  node,
}: {
  open: boolean;
  node: AllNodeType;
}) {
  const [nodeClass, setNodeClass] = useState<APIClassType | undefined>(
    node.data?.node,
  );
  const [value, setValue] = useState("");

  useEffect(() => {
    if (
      customStringify(Object.keys(node.data?.node?.template ?? {})) ===
      customStringify(Object.keys(nodeClass?.template ?? {}))
    )
      return;
    setNodeClass(node.data?.node);
  }, [node.data?.node]);
  return node && node.data && nodeClass ? (
    <Accordion
      type="single"
      collapsible
      className="w-full"
      value={value}
      onValueChange={setValue}
    >
      <AccordionItem value={node.data.id} className="border-b">
        <AccordionTrigger className="ml-3 cursor-pointer">
          <Tooltip delayDuration={500}>
            <TooltipTrigger asChild>
              <div className="text-primary">{node.data.node?.display_name}</div>
            </TooltipTrigger>
            <TooltipContent
              className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
              side="top"
              avoidCollisions={false}
              sticky="always"
            >
              {node.data.id}
            </TooltipContent>
          </Tooltip>
        </AccordionTrigger>
        <AccordionContent>
          <div className="AccordionContent flex flex-col">
            <EditNodeComponent
              open={open}
              autoHeight
              nodeClass={nodeClass}
              isTweaks
              nodeId={node.data.id}
            />
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ) : (
    <></>
  );
}
