import 'server-only';

import {boundedProductIds} from '../../products/identity.ts';
import type {CollectionProduct} from '../../catalog/collection.ts';
import {serverRequestJson} from './http.ts';

export async function getCollectionProducts(productIds: readonly number[]): Promise<CollectionProduct[]> {
    if(productIds.length > 50) throw new RangeError('At most 50 models per collection');
    const ids = boundedProductIds(productIds);
    if(!ids.length) return [];
    const params = new URLSearchParams();
    ids.forEach(id => params.append('ids', String(id)));
    return serverRequestJson<CollectionProduct[]>(`/catalog/collection-products?${params}`, {
        next:{revalidate:60}, signal:AbortSignal.timeout(2000),
    });
}
