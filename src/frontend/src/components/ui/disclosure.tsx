"use client";
import * as React from "react";
import {
  createContext,
  memo,
  useCallback,
  useContext,
  useId,
  useMemo,
} from "react";
import { cn } from "../../utils/utils";

type DisclosureContextType = {
  open: boolean;
  toggle: () => void;
};

const DisclosureContext = createContext<DisclosureContextType | undefined>(
  undefined,
);

type DisclosureProviderProps = {
  children: React.ReactNode;
  open: boolean;
  onOpenChange?: (open: boolean) => void;
};

const DisclosureProvider = memo(function DisclosureProvider({
  children,
  open: openProp,
  onOpenChange,
}: DisclosureProviderProps) {
  const toggle = useCallback(() => {
    if (onOpenChange) {
      onOpenChange(!openProp);
    }
  }, [onOpenChange, openProp]);

  const contextValue = useMemo(
    () => ({
      open: openProp,
      toggle,
    }),
    [openProp, toggle],
  );

  return (
    <DisclosureContext.Provider value={contextValue}>
      {children}
    </DisclosureContext.Provider>
  );
});

function useDisclosure() {
  const context = useContext(DisclosureContext);
  if (!context) {
    throw new Error("useDisclosure must be used within a DisclosureProvider");
  }
  return context;
}

type DisclosureProps = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
};

export const Disclosure = memo(function Disclosure({
  open: openProp = false,
  onOpenChange,
  children,
  className,
}: DisclosureProps) {
  const childrenArray = React.Children.toArray(children);

  return (
    <div className={className}>
      <DisclosureProvider open={openProp} onOpenChange={onOpenChange}>
        {childrenArray[0]}
        {childrenArray[1]}
      </DisclosureProvider>
    </div>
  );
});

const DisclosureTrigger = memo(function DisclosureTrigger({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { toggle, open } = useDisclosure();

  const handleKeyDown = useCallback(
    (e: { key: string; preventDefault: () => void }) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    },
    [toggle],
  );

  const childProps = useMemo(
    () => ({
      onClick: toggle,
      role: "button",
      "aria-expanded": open,
      tabIndex: 0,
      onKeyDown: handleKeyDown,
    }),
    [toggle, open, handleKeyDown],
  );

  return (
    <>
      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) return child;

        const childElement = child as React.ReactElement<{
          className?: string;
        }>;
        return React.cloneElement(childElement, {
          ...childProps,
          className: cn(className, childElement.props.className),
          ...childElement.props,
        } as React.Attributes);
      })}
    </>
  );
});

const DisclosureContent = memo(function DisclosureContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { open } = useDisclosure();
  const uniqueId = useId();

  // Grid-template-rows trick: animates 0fr ↔ 1fr to reveal/hide content at its
  // natural height. Replaces the previous framer-motion height: auto ↔ 0
  // animation with pure CSS.
  return (
    <div
      id={uniqueId}
      data-open={open}
      className={cn(
        "grid grid-rows-[0fr] transition-[grid-template-rows,opacity] duration-200 ease-in-out data-[open=true]:grid-rows-[1fr] overflow-hidden opacity-0 data-[open=true]:opacity-100",
        className,
      )}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
});

export { DisclosureContent, DisclosureTrigger };

export default {
  Disclosure,
  DisclosureProvider,
  DisclosureTrigger,
  DisclosureContent,
};
