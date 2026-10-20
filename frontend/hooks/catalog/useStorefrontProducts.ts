'use client';

import {getStorefrontProducts, type StorefrontQuery} from '@/lib/api/storefront';
import {storefrontQueryKey, type StorefrontInitial} from '@/lib/catalog/storefront';
import {usePublicCatalog} from './usePublicCatalog';

export function useStorefrontProducts(query: StorefrontQuery, active = true, initial?: StorefrontInitial) {
    return usePublicCatalog(query,storefrontQueryKey(query),getStorefrontProducts,active,initial);
}
