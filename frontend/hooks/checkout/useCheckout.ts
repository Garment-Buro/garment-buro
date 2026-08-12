'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';

import { calculateCdekDelivery, createCheckoutOrder } from '@/lib/api/checkout';
import type { CdekLoadState, CdekSelection, CheckoutErrors, CheckoutField, CheckoutFormValues } from '@/lib/checkout/types';
import { loadCheckoutCdekScripts } from '@/lib/checkout/utils/cdekScripts';
import {
    createCdekGoods,
    createCheckoutOrderPayload,
    EMPTY_CHECKOUT_FORM,
    getCheckoutErrors,
} from '@/lib/checkout/utils/checkout';
import { useCartStore } from '@/store/cartStore';
import { isMockDataEnabled } from '@/lib/runtime/config';

const ERROR_FIELDS = new Set<keyof CheckoutErrors>(['email', 'phone', 'firstName', 'deliveryAddress', 'agreeOffer', 'agreePolicy']);

export const useCheckout = () => {
    const router = useRouter();
    const items = useCartStore((state) => state.items);
    const getTotalPrice = useCartStore((state) => state.getTotalPrice);
    const updateQuantity = useCartStore((state) => state.updateQuantity);
    const removeItem = useCartStore((state) => state.removeItem);
    const clearCart = useCartStore((state) => state.clearCart);
    const [form, setForm] = useState<CheckoutFormValues>(EMPTY_CHECKOUT_FORM);
    const [cdekLoadState, setCdekLoadState] = useState<CdekLoadState>('idle');
    const [deliveryPrice, setDeliveryPrice] = useState<number | null>(null);
    const [errors, setErrors] = useState<CheckoutErrors>({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const deliveryWidgetRef = useRef<HTMLDivElement | null>(null);
    const itemsRef = useRef(items);
    itemsRef.current = items;

    const totalPrice = getTotalPrice();
    const cdekGoods = useMemo(() => createCdekGoods(items), [items]);
    const cdekScriptLoaded = cdekLoadState === 'loaded';

    const setField = <Key extends CheckoutField>(field: Key, value: CheckoutFormValues[Key]) => {
        setForm((current) => ({ ...current, [field]: value }));
        if (ERROR_FIELDS.has(field as keyof CheckoutErrors)) {
            setErrors((current) => ({ ...current, [field]: false }));
        }
    };

    const ensureCdekLoad = useCallback(() => {
        if (cdekLoadState === 'loading' || cdekLoadState === 'loaded') return;
        setCdekLoadState('loading');
        loadCheckoutCdekScripts()
            .then(() => setCdekLoadState('loaded'))
            .catch((error) => {
                console.error('Failed to load CDEK widget:', error);
                setCdekLoadState('error');
            });
    }, [cdekLoadState]);

    useEffect(() => {
        const element = deliveryWidgetRef.current;
        if (!element || cdekLoadState !== 'idle') return;
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                ensureCdekLoad();
                observer.disconnect();
            }
        }, { threshold: 0.01, rootMargin: '700px 0px' });
        observer.observe(element);
        return () => observer.disconnect();
    }, [cdekLoadState, ensureCdekLoad]);

    const chooseCdek = useCallback((selection: CdekSelection) => {
        const deliveryMethod = selection.deliveryType === 'office' ? 'cdek_pickup' : 'cdek_door';
        setForm((current) => ({
            ...current,
            cdekAddress: selection.address,
            deliveryAddress: selection.address,
            deliveryCity: selection.city,
            deliveryMethod,
            cdekPointCode: selection.cdekCode || '',
        }));
        setErrors((current) => ({ ...current, deliveryAddress: false }));

        void calculateCdekDelivery({
            city: selection.city,
            delivery_method: deliveryMethod,
            cart_items: itemsRef.current.map(({ product_id, quantity }) => ({ product_id, quantity })),
        }).then((result) => {
            if (result.delivery_price !== undefined) setDeliveryPrice(result.delivery_price);
        }).catch((error) => console.error('Failed to fetch CDEK tariff', error));
    }, []);

    const clearCdekSelection = () => {
        setForm((current) => ({
            ...current,
            cdekAddress: '', deliveryAddress: '', deliveryCity: '', deliveryMethod: '', cdekPointCode: '',
        }));
        setDeliveryPrice(null);
        setErrors((current) => ({ ...current, deliveryAddress: false }));
    };

    const submit = async (event: FormEvent) => {
        event.preventDefault();
        if (items.length === 0) return;
        const nextErrors = getCheckoutErrors(form);
        if (Object.keys(nextErrors).length) {
            setErrors(nextErrors);
            return;
        }

        setErrors({});
        setIsSubmitting(true);
        const order = createCheckoutOrderPayload({ form, items, totalPrice, deliveryPrice });

        if (isMockDataEnabled()) {
            window.setTimeout(() => {
                clearCart();
                router.push('/order/success');
            }, 800);
            return;
        }

        try {
            const result = await createCheckoutOrder(order);
            if (result.payment_url) {
                window.location.href = result.payment_url;
                return;
            }
            clearCart();
            router.push(`/order/${result.order_id}`);
        } catch (error) {
            console.error('Network error submitting order', error);
            router.push('/order/error');
        } finally {
            setIsSubmitting(false);
        }
    };

    return {
        form, setField, errors, isSubmitting, items, totalPrice, deliveryPrice,
        updateQuantity, removeItem, deliveryWidgetRef, cdekLoadState, cdekScriptLoaded, cdekGoods,
        ensureCdekLoad, chooseCdek, setDeliveryPrice, clearCdekSelection, submit,
    };
};

export type CheckoutController = ReturnType<typeof useCheckout>;
