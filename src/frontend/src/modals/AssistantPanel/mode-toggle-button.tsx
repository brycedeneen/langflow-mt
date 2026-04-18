import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useAssistantStore from "@/stores/assistantStore";

/** Toggle between panel and fullscreen layout modes. Only rendered in panel mode. */
export function ModeToggleButton() {
  const layoutMode = useAssistantStore((s) => s.layoutMode);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);

  if (layoutMode !== "panel") return null;

  return (
    <ShadTooltip content="Enter full-screen ADP Assist">
      <button
        aria-label="Enter full-screen ADP Assist"
        onClick={() => setLayoutMode("fullscreen")}
        className="inline-flex h-7 w-7 items-center justify-center rounded hover:bg-muted"
      >
        <ForwardedIconComponent name="Maximize2" className="h-4 w-4" />
      </button>
    </ShadTooltip>
  );
}
