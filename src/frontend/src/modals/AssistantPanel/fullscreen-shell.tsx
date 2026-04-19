import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useAssistantStore from "@/stores/assistantStore";
import Composer from "./components/composer";
import MessageList from "./components/message-list";
import SettingsRequired from "./components/settings-required";

type Props = {
  flowId: string;
  onSend: (text: string) => void;
};

/** Full-viewport overlay shell hosting the ADP Assist chat.
 *
 * Header: branding + Test button + View Canvas + Close.
 * Body: message list + composer.
 */
export function FullscreenShell({ flowId, onSend }: Props) {
  const messages = useAssistantStore((s) => s.messages);
  const settingsConfigured = useAssistantStore((s) => s.settingsConfigured);
  const setLayoutMode = useAssistantStore((s) => s.setLayoutMode);
  const setPanelOpen = useAssistantStore((s) => s.setPanelOpen);
  const showToolCalls = useAssistantStore((s) => s.showToolCalls);
  const toggleShowToolCalls = useAssistantStore((s) => s.toggleShowToolCalls);

  return (
    // Offsets: top = app header (h-[48px]); left = flow-builder SidebarProvider width (17.5rem) on md+
    <div className="fixed top-[48px] bottom-0 right-0 left-0 md:left-[17.5rem] z-50 flex flex-col bg-background">
      <header className="flex h-14 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="Bot" className="h-5 w-5" />
          <span className="text-lg font-semibold">ADP Assist</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={showToolCalls ? "secondary" : "ghost"}
            onClick={toggleShowToolCalls}
            title={showToolCalls ? "Hide tool calls" : "Show tool calls"}
            aria-pressed={showToolCalls}
            data-testid="adp-assist-toggle-tool-calls-btn"
          >
            <ForwardedIconComponent name="Wrench" className="mr-1 h-4 w-4" />
            {showToolCalls ? "Hide tools" : "Show tools"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLayoutMode("test")}
            data-testid="adp-assist-test-btn"
          >
            <ForwardedIconComponent name="FlaskConical" className="mr-1 h-4 w-4" />
            Test
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

      <div className="flex flex-1 flex-col overflow-hidden">
        {!settingsConfigured ? (
          <SettingsRequired />
        ) : (
          <>
            <MessageList messages={messages} />
            <Composer onSend={onSend} />
          </>
        )}
      </div>
    </div>
  );
}
