'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';
import { getFavoriteProducts } from '@/lib/api/favorites';
import { getStorefrontProductsByIds, type StorefrontProduct } from '@/lib/api/storefront';
import { PagedResource } from '@/lib/catalog/pagedResource';
import { runForCustomer, useCustomerAccount } from './customerSession';

export function useSavedProducts(active: boolean) {
    const {key:account, userId} = useCustomerAccount();
    const key = `favorites:${account ?? 'guest'}`;
    const [resource] = useState(() => new PagedResource<StorefrontProduct, number>());
    const snapshot = useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getSnapshot);
    useEffect(() => {
        if(!active || userId === null) {resource.dispose(); return}
        void resource.start(key, async (cursor, signal) => {
            const page = await runForCustomer(userId, token => getFavoriteProducts(token, {limit:24, cursor}, signal));
            const items = await getStorefrontProductsByIds(page.items.map(item => item.product_id), signal);
            return {items, next_cursor:page.next_cursor};
        });
        return resource.dispose;
    }, [active, key, userId, resource]);
    const state = snapshot.key === key ? snapshot : {
        key, status:'loading' as const, items:[], nextCursor:null, loadingMore:false, error:null,
    };
    return {...state, authenticated:userId !== null, loadMore:resource.loadMore, retry:resource.reload};
}
