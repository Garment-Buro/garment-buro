import type { CartItem } from './types';

export type CartDeliveryMethod = 'pickup' | 'courier';
export type CartPaymentMethod = 'qr' | 'card';
export type CartCollapsedVariant = 'glass-compact' | 'liquid-v2';

export interface CartActionBarProps {
    visible: boolean;
    title: string;
    color: string;
    price: number;
    cartItemId?: string;
    usePreferredCartItemOnly?: boolean;
    collapsedVariant?: CartCollapsedVariant;
    allowEmptyExpand?: boolean;
    liquidV2Shifted?: boolean;
    disabled?: boolean;
    onLogin?: () => void;
    onAdd: () => void;
    onEdit: () => void;
    onBuy: () => void;
}

export interface CartPanelPresentation {
    panelDragHeight?: string;
    expansionProgress: number;
    contentSwapProgress: number;
    collapsedContentProgress: number;
    expandedContentProgress: number;
    expandedSurfaceRevealProgress: number;
    footerRevealProgress: number;
    guestAuthRevealProgress: number;
    overlayRevealProgress: number;
    isPanelExpandedPresentation: boolean;
    isCompactCollapsedPresentation: boolean;
}

export interface CartActionCheckoutOptions {
    items: CartItem[];
    isAuthenticated: boolean;
    active: boolean;
}
