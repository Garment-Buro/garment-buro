import {
    CART_ACTION_CONTENT_REVEAL_RANGE,
    CART_ACTION_CONTENT_REVEAL_START,
    CART_ACTION_SURFACE_REVEAL_RANGE,
    CART_ACTION_SURFACE_REVEAL_START,
} from '../constants.ts';
import type {
    CartPanelPresentation,
} from '../actionTypes.ts';
import type { CartItem } from '../types.ts';

export const formatCartPrice = (value: number) => `${value.toLocaleString('ru-RU')} ₽`;

export const getPreferredCartItem = (
    items: CartItem[],
    activeItemId: string | null,
    cartItemId: string | undefined,
    usePreferredCartItemOnly: boolean,
) => {
    const preferredItem = cartItemId ? items.find(item => item.id === cartItemId) : undefined;
    if (usePreferredCartItemOnly) return preferredItem;
    const activeItem = activeItemId ? items.find(item => item.id === activeItemId) : undefined;
    return preferredItem || activeItem || items[items.length - 1];
};

export const getCartItemDetailsRows = (item: CartItem) => {
    const rows = new Map<string, number>();
    item.customization?.decorations.forEach(decoration => {
        rows.set(decoration.name, (rows.get(decoration.name) || 0) + 1);
    });
    if (rows.size === 0 && item.customization?.fit) {
        const fit = item.customization.fit;
        rows.set(`Посадка: ${fit.lengthCm}x${fit.widthCm}`, 1);
    }
    return Array.from(rows.entries()).map(([name, count]) => ({ name, count }));
};

export const getCartItemDetailsImage = (item: CartItem, view: 'front' | 'back') => (
    view === 'front'
        ? item.customization?.modelImages.front || item.image || '/landing-bg.webp'
        : item.customization?.modelImages.back || item.image || '/landing-bg.webp'
);

export const getCartPanelPresentation = ({
    collapsedPanelHeight,
    expandedPanelHeight,
    dragOffset,
    dragStartedExpanded,
    isExpanded,
}: {
    collapsedPanelHeight: number;
    expandedPanelHeight: number;
    dragOffset: number;
    dragStartedExpanded: boolean;
    isExpanded: boolean;
}): CartPanelPresentation => {
    const panelDragHeight = dragOffset === 0
        ? undefined
        : dragStartedExpanded
            ? `${Math.max(collapsedPanelHeight, expandedPanelHeight - dragOffset)}px`
            : `${Math.min(expandedPanelHeight, collapsedPanelHeight + Math.abs(dragOffset))}px`;
    const expansionRange = Math.max(1, expandedPanelHeight - collapsedPanelHeight);
    const expansionProgress = Math.max(0, Math.min(1,
        dragOffset !== 0
            ? dragStartedExpanded
                ? 1 - (dragOffset / expansionRange)
                : Math.abs(dragOffset) / expansionRange
            : isExpanded ? 1 : 0,
    ));
    const contentSwapProgress = Math.max(0, Math.min(
        1,
        (expansionProgress - CART_ACTION_CONTENT_REVEAL_START) / CART_ACTION_CONTENT_REVEAL_RANGE,
    ));
    return {
        panelDragHeight,
        expansionProgress,
        contentSwapProgress,
        collapsedContentProgress: 1 - contentSwapProgress,
        expandedContentProgress: contentSwapProgress,
        expandedSurfaceRevealProgress: Math.max(0, Math.min(
            1,
            (expansionProgress - CART_ACTION_SURFACE_REVEAL_START) / CART_ACTION_SURFACE_REVEAL_RANGE,
        )),
        footerRevealProgress: Math.max(0, Math.min(1, (expansionProgress - 0.28) / 0.42)),
        guestAuthRevealProgress: Math.max(0, Math.min(1, (expansionProgress - 0.42) / 0.58)),
        overlayRevealProgress: Math.max(0, Math.min(1, expansionProgress / 0.7)),
        isPanelExpandedPresentation: expansionProgress > 0.001,
        isCompactCollapsedPresentation: expansionProgress <= 0.001,
    };
};
