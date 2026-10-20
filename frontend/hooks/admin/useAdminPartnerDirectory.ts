'use client';

import { useCustomerAccount, runForCustomer } from '@/hooks/catalog/customerSession';
import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { partnerReadSearch, requestAdminPartnerPage, type AdminPartnerQuery } from '@/lib/partners/privateReads';
import { useAuthStore } from '@/store/authStore';

const load = (query: AdminPartnerQuery, signal: AbortSignal) => {
    const state = useAuthStore.getState(), id = state.user?.id;
    if (!id) throw new DOMException('Сессия изменилась.', 'AbortError');
    return runForCustomer(id, token => requestAdminPartnerPage(token, query, signal), `${id}:${state.accountEpoch ?? 'session'}`);
};
export function useAdminPartnerDirectory(query: AdminPartnerQuery, revision = 0) {
    const account = useCustomerAccount(), active = account.key !== null;
    const page = usePagedCatalog(query, `partner-profiles:${account.key}:${revision}:${partnerReadSearch(query)}`, load, active);
    return { ...page, items: active ? page.items : [], loading: !account.sessionReady || active && ['idle','loading'].includes(page.status),
        message: active && page.error instanceof Error ? page.error.message : '',
        hasMore: active && page.nextCursor !== null && !(page.error instanceof PageCursorExpiredError) };
}
