"use client";

import type { ReactNode } from 'react';
import { useCartStore } from '@/store/cartStore';

type CatalogCartItemOptions = {
    productId: number;
    title: ReactNode;
    cartTitle?: string;
    price: number;
    image: string;
};

export const useCatalogCartItem = ({
    productId,
    title,
    cartTitle,
    price,
    image,
}: CatalogCartItemOptions) => {
    const { items, addItem, updateQuantity } = useCartStore();
    const cartItem = items.find((item) => item.id === `${productId}__`);
    const quantity = cartItem?.quantity || 0;

    const addToCart = () => {
        addItem({
            product_id: productId,
            title: cartTitle || (typeof title === 'string' ? title : ''),
            price,
            image: image || '/landing-bg.webp',
            size: '',
            color: '',
            quantity: 1,
        });
    };

    const decreaseQuantity = () => {
        if (cartItem) updateQuantity(cartItem.id, cartItem.quantity - 1);
    };

    const increaseQuantity = () => {
        if (!cartItem) {
            addToCart();
            return;
        }
        updateQuantity(cartItem.id, cartItem.quantity + 1);
    };

    return { quantity, addToCart, decreaseQuantity, increaseQuantity };
};
