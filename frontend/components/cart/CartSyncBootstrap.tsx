"use client";

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useCartStore } from '@/store/cartStore';

export const CartSyncBootstrap = () => {
    const pathname = usePathname();
    const hasHydrated = useCartStore(state => state.hasHydrated);
    const isCartInitialized = useCartStore(state => state.isCartInitialized);
    const initializeCart = useCartStore(state => state.initializeCart);

    useEffect(() => {
        if (pathname.startsWith('/production') || !hasHydrated || isCartInitialized) return;
        void initializeCart();
    }, [pathname, hasHydrated, isCartInitialized, initializeCart]);

    return null;
};
