import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { normalizeTimeString } from "@/CustomNodes/GenericNode/components/NodeStatus/utils/format-run-time";
import { CircleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import { useDelayedUnmount } from "@/utils/useDelayedUnmount";
import { cn } from "@/utils/utils";
import { getTimeVariants } from "./helpers/visual-variants";

export default function FlowBuildingComponent() {
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const errorButtonsRef = useRef<HTMLDivElement>(null);
  const stopButtonRef = useRef<HTMLDivElement>(null);
  const setBuildInfo = useFlowStore((state) => state.setBuildInfo);
  const [duration, setDuration] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const prevIsBuilding = useRef(isBuilding);
  const startTimeRef = useRef<number | null>(null);
  const pastBuildFlowParams = useFlowStore(
    (state) => state.pastBuildFlowParams,
  );
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const statusBuilding = useMemo(
    () =>
      Object.entries(flowBuildStatus)
        .filter(([_, s]) => s.status === BuildStatus.BUILDING)
        .map(([id, s]) => ({
          id,
          ...s,
        })),
    [flowBuildStatus],
  );

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (isBuilding && !prevIsBuilding.current) {
      setDismissed(false);
      setDuration(0);
      startTimeRef.current = Date.now();
    }

    if (isBuilding && startTimeRef.current !== null) {
      intervalId = setInterval(() => {
        setDuration(Date.now() - startTimeRef.current!);
      }, 10);
    }

    if (!isBuilding && prevIsBuilding.current) {
      startTimeRef.current = null;
    }

    prevIsBuilding.current = isBuilding;

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [isBuilding]);

  const displayTime = duration ?? 0;
  const secondsValue = displayTime / 1000;
  const humanizedTime =
    normalizeTimeString(`${secondsValue.toFixed(1)}seconds`) ??
    `${secondsValue.toFixed(1)}s`;

  const buildingContent = useMemo(() => {
    if (!isBuilding) return null;
    return (
      <TextShimmer duration={1}>
        {statusBuilding.length > 0
          ? `Running ${statusBuilding[0]?.id}`
          : "Running flow"}
      </TextShimmer>
    );
  }, [isBuilding, statusBuilding]);

  useEffect(() => {
    if (buildInfo?.success) {
      setTimeout(() => {
        handleDismiss();
      }, 2000);
    }
  }, [buildInfo?.success]);

  const handleDismiss = () => {
    setDismissed(true);
    setTimeout(() => {
      setBuildInfo(null);
      setDismissed(false);
    }, 500);
  };

  const handleStop = () => {
    stopBuilding();
  };

  const handleRetry = () => {
    if (pastBuildFlowParams) {
      buildFlow(pastBuildFlowParams);
    }
  };

  const panelVisible =
    (isBuilding || !!buildInfo?.error || !!buildInfo?.success) && !dismissed;
  const {
    shouldRender: panelShouldRender,
    isVisible: panelIsVisible,
    handleExitTransitionEnd: handlePanelExitTransitionEnd,
  } = useDelayedUnmount(panelVisible);

  const timeVariants = getTimeVariants(
    buildInfo?.error ? errorButtonsRef : stopButtonRef,
  );
  const timeStyle = !buildInfo?.success ? timeVariants.double : timeVariants.single;

  if (!panelShouldRender) return null;

  return (
    <div className="absolute bottom-2 left-1/2 z-50 w-[530px] -translate-x-1/2">
      <div
        onTransitionEnd={handlePanelExitTransitionEnd}
        className={cn(
          "flex flex-col justify-center overflow-hidden rounded-lg border bg-background px-4 py-2 text-sm shadow-md",
          "transition-[opacity,transform,color,background-color,border-color] duration-200 ease-out",
          panelIsVisible
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-5",
          !isBuilding &&
            buildInfo?.error &&
            "border-accent-red-foreground text-accent-red-foreground",
          !isBuilding &&
            buildInfo?.success &&
            "border-accent-emerald-foreground text-accent-emerald-foreground",
        )}
      >
        {(isBuilding || buildInfo?.error || buildInfo?.success) && (
          <>
            <div className="flex min-h-10 w-full items-center justify-between gap-2">
              <div>
                {buildingContent ? (
                  buildingContent
                ) : buildInfo?.success ? (
                  "Flow built successfully"
                ) : (
                  <div className="flex items-center gap-2">
                    <CircleAlert
                      className="h-5 w-5"
                    />
                    Flow build failed
                  </div>
                )}
              </div>
              <div className="relative flex items-center gap-4">
                <div
                  style={{
                    transform: `translateX(${timeStyle.x}px)`,
                    width: timeStyle.width,
                  }}
                  className="absolute right-0 font-mono text-xs transition-transform duration-200 ease-out"
                >
                  {humanizedTime}
                </div>
                {!buildInfo?.success && (
                  <div className="absolute right-0">
                    {buildInfo?.error ? (
                      <div
                        key="error-buttons"
                        ref={errorButtonsRef}
                        className="flex items-center gap-2 animate-in fade-in-0 duration-200"
                      >
                        <div className="animate-in fade-in-0 slide-in-from-right-2 duration-200">
                          <Button size="sm" onClick={handleRetry}>
                            Retry
                          </Button>
                        </div>
                        <div className="animate-in fade-in-0 slide-in-from-right-2 duration-200">
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-primary"
                            onClick={handleDismiss}
                          >
                            Dismiss
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div
                        key="stop-button"
                        ref={stopButtonRef}
                        className="animate-in fade-in-0 duration-200"
                      >
                        <Button
                          data-testid="stop_building_button"
                          size="sm"
                          onClick={handleStop}
                        >
                          Stop
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
            <AnimatePresence>
              {buildInfo?.error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="my-1.5 align-text-top truncate-doubleline">
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ node, ...props }) => (
                          <a
                            {...props}
                            target="_blank"
                            className="underline"
                            rel="noopener noreferrer"
                          >
                            {props.children}
                          </a>
                        ),
                        p({ node, ...props }) {
                          return (
                            <span className="inline-block w-fit max-w-full align-text-top truncate-doubleline">
                              {props.children}
                            </span>
                          );
                        },
                      }}
                    >
                      {buildInfo?.error?.join("\n")}
                    </Markdown>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
    </div>
  );
}
