"use client";

import type { KeyboardEvent, TouchEvent, UIEvent } from "react";
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
import {
    COLLECTION_PREVIEW_FIXTURES,
    DRAFT_PREVIEW_FIXTURES,
} from "@/lib/unfinished/fixtures/savedItems";
import {
    DISCOUNT_CARD_FIXTURES,
    ORDER_STATUS_FIXTURES,
    PROFILE_FORM_FIXTURE,
    PROFILE_ORDER_FIXTURES,
} from "@/lib/unfinished/fixtures/profile";
import { isMockDataEnabled } from "@/lib/runtime/config";
import type { BottomPanelState, ProfilePanelTab, ProfileTab } from "@/lib/unfinished/types";
import {
    getCollapsedPanelOpenState,
    getGridItems,
    getPanelStepState,
    getScrollProgress,
    isExpandedOnlyProfileTab,
    isPersistedDraft,
} from "@/lib/unfinished/utils/unfinished";
import type { SavedProfileItem } from "@/lib/unfinished/utils/savedItems";
import {
    CONSTRUCTOR_DRAFTS_STORAGE_KEY,
    MY_COLLECTION_STORAGE_KEY,
    loadSavedProfileItems,
    removeSavedProfileItem,
} from "@/lib/unfinished/utils/savedItems";

type UseUnfinishedSurfaceOptions = {
    isOverlay: boolean;
    onClose?: () => void;
    initialTab: ProfileTab;
};

const EMPTY_SAVED_ITEMS: SavedProfileItem[] = [];

export const useUnfinishedSurface = ({ isOverlay, onClose, initialTab }: UseUnfinishedSurfaceOptions) => {
    const router = useRouter();
    const fixturesEnabled = isMockDataEnabled();
    const draftFixtures = fixturesEnabled ? DRAFT_PREVIEW_FIXTURES : EMPTY_SAVED_ITEMS;
    const collectionFixtures = fixturesEnabled ? COLLECTION_PREVIEW_FIXTURES : EMPTY_SAVED_ITEMS;
    const profileFixture = fixturesEnabled ? PROFILE_FORM_FIXTURE : null;
    const profileOrderFixtures = fixturesEnabled ? PROFILE_ORDER_FIXTURES : [];
    const orderStatusFixtures = fixturesEnabled ? ORDER_STATUS_FIXTURES : [];
    const discountCardFixtures = fixturesEnabled ? DISCOUNT_CARD_FIXTURES : [];
    const [activeTab, setActiveTab] = useState<ProfileTab>(initialTab);
    const [activeProfileTab, setActiveProfileTab] = useState<ProfilePanelTab>("settings");
    const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);
    const [isGenderOpen, setIsGenderOpen] = useState(false);
    const [isCodeRequested, setIsCodeRequested] = useState(false);
    const [isProfileSignedIn, setIsProfileSignedIn] = useState(false);
    const [loginEmail, setLoginEmail] = useState(profileFixture?.loginEmail ?? "");
    const [profileCode, setProfileCode] = useState(["", "", "", ""]);
    const [profileName, setProfileName] = useState(profileFixture?.name ?? "");
    const [profileGender, setProfileGender] = useState(profileFixture?.gender ?? "Не выбран");
    const [profilePhone, setProfilePhone] = useState(profileFixture?.phone ?? "");
    const [profileEmail, setProfileEmail] = useState(profileFixture?.email ?? "");
    const [scrollProgress, setScrollProgress] = useState(0);
    const [savedDrafts, setSavedDrafts] = useState<SavedProfileItem[]>([]);
    const [collectionItems, setCollectionItems] = useState<SavedProfileItem[]>([]);
    const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
    const [selectedCollectionId, setSelectedCollectionId] = useState<string | null>(null);
    const [bottomPanelState, setBottomPanelState] = useState<BottomPanelState>("collapsed");
    const [isTabContentVisible, setIsTabContentVisible] = useState(true);
    const [isClosing, setIsClosing] = useState(false);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    const tabTransitionTimerRef = useRef<number | null>(null);
    const tabFadeInFrameRef = useRef<number | null>(null);
    const closeTimerRef = useRef<number | null>(null);
    const collapsedPanelTouchStartRef = useRef<{ x: number; y: number } | null>(null);
    const panelStepTouchStartRef = useRef<{ x: number; y: number; state: BottomPanelState } | null>(null);
    const suppressPanelToggleClickRef = useRef(false);
    const suppressPanelToggleTimerRef = useRef<number | null>(null);
    const profileCodeInputRefs = useRef<Array<HTMLInputElement | null>>([]);

    const visibleCollectionItems = collectionItems.length > 0 ? collectionItems : collectionFixtures;
    const visibleDrafts = savedDrafts.length > 0 ? savedDrafts : draftFixtures;
    const gridItems = getGridItems(activeTab, visibleDrafts, visibleCollectionItems);
    const selectedDraft = visibleDrafts.find(draft => draft.id === selectedDraftId);
    const selectedCollectionItem = visibleCollectionItems.find(item => item.id === selectedCollectionId);
    const selectedItem = activeTab === "my-collection" ? selectedCollectionItem : activeTab === "unfinished" ? selectedDraft : undefined;
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

    useEffect(() => {
        const loadTimer = window.setTimeout(() => {
            const nextDrafts = loadSavedProfileItems(CONSTRUCTOR_DRAFTS_STORAGE_KEY);
            const nextCollectionItems = loadSavedProfileItems(MY_COLLECTION_STORAGE_KEY);
            setSavedDrafts(nextDrafts);
            setCollectionItems(nextCollectionItems);
            setSelectedDraftId(nextDrafts[0]?.id ?? draftFixtures[0]?.id ?? null);
            setSelectedCollectionId(nextCollectionItems[0]?.id ?? collectionFixtures[0]?.id ?? null);
            setBottomPanelState("collapsed");
        }, 0);
        return () => window.clearTimeout(loadTimer);
    }, [collectionFixtures, draftFixtures, initialTab]);

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
        if (activeTab !== "unfinished") return;
        if (!selectedDraft) {
            if (isClosing) return;
            setBottomPanelState("collapsed");
            setIsClosing(true);
            closeTimerRef.current = window.setTimeout(() => {
                closeTimerRef.current = null;
                window.location.replace("/?selectForConstructor=1");
            }, UNFINISHED_SHEET_EXIT_MS);
            return;
        }
        router.push(`/constructor?productId=${selectedDraft.productId}&draftId=${encodeURIComponent(selectedDraft.id)}`);
    };

    const handleDeleteSelectedItem = () => {
        if (selectedItem) setIsDeleteConfirmOpen(true);
    };

    const confirmDeleteSelectedItem = () => {
        setIsDeleteConfirmOpen(false);
        if (activeTab === "unfinished") {
            if (!selectedDraft || !isPersistedDraft(selectedDraft)) {
                setSelectedDraftId(null);
                setBottomPanelState("collapsed");
                return;
            }
            const nextDrafts = removeSavedProfileItem(CONSTRUCTOR_DRAFTS_STORAGE_KEY, selectedDraft.id);
            setSavedDrafts(nextDrafts);
            setSelectedDraftId(nextDrafts[0]?.id ?? null);
            setBottomPanelState(nextDrafts.length === 0 ? "collapsed" : "normal");
            return;
        }
        if (activeTab === "my-collection" && selectedCollectionItem) {
            const nextCollectionItems = removeSavedProfileItem(MY_COLLECTION_STORAGE_KEY, selectedCollectionItem.id);
            setCollectionItems(nextCollectionItems);
            setSelectedCollectionId(nextCollectionItems[0]?.id ?? null);
            setBottomPanelState("collapsed");
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

    const handleSelectGridItem = (item: SavedProfileItem) => {
        if (activeTab === "my-collection") {
            setSelectedCollectionId(item.id);
            return;
        }
        setSelectedDraftId(item.id);
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

    const handleProfileLoginAction = () => {
        if (!isCodeRequested) {
            setIsCodeRequested(true);
            window.requestAnimationFrame(() => profileCodeInputRefs.current[0]?.focus());
            return;
        }
        setIsProfileSignedIn(true);
    };

    const handleProfileCodeChange = (index: number, value: string) => {
        const nextValue = value.replace(/\D/g, "").slice(-1);
        setProfileCode(currentCode => currentCode.map((character, characterIndex) => characterIndex === index ? nextValue : character));
        if (nextValue && index < profileCodeInputRefs.current.length - 1) profileCodeInputRefs.current[index + 1]?.focus();
    };

    const handleProfileCodeKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
        if (event.key === "Backspace" && !profileCode[index] && index > 0) profileCodeInputRefs.current[index - 1]?.focus();
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
        activeTab, activeProfileTab, expandedOrderId,
        profileOrderFixtures, orderStatusFixtures, discountCardFixtures,
        isGenderOpen, setIsGenderOpen,
        isCodeRequested, isProfileSignedIn,
        loginEmail, setLoginEmail,
        profileCode, profileCodeInputRefs,
        profileName, setProfileName,
        profileGender, setProfileGender,
        profilePhone, setProfilePhone,
        profileEmail, setProfileEmail,
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
        handleProfileLoginAction, handleProfileCodeChange, handleProfileCodeKeyDown,
        handleCollapseOrder, handleToggleOrder,
    };
};

export type UnfinishedSurfaceViewModel = ReturnType<typeof useUnfinishedSurface>;
