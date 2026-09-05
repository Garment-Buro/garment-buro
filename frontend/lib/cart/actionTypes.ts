import type { CART_ACTION_COUPONS } from './constants';
import type { CartItem } from './types';

export type CartActionCoupon = (typeof CART_ACTION_COUPONS)[number];
export type CartDeliveryMethod = 'pickup' | 'courier';
export type CartPaymentMethod = 'qr' | 'card';
export type CartCollapsedVariant = 'legacy' | 'glass-compact' | 'liquid-v2';

export interface CartActionBarProps {
    visible: boolean;
    title: string;
    color: string;
    price: number;
    image?: string;
    cartItemId?: string;
    usePreferredCartItemOnly?: boolean;
    showAddProductCard?: boolean;
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

export interface CartActionOrderPayload {
    buyer?: import('@/lib/checkout/contact').CheckoutContact;
    recipient?: import('@/lib/checkout/contact').CheckoutContact;
    cdek_point_code?: string;
    email: string;
    phone: string;
    first_name: string;
    last_name: string;
    delivery_city: string;
    delivery_method: string;
    delivery_address: string;
    payment_method: CartPaymentMethod;
    cart_items: string;
    total_price: number;
    delivery_price: number;
}

export interface CartActionOrderResponse {
    payment_url?: string;
    order_id?: number;
}

export interface CartActionCheckoutOptions {
    items: CartItem[];
    isAuthenticated: boolean;
    user: {
        email?: string;
        first_name?: string;
        last_name?: string;
    } | null;
}
