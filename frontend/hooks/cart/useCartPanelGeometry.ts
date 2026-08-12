"use client";

import React from 'react';

import {
    CART_ACTION_BASE_VIEWPORT_WIDTH,
    CART_ACTION_EXPANDED_BASE_HEIGHT,
    CART_ACTION_EXPANDED_MAX_HEIGHT,
    CART_ACTION_EXPANDED_MIN_HEIGHT,
    CART_ACTION_EXPANDED_VIEWPORT_GAP,
    CART_ACTION_GUEST_AUTH_VIEWPORT_RESERVE,
    CART_ACTION_MAX_VIEWPORT_WIDTH,
    COLLAPSED_PRODUCT_MIN_HEIGHT,
} from '@/lib/cart/constants';

type CartPanelGeometryOptions = {
    collapsedHeight?: number;
    isExpanded: boolean;
    quantity?: number;
    displayColor?: string;
    displayPrice?: number;
    displayTitle?: string;
};

export const useCartPanelGeometry = ({
    collapsedHeight,
    isExpanded,
    quantity,
    displayColor,
    displayPrice,
    displayTitle,
}: CartPanelGeometryOptions) => {
    const productPanelRef = React.useRef<HTMLDivElement | null>(null);
    const [collapsedPanelHeight, setCollapsedPanelHeight] = React.useState(
        collapsedHeight ?? COLLAPSED_PRODUCT_MIN_HEIGHT,
    );
    const [expandedPanelHeight, setExpandedPanelHeight] = React.useState(CART_ACTION_EXPANDED_BASE_HEIGHT);

    React.useEffect(() => {
        const syncCartPanelGeometry = () => {
            const responsiveWidth = Math.min(
                CART_ACTION_MAX_VIEWPORT_WIDTH,
                Math.max(CART_ACTION_BASE_VIEWPORT_WIDTH, window.innerWidth),
            );
            const widthRatio = responsiveWidth / CART_ACTION_BASE_VIEWPORT_WIDTH;
            const widthScaledHeight = CART_ACTION_EXPANDED_BASE_HEIGHT * widthRatio;
            const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
            const headerRect = document.querySelector('header')?.getBoundingClientRect();
            const headerClearance = headerRect ? Math.max(0, headerRect.height, headerRect.bottom) : 0;
            const viewportLimitedHeight = Math.max(
                CART_ACTION_EXPANDED_MIN_HEIGHT,
                viewportHeight
                    - CART_ACTION_EXPANDED_VIEWPORT_GAP
                    - CART_ACTION_GUEST_AUTH_VIEWPORT_RESERVE
                    - headerClearance,
            );

            if (collapsedHeight !== undefined) {
                setCollapsedPanelHeight(collapsedHeight);
            } else {
                setCollapsedPanelHeight(Math.round(COLLAPSED_PRODUCT_MIN_HEIGHT * widthRatio));
            }
            setExpandedPanelHeight(Math.round(Math.min(
                widthScaledHeight,
                viewportLimitedHeight,
                CART_ACTION_EXPANDED_MAX_HEIGHT,
            )));
        };

        syncCartPanelGeometry();
        window.addEventListener('resize', syncCartPanelGeometry);
        window.visualViewport?.addEventListener('resize', syncCartPanelGeometry);

        return () => {
            window.removeEventListener('resize', syncCartPanelGeometry);
            window.visualViewport?.removeEventListener('resize', syncCartPanelGeometry);
        };
    }, [collapsedHeight]);

    React.useLayoutEffect(() => {
        if (collapsedHeight !== undefined) {
            setCollapsedPanelHeight(collapsedHeight);
            return;
        }

        if (isExpanded) return;

        const productPanel = productPanelRef.current;
        if (!productPanel) return;

        const collapsedLayer = productPanel.querySelector<HTMLElement>('.cart-action-bar-collapsed-layer');
        const collapsedContent = collapsedLayer?.firstElementChild as HTMLElement | null;
        if (!collapsedLayer || !collapsedContent) return;

        const measureCollapsedPanel = () => {
            const panelStyles = window.getComputedStyle(productPanel);
            const collapsedLayerStyles = window.getComputedStyle(collapsedLayer);
            const verticalPadding = Number.parseFloat(panelStyles.paddingTop) + Number.parseFloat(panelStyles.paddingBottom);
            const verticalBorder = Number.parseFloat(panelStyles.borderTopWidth) + Number.parseFloat(panelStyles.borderBottomWidth);
            const collapsedLayerVerticalPadding = Number.parseFloat(collapsedLayerStyles.paddingTop)
                + Number.parseFloat(collapsedLayerStyles.paddingBottom);
            const nextHeight = collapsedContent.getBoundingClientRect().height
                + collapsedLayerVerticalPadding
                + verticalPadding
                + verticalBorder;
            if (!nextHeight) return;

            setCollapsedPanelHeight(Math.max(COLLAPSED_PRODUCT_MIN_HEIGHT, Math.ceil(nextHeight)));
        };

        measureCollapsedPanel();
        const resizeObserver = new ResizeObserver(measureCollapsedPanel);
        resizeObserver.observe(collapsedContent);
        window.addEventListener('resize', measureCollapsedPanel);

        return () => {
            resizeObserver.disconnect();
            window.removeEventListener('resize', measureCollapsedPanel);
        };
    }, [collapsedHeight, displayColor, displayPrice, displayTitle, isExpanded, quantity]);

    return { productPanelRef, collapsedPanelHeight, expandedPanelHeight };
};
