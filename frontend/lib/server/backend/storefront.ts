import 'server-only';

import {storefrontQueryKey, type StorefrontInitial, type StorefrontPage, type StorefrontQuery} from '../../catalog/storefront.ts';
import {serverRequestJson} from './http.ts';

/** Only public catalog data crosses this server/client boundary. */
export async function getInitialStorefront(query: StorefrontQuery): Promise<StorefrontInitial> {
    const key = storefrontQueryKey(query);
    try {
        const page = await serverRequestJson<StorefrontPage>(`/catalog/products?${key}`, {
            cache:'no-store', signal:AbortSignal.timeout(2000),
        });
        return {key, page};
    } catch {
        // Do not serialize upstream errors or replace unavailable data with demos.
        return {key, error:'unavailable'};
    }
}
