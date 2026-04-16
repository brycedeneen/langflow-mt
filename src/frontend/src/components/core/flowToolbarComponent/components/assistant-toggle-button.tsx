import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useAssistantStore from "@/stores/assistantStore";

export default function AssistantToggleButton() {
  const togglePanel = useAssistantStore((state) => state.togglePanel);
  const panelOpen = useAssistantStore((state) => state.panelOpen);

  return (
    <ShadTooltip content="Flow Assistant">
      <button
        onClick={togglePanel}
        data-testid="assistant-toggle-btn"
        className={
          "relative inline-flex h-8 items-center justify-center gap-1.5 rounded px-2 text-sm font-normal hover:bg-muted " +
          (panelOpen ? "text-primary" : "text-muted-foreground")
        }
      >
        <ForwardedIconComponent name="Bot" className="h-4 w-4" />
        <span className="font-normal text-mmd">Assistant</span>
      </button>
    </ShadTooltip>
  );
}
