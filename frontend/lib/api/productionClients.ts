import { PageCursorExpiredError } from '../catalog/pagedResource.ts';
import { readClientOrders, readClientTickets, type ClientHistoryQuery } from '../production/clientHistory.ts';
import { ApiError, requestReadJson } from './http.ts';

async function history<T>(kind: 'orders' | 'tickets', query: ClientHistoryQuery, read: (value: unknown) => T, init?: RequestInit): Promise<T> {
    const params = new URLSearchParams({ key: query.key, limit: '24' });
    if (query.cursor) params.set('cursor', query.cursor);
    try {
        return read(await requestReadJson<unknown>(`/production/admin/clients/${kind}?${params}`, { ...init, cache: 'no-store' }));
    } catch (error) {
        if (error instanceof ApiError && error.status === 422 && error.code === 'invalid_cursor') throw new PageCursorExpiredError();
        throw error;
    }
}

export const requestClientOrders = (query: ClientHistoryQuery, init?: RequestInit) => history('orders', query, readClientOrders, init);
export const requestClientTickets = (query: ClientHistoryQuery, init?: RequestInit) => history('tickets', query, readClientTickets, init);
