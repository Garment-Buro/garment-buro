'use client';

import { useCallback, useState } from 'react';
import type { CartActionCheckoutOptions, CartDeliveryMethod, CartPaymentMethod } from '@/lib/cart/actionTypes';
import { useCheckoutFlow } from '@/hooks/checkout/useCheckoutFlow';

export const useCartActionCheckout = ({ items, isAuthenticated, active }: CartActionCheckoutOptions) => {
    const [deliveryMethod, setDeliveryMethod] = useState<CartDeliveryMethod>('pickup');
    const [paymentMethod, setPaymentMethod] = useState<CartPaymentMethod>('card');
    const [isOfferAccepted, setIsOfferAccepted] = useState(false);
    const [isPolicyAccepted, setIsPolicyAccepted] = useState(false);
    const [isAuthPopupOpen, setIsAuthPopupOpen] = useState(false);
    const flow = useCheckoutFlow({ items, active, deliveryMethod, paymentMethod, accepted: isOfferAccepted && isPolicyAccepted });
    const resetCheckout = useCallback(() => {
        setDeliveryMethod('pickup'); setPaymentMethod('card');
        setIsAuthPopupOpen(false); setIsOfferAccepted(false); setIsPolicyAccepted(false);
    }, []);
    return {
        ...flow,
        deliveryPrice: flow.deliveryPrice ?? 0,
        deliveryQuoted: Boolean(flow.quote),
        deliveryMethod, setDeliveryMethod, paymentMethod: flow.effectivePaymentMethod, setPaymentMethod,
        isPaymentSubmitting: flow.isSubmitting,
        isOfferAccepted, setIsOfferAccepted, isPolicyAccepted, setIsPolicyAccepted,
        isAuthPopupOpen: !isAuthenticated && isAuthPopupOpen, setIsAuthPopupOpen, resetCheckout, startPayment: flow.submit,
    };
};
