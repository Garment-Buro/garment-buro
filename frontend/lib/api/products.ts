import type {
    AdminProductFormResponse,
    AdminProductPayload,
    AdminProductSummary,
    ProductData,
} from '@/lib/products/types';

import { request, requestJson } from './http';
import { bearerHeaders } from './headers';

export const getProducts = (signal?: AbortSignal) => requestJson<ProductData[]>('/products', {
    signal,
});

export const getProduct = (productId: number | string, signal?: AbortSignal) => (
    requestJson<ProductData>(`/products/${productId}`, { signal })
);

export const getAdminProducts = (signal?: AbortSignal) => requestJson<AdminProductSummary[]>('/products', {
    signal,
});

export const deleteAdminProduct = async (productId: number, token?: string) => {
    await request(`/products/${productId}`, {
        method: 'DELETE',
        headers: bearerHeaders(token),
    });
};

export const getAdminProduct = (productId: string, signal?: AbortSignal) => (
    requestJson<AdminProductFormResponse>(`/products/${productId}`, { signal })
);

export const saveAdminProduct = async (
    productId: string | null,
    payload: AdminProductPayload,
    token?: string,
) => {
    await request(productId ? `/products/${productId}` : '/products', {
        method: productId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...bearerHeaders(token) },
        body: JSON.stringify(payload),
    });
};
