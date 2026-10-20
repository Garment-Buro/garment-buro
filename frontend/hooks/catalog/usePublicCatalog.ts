'use client';

import type { ResourceInitial, ResourcePage } from '@/lib/catalog/pagedResource';
import { usePagedCatalog } from './usePagedCatalog';

/** One public view owns its snapshot; SSR hydration and explicit retries share the same lifecycle. */
export function usePublicCatalog<Item extends {id:number | string}, Query extends {query?:string;cursor?:string | null}>(
    query: Query, key: string, load: (query:Query, signal:AbortSignal) => Promise<ResourcePage<Item,string>>,
    active: boolean, initial?: ResourceInitial<Item,string>,
) {
    return usePagedCatalog(query, key, load, active, initial, true);
}
