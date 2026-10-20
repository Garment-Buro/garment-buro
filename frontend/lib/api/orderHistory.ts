import type { AuthOrder, AuthOrderPage } from '../auth/types.ts';
import { ApiError, requestJson } from './http.ts';

export function getAuthOrders(token: string, cursor: number | null, signal?: AbortSignal) {
    if (cursor !== null && (!Number.isInteger(cursor) || cursor < 1 || cursor > 2147483647)) {
        throw new RangeError('Некорректная страница заказов.');
    }
    const query = new URLSearchParams({limit: '24'});
    if (cursor !== null) query.set('cursor', String(cursor));
    return requestJson<AuthOrderPage>(`/auth/orders?${query}`, {
        headers: {Authorization: `Bearer ${token}`}, signal, cache: 'no-store',
    });
}

export async function getAuthOrder(token: string, id: number, signal?: AbortSignal) {
    if (!Number.isInteger(id) || id < 1 || id > 2147483647) throw new RangeError('Некорректный номер заказа.');
    const order = await requestJson<AuthOrder>(`/orders/${id}`, {
        headers: {Authorization: `Bearer ${token}`}, signal, cache: 'no-store',
    });
    if (order.id !== id) throw new ApiError('Ответ содержит другой заказ.', 502);
    return order;
}
