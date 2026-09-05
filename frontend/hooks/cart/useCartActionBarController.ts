"use client";

import React from 'react';
import { usePathname } from 'next/navigation';
import type { CartItem } from '@/lib/cart/types';
import type { CartActionBarProps } from '@/lib/cart/actionTypes';
import { useCartActionCheckout } from '@/hooks/cart/useCartActionCheckout';
import { useCartActionVisibility } from '@/hooks/cart/useCartActionVisibility';
import { useCartPanelGeometry } from '@/hooks/cart/useCartPanelGeometry';
import {
    DRAG_SNAP_MIN_DISTANCE,
    DRAG_SNAP_PROGRESS,
    DRAG_START_THRESHOLD,
    DRAG_TAP_SLOP,
    HANDLE_CLICK_GUARD_MS,
    TOP_OVERSCROLL_COLLAPSE_THRESHOLD,
    WHEEL_GESTURE_RESET_MS,
} from '@/lib/cart/constants';
import { getCartPanelPresentation, getPreferredCartItem } from '@/lib/cart/utils/cartAction';
import { useCartStore } from '@/store/cartStore';
import { useAuthStore } from '@/store/authStore';

export const useCartActionBarController = ({
    visible,
    title,
    color,
    price,
    image,
    cartItemId,
    usePreferredCartItemOnly = false,
    showAddProductCard = false,
    collapsedVariant = 'glass-compact',
    allowEmptyExpand = false,
    liquidV2Shifted = false,
    disabled = false,
    onAdd,
    onEdit,
    onBuy,
}: CartActionBarProps) => {
    const pathname = usePathname();
    const { items, activeItemId, isCartOpen, setIsCartOpen, updateQuantity } = useCartStore();
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
    const authUser = useAuthStore((state) => state.user);
    const {
        totalQuantity,
        productsTotal,
        deliveryPrice,
        discount,
        grandTotal,
        deliveryMethod,
        setDeliveryMethod,
        paymentMethod,
        setPaymentMethod,
        isPaymentSubmitting,
        checkoutError,
        retryQuote,
        quoteLoading,
        deliveryQuoted,
        isCouponOpen,
        setIsCouponOpen,
        pendingCoupon,
        setPendingCoupon,
        appliedCoupon,
        setAppliedCoupon,
        isOfferAccepted,
        setIsOfferAccepted,
        isPolicyAccepted,
        setIsPolicyAccepted,
        isAuthPopupOpen,
        setIsAuthPopupOpen,
        resetCheckout,
        startPayment: handleExpandedPayment,
    } = useCartActionCheckout({ items, isAuthenticated, user: authUser });
    const [isExpanded, setIsExpanded] = React.useState(false);
    const [selectedDetailsItem, setSelectedDetailsItem] = React.useState<CartItem | null>(null);
    const agreementIdPrefix = React.useId().replaceAll(':', '');

    // Drag state for handle
    const expandedContentRef = React.useRef<HTMLDivElement | null>(null);
    const handleZoneRef = React.useRef<HTMLButtonElement | null>(null);
    const dragStartY = React.useRef<number | null>(null);
    const dragStartExpanded = React.useRef(false);
    const [dragStartedExpanded, setDragStartedExpanded] = React.useState(false);
    const [dragOffset, setDragOffset] = React.useState(0);
    const [isPanelDragActive, setIsPanelDragActive] = React.useState(false);
    const pendingDragOffset = React.useRef(0);
    const dragUpdateFrameRef = React.useRef<number | null>(null);
    const isDragging = React.useRef(false);
    const handledPointerGesture = React.useRef(false);
    const handleClickGuardTimer = React.useRef<number | null>(null);
    const previousPathname = React.useRef(pathname);
    const expandedWheelDistance = React.useRef(0);
    const expandedWheelResetTimer = React.useRef<number | null>(null);
    const expandedTouchStartY = React.useRef<number | null>(null);
    const expandedTouchStartedAtTop = React.useRef(false);
    const expandedTouchDragging = React.useRef(false);
    const expandedTouchMoveHandler = React.useRef<(event: TouchEvent) => void>(() => undefined);

    const currentCartItem = React.useMemo(
        () => getPreferredCartItem(items, activeItemId, cartItemId, usePreferredCartItemOnly),
        [activeItemId, cartItemId, items, usePreferredCartItemOnly],
    );

    const displayTitle = currentCartItem?.title || title;
    const displayColor = currentCartItem?.color || color;
    const displayPrice = currentCartItem?.price || price;
    const displayImage = currentCartItem?.image || image || '/landing-bg.webp';
    const shouldShowCartAction = visible || isExpanded || (isCartOpen && items.length > 0);
    const {
        isRendered,
        setIsRendered,
        isVisibleFrame,
        setIsVisibleFrame,
        isAuthHydrated,
    } = useCartActionVisibility({ visible, isExpanded, shouldShowCartAction, setIsExpanded });
    const { productPanelRef, collapsedPanelHeight, expandedPanelHeight } = useCartPanelGeometry({
        collapsedHeight: collapsedVariant === 'liquid-v2' ? 45 : undefined,
        isExpanded,
        quantity: currentCartItem?.quantity,
        displayColor,
        displayPrice,
        displayTitle,
    });
    const {
        panelDragHeight,
        expansionProgress,
        contentSwapProgress,
        collapsedContentProgress,
        expandedContentProgress,
        expandedSurfaceRevealProgress,
        footerRevealProgress,
        guestAuthRevealProgress,
        overlayRevealProgress,
        isPanelExpandedPresentation,
        isCompactCollapsedPresentation,
    } = getCartPanelPresentation({
        collapsedPanelHeight,
        expandedPanelHeight,
        dragOffset,
        dragStartedExpanded,
        isExpanded,
        collapsedVariant,
    });

    React.useEffect(() => {
        if (isCartOpen && (items.length > 0 || allowEmptyExpand)) {
            setIsExpanded(true);
            return;
        }

        setIsExpanded(false);
    }, [allowEmptyExpand, isCartOpen, items.length]);

    React.useEffect(() => {
        if (previousPathname.current === pathname) return;

        previousPathname.current = pathname;
        setIsCartOpen(false);
        setIsExpanded(false);
        setDragStartedExpanded(false);
        setDragOffset(0);
        setIsPanelDragActive(false);
        resetCheckout();
        setSelectedDetailsItem(null);
        setIsRendered(visible);
        setIsVisibleFrame(false);

        dragStartY.current = null;
        dragStartExpanded.current = false;
        isDragging.current = false;
        handledPointerGesture.current = false;
        expandedWheelDistance.current = 0;
        expandedTouchStartY.current = null;
        expandedTouchStartedAtTop.current = false;
        expandedTouchDragging.current = false;

        if (dragUpdateFrameRef.current !== null) {
            window.cancelAnimationFrame(dragUpdateFrameRef.current);
            dragUpdateFrameRef.current = null;
        }
        pendingDragOffset.current = 0;

        if (handleClickGuardTimer.current !== null) {
            window.clearTimeout(handleClickGuardTimer.current);
            handleClickGuardTimer.current = null;
        }

        if (expandedWheelResetTimer.current !== null) {
            window.clearTimeout(expandedWheelResetTimer.current);
            expandedWheelResetTimer.current = null;
        }

        if (expandedContentRef.current) {
            expandedContentRef.current.scrollTop = 0;
        }

        if (!visible) return;

        const frameId = window.requestAnimationFrame(() => setIsVisibleFrame(true));
        return () => window.cancelAnimationFrame(frameId);
    }, [pathname, resetCheckout, setIsCartOpen, setIsRendered, setIsVisibleFrame, visible]);

    React.useEffect(() => () => {
        setIsCartOpen(false);

        if (handleClickGuardTimer.current !== null) {
            window.clearTimeout(handleClickGuardTimer.current);
        }

        if (expandedWheelResetTimer.current !== null) {
            window.clearTimeout(expandedWheelResetTimer.current);
        }

        if (dragUpdateFrameRef.current !== null) {
            window.cancelAnimationFrame(dragUpdateFrameRef.current);
        }
    }, [setIsCartOpen]);

    // ─── Native-feeling panel drag ───────────────────────────────────────────
    const scheduleDragOffset = (nextOffset: number) => {
        pendingDragOffset.current = nextOffset;
        if (dragUpdateFrameRef.current !== null) return;

        dragUpdateFrameRef.current = window.requestAnimationFrame(() => {
            dragUpdateFrameRef.current = null;
            setDragOffset(pendingDragOffset.current);
        });
    };

    const resetDragOffset = () => {
        if (dragUpdateFrameRef.current !== null) {
            window.cancelAnimationFrame(dragUpdateFrameRef.current);
            dragUpdateFrameRef.current = null;
        }

        pendingDragOffset.current = 0;
        setDragOffset(0);
    };

    const beginHandleDrag = (clientY: number) => {
        if (dragStartY.current != null) return;

        dragStartY.current = clientY;
        setIsPanelDragActive(true);
        dragStartExpanded.current = isExpanded;
        setDragStartedExpanded(isExpanded);
        isDragging.current = false;
        resetDragOffset();
    };

    const moveHandleDrag = (clientY: number, captureDrag?: () => void) => {
        if (dragStartY.current == null) return;

        const deltaY = clientY - dragStartY.current;

        if (!isDragging.current && Math.abs(deltaY) < DRAG_START_THRESHOLD) return;
        if (!isDragging.current) {
            isDragging.current = true;
            captureDrag?.();
        }

        if (dragStartExpanded.current) {
            const maxCollapseOffset = Math.max(0, expandedPanelHeight - collapsedPanelHeight);
            const clampedOffset = Math.min(maxCollapseOffset, Math.max(0, deltaY));
            scheduleDragOffset(clampedOffset);
        } else {
            // Dragging up to expand — negative deltaY means expanding
            const maxExpandOffset = Math.max(0, expandedPanelHeight - collapsedPanelHeight);
            const clampedOffset = Math.max(-maxExpandOffset, Math.min(0, deltaY));
            scheduleDragOffset(clampedOffset);
        }
    };

    const getDragSnapDistance = () => Math.max(
        DRAG_SNAP_MIN_DISTANCE,
        (expandedPanelHeight - collapsedPanelHeight) * DRAG_SNAP_PROGRESS,
    );

    const finishHandleDrag = (clientY: number) => {
        if (dragStartY.current == null) return;

        const deltaY = clientY - dragStartY.current;

        if (handledPointerGesture.current && !isDragging.current) {
            dragStartY.current = null;
            setIsPanelDragActive(false);
            resetDragOffset();
            return;
        }

        if (!isDragging.current) {
            dragStartY.current = null;
            setIsPanelDragActive(false);
            isDragging.current = false;
            resetDragOffset();

            if (Math.abs(deltaY) > DRAG_TAP_SLOP) {
                suppressNextHandleClick();
            }
            return;
        }

        const snapDistance = getDragSnapDistance();

        if (dragStartExpanded.current) {
            if (deltaY >= snapDistance) {
                setExpandedFromHandle(false);
            }
        } else {
            if (deltaY <= -snapDistance) {
                setExpandedFromHandle(true);
            }
        }

        dragStartY.current = null;
        setIsPanelDragActive(false);
        isDragging.current = false;
        resetDragOffset();
        suppressNextHandleClick();
    };

    const cancelHandleDrag = () => {
        dragStartY.current = null;
        setIsPanelDragActive(false);
        isDragging.current = false;
        resetDragOffset();
    };

    const handleHandlePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
        const handleZone = event.currentTarget;
        beginHandleDrag(event.clientY);
        if (!handleZone.hasPointerCapture(event.pointerId)) {
            handleZone.setPointerCapture(event.pointerId);
        }
    };

    const handleHandlePointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
        moveHandleDrag(event.clientY);
    };

    const releaseHandlePointerCapture = (event: React.PointerEvent<HTMLButtonElement>) => {
        const handleZone = event.currentTarget;
        if (!handleZone.hasPointerCapture(event.pointerId)) return;

        handleZone.releasePointerCapture(event.pointerId);
    };

    const suppressNextHandleClick = () => {
        handledPointerGesture.current = true;

        if (handleClickGuardTimer.current !== null) {
            window.clearTimeout(handleClickGuardTimer.current);
        }

        handleClickGuardTimer.current = window.setTimeout(() => {
            handledPointerGesture.current = false;
            handleClickGuardTimer.current = null;
        }, HANDLE_CLICK_GUARD_MS);
    };

    const setExpandedFromHandle = (nextExpanded: boolean) => {
        dragStartY.current = null;
        setIsPanelDragActive(false);
        dragStartExpanded.current = nextExpanded;
        isDragging.current = false;
        setDragStartedExpanded(nextExpanded);
        resetDragOffset();
        setIsExpanded(nextExpanded);
        setIsCartOpen(nextExpanded);
    };

    const resetExpandedScrollGesture = () => {
        expandedWheelDistance.current = 0;
        expandedTouchStartY.current = null;
        expandedTouchStartedAtTop.current = false;
        expandedTouchDragging.current = false;
        setIsPanelDragActive(false);
        isDragging.current = false;
        resetDragOffset();

        if (expandedWheelResetTimer.current !== null) {
            window.clearTimeout(expandedWheelResetTimer.current);
            expandedWheelResetTimer.current = null;
        }
    };

    const handleExpandedContentWheel = (event: React.WheelEvent<HTMLDivElement>) => {
        if (!isExpanded || event.currentTarget.scrollTop > 0 || event.deltaY >= 0) {
            resetExpandedScrollGesture();
            return;
        }

        expandedWheelDistance.current += Math.abs(event.deltaY);
        setDragStartedExpanded(true);
        scheduleDragOffset(Math.min(
            expandedWheelDistance.current,
            Math.max(0, expandedPanelHeight - collapsedPanelHeight),
        ));

        if (expandedWheelResetTimer.current !== null) {
            window.clearTimeout(expandedWheelResetTimer.current);
        }

        expandedWheelResetTimer.current = window.setTimeout(() => {
            if (expandedWheelDistance.current >= TOP_OVERSCROLL_COLLAPSE_THRESHOLD) {
                setExpandedFromHandle(false);
            }
            expandedWheelDistance.current = 0;
            resetDragOffset();
            expandedWheelResetTimer.current = null;
        }, WHEEL_GESTURE_RESET_MS);
    };

    const handleExpandedContentTouchStart = (event: React.TouchEvent<HTMLDivElement>) => {
        const touch = event.touches[0];
        const startedAtTop = event.currentTarget.scrollTop <= 0;

        expandedTouchStartY.current = touch && startedAtTop ? touch.clientY : null;
        expandedTouchStartedAtTop.current = startedAtTop;
        expandedTouchDragging.current = false;
    };

    const handleExpandedContentTouchMove = (event: TouchEvent) => {
        const touch = event.touches[0];
        const startY = expandedTouchStartY.current;
        const expandedContent = expandedContentRef.current;

        if (!touch || !expandedContent || startY === null || !expandedTouchStartedAtTop.current) return;
        if (expandedContent.scrollTop > 0) {
            resetExpandedScrollGesture();
            return;
        }

        const pullPastTopDistance = touch.clientY - startY;
        if (pullPastTopDistance < DRAG_START_THRESHOLD) return;

        event.preventDefault();
        expandedTouchDragging.current = true;
        setIsPanelDragActive(true);
        isDragging.current = true;
        setDragStartedExpanded(true);
        scheduleDragOffset(Math.min(
            pullPastTopDistance,
            Math.max(0, expandedPanelHeight - collapsedPanelHeight),
        ));
    };
    React.useEffect(() => {
        expandedTouchMoveHandler.current = handleExpandedContentTouchMove;
    });

    React.useEffect(() => {
        const expandedContent = expandedContentRef.current;
        if (!isExpanded || !expandedContent) return;
        const handleTouchMove = (event: TouchEvent) => expandedTouchMoveHandler.current(event);

        expandedContent.addEventListener('touchmove', handleTouchMove, { passive: false });

        return () => {
            expandedContent.removeEventListener('touchmove', handleTouchMove);
        };
    }, [isExpanded]);

    const handleExpandedContentTouchEnd = (event: React.TouchEvent<HTMLDivElement>) => {
        const touch = event.changedTouches[0];
        const startY = expandedTouchStartY.current;
        const pullPastTopDistance = touch && startY !== null ? touch.clientY - startY : 0;

        if (expandedTouchDragging.current && pullPastTopDistance >= getDragSnapDistance()) {
            setExpandedFromHandle(false);
            suppressNextHandleClick();
        }

        resetExpandedScrollGesture();
    };

    const handleHandlePointerUp = (event: React.PointerEvent<HTMLButtonElement>) => {
        releaseHandlePointerCapture(event);
        finishHandleDrag(event.clientY);
    };

    const handleHandlePointerCancel = (event: React.PointerEvent<HTMLButtonElement>) => {
        releaseHandlePointerCapture(event);
        cancelHandleDrag();
    };

    const handleHandleClick = () => {
        if (handledPointerGesture.current) return;

        setExpandedFromHandle(isExpanded ? false : true);
    };

    const openCollapsedPanelTarget = (target: EventTarget | null) => {
        if (isExpanded) return;
        const element = target as HTMLElement | null;

        if (element?.closest('.cart-action-bar-product-summary')) {
            setExpandedFromHandle(true);
            return;
        }

        if (element?.closest('button, a, input, select, textarea, [role="button"]')) return;

        setExpandedFromHandle(true);
    };

    const handleCollapsedPanelClick = (event: React.MouseEvent<HTMLDivElement>) => {
        if (isPanelExpandedPresentation) return;

        openCollapsedPanelTarget(event.target);
    };

    const handleCollapsedPanelClickCapture = (event: React.MouseEvent<HTMLDivElement>) => {
        if (!handledPointerGesture.current) return;
        event.stopPropagation();
    };

    const handleCollapsedPanelPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
        if (isExpanded || dragStartY.current !== null || event.button !== 0) return;
        const element = event.target as HTMLElement | null;
        if (element?.closest('button, a, input, select, textarea, [role="button"]')) return;

        beginHandleDrag(event.clientY);
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.setPointerCapture(event.pointerId);
        }
    };

    const handleCollapsedPanelPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
        moveHandleDrag(event.clientY);
    };

    const handleCollapsedPanelPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
        }
        finishHandleDrag(event.clientY);
    };

    const handleCollapsedPanelPointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
        }
        cancelHandleDrag();
    };

    const isCartActionVisible = shouldShowCartAction && isVisibleFrame;

    React.useEffect(() => {
        if (!selectedDetailsItem) return;

        const nextDetailsItem = items.find(item => item.id === selectedDetailsItem.id);
        if (!nextDetailsItem) {
            setSelectedDetailsItem(null);
            return;
        }

        if (nextDetailsItem !== selectedDetailsItem) {
            setSelectedDetailsItem(nextDetailsItem);
        }
    }, [items, selectedDetailsItem]);

    return {
        showAddProductCard,
        collapsedVariant,
        liquidV2Shifted,
        disabled,
        onAdd,
        onEdit,
        onBuy,
        pathname,
        items,
        updateQuantity,
        isAuthenticated,
        totalQuantity,
        productsTotal,
        deliveryPrice,
        discount,
        grandTotal,
        deliveryMethod,
        setDeliveryMethod,
        paymentMethod,
        setPaymentMethod,
        isPaymentSubmitting,
        checkoutError,
        retryQuote,
        quoteLoading,
        deliveryQuoted,
        isCouponOpen,
        setIsCouponOpen,
        pendingCoupon,
        setPendingCoupon,
        appliedCoupon,
        setAppliedCoupon,
        isOfferAccepted,
        setIsOfferAccepted,
        isPolicyAccepted,
        setIsPolicyAccepted,
        isAuthPopupOpen,
        setIsAuthPopupOpen,
        handleExpandedPayment,
        isExpanded,
        isRendered,
        isAuthHydrated,
        agreementIdPrefix,
        collapsedPanelHeight,
        expandedPanelHeight,
        selectedDetailsItem,
        setSelectedDetailsItem,
        productPanelRef,
        expandedContentRef,
        handleZoneRef,
        isPanelDragActive,
        currentCartItem,
        displayTitle,
        displayColor,
        displayPrice,
        displayImage,
        shouldShowCartAction,
        panelDragHeight,
        expansionProgress,
        contentSwapProgress,
        collapsedContentProgress,
        expandedContentProgress,
        expandedSurfaceRevealProgress,
        footerRevealProgress,
        guestAuthRevealProgress,
        overlayRevealProgress,
        isPanelExpandedPresentation,
        isCompactCollapsedPresentation,
        setExpandedFromHandle,
        handleExpandedContentWheel,
        handleExpandedContentTouchStart,
        handleExpandedContentTouchEnd,
        handleHandlePointerDown,
        handleHandlePointerMove,
        handleHandlePointerUp,
        handleHandlePointerCancel,
        handleHandleClick,
        handleCollapsedPanelClick,
        handleCollapsedPanelClickCapture,
        handleCollapsedPanelPointerDown,
        handleCollapsedPanelPointerMove,
        handleCollapsedPanelPointerUp,
        handleCollapsedPanelPointerCancel,
        isCartActionVisible,
    };
};
