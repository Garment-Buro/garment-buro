"use client";

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getOrderDetails } from '@/lib/api/orders';
import { createOrderDetailsFixture } from '@/lib/orders/fixtures/orderDetails';
import type { OrderDetails } from '@/lib/orders/types';
import { isMockDataEnabled } from '@/lib/runtime/config';

export const useOrderDetails = (providedOrderId?: string | string[]) => {
    const params = useParams();
    const routeOrderId = providedOrderId ?? params?.id;
    const orderId = Array.isArray(routeOrderId) ? routeOrderId[0] : routeOrderId;
    const [order, setOrder] = useState<OrderDetails | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        if (!orderId) {
            setIsLoading(false);
            return;
        }

        const controller = new AbortController();
        setIsLoading(true);

        const loadOrder = async () => {
            try {
                const nextOrder = isMockDataEnabled()
                    ? createOrderDetailsFixture(orderId)
                    : await getOrderDetails(orderId, controller.signal);
                setOrder(nextOrder);
            } catch (error) {
                if (!controller.signal.aborted) {
                    console.error('Failed to fetch order', error);
                    setOrder(null);
                }
            } finally {
                if (!controller.signal.aborted) setIsLoading(false);
            }
        };

        void loadOrder();
        return () => controller.abort();
    }, [orderId]);

    return { order, isLoading };
};
