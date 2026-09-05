import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { useCheckoutDetailsStore } from '@/store/checkoutDetailsStore';
import { calculateCdekDelivery } from '@/lib/api/checkout';
import { validContact, validCourierAddress, formatCourierAddress } from '@/lib/checkout/contact';
import { getOfficeAddress } from '@/lib/cdek/utils/cdek';
import type { DeliveryCalculationResponse } from '@/lib/checkout/types';
import { createCartActionOrder } from '@/lib/api/orders';
import type {
    CartActionCheckoutOptions,
    CartActionCoupon,
    CartDeliveryMethod,
    CartPaymentMethod,
} from '@/lib/cart/actionTypes';
import { getCartActionTotals } from '@/lib/cart/utils/cartAction';



export const useCartActionCheckout = ({ items, isAuthenticated }: CartActionCheckoutOptions) => {
    const router = useRouter();
    const details = useCheckoutDetailsStore();
    const [checkoutError, setCheckoutError] = useState('');
    const [quote, setQuote] = useState<DeliveryCalculationResponse | null>(null);
    const [quoteLoading, setQuoteLoading] = useState(false);
    const [quoteAttempt, setQuoteAttempt] = useState(0);
    const [deliveryMethod, setDeliveryMethod] = useState<CartDeliveryMethod>('pickup');
    const [paymentMethod, setPaymentMethod] = useState<CartPaymentMethod>('qr');
    const [isPaymentSubmitting, setIsPaymentSubmitting] = useState(false);
    const [isCouponOpen, setIsCouponOpen] = useState(false);
    const [pendingCoupon, setPendingCoupon] = useState<CartActionCoupon | null>(null);
    const [appliedCoupon, setAppliedCoupon] = useState<CartActionCoupon | null>(null);
    const [isOfferAccepted, setIsOfferAccepted] = useState(false);
    const [isPolicyAccepted, setIsPolicyAccepted] = useState(false);
    const [isAuthPopupOpen, setIsAuthPopupOpen] = useState(false);
    const baseTotals = useMemo(
        () => getCartActionTotals(items, deliveryMethod, appliedCoupon),
        [appliedCoupon, deliveryMethod, items],
    );

    const city = deliveryMethod === 'pickup' ? details.point?.location?.city || '' : details.courier.city;
    const addressReady = deliveryMethod === 'pickup' ? Boolean(details.point) : validCourierAddress(details.courier);
    useEffect(() => {
        let cancelled = false;
        const timer = setTimeout(async () => {
            setQuote(null); setCheckoutError('');
            if (!addressReady || !items.length) { setQuoteLoading(false); return; }
            setQuoteLoading(true);
            try {
                const result = await calculateCdekDelivery({ city, delivery_method: deliveryMethod === 'pickup' ? 'cdek_pickup' : 'cdek_door', cart_items: items.map(item => ({ product_id: item.product_id, quantity: item.quantity })) });
                if (!cancelled) setQuote(result);
            } catch {
                if (!cancelled) setCheckoutError('Не удалось рассчитать доставку. Проверьте адрес и попробуйте позже.');
            } finally { if (!cancelled) setQuoteLoading(false); }
        }, 0);
        return () => { cancelled = true; clearTimeout(timer); };
    }, [addressReady, city, deliveryMethod, items, quoteAttempt]);
    const totals = { ...baseTotals, deliveryPrice: quote?.delivery_price ?? 0,
        grandTotal: Math.max(0, baseTotals.productsTotal + (quote?.delivery_price ?? 0) - baseTotals.discount) };

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
        const buyer = details.buyer;
        const recipient = details.recipientIsBuyer ? buyer : details.recipient;
        if (!validContact(buyer) || !validContact(recipient)) { setCheckoutError('Заполните ваши данные в разделе «Получатель».'); return; }
        if (!addressReady) { setCheckoutError('Выберите пункт выдачи или заполните адрес курьера.'); return; }
        if (quoteLoading || quote?.delivery_price === undefined) { setCheckoutError('Дождитесь расчёта стоимости доставки.'); return; }
        setCheckoutError('');
        setIsPaymentSubmitting(true);
        try {
            const data = await createCartActionOrder({
                buyer, recipient,
                email: buyer.email.trim(), phone: recipient.phone, first_name: recipient.name, last_name: '',
                delivery_city: city,
                delivery_method: deliveryMethod === 'pickup' ? 'cdek_pickup' : 'cdek_door',
                delivery_address: deliveryMethod === 'pickup' ? getOfficeAddress(details.point!) : formatCourierAddress(details.courier),
                cdek_point_code: deliveryMethod === 'pickup' ? details.point?.code : undefined,
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
            setCheckoutError('Не удалось оформить заказ. Данные сохранены, попробуйте ещё раз.');
        } finally {
            setIsPaymentSubmitting(false);
        }
    };

    return {
        ...totals,
        checkoutError,
        retryQuote: () => setQuoteAttempt(value => value + 1),
        quoteLoading,
        deliveryQuoted: quote?.delivery_price !== undefined,
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
