'use client';

import { useCallback, useEffect, useState } from 'react';

import { deleteAdminProduct, getAdminProducts } from '@/lib/api/products';
import type { AdminProductSummary } from '@/lib/products/types';
import { runCatalogWrite } from '@/store/catalogWrite';

type AdminProductsState = {
    products: AdminProductSummary[];
    isLoading: boolean;
};

const INITIAL_STATE: AdminProductsState = {
    products: [],
    isLoading: true,
};

export const useAdminProducts = () => {
    const [state, setState] = useState<AdminProductsState>(INITIAL_STATE);

    useEffect(() => {
        const controller = new AbortController();

        getAdminProducts(controller.signal)
            .then((products) => setState({ products, isLoading: false }))
            .catch((error: unknown) => {
                if (controller.signal.aborted) return;
                console.error('Failed to fetch products:', error);
                setState({ products: [], isLoading: false });
            });

        return () => controller.abort();
    }, []);

    const deleteProduct = useCallback(async (productId: number) => {
        if (!window.confirm('Are you sure you want to delete this product?')) return;

        try {
            await runCatalogWrite(token => deleteAdminProduct(productId, token));
            setState((current) => ({
                ...current,
                products: current.products.filter((product) => product.id !== productId),
            }));
        } catch (error) {
            console.error('Failed to delete product:', error);
        }
    }, []);

    return {
        ...state,
        deleteProduct,
    };
};
