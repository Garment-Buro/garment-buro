import type { CartServerPayload, CartServerUpdate } from '@/lib/cart/types';

import { request, requestOptionalJson } from './http';

export const getCartSnapshot = async (cartId: string): Promise<CartServerPayload | null> => {
    return requestOptionalJson<CartServerPayload>(`/cart/${encodeURIComponent(cartId)}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
    });
};

export const syncCartSnapshot = async (cartId: string, update: CartServerUpdate) => {
    await request(`/cart/${encodeURIComponent(cartId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update),
    });
};
