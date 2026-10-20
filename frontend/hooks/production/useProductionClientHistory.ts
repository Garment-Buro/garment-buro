'use client';

import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import { requestClientOrders, requestClientTickets } from '@/lib/api/productionClients';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import type { ClientHistoryPage, ClientHistoryQuery } from '@/lib/production/clientHistory';
import { useProductionAuthStore } from '@/store/productionAuthStore';

function authenticated<Item>(request: (query: ClientHistoryQuery, init: RequestInit) => Promise<ClientHistoryPage<Item>>) {
    return async (query: ClientHistoryQuery, signal: AbortSignal) => {
        const { user, sessionEpoch } = useProductionAuthStore.getState();
        const page = await useProductionAuthStore.getState().runAuthenticated(() => request(query, { signal }));
        const current = useProductionAuthStore.getState();
        if (signal.aborted || !current.isAuthenticated || user?.id !== current.user?.id || sessionEpoch !== current.sessionEpoch) {
            throw new DOMException('Сессия изменилась.', 'AbortError');
        }
        return page;
    };
}
const orders = authenticated(requestClientOrders);
const tickets = authenticated(requestClientTickets);

function useClientHistory<Item extends { id: number }>(key: string, enabled: boolean, kind: string,
    load: (query: ClientHistoryQuery, signal: AbortSignal) => Promise<ClientHistoryPage<Item>>) {
    const user = useProductionAuthStore(state => state.user);
    const epoch = useProductionAuthStore(state => state.sessionEpoch);
    const authenticated = useProductionAuthStore(state => state.isAuthenticated);
    const active = enabled && authenticated && user !== null;
    const query: ClientHistoryQuery = { key };
    const page = usePagedCatalog(query, `client-${kind}:${user?.id}:${epoch}:${key}`, load, active);
    return { ...page, items: active ? page.items : [],
        loading: active && (page.status === 'loading' || page.status === 'idle'),
        error: active && page.error instanceof Error ? page.error.message : '',
        hasMore: active && page.nextCursor !== null && !(page.error instanceof PageCursorExpiredError),
        cursorExpired: page.error instanceof PageCursorExpiredError,
    };
}

export const useProductionClientOrders = (key: string, enabled: boolean) => useClientHistory(key, enabled, 'orders', orders);
export const useProductionClientTickets = (key: string, enabled: boolean) => useClientHistory(key, enabled, 'tickets', tickets);
