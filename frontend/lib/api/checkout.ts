import type {
    CheckoutOrderPayload,
    CheckoutOrderResponse,
    DeliveryCalculationRequest,
    DeliveryCalculationResponse,
    CheckoutRequestContext,
} from '@/lib/checkout/types';

import { requestJson } from './http.ts';

export async function getCheckoutPaymentOptions(signal?: AbortSignal): Promise<Array<'card' | 'qr'>> {
    const data = await requestJson<{ hold_required: boolean; payment_methods: unknown }>('/orders/checkout/options', { cache: 'no-store', signal });
    if (typeof data.hold_required !== 'boolean' || !Array.isArray(data.payment_methods) || !data.payment_methods.includes('card')) {
        throw new Error('Не удалось проверить доступные способы оплаты.');
    }
    return !data.hold_required && data.payment_methods.includes('qr') ? ['card', 'qr'] : ['card'];
}

export const calculateCdekDelivery = (payload: DeliveryCalculationRequest, signal?: AbortSignal) => requestJson<DeliveryCalculationResponse>('/cdek/calculate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal, cache: 'no-store',
});

const purchaseHeaders = ({ idempotencyKey, actor }: CheckoutRequestContext): Record<string, string> => {
    if (!/^[A-Za-z0-9_-]{16,128}$/.test(idempotencyKey) || !actor.token
        || !['customer', 'guest'].includes(actor.kind)
        || (actor.kind === 'guest' && !/^[A-Za-z0-9_-]{43}$/.test(actor.token))) {
        throw new Error('Не удалось подготовить безопасное оформление заказа.');
    }
    return {
        'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey,
        ...(actor.kind === 'customer' ? { Authorization: `Bearer ${actor.token}` } : { 'X-Order-Access-Token': actor.token }),
    };
};

export const createCheckoutOrder = (payload: CheckoutOrderPayload, context: CheckoutRequestContext) => requestJson<CheckoutOrderResponse>('/orders', {
    method: 'POST', headers: purchaseHeaders(context), body: JSON.stringify(payload), cache: 'no-store',
});

export const retryCheckoutPayment = (orderId: number, context: CheckoutRequestContext) => requestJson<CheckoutOrderResponse>(`/orders/${orderId}/payment-attempts`, {
    method: 'POST', headers: purchaseHeaders(context), cache: 'no-store',
});
