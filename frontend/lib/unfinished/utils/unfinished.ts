import type { BottomPanelState, ProfilePanelTab } from "../types.ts";

export const isExpandedOnlyProfileTab = (tab: ProfilePanelTab) => tab === "support" || tab === "settings";

export const getCollapsedPanelOpenState = (
    isProfileTab: boolean,
    activeProfileTab: ProfilePanelTab,
): BottomPanelState => isProfileTab && isExpandedOnlyProfileTab(activeProfileTab) ? "expanded" : "normal";

export const getPanelStepState = (
    currentState: BottomPanelState,
    deltaY: number,
): BottomPanelState => deltaY > 0
    ? (currentState === "expanded" ? "normal" : "collapsed")
    : "expanded";

export const getScrollProgress = (scrollTop: number, scrollHeight: number, clientHeight: number) => {
    const scrollableHeight = scrollHeight - clientHeight;
    return scrollableHeight > 0
        ? Math.min(1, Math.max(0, scrollTop / scrollableHeight))
        : 0;
};
