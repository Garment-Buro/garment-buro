import type { AdminOrder, OrderDetails } from '@/lib/orders/types';

import { ApiError, requestJson } from './http.ts';
import type { CheckoutActor } from '../checkout/types';

export const getAdminOrders = (signal?: AbortSignal) => requestJson<AdminOrder[]>('/orders', {
    signal,
});

export const getOrderDetails = async (orderId: string, signal: AbortSignal | undefined, actor: CheckoutActor) => {
    if (!/^[1-9]\d*$/.test(orderId) || !Number.isSafeInteger(Number(orderId))) throw new ApiError('Order not found', 404);
    if (!actor?.token) throw new ApiError('Order access required', 401);
    const order = await requestJson<OrderDetails>(actor.kind === 'guest' ? '/order-access' : `/orders/${orderId}`, {
        signal, cache: 'no-store', headers: actor.kind === 'customer'
            ? { Authorization: `Bearer ${actor.token}` } : { 'X-Order-Access-Token': actor.token },
    });
    if (String(order.id) !== orderId) throw new ApiError('Order not found', 404);
    return order;
};

export { createCheckoutOrder as createCartActionOrder } from './checkout.ts';
