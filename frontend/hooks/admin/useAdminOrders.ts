'use client';

import { useEffect, useState } from 'react';

import { getAdminOrders } from '@/lib/api/orders';
import type { AdminOrder } from '@/lib/orders/types';

type AdminOrdersState = {
    orders: AdminOrder[];
    isLoading: boolean;
};

const INITIAL_STATE: AdminOrdersState = {
    orders: [],
    isLoading: true,
};

export const useAdminOrders = () => {
    const [state, setState] = useState<AdminOrdersState>(INITIAL_STATE);

    useEffect(() => {
        const controller = new AbortController();

        getAdminOrders(controller.signal)
            .then((orders) => setState({ orders, isLoading: false }))
            .catch((error: unknown) => {
                if (controller.signal.aborted) return;
                console.error('Failed to fetch orders:', error);
                setState({ orders: [], isLoading: false });
            });

        return () => controller.abort();
    }, []);

    return state;
};
