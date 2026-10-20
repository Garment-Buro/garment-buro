import { boundedProductIds, validateProductId } from '../products/identity.ts';
import { bearerHeaders } from './headers.ts';
import { request, requestJson } from './http.ts';

export interface FavoritePage {
    items: {product_id: number; saved_at: string}[];
    next_cursor: number | null;
}

export const getFavoriteProducts = (
    token: string, page: {limit?: number; cursor?: number | null} = {}, signal?: AbortSignal,
) => {
    const params = new URLSearchParams({limit: String(page.limit ?? 24)});
    if (page.cursor != null) params.set('cursor', String(page.cursor));
    return requestJson<FavoritePage>(`/profile/favorites?${params}`, {
        headers: bearerHeaders(token), signal, cache: 'no-store',
    });
};

export async function getFavoriteStatus(productIds: readonly number[], token: string, signal?: AbortSignal) {
    const ids = boundedProductIds(productIds);
    if (!ids.length) return [];
    const params = new URLSearchParams();
    ids.forEach(id => params.append('product_ids', String(id)));
    const response = await requestJson<{product_ids: number[]}>(`/profile/favorites/status?${params}`, {
        headers: bearerHeaders(token), signal, cache: 'no-store',
    });
    return response.product_ids;
}

export async function setProductFavorite(productId: number, saved: boolean, token: string, signal?: AbortSignal) {
    await request(`/profile/favorites/${validateProductId(productId)}`, {
        method: saved ? 'PUT' : 'DELETE', headers: bearerHeaders(token), signal, cache: 'no-store',
    });
}
