'use client';

import { useRouter } from 'next/navigation';

import { CartActionBar } from '@/components/cart/CartActionBar';
import { getActiveCartItem } from '@/lib/cart/utils/activeItem';
import { useCartStore } from '@/store/cartStore';

export function ServiceHomeCart() {
    const router = useRouter();
    const items = useCartStore(state => state.items);
    const activeItemId = useCartStore(state => state.activeItemId);
    const activeItem = getActiveCartItem(items, activeItemId);

    const editActiveItem = () => {
        if (!activeItem) return;
        router.push(`/constructor?productId=${activeItem.product_id}&editCartItemId=${encodeURIComponent(activeItem.id)}`);
    };

    return (
        <CartActionBar
            visible
            allowEmptyExpand
            collapsedVariant="liquid-v2"
            title={activeItem?.title || 'Корзина'}
            color={activeItem?.color || ''}
            price={activeItem?.price || 0}
            cartItemId={activeItem?.id}
            onLogin={() => router.push('/profile')}
            onAdd={() => router.push('/constructor')}
            onEdit={editActiveItem}
            onBuy={() => { if (items.length > 0) router.push('/checkout'); }}
        />
    );
}
