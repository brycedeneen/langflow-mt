import { useState } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import { useVoiceStore } from "@/stores/voiceStore";
import { MessagesSquare, Plus } from "lucide-react";
import type { SidebarOpenViewProps } from "../types/sidebar-open-view";
import SessionSelector from "./IOFieldView/components/session-selector";

export const SidebarOpenView = ({
  sessions,
  setSelectedViewField,
  setvisibleSession,
  handleDeleteSession,
  visibleSession,
  selectedViewField,
  playgroundPage,
  setActiveSession,
}: SidebarOpenViewProps) => {
  const [openMenuSession, setOpenMenuSession] = useState<string | null>(null);

  const setNewSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.setNewSessionCloseVoiceAssistant,
  );

  const setNewChatOnPlayground = useFlowStore(
    (state) => state.setNewChatOnPlayground,
  );

  return (
    <>
      <div className="flex flex-col pl-3">
        <div className="flex flex-col gap-2 pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessagesSquare
                className="h-[18px] w-[18px] text-ring"
              />
              <div className="text-mmd font-normal">Chat</div>
            </div>
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <div>
                  <Button
                    data-testid="new-chat"
                    variant="ghost"
                    className="flex h-8 w-8 items-center justify-center !p-0 hover:bg-secondary-hover"
                    onClick={(_) => {
                      setvisibleSession(undefined);
                      setSelectedViewField(undefined);
                      setNewSessionCloseVoiceAssistant(true);
                      setNewChatOnPlayground(true);
                    }}
                  >
                    <Plus
                      className="h-[18px] w-[18px] text-ring"
                    />
                  </Button>
                </div>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
                avoidCollisions={false}
                sticky="always"
              >
                New Chat
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
        <div className="flex flex-col">
          {sessions.map((session, index) => (
            <SessionSelector
              setSelectedView={setSelectedViewField}
              selectedView={selectedViewField}
              key={session}
              session={session}
              playgroundPage={playgroundPage}
              deleteSession={(session) => {
                handleDeleteSession(session);
                if (selectedViewField?.id === session) {
                  setSelectedViewField(undefined);
                }
              }}
              updateVisibleSession={(session) => {
                setvisibleSession(session);
              }}
              toggleVisibility={() => {
                setvisibleSession(session);
              }}
              isVisible={visibleSession === session}
              inspectSession={(session) => {
                setSelectedViewField({
                  id: session,
                  type: "Session",
                });
              }}
              setActiveSession={(session) => {
                setActiveSession(session);
              }}
              menuOpen={openMenuSession === session}
              onMenuOpenChange={(open) => {
                setOpenMenuSession(open ? session : null);
              }}
            />
          ))}
        </div>
      </div>
    </>
  );
};
