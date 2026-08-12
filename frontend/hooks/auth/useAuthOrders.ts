import { useEffect, useState } from 'react';

import { getAuthOrders } from '@/lib/api/auth';
import { ApiError } from '@/lib/api/http';
import type { AuthOrder } from '@/lib/auth/types';
import { hasUsableAuthToken } from '@/lib/auth/utils/auth';
import { useAuthStore } from '@/store/authStore';

export const useAuthOrders = (token: string | null) => {
    const [orders, setOrders] = useState<AuthOrder[]>([]);
    const [expandedOrderId, setExpandedOrderId] = useState<number | null>(null);
    const runAuthenticated = useAuthStore(state => state.runAuthenticated);

    useEffect(() => {
        if (!hasUsableAuthToken(token)) return;
        const controller = new AbortController();
        runAuthenticated(authToken => getAuthOrders(authToken, controller.signal))
            .then(setOrders)
            .catch(error => {
                if (controller.signal.aborted) return;
                if (error instanceof ApiError && error.status === 401) {
                    console.warn('[AUTH] Token invalid or expired');
                    return;
                }
                console.error('[AUTH] Failed to fetch orders:', error);
            });
        return () => controller.abort();
    }, [runAuthenticated, token]);

    const toggleOrder = (orderId: number) => {
        setExpandedOrderId(currentId => currentId === orderId ? null : orderId);
    };

    return { orders, expandedOrderId, toggleOrder };
};
