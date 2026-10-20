import { boundedProductIds } from '../products/identity.ts';
import {readConstructorProduct} from '../constructor/product.ts';
import type {ConstructorPriceRequest} from '../constructor/priceResource.ts';
import { requestPublicJson } from './http.ts';
import { requestPublicPage } from './publicPages.ts';
import {storefrontSearchParams, type StorefrontPage, type StorefrontOptions, type StorefrontQuery} from '../catalog/storefront.ts';

export { productConstructorHref } from '../products/identity.ts';
export {storefrontSearchParams} from '../catalog/storefront.ts';
export type {StorefrontSource, StorefrontSort, StorefrontProduct, StorefrontPage, StorefrontOptions, StorefrontQuery, StorefrontInitial} from '../catalog/storefront.ts';

export const getConstructorProduct = async (productId: number, signal?: AbortSignal) => (
    readConstructorProduct(await requestPublicJson<unknown>(`/catalog/products/${productId}`, {signal, cache:'no-store'}), productId)
);

export const getConstructorPrice = (input: ConstructorPriceRequest, signal?: AbortSignal) => (
    requestPublicJson<unknown>(`/catalog/products/${input.productId}/price`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({decorations: input.decorations}), signal, cache: 'no-store',
    })
);

export const getStorefrontProducts = (query: StorefrontQuery, signal?: AbortSignal) => (
    requestPublicPage<StorefrontPage>(`/catalog/products?${storefrontSearchParams(query)}`, {
        signal, cache: 'no-store',
    })
);

export const getStorefrontOptions = (signal?: AbortSignal) => (
    requestPublicJson<StorefrontOptions>('/catalog/options', {signal})
);

export async function getStorefrontProductsByIds(productIds: readonly number[], signal?: AbortSignal) {
    const ids = boundedProductIds(productIds);
    if (!ids.length) return [];
    const page = await getStorefrontProducts({ids, limit:ids.length}, signal);
    const products = new Map(page.items.map(product => [product.id, product]));
    return ids.flatMap(id => {
        const product = products.get(id);
        return product ? [product] : [];
    });
}
