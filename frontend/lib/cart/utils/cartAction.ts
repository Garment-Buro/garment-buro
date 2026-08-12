import {
    CART_ACTION_CONTENT_REVEAL_RANGE,
    CART_ACTION_CONTENT_REVEAL_START,
    CART_ACTION_COUPON_DISCOUNT,
    CART_ACTION_COURIER_DELIVERY_PRICE,
    CART_ACTION_SURFACE_REVEAL_RANGE,
    CART_ACTION_SURFACE_REVEAL_START,
} from '../constants.ts';
import type {
    CartActionCoupon,
    CartCollapsedVariant,
    CartDeliveryMethod,
    CartPanelPresentation,
} from '../actionTypes.ts';
import type { CartItem } from '../types.ts';

export const formatCartPrice = (value: number) => `${value.toLocaleString('ru-RU')} ₽`;

export const getCartActionTotals = (
    items: CartItem[],
    deliveryMethod: CartDeliveryMethod,
    appliedCoupon: CartActionCoupon | null,
) => {
    const totalQuantity = items.reduce((sum, item) => sum + item.quantity, 0);
    const productsTotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
    const deliveryPrice = deliveryMethod === 'courier' ? CART_ACTION_COURIER_DELIVERY_PRICE : 0;
    const discount = appliedCoupon && items.length > 0 ? CART_ACTION_COUPON_DISCOUNT : 0;
    const grandTotal = Math.max(0, productsTotal + deliveryPrice - discount);
    return { totalQuantity, productsTotal, deliveryPrice, discount, grandTotal };
};

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
    collapsedVariant,
}: {
    collapsedPanelHeight: number;
    expandedPanelHeight: number;
    dragOffset: number;
    dragStartedExpanded: boolean;
    isExpanded: boolean;
    collapsedVariant: CartCollapsedVariant;
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
        expandedSurfaceRevealProgress: collapsedVariant === 'legacy'
            ? 1
            : Math.max(0, Math.min(
                1,
                (expansionProgress - CART_ACTION_SURFACE_REVEAL_START) / CART_ACTION_SURFACE_REVEAL_RANGE,
            )),
        footerRevealProgress: collapsedVariant === 'legacy'
            ? 1
            : Math.max(0, Math.min(1, (expansionProgress - 0.28) / 0.42)),
        guestAuthRevealProgress: Math.max(0, Math.min(1, (expansionProgress - 0.42) / 0.58)),
        overlayRevealProgress: Math.max(0, Math.min(1, expansionProgress / 0.7)),
        isPanelExpandedPresentation: expansionProgress > 0.001,
        isCompactCollapsedPresentation: (
            collapsedVariant === 'glass-compact' && expansionProgress <= 0.001
        ) || (
            collapsedVariant === 'liquid-v2' && expansionProgress <= 0.001
        ),
    };
};
