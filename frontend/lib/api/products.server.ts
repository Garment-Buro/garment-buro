import { cache } from 'react';

import type { ProductData } from '@/lib/products/types';

import { serverFetch, serverRequestJson } from '@/lib/server/backend/http';

export const PRODUCT_REVALIDATE_SECONDS = 60;

export const getServerProduct = cache(async (productId: number): Promise<ProductData | null> => {
    const response = await serverFetch(`/products/${productId}`, {
        next: { revalidate: PRODUCT_REVALIDATE_SECONDS },
    });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Product ${productId} request failed with status ${response.status}`);
    return response.json() as Promise<ProductData>;
});

export const getServerProducts = cache(async (): Promise<ProductData[]> => {
    const products = await serverRequestJson<ProductData[]>('/products', {
        next: { revalidate: PRODUCT_REVALIDATE_SECONDS },
    });
    return products.sort((first, second) => first.id - second.id);
});
