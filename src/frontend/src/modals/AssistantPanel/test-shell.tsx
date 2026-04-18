import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useAssistantStore from "@/stores/assistantStore";
import Composer from "./components/composer";
import MessageList from "./components/message-list";

type Props = {
  flowId: string;
  onSend: (text: string) => void;
};

/** Split-view test shell: pipeline placeholder on the left, chat on the right.
 *
 * The pipeline placeholder will be replaced by <FlowPipelineView /> in Plan 5.
 */
export function TestShell({ flowId, onSend }: Props) {
  const messages = useAssistantStore((s) => s.messages);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);
  const setPanelOpen = useAssistantStore((s) => s.setPanelOpen);

  return (
    // Offsets: top = app header (h-[48px]); left = flow-builder SidebarProvider width (17.5rem) on md+
    <div className="fixed top-[48px] bottom-0 right-0 left-0 md:left-[17.5rem] z-50 flex flex-col bg-background">
      <header className="flex h-14 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="Bot" className="h-5 w-5" />
          <span className="text-lg font-semibold">ADP Assist — Test</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("fullscreen")}
            data-testid="adp-assist-back-to-chat-btn"
          >
            <ForwardedIconComponent name="ArrowLeft" className="mr-1 h-4 w-4" />
            Back to chat
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("panel")}
            data-testid="adp-assist-view-canvas-btn"
          >
            <ForwardedIconComponent name="PanelLeft" className="mr-1 h-4 w-4" />
            View Canvas
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setLayoutMode("panel");
              setPanelOpen(false);
            }}
            aria-label="Close ADP Assist"
            data-testid="adp-assist-close-btn"
          >
            <ForwardedIconComponent name="X" className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex w-1/2 flex-col items-center justify-center border-r text-muted-foreground">
          <ForwardedIconComponent
            name="GitBranch"
            className="mb-2 h-8 w-8 opacity-50"
          />
          <div className="text-sm">
            Pipeline view will appear here (Plan 5).
          </div>
        </div>
        <div className="flex w-1/2 flex-col">
          <MessageList messages={messages} />
          <Composer onSend={onSend} />
        </div>
      </div>
    </div>
  );
}
