'use client';

import { useState, type FormEvent } from 'react';
import { useCartStore } from '@/store/cartStore';
import type { CartDeliveryMethod, CartPaymentMethod } from '@/lib/cart/actionTypes';
import { useCheckoutFlow } from './useCheckoutFlow';

export const useCheckout = () => {
    const items = useCartStore(state => state.items);
    const updateQuantity = useCartStore(state => state.updateQuantity);
    const removeItem = useCartStore(state => state.removeItem);
    const [deliveryMethod, setDeliveryMethod] = useState<CartDeliveryMethod>('pickup');
    const [form, setForm] = useState({ agreeOffer: false, agreePolicy: false, paymentMode: 'card' as CartPaymentMethod });
    const [errors, setErrors] = useState<{ agreeOffer?: boolean; agreePolicy?: boolean }>({});
    const setField = <Key extends keyof typeof form>(field: Key, value: (typeof form)[Key]) => {
        setForm(current => ({ ...current, [field]: value }));
        setErrors(current => ({ ...current, [field]: false }));
    };
    const flow = useCheckoutFlow({ items, active: true, deliveryMethod, paymentMethod: form.paymentMode, accepted: form.agreeOffer && form.agreePolicy });
    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (event.target !== event.currentTarget) return;
        if (!form.agreeOffer || !form.agreePolicy) {
            setErrors({ agreeOffer: !form.agreeOffer, agreePolicy: !form.agreePolicy }); return;
        }
        setErrors({}); await flow.submit();
    };
    return { ...flow, form, setField, errors, items, totalPrice: flow.productsTotal, updateQuantity, removeItem, deliveryMethod, setDeliveryMethod, submit };
};

export type CheckoutController = ReturnType<typeof useCheckout>;
