import { memo } from "react";

import { PanelLeftClose, SlidersHorizontal } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarHeader, SidebarTrigger } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import type { SidebarHeaderComponentProps } from "../types";
import FeatureToggles from "./featureTogglesComponent";
import { SearchInput } from "./searchInput";
import { SidebarFilterComponent } from "./sidebarFilterComponent";

export const SidebarHeaderComponent = memo(function SidebarHeaderComponent({
  showConfig,
  setShowConfig,
  showBeta,
  setShowBeta,
  showLegacy,
  setShowLegacy,
  searchInputRef,
  isInputFocused,
  search,
  handleInputFocus,
  handleInputBlur,
  handleInputChange,
  filterName,
  filterDescription,
  resetFilters,
}: SidebarHeaderComponentProps) {
  return (
    <SidebarHeader className="flex w-full flex-col gap-2 group-data-[collapsible=icon]:hidden border-b">
      {!ENABLE_NEW_SIDEBAR && (
        <Disclosure open={showConfig} onOpenChange={setShowConfig}>
          <div className="flex w-full items-center gap-2">
            <SidebarTrigger className="text-muted-foreground">
              <PanelLeftClose />
            </SidebarTrigger>
            <h3 className="flex-1 cursor-default text-sm font-semibold">
              Components
            </h3>
            <DisclosureTrigger>
              <div>
                <Tooltip delayDuration={500}>
                  <TooltipTrigger asChild>
                    <Button
                      variant={showConfig ? "ghostActive" : "ghost"}
                      size="iconMd"
                      data-testid="sidebar-options-trigger"
                    >
                      <SlidersHorizontal
                        className="h-4 w-4"
                      />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent
                    className={cn("z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground", "z-50")}
                    avoidCollisions={false}
                    sticky="always"
                  >
                    Component settings
                  </TooltipContent>
                </Tooltip>
              </div>
            </DisclosureTrigger>
          </div>
          <DisclosureContent>
            <FeatureToggles
              showBeta={showBeta}
              setShowBeta={setShowBeta}
              showLegacy={showLegacy}
              setShowLegacy={setShowLegacy}
            />
          </DisclosureContent>
        </Disclosure>
      )}
      <SearchInput
        searchInputRef={searchInputRef}
        isInputFocused={isInputFocused}
        search={search}
        handleInputFocus={handleInputFocus}
        handleInputBlur={handleInputBlur}
        handleInputChange={handleInputChange}
      />
      {filterName !== "" && filterDescription !== "" && (
        <SidebarFilterComponent
          name={filterName}
          description={filterDescription}
          resetFilters={resetFilters}
        />
      )}
      {ENABLE_NEW_SIDEBAR && (
        <Disclosure open={showConfig} onOpenChange={setShowConfig}>
          <DisclosureContent>
            <FeatureToggles
              showBeta={showBeta}
              setShowBeta={setShowBeta}
              showLegacy={showLegacy}
              setShowLegacy={setShowLegacy}
            />
          </DisclosureContent>
        </Disclosure>
      )}
    </SidebarHeader>
  );
});

SidebarHeaderComponent.displayName = "SidebarHeaderComponent";
