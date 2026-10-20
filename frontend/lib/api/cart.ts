import type { CartServerPayload, CartServerUpdate } from '@/lib/cart/types';

import { CartRevisionConflictError } from '../cart/snapshotSync.ts';
import { ApiError, requestJson } from './http.ts';

export const CART_SNAPSHOT_READ_TIMEOUT_MS = 10_000;

export const getCartSnapshot = async (cartId: string): Promise<CartServerPayload> => {
    // A stalled initial read must release the queue for current local edits.
    const signal = AbortSignal.timeout(CART_SNAPSHOT_READ_TIMEOUT_MS);
    try {
        const snapshot = await requestJson<CartServerPayload>(`/cart/${encodeURIComponent(cartId)}`, {
            method: 'GET', cache: 'no-store', signal,
            headers: { 'Content-Type': 'application/json' },
        });
        signal.throwIfAborted();
        return snapshot;
    } catch(error) {
        signal.throwIfAborted();
        throw error;
    }
};

export const syncCartSnapshot = async (cartId: string, update: CartServerUpdate): Promise<CartServerPayload> => {
    try {
        return await requestJson<CartServerPayload>(`/cart/${encodeURIComponent(cartId)}`, {
            method: 'PUT', cache: 'no-store',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(update),
        });
    } catch(error) {
        if(error instanceof ApiError && error.status === 409 && error.code === 'cart_conflict') throw new CartRevisionConflictError();
        throw error;
    }
};
