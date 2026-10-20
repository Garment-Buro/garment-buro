'use client';

import { useCustomerAccount, runForCustomer } from '@/hooks/catalog/customerSession';
import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { requestPartnerPayoutPage, type PartnerPayoutQuery } from '@/lib/partners/privateReads';
import { useAuthStore } from '@/store/authStore';

const query = { limit: 24 };
const load = (parameters: PartnerPayoutQuery, signal: AbortSignal) => {
    const state = useAuthStore.getState(), id = state.user?.id;
    if (!id) throw new DOMException('Сессия изменилась.', 'AbortError');
    return runForCustomer(id, token => requestPartnerPayoutPage(token, parameters, signal), `${id}:${state.accountEpoch ?? 'session'}`);
};
export function usePartnerPayouts(revision = 0) {
    const account = useCustomerAccount(), active = account.key !== null;
    const page = usePagedCatalog(query, `partner-payouts:${account.key}:${revision}`, load, active);
    return { ...page, items: active ? page.items : [], loading: active && ['idle','loading'].includes(page.status),
        message: active && page.error instanceof Error ? page.error.message : '',
        hasMore: active && page.nextCursor !== null && !(page.error instanceof PageCursorExpiredError) };
}
