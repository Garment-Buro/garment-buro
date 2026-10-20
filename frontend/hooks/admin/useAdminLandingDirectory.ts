'use client';
import { useCustomerAccount, runForCustomer } from '@/hooks/catalog/customerSession';
import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { adminLandingSearch, requestAdminLandingPage, type AdminLandingQuery } from '@/lib/partners/adminDirectory';
import { useAuthStore } from '@/store/authStore';
import { useProductionAuthStore } from '@/store/productionAuthStore';
const loadIdentity = (query: AdminLandingQuery, signal: AbortSignal) => {
    const state = useAuthStore.getState(), id = state.user?.id;
    if (!id)
        throw new DOMException('Сессия изменилась.', 'AbortError');
    return runForCustomer(id, token => requestAdminLandingPage('/admin/partners/landings', query, signal, token), `${id}:${state.accountEpoch ?? 'session'}`);
};
const loadProduction = async (query: AdminLandingQuery, signal: AbortSignal) => {
    const owner = useProductionAuthStore.getState().user?.id;
    const result = await useProductionAuthStore.getState().runAuthenticated(() => requestAdminLandingPage('/production/admin/assortment/product-communities', query, signal));
    if (signal.aborted || owner !== useProductionAuthStore.getState().user?.id)
        throw new DOMException('Сессия изменилась.', 'AbortError');
    return result;
};
export function useAdminLandingDirectory(mode: 'identity' | 'production', query: AdminLandingQuery, enabled = true) {
    const account = useCustomerAccount();
    const production = useProductionAuthStore(state => state.user);
    const epoch = useProductionAuthStore(state => state.sessionEpoch);
    const authenticated = useProductionAuthStore(state => state.isAuthenticated);
    const owner = mode === 'identity' ? account.key : authenticated && production ? `${production.id}:${epoch}` : null;
    const active = enabled && owner != null;
    const page = usePagedCatalog(query, `admin-landings:${mode}:${owner}:${adminLandingSearch(query)}`, mode === 'identity' ? loadIdentity : loadProduction, active);
    return { ...page, items: active ? page.items : [], loading: active && ['loading', 'idle'].includes(page.status),
        message: active && page.error instanceof Error ? page.error.message : '',
        hasMore: active && page.nextCursor !== null && !(page.error instanceof PageCursorExpiredError) };
}
