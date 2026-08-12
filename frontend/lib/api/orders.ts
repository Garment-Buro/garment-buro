import type { AdminOrder, OrderDetails } from '@/lib/orders/types';
import type { CartActionOrderPayload, CartActionOrderResponse } from '@/lib/cart/actionTypes';

import { requestJson } from './http';

export const getAdminOrders = (signal?: AbortSignal) => requestJson<AdminOrder[]>('/orders', {
    signal,
});

export const getOrderDetails = (orderId: string, signal?: AbortSignal) => requestJson<OrderDetails>(`/orders/${orderId}`, {
    signal,
});

export const createCartActionOrder = (payload: CartActionOrderPayload) => requestJson<CartActionOrderResponse>('/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
});
