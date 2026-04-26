import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/utils";
import IconComponent from "../../../components/common/genericIconComponent";
import type { ChatViewWrapperProps } from "../types/chat-view-wrapper";
import ChatView from "./chatView/components/chat-view";

export const ChatViewWrapper = ({
  selectedViewField,
  visibleSession,
  sessions,
  sidebarOpen,
  currentFlowId,
  setSidebarOpen,
  setvisibleSession,
  setSelectedViewField,
  messagesFetched,
  sessionId,
  sendMessage,
  canvasOpen,
  setOpen,
  playgroundPage,
}: ChatViewWrapperProps) => {
  return (
    <div
      className={cn(
        "flex h-full w-full flex-col justify-between px-4 pb-4 pt-2",
        selectedViewField ? "hidden" : "",
      )}
    >
      <div
        className={cn(
          "flex h-10 shrink-0 items-center text-base font-semibold",
          playgroundPage ? "justify-between" : "lg:justify-start",
        )}
      >
        <div className={cn(sidebarOpen ? "lg:hidden" : "left-4")}>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              className="h-8 w-8"
            >
              <IconComponent
                name="PanelLeftOpen"
                className="h-[18px] w-[18px] text-ring"
              />
            </Button>
          </div>
        </div>
        {visibleSession && sessions.length > 0 && (
          <div
            className={cn(
              "truncate text-center font-semibold",
              playgroundPage ? "" : "mr-12 grow lg:mr-0",
              sidebarOpen ? "blur-sm lg:blur-0" : "",
            )}
          >
            {visibleSession === currentFlowId
              ? "Default Session"
              : `${visibleSession}`}
          </div>
        )}
        <div
          className={cn(
            sidebarOpen ? "pointer-events-none opacity-0" : "",
            "flex items-center justify-center rounded-sm ring-offset-background transition-opacity focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            playgroundPage ? "right-2 top-4" : "absolute right-12 top-2 h-8",
          )}
        >
          <Tooltip delayDuration={500}>
            <TooltipTrigger asChild>
              <Button
                className="mr-2 h-[32px] w-[32px] hover:bg-secondary-hover"
                variant="ghost"
                size="icon"
                onClick={() => {
                  setvisibleSession(undefined);
                  setSelectedViewField(undefined);
                }}
              >
                <IconComponent
                  name="Plus"
                  className="!h-[18px] !w-[18px] text-ring"
                />
              </Button>
            </TooltipTrigger>
            <TooltipContent
              className={cn("z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground", "z-50")}
              side="bottom"
              avoidCollisions={false}
              sticky="always"
            >
              New Chat
            </TooltipContent>
          </Tooltip>
          {!playgroundPage && <Separator orientation="vertical" />}
        </div>
      </div>

      {messagesFetched && (
        <ChatView
          focusChat={sessionId}
          sendMessage={sendMessage}
          visibleSession={visibleSession}
          closeChat={
            !canvasOpen
              ? undefined
              : () => {
                  setOpen(false);
                }
          }
          playgroundPage={playgroundPage}
          sidebarOpen={sidebarOpen}
        />
      )}
    </div>
  );
};
