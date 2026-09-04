'use client';

import { useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';

import { CartActionBarV2 } from '@/components/cart/CartActionBarV2';
import { getActiveCatalogCartItem } from '@/lib/catalog/utils/catalog';
import { useCartStore } from '@/store/cartStore';

export const NikitaCartAction = () => {
    const router = useRouter();
    const items = useCartStore(state => state.items);
    const activeItemId = useCartStore(state => state.activeItemId);
    const activeItem = useMemo(
        () => getActiveCatalogCartItem(items, activeItemId),
        [activeItemId, items],
    );

    const goToCheckout = useCallback(() => {
        if (items.length > 0) router.push('/checkout');
    }, [items.length, router]);

    const editActiveItem = useCallback(() => {
        if (!activeItem) return;
        router.push(
            `/constructor?productId=${activeItem.product_id}`
            + `&editCartItemId=${encodeURIComponent(activeItem.id)}&landing=nikitamoiseev`,
        );
    }, [activeItem, router]);

    const goToProfile = useCallback(() => router.push('/profile'), [router]);

    return (
        <CartActionBarV2
            title={activeItem?.title || 'Корзина'}
            color={activeItem?.color || ''}
            price={activeItem?.price || 0}
            cartItemId={activeItem?.id}
            shiftAfterElementId="nikita-merch-start"
            onLogin={goToProfile}
            onAdd={goToCheckout}
            onEdit={editActiveItem}
            onBuy={goToCheckout}
        />
    );
};
