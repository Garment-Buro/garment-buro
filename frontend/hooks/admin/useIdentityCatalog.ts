'use client';

import { getAdminProducts } from '@/lib/api/products';
import { isCatalogWritesV2Enabled } from '@/lib/auth/config';
import { PageCursorExpiredError } from '@/lib/catalog/pagedResource';
import { catalogAdminSearch, type CatalogAdminQuery } from '@/lib/products/adminCatalog';
import { runCatalogRequest } from '@/store/catalogSession';
import { useCustomerAccount } from '@/hooks/catalog/customerSession';
import { usePagedCatalog } from '@/hooks/catalog/usePagedCatalog';

const load = (query: CatalogAdminQuery, signal: AbortSignal) =>
    runCatalogRequest(token => getAdminProducts(query, token, signal));

export function useIdentityCatalog(query: CatalogAdminQuery) {
    const account = useCustomerAccount();
    const enabled = isCatalogWritesV2Enabled();
    const active = enabled && account.key !== null;
    const page = usePagedCatalog(query, `identity-products:${account.key}:${catalogAdminSearch(query)}`, load, active);
    return { ...page, items: active ? page.items : [],
        loading: !account.sessionReady || (active && ['loading', 'idle'].includes(page.status)),
        error: !enabled ? 'Управление каталогом отключено.'
            : account.sessionReady && !account.key ? 'Войдите в аккаунт для управления каталогом.'
            : page.error instanceof Error ? page.error.message : '',
        hasMore: active && page.nextCursor !== null && !(page.error instanceof PageCursorExpiredError),
    };
}
