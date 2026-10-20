'use client';

import { useState } from 'react';
import { useCheckoutDetailsStore } from '@/store/checkoutDetailsStore';
import { validContact, validCourierAddress, formatCourierAddress } from '@/lib/checkout/contact';
import { createCheckoutOrderPayload } from '@/lib/checkout/utils/checkout';
import type { CartItem } from '@/lib/cart/types';
import type { CartDeliveryMethod, CartPaymentMethod } from '@/lib/cart/actionTypes';
import type { DeliveryCalculationRequest } from '@/lib/checkout/types';
import { useCheckoutPurchase } from './useCheckoutPurchase';
import { useDeliveryQuote } from './useDeliveryQuote';
import { useCheckoutPaymentOptions } from './useCheckoutPaymentOptions';

export function useCheckoutFlow({ items, active, deliveryMethod, paymentMethod, accepted }: {
    items: CartItem[]; active: boolean; deliveryMethod: CartDeliveryMethod; paymentMethod: CartPaymentMethod; accepted: boolean;
}) {
    const details = useCheckoutDetailsStore();
    const purchase = useCheckoutPurchase(active);
    const qrAvailable = useCheckoutPaymentOptions(active);
    const effectivePaymentMethod: CartPaymentMethod = paymentMethod === 'qr' && qrAvailable ? 'qr' : 'card';
    const [validation, setValidation] = useState('');
    const method = deliveryMethod === 'pickup' ? 'cdek_pickup' : 'cdek_door';
    const addressReady = deliveryMethod === 'pickup' ? Boolean(details.point?.code) : validCourierAddress(details.courier);
    const request: DeliveryCalculationRequest | null = !items.length || !addressReady ? null : {
        city: deliveryMethod === 'pickup' ? details.point?.location?.city ?? '' : details.courier.city,
        delivery_method: method,
        ...(deliveryMethod === 'pickup' ? { cdek_point_code: details.point!.code } : { delivery_address: formatCourierAddress(details.courier) }),
        cart_items: items.map(({ product_id, quantity }) => ({ product_id, quantity })),
    };
    const quote = useDeliveryQuote(request, active && purchase.ready && !purchase.pending, JSON.stringify(items));
    const productsTotal = Math.round(items.reduce((sum, item) => sum + item.price * item.quantity, 0) * 100) / 100;
    const submit = async () => {
        if (!active || !accepted || !items.length || purchase.isSubmitting) return;
        const recipient = details.recipientIsBuyer ? details.buyer : details.recipient;
        if (!validContact(details.buyer) || !validContact(recipient)) { setValidation('Заполните ваши данные в разделе «Получатель».'); return; }
        if (!addressReady) { setValidation('Выберите пункт выдачи или заполните адрес курьера.'); return; }
        if (!quote.quote || quote.quoteExpiresAt <= Date.now()) { setValidation('Дождитесь расчёта стоимости доставки.'); quote.retryQuote(); return; }
        setValidation('');
        await purchase.purchase(createCheckoutOrderPayload({
            buyer: details.buyer, recipient, items, quote: quote.quote, deliveryMethod: method, paymentMethod: effectivePaymentMethod,
        }));
    };
    return {
        ...purchase, ...quote, submit, productsTotal, qrAvailable, effectivePaymentMethod,
        totalQuantity: items.reduce((sum, item) => sum + item.quantity, 0),
        deliveryPrice: quote.quote?.delivery_price ?? null,
        grandTotal: Math.round((productsTotal + (quote.quote?.delivery_price ?? 0)) * 100) / 100,
        checkoutError: purchase.checkoutError || validation || quote.quoteError,
    };
}
