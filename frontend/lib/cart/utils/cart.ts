import type { CartItem } from '../types.ts';

export const createCartId = (cryptoRef?: Crypto) => {
    if (cryptoRef?.randomUUID) return cryptoRef.randomUUID();
    return `cart_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
};

export const normalizeCartItem = (item: Partial<CartItem>): CartItem => {
    const productId = Number(item.product_id || 0);
    const size = String(item.size || '');
    const color = String(item.color || '');
    const fallbackId = `${productId}_${size}_${color}`;
    const customization = item.customization && typeof item.customization === 'object'
        ? item.customization
        : undefined;

    return {
        id: String(item.id || fallbackId),
        product_id: productId,
        title: String(item.title || ''),
        price: Number(item.price || 0),
        image: String(item.image || ''),
        size,
        color,
        quantity: Math.max(1, Number(item.quantity || 1)),
        ...(customization ? { customization } : {}),
    };
};

export const normalizeCartItems = (items: Partial<CartItem>[] = []) => items.map(normalizeCartItem);

export const getActiveCartItemId = (items: CartItem[], preferredId?: string | null) => {
    if (preferredId && items.some(item => item.id === preferredId)) return preferredId;
    return items[items.length - 1]?.id || null;
};

export const getCartItemsTotal = (items: CartItem[]) => (
    items.reduce((total, item) => total + item.price * item.quantity, 0)
);

