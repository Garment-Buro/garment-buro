import type { BottomPanelState, ProfilePanelTab, ProfileTab } from "../types.ts";
import type { SavedProfileItem } from "./savedItems.ts";

export const isExpandedOnlyProfileTab = (tab: ProfilePanelTab) => tab === "support" || tab === "settings";

export const getGridItems = (
    activeTab: ProfileTab,
    savedDrafts: SavedProfileItem[],
    collectionItems: SavedProfileItem[],
) => {
    if (activeTab === "my-collection") return collectionItems;
    if (activeTab === "profile") return [];
    return savedDrafts;
};

export const isPersistedDraft = (item: SavedProfileItem | undefined) => Boolean(item && item.savedAt > 0);

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
