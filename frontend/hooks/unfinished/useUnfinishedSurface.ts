"use client";

import type { TouchEvent, UIEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
    COLLAPSED_PANEL_SWIPE_UP_THRESHOLD_PX,
    ENABLE_UNFINISHED_PANEL_BACKGROUND_SWITCH,
    emptyStateCopy,
    PANEL_STEP_SWIPE_THRESHOLD_PX,
    PANEL_TOGGLE_CLICK_SUPPRESSION_MS,
    SECTION_BACKGROUND_IMAGES,
    TAB_FADE_OUT_MS,
    tabChromeColors,
    tabTitles,
    UNFINISHED_SHEET_EXIT_MS,
} from "@/lib/unfinished/config/ui";
import { useCustomerProjectLibrary } from './useCustomerProjectLibrary';
import type { ProjectSummary } from '@/lib/projects/types';
import type { BottomPanelState, ProfilePanelTab, ProfileTab } from "@/lib/unfinished/types";
import {
    getCollapsedPanelOpenState,
    getPanelStepState,
    getScrollProgress,
    isExpandedOnlyProfileTab,
} from "@/lib/unfinished/utils/unfinished";

type UseUnfinishedSurfaceOptions = {
    isOverlay: boolean;
    onClose?: () => void;
    initialTab: ProfileTab;
};

export const useUnfinishedSurface = ({ isOverlay, onClose, initialTab }: UseUnfinishedSurfaceOptions) => {
    const router = useRouter();
    const [activeTab, setActiveTab] = useState<ProfileTab>(initialTab);
    const projectLibrary = useCustomerProjectLibrary(activeTab === 'unfinished' ? 'draft' : activeTab === 'my-collection' ? 'collection' : null);
    const [activeProfileTab, setActiveProfileTab] = useState<ProfilePanelTab>("settings");
    const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
    const [scrollProgress, setScrollProgress] = useState(0);
    const [bottomPanelState, setBottomPanelState] = useState<BottomPanelState>("collapsed");
    const [isTabContentVisible, setIsTabContentVisible] = useState(true);
    const [isClosing, setIsClosing] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<{ key: string; id: number } | null>(null);
    const tabTransitionTimerRef = useRef<number | null>(null);
    const tabFadeInFrameRef = useRef<number | null>(null);
    const closeTimerRef = useRef<number | null>(null);
    const collapsedPanelTouchStartRef = useRef<{ x: number; y: number } | null>(null);
    const panelStepTouchStartRef = useRef<{ x: number; y: number; state: BottomPanelState } | null>(null);
    const suppressPanelToggleClickRef = useRef(false);
    const suppressPanelToggleTimerRef = useRef<number | null>(null);

    const gridItems = projectLibrary.items;
    const selectedDraft = activeTab === 'unfinished' ? projectLibrary.selected : undefined;
    const selectedCollectionItem = activeTab === 'my-collection' ? projectLibrary.selected : undefined;
    const selectedItem = activeTab === "my-collection" ? selectedCollectionItem : activeTab === "unfinished" ? selectedDraft : undefined;
    const isDeleteConfirmOpen = Boolean(deleteTarget && deleteTarget.key === projectLibrary.key && deleteTarget.id === selectedItem?.id);
    const setIsDeleteConfirmOpen = (open: boolean) => setDeleteTarget(open && selectedItem ? { key: projectLibrary.key, id: selectedItem.id } : null);
    const isUnfinishedTab = activeTab === "unfinished";
    const isCollectionTab = activeTab === "my-collection";
    const isProfileTab = activeTab === "profile";
    const isBottomBarCollapsed = bottomPanelState === "collapsed";
    const isBottomBarExpanded = bottomPanelState === "expanded";
    const isExpandedOnlyProfilePanel = isProfileTab && isExpandedOnlyProfileTab(activeProfileTab);
    const isExpandedOrderPanel = isProfileTab && activeProfileTab === "orders" && expandedOrderId !== null;
    const activeTitle = tabTitles[activeTab];
    const activeEmptyCopy = emptyStateCopy[activeTab];
    const unfinishedBackgroundLayers = ENABLE_UNFINISHED_PANEL_BACKGROUND_SWITCH ? [
        { id: "unfinished-collapsed", src: "/unfinished_content_bg.webp", active: isUnfinishedTab && isBottomBarCollapsed },
        { id: "unfinished-normal", src: "/unfinished_bg_2.webp", active: isUnfinishedTab && bottomPanelState === "normal" },
        { id: "unfinished-expanded", src: "/unfinished_bg_3.webp", active: isUnfinishedTab && isBottomBarExpanded },
    ] : [
        { id: "unfinished-static", src: "/landing_1.webp", active: isUnfinishedTab },
    ];
    const sectionBackgroundLayers = [
        ...unfinishedBackgroundLayers,
        { id: "my-collection", src: "/my_collection_bg.webp", active: isCollectionTab },
        { id: "profile", src: "/profile_bg.webp", active: isProfileTab },
    ];
    const pageLabel = activeTab === "unfinished" ? "Черновики конструктора" : activeTab === "profile" ? "Профиль" : "Моя коллекция";

    useEffect(() => () => {
        if (tabTransitionTimerRef.current !== null) window.clearTimeout(tabTransitionTimerRef.current);
        if (tabFadeInFrameRef.current !== null) window.cancelAnimationFrame(tabFadeInFrameRef.current);
        if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
        if (suppressPanelToggleTimerRef.current !== null) window.clearTimeout(suppressPanelToggleTimerRef.current);
    }, []);

    useEffect(() => {
        SECTION_BACKGROUND_IMAGES.forEach(src => {
            const image = new window.Image();
            image.src = src;
        });
    }, []);

    useEffect(() => {
        const html = document.documentElement;
        const body = document.body;
        const previousHtmlColor = html.style.getPropertyValue("--app-page-color");
        const previousBodyColor = body.style.getPropertyValue("--app-page-color");
        const chromeColor = tabChromeColors[activeTab];
        html.style.setProperty("--app-page-color", chromeColor);
        body.style.setProperty("--app-page-color", chromeColor);
        return () => {
            if (previousHtmlColor) html.style.setProperty("--app-page-color", previousHtmlColor);
            else html.style.removeProperty("--app-page-color");
            if (previousBodyColor) body.style.setProperty("--app-page-color", previousBodyColor);
            else body.style.removeProperty("--app-page-color");
        };
    }, [activeTab]);

    const handleScroll = (event: UIEvent<HTMLDivElement>) => {
        const { scrollTop, scrollHeight, clientHeight } = event.currentTarget;
        setScrollProgress(getScrollProgress(scrollTop, scrollHeight, clientHeight));
    };

    const handleContentAction = () => {
        if (activeTab === "profile") return;
        if (!selectedItem) {
            if (isClosing) return;
            setBottomPanelState("collapsed");
            setIsClosing(true);
            closeTimerRef.current = window.setTimeout(() => {
                closeTimerRef.current = null;
                window.location.replace("/catalog");
            }, UNFINISHED_SHEET_EXIT_MS);
            return;
        }
        router.push(`/constructor?projectId=${selectedItem.id}`);
    };

    const handleDeleteSelectedItem = () => {
        if (selectedItem) {
            projectLibrary.clearDeleteError();
            setIsDeleteConfirmOpen(true);
        }
    };

    const confirmDeleteSelectedItem = async () => {
        if (!isDeleteConfirmOpen) return;
        if (await projectLibrary.removeSelected()) {
            setIsDeleteConfirmOpen(false);
            setBottomPanelState("normal");
        }
    };

    const handleBack = () => {
        if (isClosing) return;
        setIsClosing(true);
        closeTimerRef.current = window.setTimeout(() => {
            closeTimerRef.current = null;
            if (isOverlay && onClose) onClose();
            else router.back();
        }, UNFINISHED_SHEET_EXIT_MS);
    };

    const handleToggleBottomPanel = () => {
        if (suppressPanelToggleClickRef.current) {
            suppressPanelToggleClickRef.current = false;
            if (suppressPanelToggleTimerRef.current !== null) {
                window.clearTimeout(suppressPanelToggleTimerRef.current);
                suppressPanelToggleTimerRef.current = null;
            }
            return;
        }
        if (isExpandedOrderPanel && isBottomBarExpanded) {
            setExpandedOrderId(null);
            setBottomPanelState("normal");
            return;
        }
        setBottomPanelState(currentState => {
            if (currentState === "collapsed") return getCollapsedPanelOpenState(isProfileTab, activeProfileTab);
            if (currentState === "expanded") return isExpandedOnlyProfilePanel ? "collapsed" : "normal";
            return "collapsed";
        });
    };

    const handleCollapsedPanelTouchStart = (event: TouchEvent<HTMLDivElement>) => {
        if (!isBottomBarCollapsed || event.touches.length !== 1) {
            collapsedPanelTouchStartRef.current = null;
            return;
        }
        const touch = event.touches[0];
        collapsedPanelTouchStartRef.current = { x: touch.clientX, y: touch.clientY };
    };

    const suppressNextPanelClick = () => {
        suppressPanelToggleClickRef.current = true;
        if (suppressPanelToggleTimerRef.current !== null) window.clearTimeout(suppressPanelToggleTimerRef.current);
        suppressPanelToggleTimerRef.current = window.setTimeout(() => {
            suppressPanelToggleClickRef.current = false;
            suppressPanelToggleTimerRef.current = null;
        }, PANEL_TOGGLE_CLICK_SUPPRESSION_MS);
    };

    const handleCollapsedPanelTouchEnd = (event: TouchEvent<HTMLDivElement>) => {
        const touchStart = collapsedPanelTouchStartRef.current;
        collapsedPanelTouchStartRef.current = null;
        if (!isBottomBarCollapsed || !touchStart || event.changedTouches.length !== 1) return;
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        if (deltaY > -COLLAPSED_PANEL_SWIPE_UP_THRESHOLD_PX || Math.abs(deltaY) <= Math.abs(deltaX)) return;
        event.preventDefault();
        setBottomPanelState(getCollapsedPanelOpenState(isProfileTab, activeProfileTab));
        suppressNextPanelClick();
    };

    const handleCollapsedPanelTouchCancel = () => {
        collapsedPanelTouchStartRef.current = null;
    };

    const handlePanelStepTouchStart = (event: TouchEvent<HTMLDivElement>) => {
        if (isBottomBarCollapsed || event.touches.length !== 1) {
            panelStepTouchStartRef.current = null;
            return;
        }
        const touch = event.touches[0];
        panelStepTouchStartRef.current = { x: touch.clientX, y: touch.clientY, state: bottomPanelState };
    };

    const handlePanelStepTouchEnd = (event: TouchEvent<HTMLDivElement>) => {
        const touchStart = panelStepTouchStartRef.current;
        panelStepTouchStartRef.current = null;
        if (!touchStart || event.changedTouches.length !== 1) return;
        const touch = event.changedTouches[0];
        const deltaX = touch.clientX - touchStart.x;
        const deltaY = touch.clientY - touchStart.y;
        if (Math.abs(deltaY) <= Math.abs(deltaX) || Math.abs(deltaY) < PANEL_STEP_SWIPE_THRESHOLD_PX) return;
        const nextState = getPanelStepState(touchStart.state, deltaY);
        event.preventDefault();
        if (touchStart.state === "expanded" && nextState === "normal" && isExpandedOrderPanel) setExpandedOrderId(null);
        setBottomPanelState(nextState);
        suppressNextPanelClick();
    };

    const handlePanelStepTouchCancel = () => {
        panelStepTouchStartRef.current = null;
    };

    const handleSelectGridItem = (item: ProjectSummary) => {
        projectLibrary.select(item.id);
        if (activeTab === "my-collection") return;
        setBottomPanelState("normal");
    };

    const handleSelectTab = (item: { id: ProfileTab }) => {
        if (tabTransitionTimerRef.current !== null) window.clearTimeout(tabTransitionTimerRef.current);
        if (tabFadeInFrameRef.current !== null) window.cancelAnimationFrame(tabFadeInFrameRef.current);
        if (item.id === activeTab) {
            setIsTabContentVisible(true);
            return;
        }
        const nextBottomPanelState: BottomPanelState = "collapsed";
        setIsTabContentVisible(false);
        tabTransitionTimerRef.current = window.setTimeout(() => {
            setActiveTab(item.id);
            setScrollProgress(0);
            setExpandedOrderId(null);
            setBottomPanelState(nextBottomPanelState);
            tabTransitionTimerRef.current = null;
            tabFadeInFrameRef.current = window.requestAnimationFrame(() => {
                tabFadeInFrameRef.current = window.requestAnimationFrame(() => {
                    setIsTabContentVisible(true);
                    tabFadeInFrameRef.current = null;
                });
            });
        }, TAB_FADE_OUT_MS);
    };

    const handleSelectProfileTab = (nextProfileTab: ProfilePanelTab) => {
        setActiveProfileTab(nextProfileTab);
        setExpandedOrderId(null);
        setBottomPanelState(isExpandedOnlyProfileTab(nextProfileTab) ? "expanded" : "normal");
    };

    const handleCollapseOrder = () => {
        setExpandedOrderId(null);
        setBottomPanelState("normal");
    };

    const handleToggleOrder = (orderId: string) => {
        const shouldCollapseOrder = expandedOrderId === orderId;
        setExpandedOrderId(shouldCollapseOrder ? null : orderId);
        setBottomPanelState(shouldCollapseOrder ? "normal" : "expanded");
    };

    return {
        activeTab, activeProfileTab, expandedOrderId, projectLibrary,
        scrollProgress, gridItems,
        selectedDraft, selectedCollectionItem, selectedItem,
        bottomPanelState, setBottomPanelState,
        isTabContentVisible, isClosing,
        isDeleteConfirmOpen, setIsDeleteConfirmOpen,
        isUnfinishedTab, isCollectionTab, isProfileTab,
        isBottomBarCollapsed, isBottomBarExpanded, isExpandedOnlyProfilePanel,
        activeTitle, activeEmptyCopy, sectionBackgroundLayers, pageLabel,
        handleScroll, handleContentAction, handleDeleteSelectedItem, confirmDeleteSelectedItem,
        handleBack, handleToggleBottomPanel,
        handleCollapsedPanelTouchStart, handleCollapsedPanelTouchEnd, handleCollapsedPanelTouchCancel,
        handlePanelStepTouchStart, handlePanelStepTouchEnd, handlePanelStepTouchCancel,
        handleSelectGridItem, handleSelectTab, handleSelectProfileTab,
        handleCollapseOrder, handleToggleOrder,
    };
};

export type UnfinishedSurfaceViewModel = ReturnType<typeof useUnfinishedSurface>;
