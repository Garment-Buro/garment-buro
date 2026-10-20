import { useEffect, useState, useSyncExternalStore } from 'react';

import { getAuthOrders, getAuthOrder } from '@/lib/api/orderHistory';
import type { AuthOrder, AuthOrderSummary } from '@/lib/auth/types';
import { PagedResource } from '@/lib/catalog/pagedResource';
import { runForCustomer, useCustomerAccount } from '@/hooks/catalog/customerSession';

export const useAuthOrders = (selectedOrderId?: string | null) => {
    const { key: account, userId } = useCustomerAccount();
    const [resource] = useState(() => new PagedResource<AuthOrderSummary, number>());
    const [details] = useState(() => new PagedResource<AuthOrder>());
    const [expanded, setExpanded] = useState<{ account: string | null; id: number | null }>({ account: null, id: null });
    const snapshot = useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getSnapshot);
    const detail = useSyncExternalStore(details.subscribe, details.getSnapshot, details.getSnapshot);
    useEffect(() => {
        if (userId === null || account === null) { resource.dispose(); return; }
        void resource.start(account, (cursor, signal) => runForCustomer(userId,
            token => getAuthOrders(token, cursor, signal), account));
        return resource.dispose;
    }, [resource, account, userId]);
    const current = account !== null && snapshot.key === account;
    const orders = current ? snapshot.items : [];
    const requestedId = selectedOrderId !== undefined ? Number(selectedOrderId)
        : expanded.account === account ? expanded.id : null;
    const selected = orders.find(order => order.id === requestedId) ?? null;
    const detailKey = account !== null && selected ? `${account}:${selected.id}` : null;
    const selectedId = selected?.id ?? null;
    useEffect(() => {
        if (userId === null || detailKey === null || selectedId === null) { details.dispose(); return; }
        void details.start(detailKey, async (_, signal) => ({
            items: [await runForCustomer(userId, token => getAuthOrder(token, selectedId, signal), account)],
            next_cursor: null,
        }));
        return details.dispose;
    }, [account, userId, detailKey, selectedId, details]);
    const currentDetail = detailKey !== null && detail.key === detailKey;
    return {
        orders, selected,
        loading: !current || snapshot.status === 'loading' || snapshot.status === 'idle',
        error: current ? snapshot.error : null,
        retry: resource.reload,
        hasMore: current && snapshot.nextCursor !== null,
        loadingMore: current && snapshot.loadingMore,
        loadMore: resource.loadMore,
        order: currentDetail ? detail.items[0] ?? null : null,
        detailLoading: selected !== null && (!currentDetail || detail.status === 'loading' || detail.status === 'idle'),
        detailError: currentDetail ? detail.error : null,
        retryDetail: details.reload,
        expandedOrderId: selected?.id ?? null,
        toggleOrder: (id: number) => setExpanded(previous => ({ account, id: previous.account === account && previous.id === id ? null : id })),
    };
};
