"use client";

import { useEffect } from 'react';
import { useCartStore } from '@/store/cartStore';

export const CartSyncBootstrap = () => {
    const hasHydrated = useCartStore(state => state.hasHydrated);
    const isCartInitialized = useCartStore(state => state.isCartInitialized);
    const initializeCart = useCartStore(state => state.initializeCart);

    useEffect(() => {
        if (!hasHydrated || isCartInitialized) return;
        void initializeCart();
    }, [hasHydrated, isCartInitialized, initializeCart]);

    return null;
};
