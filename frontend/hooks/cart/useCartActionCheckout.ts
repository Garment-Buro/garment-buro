import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { createCartActionOrder } from '@/lib/api/orders';
import type {
    CartActionCheckoutOptions,
    CartActionCoupon,
    CartDeliveryMethod,
    CartPaymentMethod,
} from '@/lib/cart/actionTypes';
import { getCartActionTotals } from '@/lib/cart/utils/cartAction';

const CART_ACTION_GUEST_PAYMENT_EMAIL = 'guest@garment-buro.ru';

export const useCartActionCheckout = ({ items, isAuthenticated, user }: CartActionCheckoutOptions) => {
    const router = useRouter();
    const [deliveryMethod, setDeliveryMethod] = useState<CartDeliveryMethod>('pickup');
    const [paymentMethod, setPaymentMethod] = useState<CartPaymentMethod>('qr');
    const [isPaymentSubmitting, setIsPaymentSubmitting] = useState(false);
    const [isCouponOpen, setIsCouponOpen] = useState(false);
    const [pendingCoupon, setPendingCoupon] = useState<CartActionCoupon | null>(null);
    const [appliedCoupon, setAppliedCoupon] = useState<CartActionCoupon | null>(null);
    const [isOfferAccepted, setIsOfferAccepted] = useState(false);
    const [isPolicyAccepted, setIsPolicyAccepted] = useState(false);
    const [isAuthPopupOpen, setIsAuthPopupOpen] = useState(false);
    const totals = useMemo(
        () => getCartActionTotals(items, deliveryMethod, appliedCoupon),
        [appliedCoupon, deliveryMethod, items],
    );

    useEffect(() => {
        if (isAuthenticated) setIsAuthPopupOpen(false);
    }, [isAuthenticated]);

    const resetCheckout = useCallback(() => {
        setDeliveryMethod('pickup');
        setPaymentMethod('qr');
        setIsPaymentSubmitting(false);
        setIsCouponOpen(false);
        setPendingCoupon(null);
        setAppliedCoupon(null);
        setIsAuthPopupOpen(false);
        setIsOfferAccepted(false);
        setIsPolicyAccepted(false);
    }, []);

    const startPayment = async () => {
        if (items.length === 0 || isPaymentSubmitting || !isOfferAccepted || !isPolicyAccepted) return;
        setIsPaymentSubmitting(true);
        try {
            const data = await createCartActionOrder({
                email: user?.email?.trim() || CART_ACTION_GUEST_PAYMENT_EMAIL,
                phone: '+7 900 200-00-11',
                first_name: user?.first_name || 'Гость',
                last_name: user?.last_name || '',
                delivery_city: 'Москва',
                delivery_method: deliveryMethod === 'pickup' ? 'cdek' : 'courier',
                delivery_address: 'Россия, г. Москва, пункт выдачи СДЭК, ул. Беговая, 38/1, 170007',
                payment_method: paymentMethod,
                cart_items: JSON.stringify(items),
                total_price: totals.grandTotal,
                delivery_price: totals.deliveryPrice,
            });
            if (data.payment_url) {
                window.location.assign(data.payment_url);
                return;
            }
            router.push(data.order_id ? `/order/${data.order_id}` : '/order/error');
        } catch (error) {
            console.error('Failed to start payment', error);
            router.push('/order/error');
        } finally {
            setIsPaymentSubmitting(false);
        }
    };

    return {
        ...totals,
        deliveryMethod,
        setDeliveryMethod,
        paymentMethod,
        setPaymentMethod,
        isPaymentSubmitting,
        isCouponOpen,
        setIsCouponOpen,
        pendingCoupon,
        setPendingCoupon,
        appliedCoupon,
        setAppliedCoupon,
        isOfferAccepted,
        setIsOfferAccepted,
        isPolicyAccepted,
        setIsPolicyAccepted,
        isAuthPopupOpen,
        setIsAuthPopupOpen,
        resetCheckout,
        startPayment,
    };
};
