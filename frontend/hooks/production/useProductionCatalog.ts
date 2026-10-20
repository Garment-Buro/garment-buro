'use client';

import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import { requestCatalogAdminPage } from '@/lib/api/catalogAdmin';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { catalogAdminSearch, type CatalogAdminQuery } from '@/lib/products/adminCatalog';
import { useProductionAuthStore } from '@/store/productionAuthStore';

const load = async (query: CatalogAdminQuery, signal: AbortSignal) => {
    const owner = useProductionAuthStore.getState().user?.id;
    const page = await useProductionAuthStore.getState().runAuthenticated(() =>
        requestCatalogAdminPage('/production/admin/assortment/products', query, { signal }));
    if (signal.aborted || owner !== useProductionAuthStore.getState().user?.id) {
        throw new DOMException('Сессия изменилась.', 'AbortError');
    }
    return page;
};

export function useProductionCatalog(query: CatalogAdminQuery, enabled: boolean) {
    const user = useProductionAuthStore(state => state.user);
    const epoch = useProductionAuthStore(state => state.sessionEpoch);
    const authenticated = useProductionAuthStore(state => state.isAuthenticated);
    const active = enabled && authenticated && user !== null;
    const page = usePagedCatalog(query, `production-products:${user?.id}:${epoch}:${catalogAdminSearch(query)}`, load, active);
    return {
        ...page,
        items: active ? page.items : [],
        loading: active && (page.status === 'loading' || page.status === 'idle'),
        error: active && page.error instanceof Error ? page.error.message : '',
        hasMore: active && page.nextCursor !== null && !(page.error instanceof PageCursorExpiredError),
    };
}
